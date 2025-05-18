"""Blood on the Clocktower – minimal but *play‑complete* plugin & spec
====================================================================
This file contains **(1) a full JSON spec** matching the Trouble Brewing
script and **(2) plugin abilities** needed for the game.  Copy it next to
`flex_social_deduction.py` and run:

```bash
# 1. write spec file
python blood_clocktower_plugin.py --write-spec

# 2. start a 9‑player game (6 Townsfolk, 1 Outsider, 1 Minion, 1 Demon)
python flex_social_deduction.py \
       --spec blood_clocktower_full.json \
       --plugin blood_clocktower_plugin.py \
       --model gpt-4o-mini
```

Design notes
------------
* **LLM–GM 主導**で夜順序や酔い判定を裁定する方式。コード側は
  - Demon → `demon_kill`
  - Poisoner → `poison`
  - Empath → `empath_ping`
  - Undertaker → `undertaker_reveal`
  - Slayer → `slayer_shot`
  の 5 つだけ実装。その他の役職や細かい裁量は GM が
  `gm_directive` フェーズで処理できます。
* `state["meta"]` が自由領域。ここに
  - `poisoned` dict {player: remaining_nights}
  - `last_executed` str
  - 各能力使用フラグ
  を置きます。
* **勝利条件**: Town wins if Demon dead, Evil wins if Demon ≥ Town。
  （Minion は Evil 側カウントに含む）
"""
from __future__ import annotations

import argparse, json, random
from pathlib import Path
from typing import Dict, List

from flex_social_deduction import ability, phase, draw_cards, init_deck
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.schema import AIMessage

# ---------------------------------------------------------------------------
# 1)  FULL JSON SPEC  --------------------------------------------------------
# ---------------------------------------------------------------------------
SPEC_JSON: Dict = {
    "name": "Blood on the Clocktower – Trouble Brewing (demo)",
    "lang": "en",
    "roles": [
        # Evil
        {"name": "Imp",       "team": "Evil", "abilities": ["demon_kill"], "count": 1},
        {"name": "Poisoner",  "team": "Evil", "abilities": ["poison"],     "count": 1},
        # Good
        {"name": "Empath",    "team": "Town", "abilities": ["empath_ping"],     "count": 1},
        {"name": "Undertaker","team": "Town", "abilities": ["undertaker_reveal"],"count": 1},
        {"name": "Slayer",    "team": "Town", "abilities": ["slayer_shot"],    "count": 1},
        {"name": "Villager",  "team": "Town", "abilities": [],                 "count": 4}
    ],
    "phases": [
        {"type": "discussion"},
        {"type": "vote"},
        {"type": "ability", "ability": "demon_kill"},
        {"type": "ability", "ability": "poison"},
        {"type": "ability", "ability": "empath_ping"},
        {"type": "ability", "ability": "undertaker_reveal"},
        {"type": "ability", "ability": "slayer_shot"},
        {"type": "gm_directive"}  # storyteller discretionary step
    ],
    "victory": {
        "Town": "Evil == 0",           # Imp dead & Poisoner dead
        "Evil": "Evil >= Town"         # parity or majority
    }
}

# ---------------------------------------------------------------------------
# 2)  ABILITY HANDLERS  ------------------------------------------------------
# ---------------------------------------------------------------------------

def _is_poisoned(state, player: str) -> bool:
    return state["meta"].get("poisoned", {}).get(player, 0) > 0

@ability("demon_kill")
def abil_demon_kill(state, priv, users: List[str], llm: ChatOpenAI, _cfg):
    if not users:
        return
    demon = users[0]
    convo = "\n".join(m.content for m in state["messages"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are the Imp. Choose a victim to kill."),
        ("human", f"Alive: {state['alive']}\nConversation:\n{convo}")
    ]) | llm
    tgt = prompt.invoke({}).content.strip()
    if tgt in state["alive"] and tgt != demon:
        state["alive"].remove(tgt)
        state["messages"].append(AIMessage(content=f"GM: {tgt} was killed by the Demon."))
        state["meta"]["last_killed_night"] = tgt
        print("Imp kills →", tgt)

