"""
test_game.py – rules for sdg_core v3
A minimal yet fully-featured social-deduction ruleset created only to
validate the sdg_core engine.  Theme: star-ship maintenance versus
shape-shifting mimics.
"""
import random, json
from typing import List, Dict

###############################################################################
#  RULEBOOK – four sections required by sdg_core
###############################################################################
RULEBOOK: Dict[str, str | Dict[str, str]] = {
    # ────────────────────────────────────────────────────────────────── PUBLIC
    "common": """
================ Test Social Deduction Game – Public Rulebook ================
THEME
You are crew members aboard the research vessel “VALIDATOR-ONE”.
Hidden among you are alien Mimics who want to equal or outnumber the Crew.

FACTIONS & VICTORY
• **Crew** (all non-Mimic roles) win when every Mimic is dead.  
• **Mimics** win the instant living Mimics ≥ living Crew.

ROLES
• **Crewmate** – ordinary Crew with no night ability.  
• **Mimic** – evil alien. Mimics know one another and jointly select a
  victim to eliminate each Night.  
• **Scanner** – Crew who may “scan” ONE player each Night to learn
  whether they are a Mimic.  
• **Medic** – Crew who may protect ONE player each Night from being
  eliminated (may not pick the same target two Nights in a row).  

PHASE SEQUENCE (repeats until one side wins)
1. Discussion   – open talk.  
2. Vote         – every living player DM’s the GM **exactly one name**.  
   ‑ Highest votes → execution (ties broken randomly).  
3. Night        – Mimics choose a victim.  
   • Scanner DM’s the GM one name to scan.  
   • Medic DM’s the GM one name to protect.

RESOLUTION ORDER (Night)
1) Medic target stored.  
2) Mimic kill chosen → if protected, no one dies.  
3) Scanner result returned privately.  
4) GM announces Night casualty (or none) publicly.

TURN RHYTHM (example)
GM: “Discussion phase begins …” →  
GM: “Vote phase – DM one name.” →  
GM tallies & announces execution →  
GM: “Night phase – Mimics pick a victim; Scanner & Medic send abilities.” →  
GM resolves Night → next Discussion …

TALKING RULES
• No talking in private channels except to GM for mandated actions.  
• No discussion during Night.  
• Votes/ability targets must be DM’d to GM; public posting invalid.

==============================================================================
""",

    # ─────────────────────────────────────────────────────────── ROLE-SPECIFIC
    "role": {
        "CREWMATE":
            "You are a **Crewmate** (good). You have NO special night ability.",
        "MIMIC":
            "You are a **Mimic** (evil). During every Night you and the other "
            "Mimics must agree on ONE living player to eliminate. "
            "Mimics you can contact privately: they are listed in your teammate "
            "field below.",
        "SCANNER":
            "You are the **Scanner** (good). Each Night you may choose ONE "
            "player to SCAN. The GM will reply 'Mimic' or 'Not Mimic'.",
        "MEDIC":
            "You are the **Medic** (good). Each Night you may choose ONE player "
            "to PROTECT from the Mimic kill. You may NOT protect the same "
            "player on two consecutive Nights."
    },

    # ──────────────────────────────────────────────────────────────── GM GUIDE
    "gm_guideline": """
========================= GM Procedural Guideline =========================
Always prefix public messages with “GM:”.

SET-UP
1. Use init_meta_priv() to assign roles randomly.
2. DM each player their role blurb (plus teammates/info where included).

STANDARD LOOP
• Discussion Phase  
  - Announce:  GM: Discussion phase begins.  
  - When ready, announce: GM: Vote phase – DM me exactly ONE name.

• Vote Phase  
  - Collect one DM per living player.  
  - If someone fails to vote, ping: “GM: please send a single name.”  
  - After all votes received, reveal:  
    GM: <NAME> is executed. They were <ROLE>.  
  - Move executed player to dead list. Check win via System.

• Night Phase  
  - Announce: GM: Night phase. Mimics choose a victim. Scanner/Medic send actions.  
  - Wait for: Mimic victim (joint), Scanner target, Medic target.  
  - Resolve in order:  
      1. Note Medic target (track last protected).  
      2. If victim == protected ⇒ nobody dies.  
      3. DM scan result to Scanner: “GM (private): <TARGET> is (Mimic/Not Mimic).”  
  - Publicly announce:  
      GM: <NAME> was killed during the night. (or) GM: No one died tonight.  
  - Update meta, then start next Discussion or end if System declares winner.

RULE ENFORCEMENT SHORT LIST
• Talking during Night → “GM: Night is silent. Please stop.”  
• Votes in public chat → “GM: DM your vote privately.”  
• Multiple votes → first one counts, ignore rest.  
• Medic protects same target twice consecutively → reject and ask for new name.

WHEN TO END
After every execution AND every Night resolution, invoke the System agent to
check victory. If System returns winner, announce immediately and set phase to
“end”.
===========================================================================""",

    # ─────────────────────────────────────────────────────────── SYSTEM GUIDE
    "system_guideline": """
You are the hidden SYSTEM agent managing game state.

Public meta structure you maintain:
  phase   : "discussion" | "vote" | "night" | "end"
  alive   : list[str]
  dead    : list[str]

Private meta (GM_SYSTEM key) you manage:
  roles           : {player: role}
  last_protected  : str | None
  scanner_logs    : list[dict]   # {"night": N, "scanner": P, "target": T, "is_mimic": bool}

STATE UPDATE RULES
• On GM announcing “Discussion phase”   → phase = "discussion"
• On GM announcing “Vote phase”         → phase = "vote"
• After GM reveals executed player      → move player to dead; phase stays "vote"
• On GM announcing “Night phase”        → phase = "night"
• After Night casualties announced      → move victim to dead (if any)
• Whenever GM says “Game over” or winner decided → phase = "end"

WIN CHECK (trigger after any death or execution)
  IF no Mimics remain alive → winner = "CREW"
  IF living Mimics ≥ living Crew → winner = "MIMICS"
  ELSE winner = null

ALWAYS reply with valid JSON:
{
 "update_pub":  {...changes to public meta...},
 "update_priv": {...changes to private meta...},
 "winner": null | "CREW" | "MIMICS",
 "reason": "human-readable explanation"
}
"""
}

