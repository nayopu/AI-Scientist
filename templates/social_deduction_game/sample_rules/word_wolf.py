"""
Word-Wolf (ワード人狼) rules for sdg_core v3
"""

import random
from typing import List, Dict, Tuple

_WORDS_PER_PLAYER: Dict[str, str] = {}
_PAIR: Tuple[str, str] | None = None           # (citizen_word, wolf_word)

# お好みで増やしてください
WORD_PAIRS = [
    ("apple", "pear"),           # apple / pear
    ("soccer", "basketball"),    # soccer / basketball
    ("cat", "dog"),             # cat / dog
    ("sea", "river"),           # sea / river
    ("sushi", "tempura"),       # sushi / tempura
]

RULEBOOK: Dict[str, str | Dict[str, str]] = {
    # ── 全員に公開 ────────────────────────────────────────
    "common": """
===================== Word-Wolf – Public Rulebook =====================
OVERVIEW
  • Everyone receives a secret "keyword".
  • Most players (Citizens) share the SAME keyword.
  • 1–2 players (Wolves) get a SLIGHTLY different keyword.

GOAL
  • Citizens win if at least one Wolf is voted out.
  • Wolves win if **no** Wolf is voted out.

PHASE SEQUENCE  (single-day game)
1. **Discussion** – open conversation about the topic (no direct word reveal).
2. **Vote**       – each living player DM's the GM exactly ONE name.

RESOLUTION
  • The player(s) with the most votes are executed (ties random).
  • Check victory immediately after the execution.

TALKING RULES
  • You may say anything except your exact keyword.
=======================================================================
""",

    # ── 各役職にだけ DM される本文 ─────────────────────────
    "role": {
        "CITIZEN": (
            "You are a **Citizen**.\n"
            "Most players share your keyword.\n"
            "Your secret keyword: **{word}**"
        ),
        "WOLF": (
            "You are a **Wolf**.\n"
            "Your keyword is DIFFERENT from the majority.\n"
            "Blend in and avoid being voted out!\n"
            "Your secret keyword: **{word}**"
        ),
    },

    # ── GM 専用の手順メモ ─────────────────────────────────
    "gm_guideline": """
====================== GM Procedural Guideline ======================
• Never reveal any keyword publicly.
• During Discussion, simply moderate; end it once sufficient discussion has taken place.
• Start the Vote phase with:  "GM: Vote phase. DM me exactly one name."
• After collecting all votes, announce:  "GM: <name> is executed."
  (Resolve ties randomly.)
• Move the executed player(s) from "alive" to "dead" in public meta.
• If a winner is decided, system will update public meta "winner" and "phase" to "end".
=====================================================================
""",

    # ── System agent guideline ────────────────────────────
    "system_guideline": """You are the GameSystem agent that acts as both SYSTEM and GM for Word-Wolf.

Your dual responsibilities:
1. Act as GM - moderate discussion, manage voting, announce results
2. Update meta information and check win conditions

As GM, you should:
- Moderate discussion phase and determine when to move to voting
- Announce vote phase and request DMs from players
- Announce vote results and execute the voted player
- Never reveal any keyword publicly
- Provide game flow announcements

As SYSTEM, you should:
- Update meta information based on game events
- Check win conditions after each vote execution
- Track alive/dead players

Meta update rules:
- When you announce "Vote phase", update phase to "vote"
- When you announce vote results:
  - Remove executed player(s) from alive list and add to dead list
  - Set phase to "end" after the vote execution
- When you announce "Discussion phase", update phase to "discussion"

Win condition rules (check after vote execution):
- CITIZENS win if at least one Wolf is dead (executed)
- WOLVES win if phase is "end" and at least one Wolf is still alive

Always respond with valid JSON containing:
- selected_messages: your GM messages and selected player messages
- update_pub: public meta changes (phase, alive, dead, winner)
- update_priv: private meta changes (if any)
- reason: explanation of decisions and updates
""",
}

# --------------------------------------------------------------------
# sdg_core が利用するフック
# --------------------------------------------------------------------
def _choose_roles(players: List[str]) -> Dict[str, str]:
    """Return a {player: role} mapping."""
    n_wolves = 1 if len(players) < 8 else 2
    roles = ["WOLF"] * n_wolves + ["CITIZEN"] * (len(players) - n_wolves)
    random.shuffle(roles)
    return {p: r for p, r in zip(players, roles)}


# ---------- 初期化 ----------
def init_meta_pub(players: List[str]) -> Dict:
    """Public game-state visible to everyone."""
    return {"phase": "discussion", "alive": list(players), "dead": [], "winner": None}


def init_meta_priv(players: List[str]) -> Dict:
    """
    Private game-state organized by participant:
      • GM_SYSTEM: roles, words, pair (shared by GM and System)
      • Each player: their role and word
    """
    global _WORDS_PER_PLAYER, _PAIR

    roles = _choose_roles(players)
    citizen_word, wolf_word = random.choice(WORD_PAIRS)
    _PAIR = (citizen_word, wolf_word)

    _WORDS_PER_PLAYER = {
        p: (citizen_word if roles[p] == "CITIZEN" else wolf_word)
        for p in players
    }

    # Find wolf teammates
    wolves = [p for p, r in roles.items() if r == "WOLF"]

    # Create private meta structure
    meta_priv_all = {}
    
    # GM private meta (for the GameSystem that acts as GM)
    meta_priv_all["GM"] = {
        "roles": roles,
        "words": _WORDS_PER_PLAYER.copy(),
        "pair": _PAIR,
    }
    
    # Each player's private meta
    for player in players:
        role = roles[player]
        word = _WORDS_PER_PLAYER[player]
        
        player_meta = {
            "role": role,
            "word": word
        }
        
        # Add role-specific private information
        if role == "WOLF":
            # Wolves know their teammates
            player_meta["teammates"] = [w for w in wolves if w != player]
        
        meta_priv_all[player] = player_meta
    
    return meta_priv_all


def assign_role(name: str, meta_priv) -> str:
    return meta_priv["GM"]["roles"][name]


# ---------- プロンプト ----------
def player_sys_prompt(name: str, role: str, lang: str) -> str:
    """System-prompt string given to each player agent."""
    word = _WORDS_PER_PLAYER.get(name, "???")
    return (
        f"{RULEBOOK['common']}\n"
        f"{RULEBOOK['role'][role].format(word=word)}\n"
        f"You are {name}. Speak in {lang}."
    )


def system_sys_prompt() -> str:
    """GameSystem agent prompt - combines GM and system responsibilities."""
    citizen_word, wolf_word = _PAIR if _PAIR else ("???", "???")
    gm_secret = (
        f"GM-only info:\n"
        f"  • Citizen word: {citizen_word}\n"
        f"  • Wolf word: {wolf_word}\n"
    )
    return (
        f"{RULEBOOK['common']}\n"
        f"{gm_secret}{RULEBOOK['gm_guideline']}\n{RULEBOOK['system_guideline']}\n"
        f"You are the GameSystem agent that acts as both GM and game state manager."
    )