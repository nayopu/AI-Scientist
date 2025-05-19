#!/usr/bin/env python
"""flex_social_deduction.py  ─ フル汎用 SD ゲームエンジン（GM 指示＋山札管理）

Highlights
----------
* **meta 辞書** は *完全フリー*。LLM‑GM もプラグインも自由に
  `state["meta"]["…"]` にカウンタ／フラグ／デッキを置ける。
* **山札／タイル API** は Python 側で実装し、
  データは `meta[deck_name]` に保存。
* **gm_directive phase** – LLM‑GM が状況を見て
  1) 公開メッセージ 2) meta 更新 3) 次に実行すべき *phase タグ*
  を JSON で返す。コードはそれを即実行するだけ。
* **Global turn timer** under `state['meta']['timer']` – GM can set/clear it via
  `meta_update` in *any* `gm_directive` message:
  ```jsonc
  { "timer": 5 }  // five phase-steps left
  ```
"""
from __future__ import annotations

import argparse, importlib.util, json, random, re, sys
from pathlib import Path
from typing import Any, Callable, Dict, List, TypedDict, Optional, Type

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import AIMessage, BaseMessage, SystemMessage
from pydantic import BaseModel, Field

# ───────────────────── data models ─────────────────────
class PublicState(TypedDict):
    messages: List[BaseMessage]
    turn: int
    alive: List[str]
    meta: Dict[str, Any]  # free area (decks / counters / flags)

class PrivateState(TypedDict):
    role: str
    team: str
    abilities: List[str]

# ───────────────────── structured output models ─────────────────────
class BaseMetaUpdate(BaseModel):
    """共通のメタ情報を管理するベースモデル"""
    timer: Optional[int] = Field(None, description="Global turn timer value")
    turn_limit: Optional[int] = Field(None, description="Maximum number of turns")
    timer_init: Optional[int] = Field(None, description="Initial timer value")

class BaseEngineCommand(BaseModel):
    """基本的なエンジンコマンドモデル"""
    op: str = Field(..., description="Operation to perform (e.g. 'draw', 'shuffle')")
    deck: str = Field(..., description="Name of the deck to operate on")
    n: Optional[int] = Field(None, description="Optional number of cards to draw")

class SimplifiedGMDirective(BaseModel):
    """シンプル化したゲームマスターの指示モデル"""
    next_phase: str = Field(..., description="Next phase to execute (e.g. 'discussion', 'vote', 'ability')")
    public_msg: str = Field(..., description="Message to announce to players")
    meta_update: Optional[dict] = Field(default_factory=dict, description="Optional meta state updates")
    engine_cmd: Optional[dict] = Field(None, description="Optional engine command")

class PlayerBid(BaseModel):
    bid: float = Field(..., description="Bid value between 0 and 1")

class VoteResponse(BaseModel):
    target: str = Field(..., description="Name of player to vote for")

# ───────────────────── プラグインローダー ─────────────────────
game_models: Dict[str, Type[BaseModel]] = {
    "meta": BaseMetaUpdate,
    "engine_cmd": BaseEngineCommand
}

def load_game_models_from_plugins():
    """プラグインからゲーム特有のモデルをロードする"""
    for plugin_module in sys.modules.values():
        if hasattr(plugin_module, 'MODEL_REGISTRY'):
            registry = getattr(plugin_module, 'MODEL_REGISTRY')
            if isinstance(registry, dict):
                for key, model in registry.items():
                    if issubclass(model, BaseModel):
                        game_models[key] = model
                        print(f"Loaded model '{key}' from {plugin_module.__name__}")

# ──────────────────────────────────────────────── レジストリ
PhaseFn   = Callable[[PublicState, Dict[str, PrivateState], ChatOpenAI, dict], None]
AbilityFn = Callable[[PublicState, Dict[str, PrivateState], List[str], ChatOpenAI, dict], None]

phase_handlers: Dict[str, PhaseFn] = {}
ability_handlers: Dict[str, AbilityFn] = {}

def phase(name: str):
    def _wrap(fn):
        phase_handlers[name] = fn
        return fn
    return _wrap

def ability(name: str):
    def _wrap(fn):
        ability_handlers[name] = fn
        return fn
    return _wrap

# ───────────────────── deck helpers ─────────────────────
def shuffle_deck(state: PublicState, deck_name: str):
    """Shuffle a deck in meta."""
    if deck_name not in state["meta"]:
        print(f"Warning: Deck '{deck_name}' not found in meta state")
        return
    random.shuffle(state["meta"][deck_name])

def draw(state: PublicState, deck_name: str, n: int = 1) -> List[str]:
    """Draw n cards from a deck in meta."""
    if deck_name not in state["meta"]:
        print(f"Warning: Deck '{deck_name}' not found in meta state")
        return []
    drawn, state["meta"][deck_name] = (
        state["meta"][deck_name][:n],
        state["meta"][deck_name][n:],
    )
    return drawn

def discard(state: PublicState, deck_name: str, cards: List[str]):
    """Discard cards to a deck's discard pile in meta."""
    state["meta"].setdefault(f"{deck_name}_discard", []).extend(cards)