@ability("poison")
def abil_poison(state, priv, users: List[str], llm: ChatOpenAI, _cfg):
    if not users:
        return
    poisoner = users[0]
    convo = "\n".join(m.content for m in state["messages"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Choose a player to poison (disrupt their ability)."),
        ("human", f"Alive: {state['alive']}\nConversation:\n{convo}")
    ]) | llm
    tgt = prompt.invoke({}).content.strip()
    if tgt in state["alive"] and tgt != poisoner:
        poisoned = state["meta"].setdefault("poisoned", {})
        poisoned[tgt] = 2  # remains for 2 nights
        state["messages"].append(AIMessage(content=f"GM (private): {tgt} is poisoned for 2 nights."))
        print("Poisoner poisons →", tgt)

@ability("empath_ping")
def abil_empath(state, priv, users: List[str], llm: ChatOpenAI, _cfg):
    if not users:
        return
    emp = users[0]
    if _is_poisoned(state, emp):
        result = random.choice([0,1,2])  # random info when poisoned
    else:
        # count evil among two neighbours (circular list)
        idx = state["alive"].index(emp)
        left  = state["alive"][(idx-1) % len(state["alive"])]
        right = state["alive"][(idx+1) % len(state["alive"])]
        result = sum(1 for p in (left,right) if priv[p]["team"] == "Evil")
    state["messages"].append(AIMessage(content=f"(Empath learns privately) Evil neighbours: {result}"))

@ability("undertaker_reveal")
def abil_undertaker(state, priv, users: List[str], llm: ChatOpenAI, _cfg):
    if not users or "last_executed" not in state["meta"]:
        return
    ut = users[0]
    target = state["meta"].get("last_executed")
    role = priv[target]["role"] if target in priv else "unknown"
    if _is_poisoned(state, ut):
        role = random.choice([r["name"] for r in SPEC_JSON["roles"]])
    state["messages"].append(AIMessage(content=f"(Undertaker) {target}'s role was {role}"))

@ability("slayer_shot")
def abil_slayer(state, priv, users: List[str], llm: ChatOpenAI, _cfg):
    if not users or state["meta"].get("slayer_used"):
        return
    slayer = users[0]
    convo = "\n".join(m.content for m in state["messages"])
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You may fire once per game. Name a player to slay or write 'skip'."),
        ("human", f"Alive: {state['alive']}\nConversation:\n{convo}")
    ]) | llm
    tgt = prompt.invoke({}).content.strip()
    if tgt.lower() == "skip":
        return
    state["meta"]["slayer_used"] = True
    if tgt in priv and priv[tgt]["role"] == "Imp":
        state["alive"].remove(tgt)
        state["messages"].append(AIMessage(content=f"GM: Slayer killed the Demon {tgt}!"))
    else:
        state["messages"].append(AIMessage(content=f"GM: Slayer shot {tgt} but nothing happened."))

# Hook into vote phase to record last executed --------------------------------
from flex_social_deduction import phase as _orig_phase_handler

_orig_vote = _orig_phase_handler("vote")  # retrieve existing decorator impl

a = list(_orig_vote.__closure__ or [])
# Not modifying existing; easier: monkey‑patch via new phase that wraps

@phase("vote_record")
def vote_record(state, priv, llm, _):
    # call built‑in vote then store executed player
    from flex_social_deduction import phase_handlers as _phs
    _phs["vote"](state, priv, llm, {})
    # parse last GM message
    if state["messages"]:
        content = state["messages"][-1].content
        if "is eliminated" in content:
            name = content.split()[1]
            state["meta"]["last_executed"] = name

# ---------------------------------------------------------------------------
# 3)  UTIL CLI – write spec file --------------------------------------------
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-spec", action="store_true")
    args = ap.parse_args()
    if args.write_spec:
        Path("blood_clocktower_full.json").write_text(json.dumps(SPEC_JSON, indent=2))
        print("blood_clocktower_full.json written.")

if __name__ == "__main__":
    main()
