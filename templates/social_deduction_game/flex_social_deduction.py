#!/usr/bin/env python
"""flex_social_deduction.py  ─ フル汎用 SD ゲームエンジン（GM 指示＋山札管理）

Highlights
----------
* **meta 辞書** は *完全フリー*。LLM‑GM もプラグインも自由に
  `state["meta"]["…"]` にカウンタ／フラグ／デッキを置ける。
* **山札／タイル API** (`init_deck()`, `draw_cards()`) は Python 側で実装し、
  データは `meta["decks"][name]` に保存。
* **gm_directive phase** – LLM‑GM が状況を見て
  1) 公開メッセージ 2) meta 更新 3) 次に実行すべき *phase タグ*
  を JSON で返す。コードはそれを即実行するだけ。
* **リアル秒タイマーは未使用**。ターン数を GM が読み取り判断。
"""
from __future__ import annotations

import argparse, importlib.util, json, random, re, sys
from pathlib import Path
from typing import Callable, Dict, List, TypedDict

from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import AIMessage, BaseMessage, SystemMessage

# ───────────────────── data models ─────────────────────
class PublicState(TypedDict):
    messages: List[BaseMessage]
    turn: int
    alive: List[str]
    meta: dict  # free area (decks / counters / flags)

class PrivateState(TypedDict):
    role: str
    team: str
    abilities: List[str]

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

def _decks(state: PublicState):
    return state["meta"].setdefault("decks", {})

def init_deck(state: PublicState, name: str, cards: List[str], *, shuffle: bool = True):
    _decks(state)[name] = random.sample(cards, len(cards)) if shuffle else list(cards)

def draw_cards(state: PublicState, name: str, n: int = 1) -> List[str]:
    deck = _decks(state).get(name, [])
    drawn, remain = deck[:n], deck[n:]
    _decks(state)[name] = remain
    return drawn

# ───────────────────── prompt builders ──────────────────

def build_player_chain(llm: ChatOpenAI, *, role: str, team: str, abilities: List[str], rules: str, lang: str, player_name: str):
    sys_pub  = rules + f"\n(You must speak in {lang}.) You must speak ONLY as yourself, not as other players."
    sys_priv = f"You are {player_name}. Your secret role is {role} (team {team}). Abilities: {', '.join(abilities) or 'none'}."

    bid_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=sys_pub),
        SystemMessage(content=sys_priv),
        ("human",
         "Below is the public discussion so far:\n{conversation}\n"
         "Think privately. Decide a bid (0-1) and return JSON {{\"bid\": <float>}}.")
    ])

    talk_prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=sys_pub),
        SystemMessage(content=sys_priv),
        ("human", """Below is the public discussion so far:
{conversation}

You may speak once (≤128 tokens). Compose your message. """)
    ])
    return {"bid": bid_prompt | llm, "talk": talk_prompt | llm}

# ───────────────────── phase implementations ────────────

def _parse_bid(content: str) -> float:
    """Try JSON first; fallback to first float pattern; clamp 0‑1."""
    try:
        val = json.loads(content).get("bid")
        return max(0.0, min(1.0, float(val)))
    except Exception:
        m = re.search(r"0?\.\d+", content)
        return float(m.group()) if m else random.random()

@phase("discussion")
def _ph_discuss(state, priv, llm, chains):
    convo = "\n".join(m.content for m in state["messages"])
    bids = {p: _parse_bid(chains[p]["bid"].invoke({"conversation": convo}).content) for p in state["alive"]}
    max_bid = max(bids.values())
    speaker = random.choice([p for p, v in bids.items() if v == max_bid])
    utter = chains[speaker]["talk"].invoke({"conversation": convo}).content
    state["messages"].append(AIMessage(content=f"{speaker}: {utter}"))
    print(f"[{state['turn']:02d}] {speaker}: {utter}")

@phase("vote")
def _ph_vote(state, priv, llm, _):
    convo = "\n".join(m.content for m in state["messages"])
    tally: Dict[str, List[str]] = {}
    for p in state["alive"]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Vote to eliminate ONE player (by name)."),
            ("human", """
            Alive players: {alive}
            Conversation: {conversation}
            """)
        ]) | llm
        tgt = prompt.invoke({
            "alive": state["alive"],
            "conversation": convo
        }).content.strip()
        tally.setdefault(tgt, []).append(p)
    victim = random.choice([t for t, v in tally.items() if len(v) == max(len(x) for x in tally.values())])
    if victim in state["alive"]:
        state["alive"].remove(victim)
        state["messages"].append(AIMessage(content=f"GM: {victim} is eliminated by vote."))
        print(f"GM eliminates {victim}\n")

@phase("ability")
def _ph_ability(state, priv, llm, ph_cfg):
    abil = ph_cfg["ability"]
    users = [p for p in state["alive"] if abil in priv[p]["abilities"]]
    if abil in ability_handlers:
        ability_handlers[abil](state, priv, users, llm, ph_cfg)