# ───────────────────── prompt builders ──────────────────
def build_player_chain(llm: ChatOpenAI, *, role: str, team: str, abilities: List[str], rules: str, lang: str, player_name: str):
    sys_pub  = rules + f"\n(You must speak in {lang}.) You must speak ONLY as yourself, not as other players."
    sys_priv = f"You are {player_name}. Your secret role is {role} (team {team}). Abilities: {', '.join(abilities) or 'none'}."

    bid_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=sys_pub),
        SystemMessage(content=sys_priv),
        ("human", """{header}
Below is the public discussion so far:
{conversation}

Think privately. Decide a bid (0-1) and return JSON {{\"bid\": <float>}}.""")
         ])

    talk_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=sys_pub),
        SystemMessage(content=sys_priv),
        ("human", """{header}
Below is the public discussion so far:
{conversation}

You may speak once (≤128 tokens). Compose your message. """)
    ])
    return {
        "bid": bid_prompt | llm.with_structured_output(PlayerBid, method="function_calling"),
        "talk": talk_prompt | llm
    }

# ─ GM 指示フェーズ ---------------------------------------------------------
GM_SYSTEM = """
You are the Game-Master. You control phase flow, deck operations, and hidden info.
You can use the following commands:
1. Draw cards: {{"op": "draw", "deck": "action_deck", "n": 1}}
2. Shuffle deck: {{"op": "shuffle", "deck": "action_deck"}}
"""

@phase("gm_directive")
def _ph_gm(state: PublicState, priv: Dict[str, PrivateState], llm: ChatOpenAI, _):
    # モデルをロード
    meta_model = game_models.get("meta", BaseMetaUpdate)
    engine_cmd_model = game_models.get("engine_cmd", BaseEngineCommand)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", GM_SYSTEM),
        ("human", """
        Current game state:
        Turn: {turn}
        Alive players: {alive}
        Meta information: {meta}
        Recent conversation: {log_tail}
        """)
    ])
    
    # シンプル化したPydanticモデルを使用
    convo = [m.content for m in state["messages"]][-30:]
    try:
        chain = prompt | llm.with_structured_output(SimplifiedGMDirective, method="function_calling")
        result = chain.invoke({
            "turn": state["turn"],
            "alive": state["alive"],
            "meta": state["meta"],
            "log_tail": convo
        })
        
        # 結果を辞書として取得
        js_dict = {
            "next_phase": result.next_phase,
            "public_msg": result.public_msg,
            "meta_update": result.meta_update or {},
            "engine_cmd": result.engine_cmd
        }
        
    except Exception as e:
        print(f"GM directive error: {e}")
        js_dict = {
            "next_phase": "",
            "public_msg": "GM: (invalid directive)",
            "meta_update": {},
            "engine_cmd": None
        }

    # ENGINE-sideコマンドを先に実行
    if js_dict["engine_cmd"]:
        try:
            cmd = js_dict["engine_cmd"]
            op = cmd["op"]
            deck = cmd["deck"]
            n = cmd.get("n", 1)
            
            if op == "draw":
                cards = draw(state, deck, n)
                # カードを GM に返す（meta などに保存させる）
                state["meta"]["gm_last_draw"] = cards
            elif op == "shuffle":
                shuffle_deck(state, deck)
        except Exception as e:
            print(f"Error executing engine command: {e}")

    # 公開メッセージ
    state["messages"].append(AIMessage(content=js_dict["public_msg"]))

    # meta 更新
    meta_updates = js_dict.get("meta_update", {})
    if meta_updates:
        state["meta"].update(meta_updates)

    # ターン制限チェック
    turn_limit = state["meta"].get("turn_limit")
    if turn_limit is not None and state["turn"] >= turn_limit:
        js_dict["next_phase"] = "timeout_victory"

    print(f"\n=== GM Directive (Turn {state['turn']}) ===")
    print(f"Message: {js_dict['public_msg']}")
    if meta_updates:
        print(f"Meta Update: {json.dumps(meta_updates, indent=2)}")
    if js_dict["next_phase"]:
        print(f"Next Phase: {js_dict['next_phase']}")
    print("=" * 40)

    return js_dict["next_phase"]   # エンジン側ループで次フェーズへジャンプ

# ───────────────────── phase implementations ────────────
@phase("discussion")
def _ph_discussion(state: PublicState, priv: Dict[str, PrivateState], llm: ChatOpenAI, chains):
    header = ""
    if "timer" in state["meta"]:
        t_rem = state["meta"]["timer"]
        t_init = state["meta"].get("timer_init", t_rem)
        state["meta"].setdefault("timer_init", t_init)
        header = f"[Timer {t_rem}/{t_init}]"

    convo = "\n".join(m.content for m in state["messages"])
    bids = {}
    for p in state["alive"]:
        bid = chains[p]["bid"].invoke({"header": header, "conversation": convo})
        bids[p] = bid.bid
    speaker = random.choice([p for p, v in bids.items() if v == max(bids.values())])
    utter   = chains[speaker]["talk"].invoke({"header": header, "conversation": convo}).content
    state["messages"].append(AIMessage(content=f"{speaker}: {utter}"))
    print(f"[{state['turn']:02d}] {speaker}: {utter}")

