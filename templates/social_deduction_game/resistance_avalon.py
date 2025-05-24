"""
Resistance — Avalon rules for sdg_core v3
Based on the official rules booklet and widely-accepted role mixes. [oai_citation:0‡avalon.fun](https://avalon.fun/pdfs/rules.pdf?utm_source=chatgpt.com) [oai_citation:1‡ウィキペディア](https://en.wikipedia.org/wiki/The_Resistance_%28game%29?utm_source=chatgpt.com)
"""
import json, random
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers.json import SimpleJsonOutputParser

###############################################################################
#  RULEBOOK (public, role-private, GM, and SYSTEM sections)
###############################################################################
RULEBOOK: Dict[str, Dict] = {
    # ------------------------------------------------------------------ PUBLIC
    "common": r"""
================ Resistance — Avalon: Public Rulebook ================
VICTORY
• **Loyal Servants of Arthur (GOOD)** win after 3 successful missions.  
• **Minions of Mordred (EVIL)** win after 3 failed missions, or if 5
  consecutive team proposals are rejected **or** if the Assassin
  successfully kills Merlin after GOOD reaches 3 successes.

GAME FLOW (per round)
1. **Team Proposal** – Current Leader nominates the mission team.
2. **Team Vote** – Everyone simultaneously votes to *Approve* or *Reject*.
   - If rejected, pass leadership clockwise; after 5 consecutive rejects,
     EVIL wins instantly.
   - If approved, continue.
3. **Mission** – Only nominated players secretly submit **Success** / **Fail**
   cards (GOOD **must** play Success; EVIL may choose).  
   - Reveal cards:  
     • If *any* Fail appears (two Fails on Mission 4 with ≥7 players) ⇒
       mission fails.  
     • Otherwise the mission succeeds.
4. **Record result** and pass leadership; start next round.
5. **(If GOOD achieves 3 successes)** Assassin privately names Merlin.  
   - Correct ⇒ EVIL steals victory; wrong ⇒ GOOD wins.

ROLES
GOOD SIDE
• **Loyal Servant of Arthur** – no power.  
• **Merlin** – Knows all EVIL (except Mordred). Must stay hidden.  
• **Percival** – Knows who Merlin *might* be (Merlin ∧ Morgana).  

EVIL SIDE
• **Minion of Mordred** – no power, sees other EVIL.  
• **Assassin** – Standard EVIL; gains final Merlin-kill shot.  
• **Morgana** – Appears as Merlin to Percival.  
• **Mordred** – Hidden from Merlin.  
• **Oberon** – EVIL unknown to spies and vice-versa (acts alone).

TEAM-SIZE TABLE
Players : 5  6  7  8  9 10  
Mission1  2  2  2  3  3  3  
Mission2  3  3  3  4  4  4  
Mission3  2  4  3  4  4  4  
Mission4  3  3  4  5  5  5  
Mission5  3  4  4  5  5  5  
Mission 4 needs **2 Fails** to fail when players ≥ 7.
======================================================================
""",

    # ------------------------------------------------------------ ROLE PRIVATE
    "role": {
        "LOYAL": "You are a **Loyal Servant of Arthur**. No special power.",
        "MERLIN": "You are **Merlin**. You secretly know every EVIL player "
                  "EXCEPT Mordred. Do NOT reveal yourself.",
        "PERCIVAL": "You are **Percival**. You are shown two players who might "
                    "be Merlin (Merlin and possibly Morgana). Protect Merlin.",
        "MINION": "You are a **Minion of Mordred**. Coordinate with fellow "
                  "EVIL to fail missions. You know the other EVIL.",
        "ASSASSIN": "You are the **Assassin**. If GOOD wins 3 missions, you "
                    "get ONE guess at Merlin's identity. Guess correctly to "
                    "steal victory.",
        "MORGANA": "You are **Morgana**. You appear as Merlin to Percival.",
        "MORDRED": "You are **Mordred**. Merlin does NOT see you.",
        "OBERON": "You are **Oberon**. You are EVIL but do NOT know the other "
                  "EVIL, and they do not know you."
    },

    # --------------------------------------------------------------- GM GUIDE
    "gm_guideline": r"""
======================= GM Procedural Guideline ======================
Prefix all statements with **"GM:"**.

TURN PROMPTS
• Proposal:      "GM: Leader {L}, propose a team of {n} players."
• Voting:        "GM: Everyone DM me 'Approve' or 'Reject'."
• Vote result:   "GM: The proposal is (approved/rejected) {tally}."
• Mission cards: "GM: Mission team, DM me 'Success' or 'Fail'."
• Mission result:"GM: Mission {#} (succeeded/failed). Score {S:F}."
• Assassin shot: "GM: Assassin, DM me the name of Merlin."

RULE ENFORCEMENT
• Reject spam: after five consecutive rejects, announce EVIL win.
• Mission 4 with ≥7 players requires **two Fails** to fail.
======================================================================
""",

    # ----------------------------------------------------------- SYSTEM GUIDE
    "system_guideline": r"""
You are the SYSTEM agent tracking Avalon.

PUBLIC META KEYS
phase              : "proposal" | "vote" | "mission" |
                     "assassination" | "end"
leader             : current leader name
mission_number     : 1-5
proposal_attempt   : 1-5 (resets each mission)
score              : {"success": int, "fail": int}
mission_results    : list[str]  # "SUCCESS"/"FAIL"/None ×5
pending_team       : list[str]  # team being voted / on mission

PRIVATE META EXTRA
roles              : {player: role}
rejected_in_row    : int
assassination_used : bool

UPDATE RULES (examples)
• On GM prompt "propose": phase→"proposal"
• On GM prompt "Everyone DM me 'Approve'": phase→"vote"
• After vote result approved: phase→"mission", proposal_attempt→1
• After vote result rejected: proposal_attempt++, leader→next player
• After five rejects: winner="EVIL"
• After mission result: update score & mission_results; if score reach 3
  and winner not decided, phase→"assassination" if Assassin alive & not used
• After Assassin names Merlin: set winner accordingly, phase→"end"

WIN CHECKS
• GOOD wins if score.success == 3 **and** Assassin either guessed wrong or
  already dead/absent.  
• EVIL wins if score.fail == 3 **or** five rejects **or** Assassin guessed
  correctly.
Always output valid JSON:
{
 "update_pub": {...}, "update_priv": {...},
 "winner": null|"GOOD"|"EVIL", "reason": "..."
}
"""
}

