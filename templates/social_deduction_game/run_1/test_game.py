"""
Test Social Deduction Game rules for sdg_core v3
Generated from idea: A simple test game for validation
"""
import json, random
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers.json import SimpleJsonOutputParser

###############################################################################
# Rule book for Test Social Deduction Game
###############################################################################
RULEBOOK = {
    # Public to everyone
    "common": """
===================== Test Social Deduction Game – Public Rulebook =====================
VICTORY
  • [TO BE IMPLEMENTED] Win conditions based on the game idea.

POSSIBLE ROLES
• [TO BE IMPLEMENTED] Roles based on the game concept.

PHASE SEQUENCE
1. **Discussion** – open conversation.  
2. **Vote** – each living player secretly submits ONE name to the GM.  
3. **Special Phase** – special actions based on game mechanics.

RESOLUTION
• Vote: highest-vote player is affected by game mechanics.  
• Special actions: based on specific game rules.

TURN RHYTHM  
Discussion → Vote → Special Phase → next Discussion …
======================================================================
""",

    # Private to each role owner
    "role": {
        "PLAYER": "You are a player in Test Social Deduction Game. [Role details to be implemented]",
    },

    # Visible only to the GM
    "gm_guideline": """
====================== GM Procedural Guideline ======================
Always speak to players in plain English and prefix with "GM:".

PHASE ANNOUNCEMENTS
• Start Discussion:  "GM: Discussion phase begins. Feel free to talk."  
• Start Vote:        "GM: Vote phase. DM me exactly one name."  
• Vote result:       "GM: Vote result processing."
• Start Special:     "GM: Special phase. Players with abilities, DM me your actions."  

RULE ENFORCEMENT GUIDELINES
• Basic vote enforcement and turn management
• [TO BE IMPLEMENTED] Specific rules for this game
=====================================================================
""",
    "system_guideline": """You are the SYSTEM agent managing the game state for Test Social Deduction Game.

Your responsibilities:
1. Update meta information based on game events
2. Check win conditions after each turn

[TO BE IMPLEMENTED] Specific system logic for this game variant

Always respond with valid JSON containing:
- update_pub: public meta changes
- update_priv: private meta changes  
- winner: null or winning team/player
- reason: explanation of updates/win
"""
}

# ---------- Initialization ----------
def init_meta_pub(players: List[str]):
    return {"phase": "discussion",
            "alive": list(players),
            "dead": []}

def init_meta_priv(players: List[str]):
    # Basic role assignment - to be customized per game
    num_players = len(players)
    roles = ["PLAYER"] * num_players  # Placeholder
    random.shuffle(roles)
    
    meta = {
        "roles": {p: r for p, r in zip(players, roles)},
        # Add game-specific private state here
    }
    
    return meta

def assign_role(name: str, meta_priv) -> str:
    return meta_priv["roles"][name]

# ---------- Prompts ----------
def player_sys_prompt(name: str, role: str, lang: str) -> str:
    role_prompt = RULEBOOK['role'].get(role, RULEBOOK['role'].get('PLAYER', 'You are a player.'))
    return (f"{RULEBOOK['common']}\n{role_prompt}\n"
            f"You are {name}. Speak in {lang}.")

def gm_sys_prompt(lang: str) -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n"
            f"You are the GM. Speak in {lang}.")

def system_sys_prompt() -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the game system agent managing the game state.")
