#!/usr/bin/env python3
"""
Social-Deduction Engine v3
--------------------------
Changes
* Combine bid and talk into a single call
* Store only conversation history in mem_log
* Remove status/winner from public meta
* Display and save DM contents in logs
* Separate Agent and GameMaster
* Implement LLM reasoning for GM meta updates
* Add support for different API sources (OpenAI/OpenRouter)
* Allow different model names for GM and players
* Separate private meta information for each player, with GM and System sharing private meta
* Modularized logging system for better code organization
"""

from __future__ import annotations
import argparse, importlib, json, random, sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
import os
import re
import time

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage
from langchain.output_parsers.json import SimpleJsonOutputParser
from langchain.callbacks.manager import CallbackManager
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from concurrent.futures import ThreadPoolExecutor
import asyncio
from pydantic import BaseModel, Field
import warnings

# Import the new logging system
from game_logging import (
    GameEventLogger, SetupEvent, BidEvent, MessageEvent, 
    SystemDecisionEvent, MetaUpdateEvent, GameEndEvent, ConsoleLogger
)


def create_llm(api_source: str, model_name: str, temperature: float = 0.1) -> ChatOpenAI:
    """
    Create an LLM instance based on the specified API source and model name.

    Args:
        api_source: Either "openai" or "openrouter"
        model_name: The name of the model to use
        temperature: Temperature for the model (default: 0.1)

    Returns:
        A configured ChatOpenAI instance

    Raises:
        ValueError: If API source is invalid or required API key is missing
    """
    api_source = api_source.lower()
    temperature = 1.0 if model_name == "o3" else temperature
    if api_source == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_key=api_key,
            temperature=temperature
        )
    elif api_source == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required for OpenRouter API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=api_key,
            temperature=temperature,
            default_headers={
                "HTTP-Referer": "https://github.com/your-repo",  # Required by OpenRouter
                "X-Title": "Social Deduction Game"  # Optional but helpful
            }
        )
    else:
        raise ValueError(f"Unsupported API source: {api_source}. Must be 'openai' or 'openrouter'")


def clean_json_response(response: str) -> dict:
    """
    Clean and validate JSON response from LLM.
    Handles common issues like:
    - JSON wrapped in markdown code blocks
    - Trailing commas
    - Invalid control characters
    - Missing quotes around keys
    - Malformed JSON with extra text
    """
    if not isinstance(response, str):
        return {}
        
    # Remove any text before the first { and after the last }
    response = re.sub(r'^[^{]*({.*})[^}]*$', r'\1', response, flags=re.DOTALL)
    
    # Remove markdown code blocks if present
    response = re.sub(r"```json\s*|\s*```", "", response)
    
    # Remove trailing commas
    response = re.sub(r",\s*}", "}", response)
    response = re.sub(r",\s*]", "]", response)
    
    # Remove invalid control characters
    response = re.sub(r"[\x00-\x1F\x7F]", "", response)
    
    # Fix missing quotes around keys
    response = re.sub(r'([{,])\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', response)
    
    # Fix single quotes to double quotes
    response = re.sub(r"'", '"', response)
    
    # Fix unescaped quotes in values
    response = re.sub(r':\s*"([^"]*)"([^"]*)"', r': "\1\2"', response)
    
    # Remove any remaining whitespace between quotes and colons
    response = re.sub(r'"\s*:', '":', response)
    response = re.sub(r':\s*"', ':"', response)
    
    try:
        return json.loads(response)
    except json.JSONDecodeError as e:
        ConsoleLogger.log_warning(f"JSON cleaning failed: {e}")
        ConsoleLogger.log_warning(f"Original response: {response}")
        # Try one more time with more aggressive cleaning
        try:
            # Remove any non-JSON text
            response = re.sub(r'[^{}\[\]",:0-9\s]', '', response)
            return json.loads(response)
        except json.JSONDecodeError:
            return {}

class AgentResponse(BaseModel):
    bid: float = Field(ge=0.0, le=1.0)
    msg: str
    to: str
    reason: str = ""

    @classmethod
    def from_llm_response(cls, response: Any) -> 'AgentResponse':
        """Create AgentResponse from LLM response with validation and cleaning"""
        if isinstance(response, str):
            response = clean_json_response(response)
        
        if not isinstance(response, dict):
            ConsoleLogger.log_warning(f"Invalid response type: {type(response)}")
            return cls(bid=0.0, msg="", to="ALL", reason="Invalid response format")
        
        # Ensure required fields exist with defaults
        response = {
            "bid": float(response.get("bid", 0.0)),
            "msg": str(response.get("msg", "")),
            "to": str(response.get("to", "ALL")),
            "reason": str(response.get("reason", ""))
        }
        
        # Validate bid range
        response["bid"] = max(0.0, min(1.0, response["bid"]))
        
        return cls(**response)

