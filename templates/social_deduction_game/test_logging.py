"""
Test New Logging System rules for sdg_core v3
Generated from idea: Testing the new immediate logging system

IMPLEMENTATION GUIDE:
This template provides a comprehensive framework for implementing social deduction games.
Study the examples in sample_rules/ (werewolf.py, resistance_avalon.py, spyfall.py, insider.py)
to understand the full complexity possible within this structure.

Key implementation patterns:
1. RULEBOOK: Contains 4 sections (common, role, gm_guideline, system_guideline)
2. init_meta_pub: Simple public game state
3. init_meta_priv: Complex private state with role assignments and faction knowledge
4. Prompt functions: Combine rulebook sections with dynamic content
"""
import json, random
from typing import List, Dict, Any

###############################################################################
# Rule book for Test New Logging System
# 
# STRUCTURE EXPLANATION:
# The RULEBOOK dictionary is the core of any social deduction game implementation.
# It contains four critical sections that work together to create the game experience:
#
# 1. "common" - Public rules visible to ALL players
#    Contains: Victory conditions, role descriptions, phase sequence, game mechanics
#    Example pattern: "FACTION wins when CONDITION" (see werewolf.py lines 19-21)
#
# 2. "role" - Private role descriptions sent to individual players
#    Contains: Role-specific abilities, faction knowledge, special instructions
#    Can use placeholders like {location} for dynamic content (see spyfall.py lines 58-62)
#
# 3. "gm_guideline" - Instructions for the GM agent
#    Contains: Phase announcements, rule enforcement, special ability handling
#    Critical for consistent game flow and rule adherence
#
# 4. "system_guideline" - Instructions for the system agent
#    Contains: Meta update rules, win condition checks, JSON response format
#    Handles automatic game state management and victory detection
###############################################################################
RULEBOOK = {
    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLIC RULEBOOK - Visible to ALL players
    # ═══════════════════════════════════════════════════════════════════════════
    # 
    # IMPLEMENTATION NOTES:
    # - Start with clear victory conditions for each faction
    # - List all possible roles with brief descriptions
    # - Define the phase sequence (Discussion → Vote → Special phases)
    # - Include any special mechanics (team sizes, voting rules, etc.)
    # 
    # EXAMPLES FROM EXISTING GAMES:
    # - Werewolf: "Villagers win when every Werewolf is dead"
    # - Avalon: "GOOD wins after 3 successful missions"
    # - Spyfall: "Locals win if they identify the Spy"
    # - Insider: "Guess the secret word, then find the Insider"
    "common": """
===================== Test New Logging System – Public Rulebook =====================
VICTORY CONDITIONS
  • [FACTION 1] wins when [SPECIFIC CONDITION]
  • [FACTION 2] wins when [SPECIFIC CONDITION]
  • [Additional win conditions if any]

POSSIBLE ROLES
• **[ROLE 1]** – [Brief description of abilities and faction]
• **[ROLE 2]** – [Brief description of abilities and faction]
• **[ROLE 3]** – [Brief description of abilities and faction]
[Add more roles as needed for your game concept]

PHASE SEQUENCE
1. **Discussion** – Open conversation and information gathering
2. **Vote** – Players secretly submit votes to GM
3. **[Special Phase]** – Role-specific actions and abilities
[Modify phases based on your game mechanics]

RESOLUTION RULES
• Vote: [How votes are resolved - majority, elimination, etc.]
• [Special Phase]: [How special abilities are resolved]
• [Additional mechanics specific to your game]

TURN RHYTHM
Discussion → Vote → [Special Phase] → next Discussion …
[Modify the flow based on your game's needs]

SPECIAL RULES
[Any unique mechanics, restrictions, or special cases for your game]
======================================================================
""",

    # ═══════════════════════════════════════════════════════════════════════════
    # ROLE DESCRIPTIONS - Private information for each role
    # ═══════════════════════════════════════════════════════════════════════════
    #
    # IMPLEMENTATION NOTES:
    # - Each role gets sent only their specific description
    # - Include faction alignment and special abilities
    # - Use placeholders {variable} for dynamic content (like locations, teammates)
    # - Keep descriptions focused on what the player CAN do
    #
    # EXAMPLES FROM EXISTING GAMES:
    # - Werewolf roles have faction knowledge: "You and fellow Wolves must agree"
    # - Avalon roles have information asymmetry: "You secretly know every EVIL"
    # - Spyfall uses placeholders: "You know the secret location: **{location}**"
    "role": {
        "[ROLE_1]": "You are a **[Role 1]**. [Detailed description of abilities, faction, and strategy]",
        "[ROLE_2]": "You are a **[Role 2]**. [Detailed description of abilities, faction, and strategy]",
        "[ROLE_3]": "You are a **[Role 3]**. [Detailed description of abilities, faction, and strategy]",
        # Add more roles as needed
        
        # ROLE IMPLEMENTATION EXAMPLES:
        # Basic role: "You are a **Villager**. You have NO special power."
        # Faction role: "You are a **Werewolf**. During Night you and fellow Wolves must agree on one victim."
        # Information role: "You are a **Seer**. Each Night, you may investigate one player."
        # Dynamic content: "You are a **Local**. You know the secret location: **{location}**."
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # GM PROCEDURAL GUIDELINE - Instructions for the GM agent
    # ═══════════════════════════════════════════════════════════════════════════
    #
    # IMPLEMENTATION NOTES:
    # - Provide exact phrase examples for consistency
    # - Cover all phase transitions and announcements
    # - Include rule enforcement guidelines
    # - Handle special abilities and edge cases
    # - Always prefix with "GM:" for clarity
    #
    # CRITICAL PATTERNS:
    # - Phase announcements: "GM: [Phase] phase begins. [Instructions]"
    # - Vote collection: "GM: Vote phase. DM me exactly one name."
    # - Results: "GM: [Player] is [action]. [Outcome]"
    # - Special abilities: "GM: [Role], DM me your [ability] target."
    "gm_guideline": """
====================== GM Procedural Guideline ======================
Always speak to players in plain English and prefix with "GM:".

PHASE ANNOUNCEMENTS (Use these exact phrases for consistency)
• Start Discussion:  "GM: Discussion phase begins. Feel free to talk."
• Start Vote:        "GM: Vote phase. DM me exactly one name."
• Vote result:       "GM: [Player] is [voted out/eliminated]. [Additional info]"
• Start [Special]:   "GM: [Special phase] begins. [Role-specific instructions]"
• [Special] result:  "GM: [Outcome of special phase actions]"

ROLE-SPECIFIC HANDLING
• [Role 1]: [Specific instructions for handling this role's abilities]
• [Role 2]: [Specific instructions for handling this role's abilities]
• [Role 3]: [Specific instructions for handling this role's abilities]

WHEN TO END PHASES
• Discussion: End when [specific condition - time limit, sufficient talk, etc.]
• Vote: End when all living players have voted
• [Special]: End when [specific conditions for your game]

RULE ENFORCEMENT GUIDELINES
• Invalid votes: "GM: Please vote by sending me DM with exactly one player name."
• Multiple votes: "GM: You may only vote once per vote phase."
• Public votes: "GM: Please DM your vote to me instead of posting it publicly."
• Wrong phase actions: "GM: [Ability] can only be used during [correct phase]."
• [Add more enforcement rules specific to your game]

SPECIAL SITUATIONS
[Handle any unique situations, tie-breaking, simultaneous actions, etc.]

EXAMPLES FROM EXISTING GAMES:
Werewolf GM: "GM: Night phase. Werewolves, DM me one victim, and special roles, DM me your actions."
Avalon GM: "GM: Leader Alice, propose a team of 3 players."
Spyfall GM: "GM: Vote phase – DM me one suspect."
Insider GM: "GM: Question phase begins – ask yes/no questions."
=====================================================================
""",

    # ═══════════════════════════════════════════════════════════════════════════
    # SYSTEM AGENT GUIDELINE - Instructions for automatic game state management
    # ═══════════════════════════════════════════════════════════════════════════
    #
    # IMPLEMENTATION NOTES:
    # - Define all public and private meta variables
    # - Specify exact update triggers (GM phrases, game events)
    # - Include comprehensive win condition logic
    # - Always respond with valid JSON format
    # - Handle edge cases and error states
    #
    # CRITICAL COMPONENTS:
    # 1. Meta variable definitions
    # 2. Update trigger rules
    # 3. Win condition checks
    # 4. JSON response format
    "system_guideline": """You are the SYSTEM agent managing the game state for Test New Logging System.

Your responsibilities:
1. Update meta information based on game events
2. Check win conditions after each turn
3. Maintain game state consistency

PUBLIC META VARIABLES (visible to all players):
- phase: Current game phase ["discussion", "vote", "[special_phase]", "end"]
- alive: List of living players
- dead: List of eliminated players
- [game_specific_vars]: [Additional public state variables for your game]

PRIVATE META VARIABLES (GM_SYSTEM section):
- roles: Player role assignments {player: role}
- [game_specific_state]: [Additional private state for your game]

META UPDATE RULES (trigger → action):
• GM announces "Discussion phase" → phase = "discussion"
• GM announces "Vote phase" → phase = "vote"  
• GM announces "[Player] is eliminated" → move player from alive to dead
• GM announces "[Special phase]" → phase = "[special_phase]"
• [Add specific update rules for your game mechanics]

WIN CONDITION RULES:
• [FACTION 1] wins when: [Specific conditions to check]
• [FACTION 2] wins when: [Specific conditions to check]
• [Additional win conditions and edge cases]

EXAMPLES FROM EXISTING GAMES:
Werewolf: "VILLAGERS win when ALL Werewolves are dead"
Avalon: "GOOD wins if score.success == 3 AND Assassin guessed wrong"
Spyfall: "SPY wins if spy_guess matches secret location"
Insider: "COMMONS win if roles[accused] == 'INSIDER'"

Always respond with valid JSON containing:
- update_pub: public meta changes ({key: new_value})
- update_priv: private meta changes ({section: {key: new_value}})
- winner: null or "[FACTION_NAME]" or "NONE"
- reason: explanation of updates/win condition

JSON RESPONSE EXAMPLE:
{
  "update_pub": {"phase": "vote", "current_round": 2},
  "update_priv": {"GM_SYSTEM": {"special_action_used": true}},
  "winner": null,
  "reason": "Moved to vote phase, tracking special action usage"
}
"""
}

# ═════════════════════════════════════════════════════════════════════════════════
# INITIALIZATION FUNCTIONS
# These functions set up the initial game state when a new game begins
# ═════════════════════════════════════════════════════════════════════════════════

def init_meta_pub(players: List[str]) -> Dict:
    """
    Initialize public game metadata visible to all players.
    
    IMPLEMENTATION GUIDE:
    - Keep this simple and focused on information all players should see
    - Common patterns: phase tracking, player lists, score counters
    - Avoid revealing private information (roles, hidden state)
    
    EXAMPLES FROM EXISTING GAMES:
    
    Werewolf (simple):
    return {"phase": "discussion", "alive": list(players), "dead": []}
    
    Avalon (complex with mission tracking):
    return {
        "phase": "proposal",
        "leader": players[0], 
        "mission_number": 1,
        "score": {"success": 0, "fail": 0},
        "mission_results": [None, None, None, None, None]
    }
    
    Spyfall (minimal):
    return {"phase": "discussion", "alive": list(players)}
    
    Insider (with game-specific state):
    return {"phase": "question", "word_guessed": False, "accused": None}
    """
    return {
        "phase": "discussion",  # Starting phase
        "alive": list(players),  # All players start alive
        "dead": [],  # No one eliminated yet
        # Add your game-specific public state variables here:
        # "round": 1,
        # "score": {"team1": 0, "team2": 0},
        # "special_events": [],
        # etc.
    }

def init_meta_priv(players: List[str]) -> Dict:
    """
    Initialize private game metadata organized by participant.
    
    IMPLEMENTATION GUIDE:
    - Create "GM_SYSTEM" section for global private state
    - Create individual player sections for role-specific private info
    - Handle role assignment logic based on player count
    - Set up faction knowledge and teammate information
    
    ROLE ASSIGNMENT PATTERNS:
    
    Simple (Spyfall - one spy):
    spy = random.choice(players)
    role_assignments = {p: ("SPY" if p == spy else "LOCAL") for p in players}
    
    Balanced factions (Werewolf - scales with player count):
    if num_players < 5:
        roles = ["WEREWOLF"] + ["VILLAGER"]*(num_players-1)
    elif num_players < 8:
        roles = ["WEREWOLF"]*2 + ["SEER", "DOCTOR"] + ["VILLAGER"]*(num_players-4)
    else:
        roles = ["WEREWOLF"]*3 + ["SEER", "DOCTOR", "HUNTER", "WITCH"] + ["VILLAGER"]*(num_players-7)
    
    Complex distribution (Avalon - role-specific logic):
    num_evil = 2 if num_players < 7 else 3 if num_players < 10 else 4
    roles = ["ASSASSIN"] + ["MERLIN", "PERCIVAL"] + ["LOYAL"]*(num_players-3)
    
    FACTION KNOWLEDGE EXAMPLES:
    
    Werewolf teammates:
    werewolves = [p for p, r in role_assignments.items() if r == "WEREWOLF"]
    if role == "WEREWOLF":
        player_meta["teammates"] = [w for w in werewolves if w != player]
    
    Avalon evil coordination:
    evil_players = [p for p, r in role_assignments.items() if r in ["ASSASSIN", "MORGANA"]]
    if role in ["ASSASSIN", "MORGANA"]:
        player_meta["teammates"] = [e for e in evil_players if e != player]
        
    Special information (Avalon Merlin):
    if role == "MERLIN":
        evil_visible = [p for p, r in role_assignments.items() if r in ["ASSASSIN", "MORGANA"]]
        player_meta["evil_players"] = evil_visible
    """
    num_players = len(players)
    
    # ─────────────────────────────────────────────────────────────────────────
    # ROLE ASSIGNMENT LOGIC
    # Customize this section based on your game's role distribution
    # ─────────────────────────────────────────────────────────────────────────
    
    # Example role assignment (customize for your game):
    if num_players < 5:
        # Small game setup
        roles_list = ["[ROLE_1]"] + ["[ROLE_2]"] * (num_players - 1)
    elif num_players < 8:
        # Medium game setup  
        roles_list = ["[ROLE_1]"] * 2 + ["[ROLE_2]", "[ROLE_3]"] + ["[ROLE_4]"] * (num_players - 4)
    else:
        # Large game setup
        roles_list = ["[ROLE_1]"] * 3 + ["[ROLE_2]", "[ROLE_3]", "[ROLE_4]", "[ROLE_5]"] + ["[ROLE_6]"] * (num_players - 7)
    
    random.shuffle(roles_list)
    role_assignments = {p: r for p, r in zip(players, roles_list)}
    
    # ─────────────────────────────────────────────────────────────────────────
    # FACTION/TEAM ORGANIZATION
    # Set up teammate relationships and faction knowledge
    # ─────────────────────────────────────────────────────────────────────────
    
    # Example faction setup (customize for your game):
    faction_1_players = [p for p, r in role_assignments.items() if r in ["[ROLE_1]", "[ROLE_2]"]]
    faction_2_players = [p for p, r in role_assignments.items() if r in ["[ROLE_3]", "[ROLE_4]"]]
    
    # ─────────────────────────────────────────────────────────────────────────
    # PRIVATE META STRUCTURE
    # ─────────────────────────────────────────────────────────────────────────
    
    meta_priv_all = {}
    
    # GM_SYSTEM private meta (shared by GM and System)
    meta_priv_all["GM_SYSTEM"] = {
        "roles": role_assignments,
        # Add your game-specific private state here:
        # "special_abilities_used": {},
        # "secret_information": "...",
        # "round_history": [],
        # etc.
    }
    
    # Each player's private meta
    for player in players:
        role = role_assignments[player]
        player_meta = {
            "role": role
        }
        
        # Add role-specific private information
        if role == "[ROLE_1]":
            # Example: Faction member who knows teammates
            teammates = [p for p in faction_1_players if p != player]
            player_meta["teammates"] = teammates
            # player_meta["special_ability"] = "..."
            
        elif role == "[ROLE_2]":
            # Example: Information role with special knowledge
            # player_meta["known_information"] = [...]
            # player_meta["ability_uses"] = 3
            pass
            
        elif role == "[ROLE_3]":
            # Example: Solo role with unique mechanics
            # player_meta["secret_target"] = "..."
            pass
            
        # Add more role-specific logic as needed
        
        meta_priv_all[player] = player_meta
    
    return meta_priv_all

def assign_role(name: str, meta_priv: Dict) -> str:
    """
    Lookup a player's role from the private metadata.
    
    IMPLEMENTATION GUIDE:
    - This is a simple lookup function used by the game engine
    - Always returns meta_priv["GM_SYSTEM"]["roles"][name]
    - No customization needed unless you have a very unusual role system
    
    EXAMPLES FROM ALL GAMES:
    return meta_priv["GM_SYSTEM"]["roles"][name]
    
    This function is consistent across all implementations.
    """
    return meta_priv["GM_SYSTEM"]["roles"][name]

# ═════════════════════════════════════════════════════════════════════════════════
# PROMPT CONSTRUCTION FUNCTIONS
# These functions build the system prompts sent to AI agents (players, GM, system)
# ═════════════════════════════════════════════════════════════════════════════════

def player_sys_prompt(name: str, role: str, lang: str) -> str:
    """
    Construct system prompt for player agents.
    
    IMPLEMENTATION GUIDE:
    - Combines public rules + role-specific info + player identity
    - Use dynamic content replacement for placeholders
    - Language parameter allows internationalization
    
    EXAMPLES FROM EXISTING GAMES:
    
    Basic (Werewolf):
    return (f"{RULEBOOK['common']}\n{RULEBOOK['role'][role]}\n"
            f"You are {name}. Speak in {lang}.")
            
    Dynamic content (Spyfall):
    if role == "SPY":
        role_text = RULEBOOK["role"]["SPY"]
    else:
        role_text = RULEBOOK["role"]["LOCAL"].format(location=CURRENT_LOCATION)
    return f"{RULEBOOK['common']}\n{role_text}\nYou are {name}. Speak in {lang}."
    
    Complex private info (Avalon with teammates):
    private_info = meta_priv[name]
    role_text = RULEBOOK["role"][role]
    if "teammates" in private_info:
        role_text += f"\nYour teammates are: {', '.join(private_info['teammates'])}"
    return f"{RULEBOOK['common']}\n{role_text}\nYou are {name}. Speak in {lang}."
    """
    role_prompt = RULEBOOK['role'].get(role, RULEBOOK['role'].get('[DEFAULT_ROLE]', 'You are a player.'))
    
    # Add dynamic content replacement here if needed:
    # role_prompt = role_prompt.format(location=CURRENT_LOCATION, teammates=...)
    
    return (f"{RULEBOOK['common']}\n{role_prompt}\n"
            f"You are {name}. Speak in {lang}.")

def gm_sys_prompt(lang: str) -> str:
    """
    Construct system prompt for GM agent.
    
    IMPLEMENTATION GUIDE:
    - Combines public rules + GM guidelines + any secret information
    - GM needs access to private game state for proper moderation
    - Language parameter for consistent communication
    
    EXAMPLES FROM EXISTING GAMES:
    
    Basic (Werewolf, Avalon, Insider):
    return (f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n"
            f"You are the GM. Speak in {lang}.")
            
    With secret info (Spyfall):
    return (f"{RULEBOOK['common']}\nSecret location = {CURRENT_LOCATION}\n"
            f"{RULEBOOK['gm_guideline']}\nYou are the GM. Speak in {lang}.")
    """
    return (f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n"
            f"You are the GM. Speak in {lang}.")

def system_sys_prompt() -> str:
    """
    Construct system prompt for the system agent.
    
    IMPLEMENTATION GUIDE:
    - Provides instructions for automatic game state management
    - Handles meta updates and win condition checking
    - Returns JSON responses for game engine integration
    
    EXAMPLES FROM ALL GAMES:
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the game system agent managing the game state.")
    
    This function is consistent across all implementations.
    """
    return (f"{RULEBOOK['common']}\n{RULEBOOK['system_guideline']}\n"
            f"You are the game system agent managing the game state.")

# ═════════════════════════════════════════════════════════════════════════════════
# ADDITIONAL HELPER FUNCTIONS (if needed)
# Add any game-specific helper functions here
# ═════════════════════════════════════════════════════════════════════════════════

# Example helper functions you might need:
# def calculate_team_size(mission_number: int, num_players: int) -> int:
#     """Calculate team size for mission games like Avalon"""
#     pass
#
# def check_special_ability_valid(player: str, ability: str, meta_priv: Dict) -> bool:
#     """Validate special ability usage"""
#     pass
#
# def update_game_specific_state(action: str, meta_priv: Dict) -> Dict:
#     """Handle complex state transitions"""
#     pass
