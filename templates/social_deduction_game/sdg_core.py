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

# Suppress Pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

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
        print(f"Warning: JSON cleaning failed: {e}")
        print(f"Original response: {response}")
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
            print(f"Warning: Invalid response type: {type(response)}")
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
                print(f"Warning: Error in agent {self.name}'s response (attempt {attempt + 1}/{self.max_retries}): {e}")
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
                print(f"Warning: Error in agent {self.name}'s response (attempt {attempt + 1}/{self.max_retries}): {e}")
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
        
        # Meta update and win condition check chain
        self.system_chain = ChatPromptTemplate.from_messages([
            SystemMessage(content=sys_prompt),
            ("human",
             """=== RECENT CONVERSATIONS ===
{history}
=== PUBLIC META ===
{meta_pub}
=== PRIVATE META (All participants) ===
{meta_priv}
Message history format is <turn>: <sender>▶<recipient>: <message>

TURN STRUCTURE:
You are the SYSTEM agent that executes step 3 of each turn:
1. Bidding Phase: All players and GM submit bids (completed)
2. Speaking Phase: Highest bidder's message is delivered (completed)
3. **System Update Phase (YOUR ROLE)**: Update game state and check win conditions

Meta information structure:
- Public meta: visible to all players including the GM
- Private meta: separated by participant (GM_SYSTEM, P1, P2, P3, etc.)
  - GM and SYSTEM share the same private meta section (GM_SYSTEM)
  - Each player can only see their own private meta section

Your responsibilities:
- Analyze the most recent message and all conversation history
- Update public meta information ONLY with information that has already been publicly announced or revealed
- Update private meta information for ALL participants based on game events and private communications
- Check if any win conditions have been met
- This happens AUTOMATICALLY after each speaking phase

Based on the conversation history and current game state:
1. Determine if any meta information needs to be updated
2. Check if any win conditions have been met

Return ONLY valid JSON with the following structure:
{{"update_pub": {{...}}, "update_priv": {{"GM_SYSTEM": {{...}}, "P1": {{...}}, "P2": {{...}}, ...}}, 
"winner": null|"TEAM_NAME", "reason": "explanation"}}

Note: Only include fields that have changes. For example:
- If only public meta changes: {{"update_pub": {{...}}, "reason": "..."}}
- If only specific private meta changes: {{"update_priv": {{"P1": {{...}}, "P3": {{...}}}}, "reason": "..."}}
- If only winner changes: {{"winner": "TEAM_NAME", "reason": "..."}}
- If nothing changes: {{"reason": "No updates needed"}}

The update_priv should contain updates for any participant whose private information has changed.
Each player's private meta should contain information relevant only to that player (e.g., team members, special abilities, investigation results).
GM_SYSTEM private meta contains all game management information visible to both GM and SYSTEM.
"""
        )]) | llm | SimpleJsonOutputParser()
    
    def process_game_state(self, meta_pub: Dict, meta_priv_all: Dict) -> dict:
        """
        Process game state to update meta and check win conditions.
        Returns: dict {"update_pub": {...}, "update_priv": {...}, "winner": null|str, "reason": "..."}
        """
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                    for turn, sender, recv, txt in self.mem_log[-30:])
        
        for attempt in range(self.max_retries):
            try:
                response = self.system_chain.invoke({
                    "history": history,
                    "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                    "meta_priv": json.dumps(meta_priv_all, ensure_ascii=False)
                })
                
                # Clean and validate the response
                if isinstance(response, str):
                    response = clean_json_response(response)
                
                if not response or not isinstance(response, dict):
                    print(f"Warning: Invalid response from System (attempt {attempt + 1}/{self.max_retries}): {response}")
                    if attempt == self.max_retries - 1:
                        return {"reason": "Failed to get valid system response"}
                    time.sleep(0.5)
                    continue
                
                # Validate response structure
                valid_keys = {"update_pub", "update_priv", "winner", "reason"}
                if not any(key in response for key in valid_keys):
                    print(f"Warning: System response missing required keys (attempt {attempt + 1}/{self.max_retries})")
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
                print(f"Warning: Error in System processing (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    return {"reason": f"System processing error: {str(e)}"}
                time.sleep(0.5)

# ---------- LLM Factory ----------
def create_llm(api_source: str, model_name: str) -> ChatOpenAI:
    """
    Create an LLM instance based on the specified API source and model name.
    
    Args:
        api_source: Either "openai" or "openrouter"
        model_name: The name of the model to use
        
    Returns:
        A configured ChatOpenAI instance
        
    Raises:
        ValueError: If API source is invalid or required API key is missing
    """
    api_source = api_source.lower()
    
    if api_source == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_key=api_key
        )
    elif api_source == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required for OpenRouter API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/your-repo",  # Required by OpenRouter
                "X-Title": "Social Deduction Game"  # Optional but helpful
            }
        )
    else:
        raise ValueError(f"Unsupported API source: {api_source}. Must be 'openai' or 'openrouter'")

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