###############################################################################
#  INITIALISATION HELPERS
###############################################################################
def _role_distribution(num_players: int) -> List[str]:
    """
    Return a list of role names sized to num_players.
    Very simple heuristic mirroring common setups. [oai_citation:2‡Reddit](https://www.reddit.com/r/boardgames/comments/792bcb/ideal_role_distribution_for_the_resistance_avalon/?utm_source=chatgpt.com)
    """
    # Baseline counts
    num_evil = 2 if num_players < 7 else 3 if num_players < 10 else 4
    roles = []
    # EVIL core
    roles += ["ASSASSIN"]
    if num_evil >= 3:
        roles += ["MINION"]
    # GOOD core
    roles += ["MERLIN"]
    if num_players >= 7:
        roles += ["PERCIVAL"]
    # Fill remaining GOOD with LOYAL
    while len(roles) < num_players:
        # add EVIL extras first to hit count
        if roles.count("MINION") + 1 < num_evil:
            roles += ["MINION"]
        else:
            roles += ["LOYAL"]
    random.shuffle(roles)
    return roles


###############################################################################
#  PUBLIC / PRIVATE META INIT
###############################################################################
def init_meta_pub(players: List[str]) -> Dict:
    return dict(
        phase="proposal",
        leader=players[0],
        mission_number=1,
        proposal_attempt=1,
        score={"success": 0, "fail": 0},
        mission_results=[None, None, None, None, None],
        pending_team=[]
    )

def init_meta_priv(players: List[str]) -> Dict:
    roles = _role_distribution(len(players))
    meta = dict(
        roles={p: r for p, r in zip(players, roles)},
        rejected_in_row=0,
        assassination_used=False
    )
    return meta

def assign_role(name: str, meta_priv) -> str:
    return meta_priv["roles"][name]

###############################################################################
#  PROMPT HELPERS
###############################################################################
def player_sys_prompt(name: str, role: str, lang: str="en") -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['role'][role]}\n"
            f"You are {name}. Speak in {lang}.")

def gm_sys_prompt(lang: str="en") -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n"
            f"You are the GM. Speak in {lang}.")

def system_sys_prompt() -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the SYSTEM agent managing the game state.")