# ─ GM 指示フェーズ ---------------------------------------------------------
GM_SYS_PROMPT = (
    "You are an impartial Game-Master for a social-deduction game. "
    "Given the JSON state you receive, decide the next public instruction. "
    "Return STRICT JSON exactly like this: {{\"public_msg\": <str>, \"meta_update\": <dict>, \"next_phase\": <str>}} "
    "– no markdown, no extra keys."
)

@phase("gm_directive")
def _ph_gm(state, priv, llm, _):
    convo = [m.content for m in state["messages"]][-30:]
    prompt = ChatPromptTemplate.from_messages([
        ("system", GM_SYS_PROMPT),
        ("human", """
        Current game state:
        Turn: {turn}
        Alive players: {alive}
        Meta information: {meta}
        Recent conversation: {log_tail}
        """)
    ]) | llm
    try:
        result = prompt.invoke({
            "turn": state["turn"],
            "alive": state["alive"],
            "meta": state["meta"],
            "log_tail": convo
        })
        js = json.loads(result.content)
    except Exception as e:
        js = {"public_msg": "GM: (invalid directive)", "meta_update": {}, "next_phase": ""}
    state["messages"].append(AIMessage(content=js.get("public_msg", "")))
    state["meta"].update(js.get("meta_update", {}))
    state["meta"]["_gm_next"] = js.get("next_phase", "")
    print(f"GM says → {js.get('public_msg')}")

# ──────────────────────────────────────────────── 能力ビルトイン
@ability("kill")
def _ab_kill(state, priv, users, llm, _):
    if not users:
        return
    convo = "\n".join(m.content for m in state["messages"])
    votes: Dict[str, List[str]] = {}
    for u in users:
        prompt = ChatPromptTemplate.from_messages([
            ("system", "Select a victim (cannot be yourself)."),
            ("human", """
            Alive players: {alive}
            Conversation: {conversation}
            """)
        ]) | llm
        tgt = prompt.invoke({
            "alive": state["alive"],
            "conversation": convo
        }).content.strip()
        votes.setdefault(tgt, []).append(u)
    victim = random.choice([t for t, vs in votes.items() if len(vs) == max(len(x) for x in votes.values())])
    if victim in state["alive"]:
        state["alive"].remove(victim)
        state["messages"].append(AIMessage(content=f"GM: {victim} was killed."))
        print(f"Night kill → {victim}\n")

@ability("inspect")
def _ab_inspect(state, priv, users, llm, _):
    if not users:
        return
    u = users[0]
    convo = "\n".join(m.content for m in state["messages"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Choose a player to inspect."),
        ("human", """
        Alive players: {alive}
        Conversation: {conversation}
        """)
    ]) | llm
    tgt = prompt.invoke({
        "alive": state["alive"],
        "conversation": convo
    }).content.strip()
    result = priv[tgt]["team"] if tgt in priv else "unknown"
    state["meta"].setdefault("inspections", {}).setdefault(u, []).append({"target": tgt, "team": result})

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

# ──────────────────────────────────────────────── 公開ルール生成

def render_rules(spec: dict):
    out = [f"### {spec.get('name', 'Social Deduction Game')}"]
    out.append(f"Language: {spec.get('lang', 'en')}")
    out.append("\n#### Roles")
    for r in spec["roles"]:
        cnt = r["count"] if isinstance(r["count"], int) else "var"
        abil = ", ".join(r["abilities"]) or "none"
        out.append(f"* **{r['name']}** × {cnt} – team {r['team']} – abil: {abil}")
    out.append("\n#### Phase order")
    for ph in spec["phases"]:
        out.append(f"* {ph.get('name', ph['type'])} [{ph['type']}]")
    out.append("\n#### Victory")
    for t, c in spec["victory"].items():
        out.append(f"* {t}: `{c}`")
    return "\n".join(out)

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
    ap.add_argument("--spec", required=True)
    ap.add_argument("--plugin", action="append", default=[])
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--log", default="public_log.json")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text())
    for pl in args.plugin or spec.get("plugins", []):
        load_plugin(pl)

    llm        = ChatOpenAI(model_name=args.model, temperature=0.7)
    rules_text = render_rules(spec)
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

    state: PublicState = {"messages": [AIMessage(content="GM: Game begins")], "turn": 0, "alive": players, "meta": {}}
    phases = spec["phases"]

    while True:
        for ph in phases:
            # gm_directive がフェーズリストを書き換える場合に備えてループ内部で確認
            state["turn"] += 1
            tag = ph["type"]
            handler = phase_handlers.get(tag)
            if not handler:
                raise ValueError(f"No phase handler '{tag}'")
            handler(state, priv, llm, chains if tag == "discussion" else ph)
            # 動的 next_phase 指示があれば即ジャンプ
            nxt = state["meta"].pop("_gm_next", "")
            if nxt and nxt in phase_handlers:
                phase_handlers[nxt](state, priv, llm, chains if nxt == "discussion" else ph)
            win = check_victory(state, priv, spec)
            if win:
                state["messages"].append(AIMessage(content=f"GM: {win} win!"))
                print("***", win, "win! ***")
                Path(args.log).write_text(json.dumps([m.content for m in state["messages"]], ensure_ascii=False, indent=2))
                return

if __name__ == "__main__":
    main()