# ---------- エージェント ----------
class Agent:
    def __init__(self, name: str, role: str | None,
                 sys_prompt: str, llm: ChatOpenAI):
        self.name, self.role = name, role
        self.llm = llm
        self.mem_log: List[Tuple[int, str, str, str]] = []   # (turn, sender, recipients, text)
        self.max_retries = 3

    async def decide_async(self, turn: int, meta_pub, meta_priv_all, public_log) -> dict:
        # Extract private meta for this agent (GM and System share the same private meta, players see only their own)
        if isinstance(self, GameMaster) or isinstance(self, GameSystem):
            meta_priv = meta_priv_all.get("GM_SYSTEM", {})
        else:
            meta_priv = meta_priv_all.get(self.name, {})
        
        # Create history string from mem_log
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                           for turn, sender, recv, txt in self.mem_log[-30:])
        
        for attempt in range(self.max_retries):
            try:
                js = await self.main_chain.ainvoke({
                    "history": history,
                    "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                    "meta_priv": json.dumps(meta_priv, ensure_ascii=False),
                })
                
                # Use the new validator
                response = AgentResponse.from_llm_response(js)
                return response.model_dump()
                
            except Exception as e:
                ConsoleLogger.log_warning(f"Error in agent {self.name}'s response (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    # Return a safe default response on final attempt
                    return {
                        "bid": 0.0,
                        "msg": "", 
                        "to": "ALL",
                        "reason": f"Error in response generation after {self.max_retries} attempts"
                    }
                # Wait briefly before retrying
                await asyncio.sleep(0.5)

    def decide(self, turn: int, meta_pub, meta_priv_all, public_log) -> dict:
        # Extract private meta for this agent (GM and System share the same private meta, players see only their own)
        if isinstance(self, GameMaster) or isinstance(self, GameSystem):
            meta_priv = meta_priv_all.get("GM_SYSTEM", {})
        else:
            meta_priv = meta_priv_all.get(self.name, {})
        
        # Create history string from mem_log
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                           for turn, sender, recv, txt in self.mem_log[-30:])
        
        for attempt in range(self.max_retries):
            try:
                js = self.main_chain.invoke({
                    "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                    "meta_priv": json.dumps(meta_priv, ensure_ascii=False),
                    "history": history
                })
                
                # Use the new validator
                response = AgentResponse.from_llm_response(js)
                return response.model_dump()
                
            except Exception as e:
                ConsoleLogger.log_warning(f"Error in agent {self.name}'s response (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    # Return a safe default response on final attempt
                    return {
                        "bid": 0.0,
                        "msg": "",
                        "to": "ALL",
                        "reason": f"Error in response generation after {self.max_retries} attempts"
                    }
                # Wait briefly before retrying
                time.sleep(0.5)

class Player(Agent):
    def __init__(self, name: str, role: str | None,
                 sys_prompt: str, llm: ChatOpenAI):
        super().__init__(name, role, sys_prompt, llm)
        parser = SimpleJsonOutputParser()
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=sys_prompt),
            ("human", """
=== RECENT CONVERSATIONS (<turn>: <sender>▶<recipient>: <message>) ===
{history}
=== PUBLIC META ===
{meta_pub}
=== PRIVATE META ===
{meta_priv}

TURN STRUCTURE:
Each turn follows this exact sequence:
1. **Bidding Phase**: All players and GM submit bids simultaneously
2. **Speaking Phase**: Only the highest bidder's message is used
3. **System Update**: The system automatically updates game state and checks win conditions
This cycle repeats until a winner is determined.

Important mechanics:
- All players and GM bid simultaneously in each turn
- Only the highest bidder's message will be used
- The conversation follows a strict pattern: bid → speak → system update → bid → speak → system update ...
- This applies to both public messages and DMs
- **You must win the bid first to send a DM, otherwise your DM will be ignored.**
- You cannot speak outside of this turn structure

GM Phase Management:
- If you notice the GM has skipped a required phase (e.g., night phase for abilities, voting phase),
  you should bid high (0.8-1.0) and speak to ALL to remind the GM
- This is especially important if you need to use your ability or vote
- Example: "GM, we haven't had the night phase yet for abilities"
- The GM will then correct the phase sequence

Bidding guidelines:
- Bid to speak (0-1) and *optionally* send a message.
- Higher bids indicate stronger desire to speak.
- Consider your role, the current phase, and game state when bidding.
- Use 1.0 bids sparingly - only when you believe you have critical information, a strong strategic reason to speak, or you need to DM the GM to finish your voting or ability.
- Lower bids (0.3-0.7) are appropriate for general discussion or when others should - speak first.
- Use 0.0 bids when you don't want to speak or you finished your voting or ability.

Message guidelines:
- Use "to": "ALL" for public messages visible to everyone
- Use "to": "GM" for private messages only visible to the GM (use this for voting or your ability)
- Use "to": "P1,P2,..." to send DMs to specific players
Remember that DMs are only visible to the specified recipients.

Respond ONLY JSON:
{{"bid": <0.0-1.0 (float)>, "reason": <free text>, "msg": <string>, "to": "ALL"|"GM"|"P1,P2,..."}}
""")])
        self.main_chain = prompt | llm | parser