@phase("vote")
def _ph_vote(state: PublicState, priv: Dict[str, PrivateState], llm: ChatOpenAI, _):
    convo = "\n".join(m.content for m in state["messages"])
    tally: Dict[str, List[str]] = {}
    print(f"\n=== Vote Phase (Turn {state['turn']}) ===")
    
    vote_prompt = ChatPromptTemplate.from_messages([
        ("system", "Vote to eliminate ONE player (by name). No other text."),
        ("human", """
        Alive players: {alive}
        Conversation: {conversation}
        """)
    ]) | llm.with_structured_output(VoteResponse, method="function_calling")
    
    for p in state["alive"]:
        vote = vote_prompt.invoke({
            "alive": state["alive"],
            "conversation": convo
        })
        tally.setdefault(vote.target, []).append(p)
        print(f"{p} votes for: {vote.target}")
    
    # Print vote tally
    print("\nVote Tally:")
    for target, voters in tally.items():
        print(f"{target}: {len(voters)} votes ({', '.join(voters)})")
    
    victim = random.choice([t for t, v in tally.items() if len(v) == max(len(x) for x in tally.values())])
    if victim in state["alive"]:
        state["alive"].remove(victim)
        state["messages"].append(AIMessage(content=f"GM: {victim} is eliminated by vote."))
        print(f"\nResult: {victim} is eliminated by vote")
    print("=" * 40)

@phase("ability")
def _ph_ability(state: PublicState, priv: Dict[str, PrivateState], llm: ChatOpenAI, ph_cfg):
    abil = ph_cfg["ability"]
    users = [p for p in state["alive"] if abil in priv[p]["abilities"]]
    if abil in ability_handlers:
        ability_handlers[abil](state, priv, users, llm, ph_cfg)

# ──────────────────────────────────────────────── 勝利判定 DSL
def check_victory(state: PublicState, priv: Dict[str, PrivateState], spec: dict):
    counts: Dict[str, int] = {}
    for p in state["alive"]:
        counts[priv[p]["team"]] = counts.get(priv[p]["team"], 0) + 1
    counts.update(state["meta"])  # 各種カウンタを DSL で参照可
    for team, rule in spec["victory"].items():
        expr = rule
        for k, v in counts.items():
            expr = re.sub(fr"\b{k}\b", str(v), expr)
        expr = re.sub(r"[^0-9A-Za-z><=+\-*/ ()]", "", expr)
        try:
            if eval(expr):
                return team
        except Exception:
            continue
    return None

# ──────────────────────────────────────────────── プラグイン読込
def load_plugin(path: str):
    mname = "plugin_" + Path(path).stem
    spec = importlib.util.spec_from_file_location(mname, path)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        sys.modules[mname] = module
        spec.loader.exec_module(module)
        print(f"Plugin loaded: {path}")
    else:
        raise ImportError(path)

# ──────────────────────────────────────────────── メイン
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default="spec.json")
    ap.add_argument("--rule", default="rules.md")
    ap.add_argument("--plugin", action="append", default=[])
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--log", default="public_log.json")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    for pl in args.plugin or spec.get("plugins", []):
        load_plugin(pl)
    
    # プラグインからモデルをロード
    load_game_models_from_plugins()

    llm        = ChatOpenAI(model_name=args.model, temperature=0.7)
    rules_text = Path(args.rule).read_text()
    lang       = spec.get("lang", "en")

    # players & chains
    role_objs = []
    for r in spec["roles"]:
        role_objs.extend([r] * (r["count"] if isinstance(r["count"], int) else 0))
    random.shuffle(role_objs)
    players = [f"P{i+1}" for i in range(len(role_objs))]

    chains, priv = {}, {}
    for p, r in zip(players, role_objs):
        chains[p] = build_player_chain(llm, role=r["name"], team=r["team"], abilities=r["abilities"], rules=rules_text, lang=lang, player_name=p)
        priv[p] = {"role": r["name"], "team": r["team"], "abilities": r["abilities"]}

    state: PublicState = {
        "messages": [AIMessage(content="GM: Game begins")],
        "turn": 0,
        "alive": players,
        "meta": {} | spec.get("meta", {})  # 空でも可。JSON Spec 側に "meta": {...} があれば上書きする
    }

    while True:
        # GM が次フェーズを決定
        phase = _ph_gm(state, priv, llm, {})
        if not phase or phase not in phase_handlers:
            break

        # フェーズ実行
        state["turn"] += 1
        phase_handlers[phase](state, priv, llm, chains if phase == "discussion" else {})

        # 勝利判定
        win = check_victory(state, priv, spec)
        if win:
            state["messages"].append(AIMessage(content=f"GM: {win} win!"))
            print("***", win, "win! ***")
            Path(args.log).write_text(json.dumps([m.content for m in state["messages"]], ensure_ascii=False, indent=2))
            return

if __name__ == "__main__":
    main()
