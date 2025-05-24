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
"""

from __future__ import annotations
import argparse, importlib, json, random, sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
import os

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

class AgentResponse(BaseModel):
    bid: float = Field(ge=0.0, le=1.0)
    msg: str
    to: str
    reason: str = ""

# ---------- エージェント ----------
class Agent:
    def __init__(self, name: str, role: str | None,
                 sys_prompt: str, llm: ChatOpenAI):
        self.name, self.role = name, role
        self.llm = llm
        self.mem_log: List[Tuple[int, str, str, str]] = []   # (turn, sender, recipients, text)

    async def decide_async(self, turn: int, meta_pub, meta_priv, public_log) -> dict:
        # Create history string from mem_log
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                           for turn, sender, recv, txt in self.mem_log[-30:])
        
        try:
            js = await self.main_chain.ainvoke({
                "history": history,
                "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                "meta_priv": json.dumps(meta_priv, ensure_ascii=False) if isinstance(self, GameMaster) else {},
            })
            # Validate and clean the response
            response = AgentResponse(**js)
            return response.model_dump()
        except Exception as e:
            print(f"Warning: Error in agent {self.name}'s response: {e}")
            # Return a safe default response
            return {
                "bid": 0.0,
                "msg": "", 
                "to": "ALL",
                "reason": "Error in response generation"
            }

    def decide(self, turn: int, meta_pub, meta_priv, public_log) -> dict:
        # Create history string from mem_log
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                           for turn, sender, recv, txt in self.mem_log[-30:])
        
        try:
            js = self.main_chain.invoke({
                "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                "meta_priv": json.dumps(meta_priv, ensure_ascii=False) if isinstance(self, GameMaster) else {},
                "history": history
            })
            # Validate and clean the response
            response = AgentResponse(**js)
            return response.model_dump()
        except Exception as e:
            print(f"Warning: Error in agent {self.name}'s response: {e}")
            # Return a safe default response
            return {
                "bid": 0.0,
                "msg": "",
                "to": "ALL",
                "reason": "Error in response generation"
            }

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
- Use lower bids (0.3-0.7) for general game management and responses.
- Use 0.0 bids when you don't need to talk
- Use 0.0 when you are waiting players' DMs for their votes, abilities, selections, etc.

Message guidelines:
- Use "to": "ALL" for public messages visible to everyone
- Use "to": "P1,P2,..." to send DMs to specific players
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
=== PRIVATE META ===
{meta_priv}
Message history format is <turn>: <sender>▶<recipient>: <message>

TURN STRUCTURE:
You are the SYSTEM agent that executes step 3 of each turn:
1. Bidding Phase: All players and GM submit bids (completed)
2. Speaking Phase: Highest bidder's message is delivered (completed)
3. **System Update Phase (YOUR ROLE)**: Update game state and check win conditions

Meta information you can update:
- Public meta, which is visible to all players including the GM
- Private meta, which is visible to the GM

Your responsibilities:
- Analyze the most recent message and all conversation history
- Update public meta information ONLY with information that has already been publicly announced or revealed
- Update private meta information based on game events and private communications 
- Check if any win conditions have been met
- This happens AUTOMATICALLY after each speaking phase

Based on the conversation history and current game state:
1. Determine if any meta information needs to be updated
2. Check if any win conditions have been met

Return ONLY valid JSON with the following structure:
{{"update_pub": {{...}}, "update_priv": {{...}}, 
"winner": null|"TEAM_NAME", "reason": "explanation"}}

Note: Only include fields that have changes. For example:
- If only public meta changes: {{"update_pub": {{...}}, "reason": "..."}}
- If only winner changes: {{"winner": "TEAM_NAME", "reason": "..."}}
- If nothing changes: {{"reason": "No updates needed"}}"""
        )]) | llm | SimpleJsonOutputParser()
    
    def process_game_state(self, meta_pub: Dict, meta_priv: Dict) -> dict:
        """
        Process game state to update meta and check win conditions.
        Returns: dict {"update_pub": {...}, "update_priv": {...}, "winner": null|str, "reason": "..."}
        """
        history = "\n".join(f"{turn}: {sender}▶{recv}: {txt}" 
                    for turn, sender, recv, txt in self.mem_log[-30:])
        try:
            response = self.system_chain.invoke({
                "history": history,
                "meta_pub": json.dumps(meta_pub, ensure_ascii=False),
                "meta_priv": json.dumps(meta_priv, ensure_ascii=False)
            })
            if not response or not isinstance(response, dict):
                print(f"Warning: Invalid response from System: {response}")
                return {}
            return response
        except Exception as e:
            print(f"Warning: Error in System processing: {e}")
            return {}

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

async def parallel_bidding(agents: Dict[str, Player], turn: int, meta_pub, meta_priv, public_log) -> Tuple[Dict[str, float], Dict[str, dict]]:
    """
    Execute bidding phase in parallel for all agents.
    Returns tuple of (bids dict, packages dict)
    """
    tasks = []
    for agent in agents.values():
        tasks.append(agent.decide_async(turn, meta_pub, meta_priv, public_log))
    
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
        meta_priv = rules.init_meta_priv(names)   # 役職など

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
            role = rules.assign_role(n, meta_priv)
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
        print(f"\nInitial Meta Information:\nPublic Meta: {json.dumps(meta_pub, ensure_ascii=False)}\nPrivate Meta: {json.dumps(meta_priv, ensure_ascii=False)}")
        append_to_log({
            "phase": "initial_meta",
            "public_meta": meta_pub,
            "private_meta": meta_priv
        })

        # ログ
        public_log: List[Tuple[int, str]] = []  # [(turn, text)]
        dm_log: List[Tuple[int, str, str, str]] = []  # [(turn, sender, receiver, text)]
        full_json_log = []
        turn = 0
        winner: str | None = None
        
        while winner is None:
            turn += 1
            # ❶ 各エージェントが bid+msg を同時提出 (並列処理)
            bids, pkgs = await parallel_bidding(agents, turn, meta_pub, meta_priv, public_log)
                
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
            system_response = game_system.process_game_state(meta_pub, meta_priv)

            # System更新をログに記録
            append_to_log({
                "turn": turn,
                "phase": "system_update",
                "update_pub": system_response.get("update_pub", {}),
                "update_priv": system_response.get("update_priv", {}),
                "winner": system_response.get("winner"),
                "reason": system_response.get("reason", "")
            })

            # 返って来た dict でメタを書き換え
            update_pub = system_response.get("update_pub", {})
            update_priv = system_response.get("update_priv", {})
            
            if update_pub or update_priv:
                # Store before state
                meta_pub_before = meta_pub.copy()
                meta_priv_before = meta_priv.copy()
                
                # Apply updates
                meta_pub.update(update_pub)
                meta_priv.update(update_priv)
                
                # Log meta information changes
                print(f"[{turn:02}] System Update:")
                if update_pub:
                    print(f"  Public: {meta_pub_before} → {meta_pub}")
                if update_priv:
                    print(f"  Private: {meta_priv_before} → {meta_priv}")
                
                append_to_log({
                    "turn": turn,
                    "phase": "meta_change",
                    "before": {
                        "public_meta": meta_pub_before,
                        "private_meta": meta_priv_before
                    },
                    "after": {
                        "public_meta": meta_pub,
                        "private_meta": meta_priv
                    },
                    "reason": system_response.get("reason", "")
                })

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