###############################################################################
#  INITIALISERS
###############################################################################
def init_meta_pub(players: List[str]) -> Dict:
    """
    Public game state visible to every participant.
    """
    return {
        "phase": "discussion",
        "alive": list(players),
        "dead": []
    }


def init_meta_priv(players: List[str]) -> Dict:
    """
    Private game state organised by participant key.
    • GM_SYSTEM: all authoritative hidden info shared by GM & System agents
    • each player: role + extra knowledge
    """
    num_players = len(players)

    # ---- decide how many Mimics
    if   num_players < 6:        n_mimics = 1
    elif num_players < 9:        n_mimics = 2
    else:                        n_mimics = max(3, num_players // 4)

    roles_pool = (["MIMIC"] * n_mimics +
                  ["SCANNER"] +
                  (["MEDIC"] if num_players >= 6 else []) +
                  ["CREWMATE"] * 99)           # oversized filler; trimmed later
    roles_pool = roles_pool[:num_players]      # cut to exact size
    random.shuffle(roles_pool)

    role_assignments = {p: r for p, r in zip(players, roles_pool)}
    mimics = [p for p, r in role_assignments.items() if r == "MIMIC"]

    # ---- build meta_priv dict
    meta_priv_all: Dict[str, Dict] = {}

    # GM_SYSTEM shared block
    meta_priv_all["GM_SYSTEM"] = {
        "roles": role_assignments,
        "last_protected": None,
        "scanner_logs": []
    }

    # Per-player private info
    for player in players:
        role = role_assignments[player]
        pdata = {"role": role}

        if role == "MIMIC":
            pdata["teammates"] = [m for m in mimics if m != player]

        elif role == "SCANNER":
            pdata["scan_history"] = []          # player will log their results

        elif role == "MEDIC":
            pdata["cannot_protect"] = None      # filled nightly by GM/System

        # Crewmate has no extra fields

        meta_priv_all[player] = pdata

    return meta_priv_all


###############################################################################
#  ACCESSOR
###############################################################################
def assign_role(name: str, meta_priv: Dict) -> str:
    """
    Quick helper for sdg_core to fetch a player's role string.
    """
    return meta_priv["GM_SYSTEM"]["roles"][name]


###############################################################################
#  PROMPT HELPERS
###############################################################################
def player_sys_prompt(name: str, role: str, lang: str = "en") -> str:
    """
    System prompt delivered to a *player* agent.
    """
    role_text = RULEBOOK["role"][role]
    return (f"{RULEBOOK['common']}\n{role_text}\n"
            f"You are {name}. Speak in {lang}.")


def gm_sys_prompt(lang: str = "en") -> str:
    """
    System prompt delivered to the GM agent (human or AI).
    Shows full rulebook plus GM-only section.
    """
    return (f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n"
            f"You are the GM. Speak in {lang}.")


def system_sys_prompt() -> str:
    """
    Prompt for the hidden System agent that updates meta and checks victory.
    """
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the game system agent.")