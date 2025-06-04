"""
test_game rules for sdg_core v3
A deliberately small yet fully-featured social-deduction ruleset
used for validation / unit-testing of the sdg_core framework.
"""
import json, random
from typing import List, Dict

###############################################################################
#  RULEBOOK – public, private role blurbs, GM guide, and hidden SYSTEM guide
###############################################################################
RULEBOOK: Dict[str, Dict | str] = {
    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC RULEBOOK  (sent to EVERY participant including GM & System)
    # ─────────────────────────────────────────────────────────────────────────
    "common": """
================== Test Social Deduction Game – Public Rulebook ==================
THEME
  You are software engineers working on a critical release.
  • The TESTERS team hunts software BUGS hiding in the code base.
  • BUGS sabotage the project each night.

VICTORY
  • TESTERS win when every BUG is eliminated (no BUGS alive).
  • BUGS win once BUGS ≥ TESTERS among the living players.

ROLES (all players receive exactly ONE)
  • TESTER   – Vanilla good role. Discuss and vote.
  • DEBUGGER – Good role. Each night may inspect one player; the GM reveals
               that player's exact role.
  • QA_LEAD  – Good role. Each night may shield one player from the BUG kill
               (cannot shield the same player two consecutive nights).
  • BUG      – Evil role. Knows fellow BUGS. During Night the BUGS jointly
               pick one victim to remove from play.

PHASE SEQUENCE (loops until a side wins)
  1. Discussion  – open conversation in public chat.
  2. Vote        – every living player DM's the GM exactly ONE name. Highest
                   vote is eliminated (ties broken randomly).
  3. Night       – BUGS select one victim; DEBUGGER & QA_LEAD use abilities.

ELIMINATION & DEATH
  • A voted-out or night-killed player is dead immediately and may no longer
    talk nor vote.
  • The GM publicly announces the name and role of each eliminated player.

TURN RHYTHM  (example chat prompts)
  Discussion → GM: "Vote phase – DM me a name" → Vote resolution →
  GM: "Night phase – BUGS choose a victim; special roles DM me your targets" →
  Night resolution → next Discussion …
==================================================================================
""",

    # ─────────────────────────────────────────────────────────────────────────
    # ROLE-SPECIFIC BLURBS  (DM'd individually in addition to public rules)
    # ─────────────────────────────────────────────────────────────────────────
    "role": {
        "TESTER":   "You are a **TESTER** (good). You have NO special power. "
                    "Find and eliminate the BUGS.",
        "DEBUGGER": "You are the **DEBUGGER** (good). Each Night you may DM the "
                    "GM ONE player's name to learn that player's role.",
        "QA_LEAD":  "You are the **QA_LEAD** (good). Each Night you may DM the "
                    "GM ONE player to shield from the BUG kill. You cannot "
                    "shield the same player two Nights in a row.",
        "BUG":      "You are a **BUG** (evil). Coordinate with fellow BUGS. "
                    "Each Night, BUGS must agree on and DM the GM ONE victim. "
                    "BUGS know each other's identities."
    },

    # ─────────────────────────────────────────────────────────────────────────
    # GM PROCEDURAL GUIDELINE  (sent ONLY to the GM)
    # ─────────────────────────────────────────────────────────────────────────
    "gm_guideline": """
========================= GM Procedural Guideline =========================
Always prefix public messages with "GM:".

PHASE CONTROL
• Start Discussion:  "GM: Discussion phase begins. Talk freely."
• Start Vote:        "GM: Vote phase – DM me exactly one player name."
• Reveal Vote:       "GM: <NAME> is voted out and was a <ROLE>."
• Start Night:       "GM: Night phase. BUGS, choose a victim. DEBUGGER & "
                     "QA_LEAD, DM me your actions now."
• Reveal Night:      "GM: <NAME> was removed during the Night and was a <ROLE>."

RESOLUTION DETAILS
Vote
  – Highest vote dies; ties → randomly pick one of the tied players.
  – Immediately announce name & role; move player from alive → dead.

Night
  1. Collect BUG victim (must be unanimous).
  2. Ask DEBUGGER for inspection target; reply privately with role.
  3. Ask QA_LEAD for shield target, enforcing the no-repeat rule.
  4. Apply shield: if the BUG victim is shielded, they survive.
  5. Announce night death publicly (or "No one died.").

RULE ENFORCEMENT HINTS
• Votes or ability uses in public chat → remind to DM.
• Multiple votes/targets from the same player → accept first, ignore rest.
• Discussion during Night → warn once, then silence if repeated.

WHEN TO MOVE TO NEXT PHASE
• Vote ends when all living players have voted.
• Night ends when BUGS & relevant special roles have all acted.

WIN DECLARATION
• After any elimination, ask the SYSTEM agent for a win check.
• When SYSTEM returns a winner, announce: "GM: <TEAM> wins! <reason>"
============================================================================
""",

    # ─────────────────────────────────────────────────────────────────────────
    # SYSTEM AGENT GUIDELINE  (hidden, consumed by automated system agent)
    # ─────────────────────────────────────────────────────────────────────────
    "system_guideline": """
You are the hidden SYSTEM agent managing Test Social Deduction Game.

PUBLIC META YOU MAINTAIN
  phase            – "discussion" | "vote" | "night"
  alive            – list[str]    # living player names
  dead             – list[str]    # dead player names

PRIVATE META YOU MAINTAIN
  roles            – {player: role}
  qa_last_shield   – str | null   # target QA_LEAD shielded last night
  pending_kill     – str | null   # BUGS' selected victim (reset each day)

STATE UPDATE RULES (triggered by GM announcements)
• "Discussion phase begins"                  → phase = "discussion"
• "Vote phase"                                → phase = "vote"
• Vote result line "is voted out"             → remove NAME from alive → dead
                                               pending_kill = null
• "Night phase"                               → phase = "night"
• At Night resolution:
    – If GM announces "<NAME> was removed ..."→ remove NAME from alive → dead
    – If GM announces "No one died."          → no change to alive/dead
    – After processing death, pending_kill = null
    – Update qa_last_shield with tonight's QA target (from GM DM log)

WIN CHECK (run after every death or end of vote/night)
• TESTERS win if no player with role "BUG" remains in alive list.
• BUGS win if len([BUG in alive]) >= len([non-BUG in alive]).

OUTPUT FORMAT
Always respond with valid JSON:
{
  "update_pub":  {...changes to public meta...},
  "update_priv": {...changes to private meta...},
  "winner": null | "TESTERS" | "BUGS",
  "reason": "text explanation of what happened / why someone won"
}
"""
}

