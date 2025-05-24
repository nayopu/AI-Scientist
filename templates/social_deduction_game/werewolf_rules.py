"""
Werewolf rules for sdg_core v3
"""
import json, random
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers.json import SimpleJsonOutputParser

###############################################################################
# 追加: ルールブック辞書
###############################################################################
RULEBOOK = {
    # Public to everyone
    "common": """
===================== Werewolf – Public Rulebook =====================
VICTORY
  • Villagers win when every Werewolf is dead.  
• Werewolves win once Werewolves ≥ Villagers.

POSSIBLE ROLES
• **Villager**: Basic role with no special abilities. Can participate in discussions and vote to eliminate suspicious players.
• **Werewolf**: Evil role that works with other wolves. Each night, wolves must agree on one player to kill. Wolves know each other's identities.
• **Seer**: Town role that can investigate one player each night. The GM will tell them if that player is a Werewolf or not.
• **Doctor**: Town role that can protect one player each night from being killed by wolves. Cannot protect the same player two nights in a row.
• **Hunter**: Town role with a final revenge ability. When killed (by vote or night kill), can immediately eliminate one other player.

• **Witch**: Town role with two special potions:
  - Save potion: Can save the wolf's victim once
  - Kill potion: Can eliminate any player once
  Can only use one potion per night.

PHASE SEQUENCE
1. **Discussion** – open conversation.  
2. **Vote** – each living player secretly submits ONE name to the GM.  
3. **Night** – all living Werewolves agree on one victim and DM the GM.
              Special roles use their abilities during Night.

RESOLUTION
• Vote: highest-vote player is executed (ties random).  
• Night kill: chosen victim dies immediately (unless protected).

TURN RHYTHM  
Discussion → GM says "Vote phase – send your target" → Vote →  
GM announces execution → GM says "Night phase – Wolves choose" →  
Night kill & special abilities → next Discussion …
======================================================================
""",

    # Private to each role owner
    "role": {
        "VILLAGER": "You are a **Villager**. You have NO special power.",
        "WEREWOLF": "You are a **Werewolf**. During Night you and fellow Wolves\n"
                    "must agree on one victim and DM the GM.",
        "SEER": "You are a **Seer**. Each Night, you may DM the GM one player's name\n"
                "to learn if they are a Werewolf or not.",
        "DOCTOR": "You are a **Doctor**. Each Night, you may DM the GM one player's name\n"
                  "to protect them from the Werewolf kill that night.",
        "HUNTER": "You are a **Hunter**. When you die (by vote or night kill),\n"
                  "you may immediately take one other player down with you.",
        "WITCH": "You are a **Witch**. You have ONE save potion and ONE kill potion.\n"
                 "During Night, you may use either (but not both in same night):\n"
                 "• Save potion: saves the werewolf victim\n"
                 "• Kill potion: kills any player of your choice"
    },

    # Visible only to the GM
    "gm_guideline": """
====================== GM Procedural Guideline ======================
Always speak to players in plain English and prefix with "GM:".

PHASE ANNOUNCEMENTS (examples)
• Start Discussion:  "GM: Discussion phase begins. Feel free to talk."  
• Start Vote:        "GM: Vote phase. DM me exactly one name."  
• Vote result:       "GM: <name> is executed."  
• Start Night:       "GM: Night phase. Werewolves, DM me one victim."  
• Night result:      "GM: <name> was killed during the night."

SPECIAL ROLE HANDLING
• Seer: After wolves choose, ask "GM: Seer, DM me who you want to investigate."
• Doctor: Ask "GM: Doctor, DM me who you want to protect."
• Hunter: When Hunter dies, ask "GM: Hunter, you may take someone with you. DM me a name."
• Witch: Show victim to Witch, ask if they want to save or kill someone.

WHEN TO END DISCUSSION  
End the Discussion phase (and start Vote) by your announcement as soon as sufficient discussion has taken place

RULE ENFORCEMENT GUIDELINES
• If a player votes without specifying a name: "GM: Please vote by sending me DM with exactly one player name."
• If a player tries to vote multiple times: "GM: You may only vote once per vote phase."
• If a player votes in public chat: "GM: Please DM your vote to me instead of posting it publicly."
• If a player tries to use abilities during discussion: "GM: Special abilities can only be used during the night phase."
• If a player tries to vote during discussion: "GM: Voting is only allowed during the vote phase."
• If a player tries to discuss during night: "GM: No discussion is allowed during the night phase."
=====================================================================
""",
    "system_guideline": """You are the SYSTEM agent managing the game state for Werewolf.

Your responsibilities:
1. Update meta information based on game events
2. Check win conditions after each turn

Meta update rules:
- When GM announces "Vote phase", update phase to "vote"
- When GM announces vote results, remove executed player from alive list and add to dead list
- When GM announces "Night phase", update phase to "night"
- When GM announces night kill results, remove killed player from alive list and add to dead list
- When GM announces "Discussion phase", update phase to "discussion"
- Track special role actions in meta_priv (seer investigations, doctor protections, witch potions)

Win condition rules:
- VILLAGERS win when ALL Werewolves are dead (no werewolves in alive list)
- WEREWOLVES win when Werewolves >= non-Werewolves among living players

Always respond with valid JSON containing:
- update_pub: public meta changes (phase, alive, dead)
- update_priv: private meta changes (special role states)
- winner: null or "VILLAGERS" or "WEREWOLVES"
- reason: explanation of updates/win
"""
}

# ---------- 初期化 ----------
def init_meta_pub(players: List[str]):
    return {"phase": "discussion",
            "alive": list(players),
            "dead": []}

def init_meta_priv(players: List[str]):
    # Assign roles based on player count
    num_players = len(players)
    
    if num_players < 5:
        # Small game: 1 werewolf, rest villagers
        roles = ["WEREWOLF"] + ["VILLAGER"]*(num_players-1)
    elif num_players < 8:
        # Medium game: 1-2 werewolves, 1 seer, 1 doctor, rest villagers
        num_wolves = 2 if num_players >= 6 else 1
        roles = ["WEREWOLF"]*num_wolves + ["SEER", "DOCTOR"]
        roles += ["VILLAGER"]*(num_players - len(roles))
    else:
        # Large game: 2+ werewolves, all special roles
        num_wolves = max(2, num_players // 4)
        roles = ["WEREWOLF"]*num_wolves + ["SEER", "DOCTOR", "HUNTER", "WITCH"]
        roles += ["VILLAGER"]*(num_players - len(roles))
    
    random.shuffle(roles)
    
    # Initialize special role states
    meta = {
        "roles": {p: r for p, r in zip(players, roles)},
        "witch_potions": {"save": True, "kill": True},  # Witch's available potions
        "protected": None,  # Who the doctor protected this night
        "seer_results": {}  # Seer's investigation history
    }
    
    return meta

def assign_role(name: str, meta_priv) -> str:
    return meta_priv["roles"][name]

# ---------- プロンプト ----------
def player_sys_prompt(name: str, role: str, lang: str) -> str:
    # lang still lets you force non-English speech if you wish,
    # but the rules themselves are now in English.
    return (f"{RULEBOOK['common']}\n{RULEBOOK['role'][role]}\n"
            f"You are {name}. Speak in {lang}.")

def gm_sys_prompt(lang: str) -> str:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n"
            f"You are the GM. Speak in {lang}.")

def system_sys_prompt() -> str:
    # system agent prompt for handling meta updates and win condition checks
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the game system agent managing the game state.")
