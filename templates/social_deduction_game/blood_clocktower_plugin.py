"""Blood on the Clocktower – minimal but *play‑complete* plugin & spec
====================================================================
This file contains **(1) a full JSON spec** matching the Trouble Brewing
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

import argparse, json, random, textwrap
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

# ─────────────────── Pydantic Models for Blood on the Clocktower ─────────────
class BloodClockTowerMeta(BaseModel):
    """Blood Clocktower specific meta state."""
    poisoned: Dict[str, int] = Field(default_factory=dict, description="Poison status for players {player: remaining_nights}")
    last_executed: Optional[str] = Field(None, description="Last executed player")
    slayer_used: bool = Field(False, description="Whether Slayer has used their ability")
    night_order: List[str] = Field(
        default_factory=lambda: ["demon_kill", "poison", "empath_ping", "undertaker_reveal", "slayer_shot"],
        description="Order of night actions"
    )
    last_killed_night: Optional[str] = Field(None, description="Player killed during the last night")

# ─────────────────── EngineCommandTypes for Blood on the Clocktower ─────────────
class BloodClockTowerEngineCommand(BaseModel):
    """Engine commands for Blood Clocktower."""
    op: str = Field(..., description="Operation to perform")

# Register the models to be imported by the engine
MODEL_REGISTRY = {
    "meta": BloodClockTowerMeta,
    "engine_cmd": BloodClockTowerEngineCommand
}

from flex_social_deduction import ability, phase
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
    },
    "meta": {
        "turn_limit": 20,              # 20ターンで終了
        "poisoned": {},                # {player: remaining_nights}
        "last_executed": None,         # 最後に処刑されたプレイヤー
        "slayer_used": False,          # Slayerの能力使用フラグ
        "night_order": [               # 夜の行動順序
            "demon_kill",
            "poison",
            "empath_ping",
            "undertaker_reveal",
            "slayer_shot"
        ]
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

def render_rules(spec: dict):
    # Extract role counts from spec
    townsfolk = [r for r in spec["roles"] if r["team"] == "Town"]
    outsiders = []  # No outsiders in current spec
    minions = []    # No minions in current spec
    demons = [r for r in spec["roles"] if r["team"] == "Evil"]
    
    # Calculate player counts
    min_players = len(townsfolk) + len(outsiders) + len(minions) + len(demons)
    max_players = min_players + 10  # Assuming max 10 extra players
    
    out = textwrap.dedent(f"""
# Blood on the Clocktower – *{spec.get('name', 'Custom Script')}*
*Edition v1.0  •  Generated {datetime.now().strftime('%d %b %Y')}*

---
## 1 ▪ Theme & Goal
A Demon stalks the town at night, killing one resident every dawn.  
**Good (Townsfolk + Outsiders)** must identify and execute the Demon.  
**Evil (Minions + Demon)** must survive until evil players ≥ good players *or* mislead the town into killing itself.

---

## 2 ▪ Teams & Victory
| Team | Includes | Wins when… |
|------|----------|------------|
| **Good** | Townsfolk ＋ Outsiders | the Demon is dead **and** at least one good player lives |
| **Evil** | Minions ＋ Demon | evil players ≥ good players **or** good executes themselves into defeat (Saint, etc.) |

---

## 3 ▪ Player Count
*{min_players}–{max_players} players.*  
Start with **{len(demons)} Demon(s)**, **{len(minions)} Minion(s)**, and **{len(outsiders)} Outsider(s)**.  
Fill the rest with Townsfolk.

---

## 4 ▪ Components
* Character tokens (roles below)  
* Reminder tokens for status (Poisoned, Drunk, Red Herring, etc.)  
* A **Night Order sheet** (page 2) to remind the GM of wake-up order  
* GM Grimoire (private tableau)  
* Discussion timer – *default 5 turns* (see § 7)

---