class GameMaster(Player):
    def __init__(self, name: str, sys_prompt: str, llm: ChatOpenAI):
        super().__init__(name, None, sys_prompt, llm)
        parser = SimpleJsonOutputParser()
        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content=sys_prompt),
            ("human",
             """
=== RECENT CONVERSATIONS (<turn>: <sender>▶<recipient>: <message>) ===
{history}
=== PUBLIC META ===
{meta_pub}
=== PRIVATE META ===
{meta_priv}

TURN STRUCTURE:
Each turn follows this exact sequence:
1. **Bidding Phase**: All players and GM submit bids simultaneously
2. **Speaking Phase**: Only the highest bidder's message is used
3. **System Update**: The system automatically updates game state and checks win conditions
This cycle repeats until a winner is determined.

Important mechanics:
- All players and GM bid simultaneously in each turn
- Only the highest bidder's message will be used
- The conversation follows a strict pattern: bid → speak → system update → bid → speak → system update ...
- This applies to both public messages and DMs
- Even if you want to send a DM, you must win the bid first
- PUBLIC META is automatically updated by the system after each turn
- You do NOT update the meta directly - the system handles this

GM Phase Management:
- If you notice the GM has skipped a required phase (e.g., night phase for abilities, voting phase),
  - you should bid high (0.8-1.0) and speak to ALL to remind the GM
- This is especially important if you need to use your ability or vote
- Example: "GM, we haven't had the night phase yet for abilities"
- The GM will then correct the phase sequence

Bidding guidelines:
- Bid to speak (0-1) and *optionally* send a message.
- Higher bids indicate stronger desire to speak.
- Consider the current phase and game state when bidding.
- Use 1.0 bids only when:
  - Announcing phase changes (e.g., starting vote phase, night phase)
  - Enforcing rules or correcting player behavior
  - DMing specific players or player groups to give secret investigation results
- Use lower bids (0.3-0.7) for general game management and responses.
- Use 0.0 bids when you don't need to talk
- Use 0.0 when you are waiting players' DMs for their votes, abilities, selections, etc.

Message guidelines:
- Use "to": "ALL" for public messages visible to everyone (e.g., announcing phase changes, correcting player behavior, etc.)
- Use "to": "P1,P2,..." to send DMs to specific players (e.g., secret investigation results, ability results, etc.)
Remember that DMs are only visible to the specified recipients.

Respond ONLY JSON:
{{"bid": <0.0-1.0 (float)>, "msg": <string>, "to": "ALL"|"P1,P2,...", "reason": <free text>}}"""),
        ])
        self.main_chain = prompt | llm | parser