# ---------- メインループ ----------
async def main_async():
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
    ap.add_argument("--out", default="game_log.json")
    args = ap.parse_args()

    try:
        rules = importlib.import_module(args.rules)
        names = [f"P{i+1}" for i in range(args.players)]

        # JSONログファイルが存在するか確認し、存在しなければ空の配列で初期化
        log_path = Path(args.out)
        full_json_log = []  # Initialize here first
        if log_path.exists():
            try:
                with open(log_path, 'r', encoding='utf-8') as f:
                    full_json_log = json.load(f)
            except json.JSONDecodeError:
                # ファイルが壊れている場合は新規作成
                full_json_log = []
        
        # JSONログを追記する関数
        def append_to_log(entry):
            full_json_log.append(entry)
            with open(log_path, 'w', encoding='utf-8') as f:
                json.dump(full_json_log, ensure_ascii=False, indent=2, fp=f)

        meta_pub = rules.init_meta_pub(names)     # phase / alive / dead など
        meta_priv_all = rules.init_meta_priv(names)   # 役職など - now returns dict with keys for each participant

        # Create LLM instances
        try:
            player_llm = create_llm(args.api, args.model)
            gm_llm = create_llm(args.api, args.gm_model or args.model)
            system_llm = create_llm(args.api, args.gm_model or args.model)
        except ValueError as e:
            print(f"Error: {e}")
            print("\nPlease set the required API key environment variable:")
            if args.api == "openai":
                print("export OPENAI_API_KEY='your-api-key'")
            else:
                print("export OPENROUTER_API_KEY='your-api-key'")
            sys.exit(1)

        agents: Dict[str, Player] = {}

        # プレイヤー
        for n in names:
            role = rules.assign_role(n, meta_priv_all)
            agents[n] = Player(n, role,
                              rules.player_sys_prompt(n, role, args.lang),
                              player_llm)
        # Log role assignments
        role_assignments = {name: agents[name].role for name in names}
        print(f"\nRole Assignments: {json.dumps(role_assignments, ensure_ascii=False)}")
        append_to_log({
            "phase": "role_assignment",
            "roles": role_assignments
        })
        # GM
        agents["GM"] = GameMaster("GM",
                                 rules.gm_sys_prompt(args.lang), gm_llm)
        
        # Create GameSystem agent
        game_system = GameSystem(rules.system_sys_prompt(), 
                                system_llm)

        # Print and log initial meta information
        print(f"\nInitial Meta Information:\nPublic Meta: {json.dumps(meta_pub, ensure_ascii=False)}\nPrivate Meta: {json.dumps(meta_priv_all, ensure_ascii=False)}")
        append_to_log({
            "phase": "initial_meta",
            "public_meta": meta_pub,
            "private_meta": meta_priv_all
        })

        # ログ
        public_log: List[Tuple[int, str]] = []  # [(turn, text)]
        dm_log: List[Tuple[int, str, str, str]] = []  # [(turn, sender, receiver, text)]
        turn = 0
        winner: str | None = None
        
        while winner is None:
            turn += 1
            # ❶ 各エージェントが bid+msg を同時提出 (並列処理)
            bids, pkgs = await parallel_bidding(agents, turn, meta_pub, meta_priv_all, public_log)
                
            # 全エージェントの出力をログに追加
            for agent_name, pkg in pkgs.items():
                log_entry = {
                    "turn": turn,
                    "phase": "bid",
                    "agent": agent_name,
                    "bid": float(pkg["bid"]),
                    "msg": pkg["msg"].strip(),
                    "to": pkg["to"],
                    "reason": pkg.get("reason", "")
                }
                append_to_log(log_entry)

            # ❷ 最高 bid のメッセージを採用 (GM が最高 bid の場合は GM が発言)
            max_bid = max(bids.values())
            max_bidders = [n for n, b in bids.items() if b == max_bid]
            # If GM is among max bidders, choose GM. Otherwise random choice
            speaker = "GM" if "GM" in max_bidders else random.choice(max_bidders)
            pkg = pkgs[speaker]
            utter = pkg["msg"].strip()
            # Convert to "ALL" if all players are recipients
            recipients = [x.strip() for x in pkg["to"].split(",")]
            if all(name in recipients for name in names):
                recipients = ["ALL"]

            # 選択結果をログに記録
            append_to_log({
                "turn": turn,
                "phase": "selection",
                "selected_speaker": speaker,
                "max_bid": max_bid
            })

            if utter:
                # 公開ログ更新
                if "ALL" in recipients:
                    public_log.append((turn, f"{speaker}: {utter}"))
                    print(f"[{turn:02}] {speaker}▶ALL: {utter}")
                else:
                    # DMの場合
                    for recipient in recipients:
                        dm_log.append((turn, speaker, recipient, utter))
                    recipients_str = ",".join(recipients)
                    print(f"[{turn:02}] {speaker}▶DM({recipients_str}): {utter}")
                
                # 各エージェントの private memory に追加
                if "ALL" in recipients:
                    for agent in agents.values():
                        agent.mem_log.append((turn, speaker, "ALL", utter))
                    # Also add to game system's memory
                    game_system.mem_log.append((turn, speaker, "ALL", utter))
                else:
                    # 発言者のログに記録
                    agents[speaker].mem_log.append((turn, speaker, ",".join(recipients), utter))
                    # 受信者のログに記録
                    for r in recipients:
                        agents[r].mem_log.append((turn, speaker, r, utter))
                    # Game system sees all messages
                    game_system.mem_log.append((turn, speaker, ",".join(recipients), utter))
                
                # メッセージ実行をログに記録
                append_to_log({
                    "turn": turn, 
                    "phase": "message",
                    "speaker": speaker,
                    "to": recipients, 
                    "is_dm": "ALL" not in recipients,
                    "msg": utter
                })

            # ❸ GameSystem によるメタ更新と勝利判定
            system_response = game_system.process_game_state(meta_pub, meta_priv_all)

            # System更新をログに記録
            append_to_log({
                "turn": turn,
                "phase": "system_update",
                "system_response": system_response,
            })

            # 返って来た dict でメタを書き換え
            update_pub = system_response.get("update_pub", {})
            update_priv_all = system_response.get("update_priv", {})
            
            if update_pub or update_priv_all:
                # Store before state
                meta_pub_before = meta_pub.copy()
                meta_priv_all_before = meta_priv_all.copy()
                
                # Apply updates
                meta_pub.update(update_pub)
                # Apply private meta updates for each participant
                for participant, updates in update_priv_all.items():
                    if participant in meta_priv_all:
                        meta_priv_all[participant].update(updates)
                    else:
                        meta_priv_all[participant] = updates
                
                # Log meta information changes
                print(f"[{turn:02}] System Update:")
                if update_pub:
                    print(f"  Public: {meta_pub_before} → {meta_pub}")
                if update_priv_all:
                    print(f"  Private: {meta_priv_all_before} → {meta_priv_all}")

            # ❹ 勝利判定
            winner = system_response.get("winner")

        print(f"*** Game End. Winner = {winner} ***")
        
        # ゲーム終了をログに記録
        append_to_log({"phase": "end", "winner": winner})
        print("log →", args.out)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    sys.exit(main())