###############################################################################
#  PUBLIC META INITIALISER
###############################################################################
def init_meta_pub(players: List[str]) -> Dict:
    """Initial public state: everyone alive, phase starts in discussion."""
    return {
        "phase": "discussion",
        "alive": list(players),
        "dead": []
    }

###############################################################################
#  PRIVATE META INITIALISER
###############################################################################
def init_meta_priv(players: List[str]) -> Dict:
    """
    Assign roles, build per-player private views, plus a GM_SYSTEM block
    containing full secret state.
    """
    num_players = len(players)

    # ---------- role distribution ----------
    # Very small game (≤4) → 1 BUG, 1 DEBUGGER, rest TESTER
    # Medium (5-7)         → 2 BUGS, 1 DEBUGGER, 1 QA_LEAD, rest TESTER
    # Large (≥8)           → 3 BUGS, 1 DEBUGGER, 1 QA_LEAD, rest TESTER
    if num_players <= 4:
        roles_pool = ["BUG", "DEBUGGER"] + ["TESTER"] * (num_players - 2)
    elif num_players <= 7:
        roles_pool = ["BUG", "BUG", "DEBUGGER", "QA_LEAD"] \
                     + ["TESTER"] * (num_players - 4)
    else:
        roles_pool = ["BUG", "BUG", "BUG", "DEBUGGER", "QA_LEAD"] \
                     + ["TESTER"] * (num_players - 5)

    random.shuffle(roles_pool)
    role_assignments = {p: r for p, r in zip(players, roles_pool)}

    # Identify BUG teammates for knowledge sharing
    bugs = [p for p, r in role_assignments.items() if r == "BUG"]

    # ---------- build meta_priv ----------
    meta_priv_all: Dict[str, Dict] = {}

    # GM_SYSTEM view (shared between GM agent & SYSTEM agent)
    meta_priv_all["GM_SYSTEM"] = {
        "roles": role_assignments.copy(),
        "qa_last_shield": None,   # Who was shielded last night (for repeat rule)
        "pending_kill": None      # Will hold tonight's BUG victim
    }

    # Per-player private blocks
    for player in players:
        role = role_assignments[player]
        block = {"role": role}

        # Extra knowledge per role
        if role == "BUG":
            block["teammates"] = [b for b in bugs if b != player]
        elif role == "DEBUGGER":
            block["inspect_history"] = {}   # night_number → {player: role}
        elif role == "QA_LEAD":
            block["shield_history"] = []    # list of names

        meta_priv_all[player] = block

    return meta_priv_all

###############################################################################
#  HELPER – quick role lookup
###############################################################################
def assign_role(name: str, meta_priv: Dict) -> str:
    """Return the role for a given player from stored meta."""
    return meta_priv["GM_SYSTEM"]["roles"][name]

###############################################################################
#  PROMPT BUILDERS
###############################################################################
def player_sys_prompt(name: str, role: str, lang: str = "en") -> str:
    """System prompt delivered to a player agent at game start."""
    return (
        f"{RULEBOOK['common']}\n"
        f"{RULEBOOK['role'][role]}\n"
        f"You are {name}. Speak in {lang}."
    )

def gm_sys_prompt(lang: str = "en") -> str:
    """System prompt delivered to the GM agent at game start."""
    return (
        f"{RULEBOOK['common']}\n"
        f"{RULEBOOK['gm_guideline']}\n"
        f"You are the GM. Speak in {lang}."
    )

def system_sys_prompt() -> str:
    """System prompt delivered to the hidden SYSTEM agent."""
    return (
        f"{RULEBOOK['common']}\n"
        f"{RULEBOOK['system_guideline']}\n"
        f"You are the game system agent managing the game state."
    )