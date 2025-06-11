import json
import random
from typing import Dict, List, Any

# Initial rule file - this will be iteratively improved based on experimental results

RULEBOOK = {
    "common": """
    BASIC SOCIAL DEDUCTION GAME RULES
    
    This is a social deduction game for 3-8 players where some players are secretly assigned as "Infiltrators" 
    while others are "Citizens". The goal is for each faction to eliminate the opposing faction.
    
    ROLES:
    - Citizens: The majority faction. They win by eliminating all Infiltrators.
    - Infiltrators: The minority faction. They win by eliminating enough Citizens to equal their numbers.
    
    GAME PHASES:
    1. Discussion Phase: All players discuss and share information to identify Infiltrators
    2. Vote Phase: Players vote to eliminate someone they suspect
    3. Resolution: The voted player is eliminated and the game checks for win conditions
    
    VICTORY CONDITIONS:
    - Citizens win if all Infiltrators are eliminated
    - Infiltrators win if they equal or outnumber the Citizens
    
    SPECIAL RULES:
    - Players cannot reveal their roles directly
    - All communication is public except for role assignments
    - Eliminated players cannot participate further
    """,
    
    "role": {
        "CITIZEN": "You are a loyal CITIZEN. Your goal is to identify and eliminate all Infiltrators through discussion and voting. You have no special abilities, but you can observe behavior and voting patterns to deduce who might be an Infiltrator.",
        
        "INFILTRATOR": "You are an INFILTRATOR working to overthrow the Citizens. Your goal is to eliminate enough Citizens so that Infiltrators equal or outnumber them. You must blend in during discussions while secretly working against the Citizens. You know who your fellow Infiltrators are."
    },
    
    "gm_guideline": """
    As the Game Master, your responsibilities include:
    
    1. PHASE MANAGEMENT:
    - Announce the start of Discussion Phase
    - Moderate discussion and determine when to move to voting
    - Announce Vote Phase and collect votes via DMs
    - Announce vote results and eliminate the chosen player
    
    2. INFORMATION MANAGEMENT:
    - Track which players are alive/eliminated
    - Monitor vote counts and announce results
    - Check win conditions after each elimination
    - Maintain game state and phase tracking
    
    3. COMMUNICATION:
    - Send role information to players via DM at game start
    - Provide Infiltrators with teammate information via DM
    - Announce phase changes and eliminations publicly
    - Declare the winner when conditions are met
    """,
    
    "system_guideline": """
    You are the GameSystem agent that acts as both GM and game state manager.
    
    Your dual responsibilities:
    1. Act as GM - communicate with players, manage phases, announce results
    2. Update meta information and check win conditions
    
    RESPONSE FORMAT:
    Always respond with valid JSON containing:
    - selected_messages: array of messages to send (GM announcements and selected player messages)
    - update_pub: public meta changes (phase, alive, dead, winner)
    - update_priv: private meta changes (if any)
    - reason: explanation of decisions and updates
    
    META UPDATE RULES:
    - When announcing "Vote phase", update phase to "vote"
    - When announcing vote results, remove eliminated player from alive list, add to dead list
    - When announcing "Discussion phase", update phase to "discussion"
    - Set winner when win conditions are met
    
    WIN CONDITION CHECKING:
    - CITIZENS win when all Infiltrators are eliminated
    - INFILTRATORS win when they equal or outnumber Citizens among living players
    """
}

def init_meta_pub(players: List[str]) -> Dict:
    """Initialize public game state"""
    return {
        "phase": "discussion",
        "alive": list(players),
        "dead": [],
        "winner": None
    }

def init_meta_priv(players: List[str]) -> Dict:
    """Initialize private game state with role assignments"""
    # Determine role distribution based on player count
    num_players = len(players)
    if num_players <= 4:
        num_infiltrators = 1
    elif num_players <= 7:
        num_infiltrators = 2
    else:
        num_infiltrators = 3
    
    # Assign roles randomly
    shuffled_players = players.copy()
    random.shuffle(shuffled_players)
    
    infiltrators = shuffled_players[:num_infiltrators]
    citizens = shuffled_players[num_infiltrators:]
    
    roles = {}
    for player in infiltrators:
        roles[player] = "INFILTRATOR"
    for player in citizens:
        roles[player] = "CITIZEN"
    
    # Create private meta structure
    meta_priv_all = {}
    
    # GM private meta
    meta_priv_all["GM"] = {
        "roles": roles,
        "infiltrators": infiltrators,
        "citizens": citizens,
    }
    
    # Each player's private meta
    for player in players:
        role = roles[player]
        player_meta = {
            "role": role
        }
        
        # Infiltrators know their teammates
        if role == "INFILTRATOR":
            player_meta["teammates"] = [p for p in infiltrators if p != player]
        
        meta_priv_all[player] = player_meta
    
    return meta_priv_all

def assign_role(name: str, meta_priv: Dict) -> str:
    """Get role assignment for a player"""
    return meta_priv.get(name, {}).get("role", "CITIZEN")

def player_sys_prompt(name: str, role: str, lang: str = "en") -> str:
    """Generate system prompt for a player"""
    return f"{RULEBOOK['common']}\n\nYour role: {RULEBOOK['role'][role]}\n\nYou are {name}."

def system_sys_prompt() -> str:
    """GameSystem agent prompt - combines GM and system responsibilities"""
    return f"{RULEBOOK['common']}\n{RULEBOOK['gm_guideline']}\n{RULEBOOK['system_guideline']}" 