"""
Spyfall rules for sdg_core v3
"""
import random
from typing import List, Dict, Tuple

###############################################################################
# Game constants
###############################################################################
# A slimmed-down list of classic Spyfall locations. Feel free to extend it.
LOCATIONS = [
    "Airplane", "Casino", "Cathedral", "Corporate Party", "Crusader Army",
    "Day Spa", "Embassy", "Hospital", "Hotel", "International Space Station",
    "Movie Studio", "Ocean Liner", "Passenger Train", "Pirate Ship",
    "Polar Station", "Police Station", "Restaurant", "School", "Service Station",
    "Submarine", "Supermarket", "Theater", "University", "Vacation Resort"
]

CURRENT_LOCATION: str | None = None      # set in init_meta_priv

###############################################################################
# ルールブック辞書
###############################################################################
RULEBOOK: Dict[str, Dict | str] = {
    # Public to everyone
    "common": """
==================== Spyfall – Public Rulebook ====================
OBJECTIVE
• **Locals** (all non-Spies) win if they identify and vote out the Spy.
• The **Spy** wins if they correctly guess the secret location *before* being voted out.

PHASE SEQUENCE
1. **Discussion** – ask & answer questions to expose the Spy
2. **Vote** – each living player secretly names one suspect to the GM
3. **Spy-Guess (optional)** – the Spy may DM the GM one location guess

RESOLUTION
• Vote: highest-vote player is revealed.  
  – If it is the Spy ⇒ Locals win.  
  – Otherwise ⇒ Spy instantly wins (locals exposed themselves).  
• Spy-Guess: if the Spy's DM'd location matches the secret one, the Spy wins.

TURN RHYTHM
Discussion → GM says "Vote phase – DM your suspect" → Vote → 
GM reveals accused → *if Spy still alive* GM whispers "Spy, DM your location guess" →
Spy-Guess (optional) → next Discussion … until a side wins.
===================================================================
""",

    # Private to each role owner (the {location} placeholder is filled at runtime)
    "role": {
        "LOCAL": "You are a **Local**. You know the secret location: **{location}**.\n"
                 "Convince others you are not the Spy and find the Spy!",
        "SPY":   "You are the **Spy**. You do **NOT** know the location!\n"
                 "Blend in and, when ready, DM the GM one location to win."
    },

    # Visible only to the GM
    "gm_guideline": """
================== GM Procedural Guideline ==================
Always prefix public messages with "GM:".

PHASE ANNOUNCEMENTS (examples)
• Start Discussion: "GM: Discussion phase begins. Ask away!"
• Start Vote:       "GM: Vote phase – DM me one suspect."
• Reveal vote:      "GM: <name> is accused and revealed to be <role>."
• Spy Guess prompt: "GM: Spy, DM me your location guess now."

HANDLING VOTES
• Highest-vote player is revealed. Ties: pick randomly.
• If the revealed player is the Spy ⇒ Locals win immediately.
• Otherwise the Spy wins immediately (the group mis-fired).

HANDLING SPY GUESS
• Accept exactly one DM from the Spy with a location name.
• If it matches the secret location (case-insensitive) ⇒ Spy wins.
• If incorrect, continue the game.

RULE ENFORCEMENT
• Votes or guesses sent publicly → remind to DM.
• Multiple guesses/votes → accept first, ignore the rest.
• Talking outside Discussion phase → warn the player.
=============================================================
""",

    # System agent guideline
    "system_guideline": """You are the GameSystem agent that acts as both SYSTEM and GM for Spyfall.

Your dual responsibilities:
1. Act as GM - manage discussion, voting, and spy guess phases
2. Update meta information and check win conditions

As GM, you should:
- Announce phase changes and manage flow
- Request votes via DM during vote phase
- Reveal vote results and player roles
- Prompt Spy for location guess when appropriate
- Provide game announcements and enforcement

As SYSTEM, you should:
- Update meta information based on game events
- Check win conditions after each turn
- Track special actions (spy guesses)

Meta update rules:
- When you announce "Vote phase", update phase to "vote"
- When you announce vote results, remove executed player from alive list and add to dead list
- When you announce "Discussion phase", update phase to "discussion"
- When Spy DMs a location guess to you, record it in meta_priv as spy_guess

Win condition rules:
- LOCALS win if the Spy is voted out (not in alive list)
- SPY wins if:
  a) A non-Spy is voted out (Spy is still alive after someone was executed)
  b) Spy correctly guesses the location (spy_guess matches secret location)

Always respond with valid JSON containing:
- selected_messages: your GM messages and selected player messages
- update_pub: public meta changes (phase, alive, winner)
- update_priv: private meta changes (spy_guess)
- reason: explanation of decisions and updates
"""
}

###############################################################################
# Initialisation helpers
###############################################################################
def init_meta_pub(players: List[str]) -> Dict:
    """Public meta visible to everyone"""
    return {"phase": "discussion", "alive": list(players), "winner": None}

def init_meta_priv(players: List[str]) -> Dict:
    """Private meta organized by participant"""
    global CURRENT_LOCATION
    CURRENT_LOCATION = random.choice(LOCATIONS)

    # Exactly one Spy; everyone else is Local
    spy = random.choice(players)
    role_assignments = {p: ("SPY" if p == spy else "LOCAL") for p in players}

    # Create private meta structure
    meta_priv_all = {}
    
    # GM private meta (for the GameSystem that acts as GM)
    meta_priv_all["GM"] = {
        "roles": role_assignments,     # mapping player → role
        "location": CURRENT_LOCATION,  # secret location
        "spy_guess": None,             # later: {"player": name, "guess": str, "correct": bool}
    }
    
    # Each player's private meta
    for player in players:
        role = role_assignments[player]
        player_meta = {
            "role": role
        }
        
        # Add role-specific private information
        if role == "LOCAL":
            # Locals know the location
            player_meta["location"] = CURRENT_LOCATION
        elif role == "SPY":
            # Spy doesn't know the location
            player_meta["location"] = None
        
        meta_priv_all[player] = player_meta
    
    return meta_priv_all

def assign_role(name: str, meta_priv) -> str:
    return meta_priv["GM"]["roles"][name]

###############################################################################
# Prompt builders
###############################################################################
def player_sys_prompt(name: str, role: str, lang: str) -> str:
    """System prompt for each player. Locals receive the location string."""
    if role == "SPY":
        role_text = RULEBOOK["role"]["SPY"]
    else:
        role_text = RULEBOOK["role"]["LOCAL"].format(location=CURRENT_LOCATION)

    return f"{RULEBOOK['common']}\n{role_text}\nYou are {name}. Speak in {lang}."

def system_sys_prompt() -> str:
    """GameSystem agent prompt - combines GM and system responsibilities."""
    return (f"{RULEBOOK['common']}\nSecret location = {CURRENT_LOCATION}\n"
            f"{RULEBOOK['gm_guideline']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the GameSystem agent that acts as both GM and game state manager.")