class GameSystem(Agent):
    def __init__(self, sys_prompt: str, llm: ChatOpenAI):
        super().__init__("SYSTEM", None, sys_prompt, llm)
        # System agent doesn't participate in bidding/messaging
        
        # Combined system processing chain for speaker selection, DM processing, and meta updates
        self.system_chain = ChatPromptTemplate.from_messages([
            SystemMessage(content=sys_prompt),
            ("human",
             """=== RECENT CONVERSATIONS ===
{history}
=== PUBLIC META ===
{meta_pub}
=== PRIVATE META (All participants) ===
{meta_priv}
=== ALL SUBMITTED BIDS AND MESSAGES ===
{all_submissions}

TURN STRUCTURE:
You are the SYSTEM agent that executes the core decision-making phase of each turn:
1. Bidding Phase: All players and GM submit bids and messages (completed)
2. **System Decision Phase (YOUR ROLE)**: Select which messages to execute and in what order
3. **System Update Phase (YOUR ROLE)**: Update game state and check win conditions

Your responsibilities:
- Analyze all submitted bids and messages from players and GM
- Decide which public message (if any) should be executed first
- Decide which DMs should be executed (can be multiple DMs in one turn for efficiency)
- For DMs, you can allow unlimited exchanges within this turn to facilitate voting/ability phases
- Update public and private meta information based on executed messages
- You MUST check win conditions EVERY turn and update the winner field accordingly
  - If win conditions are met, set winner to appropriate team (e.g. "WEREWOLF" or "VILLAGER")

Message Selection Guidelines:
- Consider both bid values and message content when making decisions
- Higher bids indicate stronger desire to speak, but content relevance is equally important
- For public messages: select only ONE public message per turn (or none if only DMs are relevant)
- For DMs: you can select MULTIPLE DMs to execute simultaneously for game efficiency
- Prioritize messages that advance the game state (voting, abilities, phase transitions)
- GM messages about phase management should generally be prioritized

DM Processing:
- DMs can be processed simultaneously and multiple times per turn
- This is especially useful for voting phases, ability usage, and private communications
- You decide which DMs from the current submissions should be executed

Meta information structure:
- Public meta: visible to all players including the GM
- Private meta: separated by participant (GM_SYSTEM, P1, P2, P3, etc.)
  - GM and SYSTEM share the same private meta section (GM_SYSTEM)
  - Each player can only see their own private meta section

Return ONLY valid JSON with the following structure:
{{
  "selected_messages": [
    {{"speaker": "P1", "to": ["ALL"], "message": "...", "reason": "why this message was selected"}},
    {{"speaker": "GM", "to": ["P2", "P3"], "message": "...", "reason": "why this DM was selected"}},
    ...
  ],
  "update_pub": {{...}},
  "update_priv": {{"GM_SYSTEM": {{...}}, "P1": {{...}}, "P2": {{...}}, ...}},
  "reason": "overall explanation of decisions made"
}}

Notes:
- selected_messages: Array of messages to execute (can be empty, single public, multiple DMs, or mix)
- Only include update fields that have actual changes
- If no messages are selected, return empty selected_messages array
- Each selected message should include the original speaker, recipients, and content
- The "to" field should be an array: ["ALL"] for public, ["P1","P2"] for DMs
"""
        )]) | llm | SimpleJsonOutputParser()
    
    def process_turn_with_all_submissions(self, meta_pub: Dict, meta_priv_all: Dict, all_submissions: Dict) -> dict:
        """
        Process an entire turn: select messages to execute, update meta, and check win conditions.
        
        Args:
            meta_pub: Current public meta information
            meta_priv_all: Current private meta information for all participants
            all_submissions: Dict with agent names as keys and their {bid, msg, to, reason} as values
        
        Returns: 
            dict {
                "selected_messages": [...],
                "update_pub": {...}, 
                "update_priv": {...}, 
                "winner": null|str, 
                "reason": "..."
            }
        """
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                    for turn, sender, recv, txt in self.mem_log[-30:])
        
        # Format all submissions for the prompt
        submissions_text = []
        for agent_name, submission in all_submissions.items():
            bid = submission.get("bid", 0.0)
            msg = submission.get("msg", "").strip()
            to = submission.get("to", "ALL")
            reason = submission.get("reason", "")
            submissions_text.append(f"{agent_name}: bid={bid}, to={to}, msg='{msg}', reason='{reason}'")
        
        submissions_str = "\n".join(submissions_text)
        
        for attempt in range(self.max_retries):
            try:
                response = self.system_chain.invoke({
                    "history": history,
                    "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                    "meta_priv": json.dumps(meta_priv_all, ensure_ascii=False),
                    "all_submissions": submissions_str
                })
                
                # Clean and validate the response
                if isinstance(response, str):
                    response = clean_json_response(response)
                
                if not response or not isinstance(response, dict):
                    ConsoleLogger.log_warning(f"Invalid response from System (attempt {attempt + 1}/{self.max_retries}): {response}")
                    if attempt == self.max_retries - 1:
                        return {"selected_messages": [], "reason": "Failed to get valid system response"}
                    time.sleep(0.5)
                    continue
                
                # Validate response structure
                if "selected_messages" not in response:
                    response["selected_messages"] = []
                
                # Ensure selected_messages is a list
                if not isinstance(response["selected_messages"], list):
                    response["selected_messages"] = []
                
                # Validate each selected message
                valid_messages = []
                for msg in response["selected_messages"]:
                    if isinstance(msg, dict) and "speaker" in msg and "to" in msg and "message" in msg:
                        # Ensure 'to' is a list
                        if isinstance(msg["to"], str):
                            if msg["to"] == "ALL":
                                msg["to"] = ["ALL"]
                            else:
                                msg["to"] = [x.strip() for x in msg["to"].split(",")]
                        elif not isinstance(msg["to"], list):
                            msg["to"] = ["ALL"]
                        valid_messages.append(msg)
                
                response["selected_messages"] = valid_messages
                
                # Ensure other fields are of correct type
                if "update_pub" in response and not isinstance(response["update_pub"], dict):
                    response["update_pub"] = {}
                if "update_priv" in response and not isinstance(response["update_priv"], dict):
                    response["update_priv"] = {}
                if "winner" in response and response["winner"] not in [None, "WEREWOLF", "VILLAGER"]:
                    response["winner"] = None
                if "reason" not in response:
                    response["reason"] = "No reason provided"
                
                return response
                
            except Exception as e:
                ConsoleLogger.log_warning(f"Error in System processing (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    return {"selected_messages": [], "reason": f"System processing error: {str(e)}"}
                time.sleep(0.5)

    def process_game_state(self, meta_pub: Dict, meta_priv_all: Dict) -> dict:
        """
        Legacy method for backward compatibility.
        This is now replaced by process_turn_with_all_submissions but kept for existing code.
        """
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                    for turn, sender, recv, txt in self.mem_log[-30:])
        
        for attempt in range(self.max_retries):
            try:
                response = self.system_chain.invoke({
                    "history": history,
                    "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                    "meta_priv": json.dumps(meta_priv_all, ensure_ascii=False),
                    "all_submissions": "Legacy mode - no submissions provided"
                })
                
                # Clean and validate the response
                if isinstance(response, str):
                    response = clean_json_response(response)
                
                if not response or not isinstance(response, dict):
                    ConsoleLogger.log_warning(f"Invalid response from System (attempt {attempt + 1}/{self.max_retries}): {response}")
                    if attempt == self.max_retries - 1:
                        return {"reason": "Failed to get valid system response"}
                    time.sleep(0.5)
                    continue
                
                # Validate response structure
                valid_keys = {"update_pub", "update_priv", "winner", "reason"}
                if not any(key in response for key in valid_keys):
                    ConsoleLogger.log_warning(f"System response missing required keys (attempt {attempt + 1}/{self.max_retries})")
                    if attempt == self.max_retries - 1:
                        return {"reason": "Invalid system response structure"}
                    time.sleep(0.5)
                    continue
                
                # Ensure all fields are of correct type
                if "update_pub" in response and not isinstance(response["update_pub"], dict):
                    response["update_pub"] = {}
                if "update_priv" in response and not isinstance(response["update_priv"], dict):
                    response["update_priv"] = {}
                if "winner" in response and response["winner"] not in [None, "WEREWOLF", "VILLAGER"]:
                    response["winner"] = None
                if "reason" not in response:
                    response["reason"] = "No reason provided"
                
                return response
                
            except Exception as e:
                ConsoleLogger.log_warning(f"Error in System processing (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    return {"reason": f"System processing error: {str(e)}"}
                time.sleep(0.5)

async def parallel_bidding(agents: Dict[str, Player], turn: int, meta_pub, meta_priv_all, public_log) -> Tuple[Dict[str, float], Dict[str, dict]]:
    """
    Execute bidding phase in parallel for all agents.
    Returns tuple of (bids dict, packages dict)
    """
    tasks = []
    for agent in agents.values():
        tasks.append(agent.decide_async(turn, meta_pub, meta_priv_all, public_log))
    
    results = await asyncio.gather(*tasks)
    
    bids = {}
    pkgs = {}
    for agent, result in zip(agents.values(), results):
        bids[agent.name] = float(result["bid"])
        pkgs[agent.name] = result
    
    return bids, pkgs

async def run_game(rules_module: str, num_players: int = 5, api_source: str = "openai", 
                  model_name: str = "gpt-4o-mini", gm_model_name: str = None, 
                  lang: str = "en", out_dir: str = "game_logs") -> Dict[str, Any]:
    """
    Run a social deduction game programmatically.
    
    Args:
        rules_module: Name of the rules module to import
        num_players: Number of players (default: 5)
        api_source: API source ("openai" or "openrouter", default: "openai")
        model_name: Model name for players (default: "gpt-4o-mini")  
        gm_model_name: Model name for GM (if different from players)
        lang: Language code (default: "en")
        out_dir: Directory to store game logs (default: "game_logs")
    
    Returns:
        Dict containing game results with keys:
        - success: bool indicating if game completed successfully
        - winner: str or None indicating the winner
        - turn_count: int number of turns played
        - error: str error message if game failed
    """
    try:
        rules = importlib.import_module(rules_module)
        names = [f"P{i+1}" for i in range(num_players)]

        # Initialize logger
        logger = GameEventLogger(out_dir)

        meta_pub = rules.init_meta_pub(names)     # phase / alive / dead など
        meta_priv_all = rules.init_meta_priv(names)   # 役職など - now returns dict with keys for each participant

        # Create LLM instances
        try:
            player_llm = create_llm(api_source, model_name)
            gm_llm = create_llm(api_source, gm_model_name or model_name)
            system_llm = create_llm(api_source, gm_model_name or model_name)
        except ValueError as e:
            error_msg = f"Error: {e}\nPlease set the required API key environment variable"
            return {"success": False, "error": error_msg, "winner": None, "turn_count": 0}

        agents: Dict[str, Player] = {}

        # プレイヤー
        for n in names:
            role = rules.assign_role(n, meta_priv_all)
            agents[n] = Player(n, role,
                              rules.player_sys_prompt(n, role, lang),
                              player_llm)
        
        # Log role assignments
        role_assignments = {name: agents[name].role for name in names}
        
        # Log game setup using new event system
        setup_event = SetupEvent(
            roles=role_assignments,
            initial_meta={
                "public": meta_pub,
                "private": meta_priv_all
            }
        )
        logger.log_event(setup_event)

        # GM
        agents["GM"] = GameMaster("GM",
                                 rules.gm_sys_prompt(lang), gm_llm)
        
        # Create GameSystem agent
        game_system = GameSystem(rules.system_sys_prompt(), 
                                system_llm)

        # Print and log initial meta information
        logger.log_initial_meta(meta_pub, meta_priv_all)

        # ログ
        public_log: List[Tuple[int, str]] = []  # [(turn, text)]
        dm_log: List[Tuple[int, str, str, str]] = []  # [(turn, sender, receiver, text)]
        turn = 0
        winner: str | None = None
        max_turns = 100  # Safety limit to prevent infinite games
        
        try:
            while winner is None and turn < max_turns:
                turn += 1
                # ❶ 各エージェントが bid+msg を同時提出 (並列処理)
                bids, pkgs = await parallel_bidding(agents, turn, meta_pub, meta_priv_all, public_log)
                    
                # Log all agent bids using new event system
                for agent_name, pkg in pkgs.items():
                    bid_event = BidEvent(
                        turn=turn,
                        agent=agent_name,
                        bid=float(pkg["bid"]),
                        msg=pkg["msg"].strip(),
                        to=pkg["to"],
                        reason=pkg.get("reason", "")
                    )
                    logger.log_event(bid_event)

                # ❂ System agent が全提出を分析して発言者・DM・meta更新・勝利判定を決定
                system_response = game_system.process_turn_with_all_submissions(meta_pub, meta_priv_all, pkgs)

                # Log system decision using new event system
                system_decision_event = SystemDecisionEvent(turn, system_response)
                logger.log_event(system_decision_event)

                # ❸ 選択されたメッセージを実行 (複数可能、特にDM)
                selected_messages = system_response.get("selected_messages", [])
                
                for msg_data in selected_messages:
                    speaker = msg_data["speaker"]
                    recipients = msg_data["to"]  # Already a list from validation
                    message = msg_data["message"].strip()
                    selection_reason = msg_data.get("reason", "")
                    
                    if message:
                        is_dm = "ALL" not in recipients
                        
                        # Update game logs and agent memories
                        if not is_dm:
                            # Public message
                            public_log.append((turn, f"{speaker}: {message}"))
                            ConsoleLogger.log_info(f"Turn {turn} - {speaker}: {message}")
                            
                            # Add to all agent memories
                            for agent in agents.values():
                                agent.mem_log.append((turn, speaker, "ALL", message))
                            game_system.mem_log.append((turn, speaker, "ALL", message))
                            
                        else:
                            # DM - multiple recipients possible
                            for recipient in recipients:
                                dm_log.append((turn, speaker, recipient, message))
                                ConsoleLogger.log_info(f"Turn {turn} - {speaker}▶{recipient}: {message}")
                            recipients_str = ",".join(recipients)
                            
                            # Add to sender's memory
                            agents[speaker].mem_log.append((turn, speaker, recipients_str, message))
                            # Add to each recipient's memory
                            for r in recipients:
                                agents[r].mem_log.append((turn, speaker, r, message))
                            # Game system sees all messages
                            game_system.mem_log.append((turn, speaker, recipients_str, message))
                        
                        # Log message execution using new event system
                        message_event = MessageEvent(
                            turn=turn,
                            speaker=speaker,
                            recipients=recipients,
                            message=message,
                            is_dm=is_dm,
                            selection_reason=selection_reason
                        )
                        logger.log_event(message_event)

                # ❹ Meta更新と勝利判定（System agentが既に実行済み）
                update_pub = system_response.get("update_pub", {})
                update_priv_all = system_response.get("update_priv", {})
                
                if update_pub or update_priv_all:
                    # Apply updates
                    if update_pub:
                        meta_pub.update(update_pub)
                    # Apply private meta updates for each participant
                    if update_priv_all:
                        for participant, updates in update_priv_all.items():
                            if updates is not None and isinstance(updates, dict):
                                if participant in meta_priv_all:
                                    meta_priv_all[participant].update(updates)
                                else:
                                    meta_priv_all[participant] = updates
                    
                    # Log meta update using new event system
                    meta_update_event = MetaUpdateEvent(
                        turn=turn,
                        public_changes=update_pub,
                        private_changes=update_priv_all
                    )
                    logger.log_event(meta_update_event)

                # ❺ 勝利判定
                winner = system_response.get("winner")

            # Log game end using new event system
            game_completed = winner is not None and turn < max_turns
            game_end_event = GameEndEvent(
                winner=winner,
                total_turns=turn,
                completed=game_completed
            )
            logger.log_event(game_end_event)
            
            return {
                "success": True,
                "winner": winner,
                "turn_count": turn,
                "game_completed": game_completed,
                "error": None
            }
            
        finally:
            # Save all logs even if the game was interrupted
            logger.save_logs()
            ConsoleLogger.log_info(f"Logs saved to directory: {out_dir}")

    except Exception as e:
        error_msg = f"Game execution error: {str(e)}"
        ConsoleLogger.log_error(error_msg)
        # Try to save logs if logger exists
        if 'logger' in locals():
            logger.save_logs()
            ConsoleLogger.log_info(f"Logs saved to directory: {out_dir} (after error)")
        return {
            "success": False,
            "winner": None,
            "turn_count": locals().get('turn', 0),
            "game_completed": False,
            "error": error_msg
        }

# ---------- メインループ ----------
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--players", type=int, default=5)
    ap.add_argument("--api", choices=["openai", "openrouter"], default="openai",
                    help="API source to use (OpenAI or OpenRouter)")
    ap.add_argument("--model", default="gpt-4o-mini",
                    help="Model name for players")
    ap.add_argument("--gm-model", default=None,
                    help="Model name for GM (if different from players)")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--out", default="game_logs",
                    help="Directory to store game logs. Will create two files: "
                         "game_log.json (detailed log) and game_summary.txt (evaluation summary)")
    args = ap.parse_args()

    # Call the run_game function with parsed arguments
    result = await run_game(
        rules_module=args.rules,
        num_players=args.players,
        api_source=args.api,
        model_name=args.model,
        gm_model_name=args.gm_model,
        lang=args.lang,
        out_dir=args.out
    )
    
    if not result["success"]:
        ConsoleLogger.log_error(f"Game failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