## 5 ▪ Setup
1. GM secretly chooses **one script** (here: *{spec.get('name', 'Custom Script')}*) and selects characters as per § 3.  
2. Deal one face-down character token to each player; place the same token upright in the Grimoire.  
3. Place any initial reminder tokens (e.g. Fortune Teller **Red Herring**).  
4. Set `meta.timer = 5` and `_timer_init = 5` so all agents see a 5-turn discussion clock.  
5. Night falls; proceed to **First-Night Order** in § 6.

---

## 6 ▪ Night Order
*(characters marked ★ act first night only)*

{_format_night_order(spec)}

---

## 7 ▪ Day Sequence
> `[Timer x / 5]` is shown at each public message; after the fifth spoken message the timer expires.

1. **Discussion** – free talk; each chat message decrements `meta.timer`.  
2. When `meta.timer == 0`, GM announces *"Discussion closed"* and resets the timer if another discussion phase begins later.  
3. **Nominations & Voting**  
   * Any living player may nominate once per day.  
   * Majority vote executes the nominee immediately. Ties = no execution.  
4. **Execution Resolution** – GM announces the role of the executed player **only if a role ability requires** (e.g. Undertaker next night).  
5. **Check victory**; if none, night falls.

---

## 8 ▪ Role Almanac

{_format_role_almanac(spec)}

---

## 9 ▪ States: Drunk & Poisoned
A *Drunk* or *Poisoned* player's ability is ineffective, but they **still appear normal** to others. GM silently tracks status with reminder tokens.

---

## 10 ▪ GM Guidance
* You may alter, withhold, or invent information to keep the game balanced.  
* Maintain meta information if needed.
* Use `meta.timer` freely (`{{"timer": N, "_timer_init": N}}`) to extend/shorten discussions or special phases.  
* If contradictory rules arise, character ability text supersedes this sheet.

---

## 11 ▪ Quick Reference
* **Night start order** → see § 6.  
* **Discussion** → 5 messages max (resettable).  
* **Nomination** → 1 per player per day.  
* **Execution** → majority vote, ties fail.  
* **Win** → Demon dead = Good wins; evil ≥ good **or** Saint executed = Evil wins.

---

**Enjoy the chaos, deduction, and storytelling!**
""")
    return out

def _format_night_order(spec: dict) -> str:
    """Format the night order section based on spec roles."""
    night_order = []
    first_night = []
    
    # Group roles by their night order
    for role in spec["roles"]:
        if role.get("first_night_only"):
            first_night.append(f"★ {role['name']}")
        else:
            night_order.append(role["name"])
    
    # Format the output
    out = []
    if first_night:
        out.append("1. " + "  ".join(first_night))
    if night_order:
        out.append("2. " + "  ".join(night_order))
    
    return "\n".join(out)

def _format_role_almanac(spec: dict) -> str:
    """Format the role almanac section based on spec roles."""
    # Group roles by team
    teams = {}
    for role in spec["roles"]:
        team = role["team"]
        if team not in teams:
            teams[team] = []
        teams[team].append(role)
    
    # Format each team section
    sections = []
    for team in ["Town", "Evil"]:  # Updated to match SPEC_JSON team names
        if team in teams:
            roles = teams[team]
            section = f"### 8.{len(sections) + 1} {team}s\n"
            section += "| Role | Ability |\n|------|---------|\n"
            for role in roles:
                # Join multiple abilities with commas if present
                abilities = ", ".join(role["abilities"]) if role["abilities"] else "None"
                section += f"| **{role['name']}** | {abilities} |\n"
            sections.append(section)
    
    return "\n".join(sections)

# ---------------------------------------------------------------------------
# 3)  UTIL CLI – write spec file --------------------------------------------
# ---------------------------------------------------------------------------

def main():
    Path("spec.json").write_text(json.dumps(SPEC_JSON, indent=2))
    print("spec.json written.")
    md = render_rules(SPEC_JSON)
    Path("rules.md").write_text(md)
    print("rules.md written.")
    print("Done.")

if __name__ == "__main__":
    main()
