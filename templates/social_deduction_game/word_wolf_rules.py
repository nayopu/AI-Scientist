#!/usr/bin/env python3
"""
Word-Wolf (ワード人狼) rules for sdg_core v3
"""

import random
from typing import List, Dict, Tuple

# --------------------------------------------------------------------
# ★ 内部共有用のグローバル (init_meta_priv → *_sys_prompt で参照)
# --------------------------------------------------------------------
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
• During Discussion, simply moderate; end it once every living player
  has spoken or 5 public messages have passed – whichever comes first.
• Start the Vote phase with:  "GM: Vote phase. DM me exactly one name."
• After collecting all votes, announce:  "GM: <name> is executed."
  (Resolve ties randomly.)
• Move the executed player(s) from "alive" to "dead" in public meta.
• Then call check_end(). If a winner is decided, announce it and set
  public meta "phase" to "end".
=====================================================================
""",

    # ── System agent guideline ────────────────────────────
    "system_guideline": """You are the SYSTEM agent managing the game state for Word-Wolf.

Your responsibilities:
1. Update meta information based on game events
2. Check win conditions after each turn

Meta update rules:
- When GM announces "Vote phase", update phase to "vote"
- When GM announces vote results:
  - Remove executed player(s) from alive list and add to dead list
  - Set phase to "end" after the vote execution
- When GM announces "Discussion phase", update phase to "discussion"

Win condition rules (check after vote execution):
- CITIZENS win if at least one Wolf is dead (executed)
- WOLVES win if phase is "end" and at least one Wolf is still alive

Always respond with valid JSON containing:
- update_pub: public meta changes (phase, alive, dead)
- update_priv: private meta changes (if any)
- winner: null or "CITIZENS" or "WOLVES"
- reason: explanation of updates/win
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
    return {"phase": "discussion", "alive": list(players), "dead": []}


def init_meta_priv(players: List[str]) -> Dict:
    """
    Private game-state (GM only):
      • roles {player: role}
      • words {player: keyword}
      • pair  (citizen_word, wolf_word)
    """
    global _WORDS_PER_PLAYER, _PAIR

    roles = _choose_roles(players)
    citizen_word, wolf_word = random.choice(WORD_PAIRS)
    _PAIR = (citizen_word, wolf_word)

    _WORDS_PER_PLAYER = {
        p: (citizen_word if roles[p] == "CITIZEN" else wolf_word)
        for p in players
    }

    return {
        "roles": roles,
        "words": _WORDS_PER_PLAYER.copy(),
        "pair": _PAIR,
    }


def assign_role(name: str, meta_priv) -> str:
    return meta_priv["roles"][name]


# ---------- プロンプト ----------
def player_sys_prompt(name: str, role: str, lang: str) -> str:
    """System-prompt string given to each player agent."""
    word = _WORDS_PER_PLAYER.get(name, "???")
    return (
        f"{RULEBOOK['common']}\n"
        f"{RULEBOOK['role'][role].format(word=word)}\n"
        f"You are {name}. Speak in {lang}."
    )


def gm_sys_prompt(lang: str) -> str:
    citizen_word, wolf_word = _PAIR if _PAIR else ("???", "???")
    gm_secret = (
        f"GM-only info:\n"
        f"  • Citizen word: {citizen_word}\n"
        f"  • Wolf word: {wolf_word}\n"
    )
    return (
        f"{RULEBOOK['common']}\n"
        f"{gm_secret}{RULEBOOK['gm_guideline']}\n"
        f"You are the GM. Speak in {lang}."
    )


def system_sys_prompt() -> str:
    """System agent prompt for handling meta updates and win condition checks."""
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the game system agent managing the game state.")