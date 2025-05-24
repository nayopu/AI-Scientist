"""
Insider rules for sdg_core v3
"""
import json, random
from typing import List, Dict

###############################################################################
#  RULEBOOK
###############################################################################
RULEBOOK: Dict[str, Dict | str] = {
    # ─────────────────────────────────────────────────────────────────────────
    # Public rulebook (visible to every player)
    # ─────────────────────────────────────────────────────────────────────────
    "common": """
==================== INSIDER – Public Rulebook ====================
GOAL
• Guess the secret word within the 5-minute Question Phase.
• Then identify the hidden Insider during the Vote.
  ↳ If the word is **not** guessed in time → everybody loses.

ROLES
• **Master** – Moderates the game, answers only “Yes / No / I don't know”.  
  Shows their role openly.
• **Insider** – Knows the secret word but stays hidden.  
  Guides the group toward guessing without being found.
• **Commoner** – Does not know the word. Must discover it and expose the Insider.

PHASE SEQUENCE
1. **Question Phase** (5 min)  
   Players ask Master yes/no questions to find the word.
2. **(If word guessed)** **Discussion Phase** (≈2 min)  
   Open talk to find the Insider.
3. **Vote Phase** – Everyone simultaneously names ONE suspect.

VICTORY (when the Vote is resolved)
• **Commons + Master win** if the accused player *is* the Insider.  
• **Insider wins** if someone else is accused.  
• If the word was never guessed → **No one wins**.
====================================================================
""",

    # ─────────────────────────────────────────────────────────────────────────
    # Private role blurbs (sent individually)
    # ─────────────────────────────────────────────────────────────────────────
    "role": {
        "MASTER":   "You are the **Master**. Reveal yourself. Answer ONLY “Yes”, "
                    "“No”, or “I don't know” to questions about the secret word.",
        "INSIDER":  "You are the **Insider**. You secretly know the word. Help the "
                    "group guess it, but avoid being revealed in the Vote.",
        "COMMONER": "You are a **Commoner**. You don't know the word. Work with "
                    "others to guess it and to expose the Insider."
    },

    # ─────────────────────────────────────────────────────────────────────────
    # Guidance for the GM agent (not a role in-game)
    # ─────────────────────────────────────────────────────────────────────────
    "gm_guideline": """
==================== GM Procedural Guideline =====================
Always prefix messages with “GM:”.

SET-UP
• Privately choose a secret word (e.g. draw a card).  
• DM the word to both Master and Insider.

PHASE CONTROL
1. Announce “GM: Question phase begins – ask yes/no questions.”  
   Start 5-minute timer (you may shorten in chat play).
2. If word is guessed in time:  
   • Announce “GM: Correct! The word was <WORD>. Discussion phase – 2 min.”  
   • After discussion, announce “GM: Vote phase – DM one suspect.”
3. Collect votes (DM). Announce result:  
   “GM: <NAME> is accused as Insider.”

RULE ENFORCEMENT
• Reject questions not answerable by Yes/No/I don't know.  
• During Question Phase the Master answers only with those words.  
• During Discussion/Vote the Master is a normal speaker.

TIE-BREAKING
• If Vote ties, randomly pick one of the tied players as accused.

END & WIN CHECK
• After announcing the accused, let the System agent evaluate victory.
===================================================================
""",

    # ─────────────────────────────────────────────────────────────────────────
    # Guidance for the hidden System agent
    # ─────────────────────────────────────────────────────────────────────────
    "system_guideline": """
You are the SYSTEM agent tracking game state for Insider.

Public meta you maintain:
  phase            – "question" | "discussion" | "vote"
  word_guessed     – true/false
  accused          – null or player name

Private meta you maintain:
  roles            – {player: role}
  secret_word      – string

UPDATE RULES
• When GM says “Question phase begins”            → phase = "question"
• When GM announces the correct word              → phase = "discussion", word_guessed = true
• When GM says “Vote phase”                       → phase = "vote"
• When GM announces “<NAME> is accused …”         → accused = <NAME>

WIN CHECK
• If phase == "question" and GM says “time’s up” AND word_guessed == false  
    → everyone loses → winner = "NONE"
• If phase == "vote" and accused is set:  
    – If roles[accused] == "INSIDER" → winner = "COMMONS"  
    – else                           → winner = "INSIDER"

Always respond with valid JSON:
{
  "update_pub":  { …changes to public meta… },
  "update_priv": { …changes to private meta… },
  "winner": null | "COMMONS" | "INSIDER" | "NONE",
  "reason": "explanation"
}
"""
}

###############################################################################
#  INITIALISERS
###############################################################################
def init_meta_pub(players: List[str]) -> Dict:
    """Initial public state – game starts in Question Phase."""
    return {
        "phase": "question",
        "word_guessed": False,
        "accused": None
    }

def init_meta_priv(players: List[str]) -> Dict:
    """Assign 1 Master, 1 Insider, rest Commoners; store secret word placeholder."""
    roles = ["MASTER", "INSIDER"] + ["COMMONER"] * (len(players) - 2)
    random.shuffle(roles)
    return {
        "roles": {p: r for p, r in zip(players, roles)},
        "secret_word": "<SECRET_WORD>"
    }

def assign_role(name: str, meta_priv: Dict) -> str:
    """Return this player's role."""
    return meta_priv["roles"][name]

###############################################################################
#  PROMPT HELPERS
###############################################################################
def player_sys_prompt(name: str, role: str, lang: str) -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['role'][role]}\n"
            f"You are {name}. Speak in {lang}.")

def gm_sys_prompt(lang: str) -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n"
            f"You are the GM. Speak in {lang}.")

def system_sys_prompt() -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the game system agent.")