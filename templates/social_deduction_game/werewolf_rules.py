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

PHASE SEQUENCE
1. **Discussion** – open conversation.  
2. **Vote** – each living player secretly submits ONE name to the GM.  
3. **Night** – all living Werewolves agree on one victim and DM the GM.

RESOLUTION
• Vote: highest-vote player is executed (ties random).  
• Night kill: chosen victim dies immediately.

TURN RHYTHM  
Discussion → GM says "Vote phase – send your target" → Vote →  
GM announces execution → GM says "Night phase – Wolves choose" →  
Night kill → next Discussion …
======================================================================
""",

    # Private to each role owner
    "role": {
        "VILLAGER": "You are a **Villager**. You have NO special power.",
        "WEREWOLF": "You are a **Werewolf**. During Night you and fellow Wolves\n"
                    "must agree on one victim and DM the GM."
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

WHEN TO END DISCUSSION  
End the Discussion phase (and start Vote) by your announcement as soon as  
  • every living player has spoken at least once, **or**  
  • 5 public messages have been posted – whichever comes first.

RULE ENFORCEMENT GUIDELINES
• If a player votes without specifying a name: "GM: Please vote by sending me DM with exactly one player name."
• If a player tries to vote multiple times: "GM: You may only vote once per vote phase."
• If a player votes in public chat: "GM: Please DM your vote to me instead of posting it publicly."
• If a player tries to use abilities during discussion: "GM: Special abilities can only be used during the night phase."
• If a player tries to vote during discussion: "GM: Voting is only allowed during the vote phase."
• If a player tries to discuss during night: "GM: No discussion is allowed during the night phase."
=====================================================================
"""
}

# ---------- 初期化 ----------
def init_meta_pub(players: List[str]):
    return {"phase": "discussion",
            "alive": list(players),
            "dead": []}

def init_meta_priv(players: List[str]):
    roles = ["WEREWOLF"] + ["VILLAGER"]*(len(players)-1)
    random.shuffle(roles)
    return {"roles": {p: r for p, r in zip(players, roles)}}

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

# ---------- 終了判定 ----------
def check_end(meta_pub, meta_priv) -> str | None:
    wolves = [p for p in meta_pub["alive"]
              if meta_priv["roles"].get(p) == "WEREWOLF"]
    vill  = [p for p in meta_pub["alive"]
              if meta_priv["roles"].get(p) == "VILLAGER"]
    if not wolves:
        return "VILLAGERS"
    if len(wolves) >= len(vill):
        return "WEREWOLVES"
    return None

