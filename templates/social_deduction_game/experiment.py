import argparse
import json
import os
import sys
import time
import subprocess
import asyncio
import tempfile
import shutil
from pathlib import Path
import importlib.util
import re
from typing import Dict, List, Any

# Add your experiment-specific imports here
import numpy as np

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", type=str, required=True)
    parser.add_argument("--idea", type=str, help="JSON string of the idea to implement")
    parser.add_argument("--baseline_game", type=str, default="werewolf", 
                        help="Baseline game to compare against")
    return parser.parse_args()

def generate_rule_file(idea: Dict[str, Any], output_path: str) -> bool:
    """
    Generate a Python rule file from the game idea using LLM.
    """
    # This would typically use an LLM to convert the idea into a rule file
    # For now, we'll create a template structure
    
    game_name = idea.get("Name", "custom_game")
    title = idea.get("Title", "Custom Social Deduction Game")
    description = idea.get("Experiment", "A new social deduction game")
    
    # Read werewolf.py as a template to understand the structure
    werewolf_path = Path(__file__).parent / "sample_rules" / "werewolf.py"
    with open(werewolf_path, 'r') as f:
        werewolf_content = f.read()
    
    # Create a basic template - in a real implementation, this would use LLM
    # to generate the actual game rules based on the idea
    rule_template = f'''"""
{title} rules for sdg_core v3
Generated from idea: {description}
"""
import json, random
from typing import List, Dict
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers.json import SimpleJsonOutputParser

###############################################################################
# Rule book for {title}
###############################################################################
RULEBOOK = {{
    # Public to everyone
    "common": """
===================== {title} – Public Rulebook =====================
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
    "role": {{
        "PLAYER": "You are a player in {title}. [Role details to be implemented]",
    }},

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
    "system_guideline": """You are the SYSTEM agent managing the game state for {title}.

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
}}

# ---------- Initialization ----------
def init_meta_pub(players: List[str]):
    return {{"phase": "discussion",
            "alive": list(players),
            "dead": []}}

def init_meta_priv(players: List[str]):
    # Basic role assignment - to be customized per game
    num_players = len(players)
    roles_list = ["PLAYER"] * num_players  # Placeholder
    random.shuffle(roles_list)
    role_assignments = {{p: r for p, r in zip(players, roles_list)}}
    
    # Create private meta structure
    meta_priv_all = {{}}
    
    # GM_SYSTEM private meta (shared by GM and System)
    meta_priv_all["GM_SYSTEM"] = {{
        "roles": role_assignments,
        # Add game-specific private state here
    }}
    
    # Each player's private meta
    for player in players:
        role = role_assignments[player]
        player_meta = {{
            "role": role
            # Add role-specific private information here
        }}
        
        meta_priv_all[player] = player_meta
    
    return meta_priv_all

def assign_role(name: str, meta_priv) -> str:
    return meta_priv["GM_SYSTEM"]["roles"][name]

# ---------- Prompts ----------
def player_sys_prompt(name: str, role: str, lang: str) -> str:
    role_prompt = RULEBOOK['role'].get(role, RULEBOOK['role'].get('PLAYER', 'You are a player.'))
    return (f"{{RULEBOOK['common']}}\\n{{role_prompt}}\\n"
            f"You are {{name}}. Speak in {{lang}}.")

def gm_sys_prompt(lang: str) -> str:
    return (f"{{RULEBOOK['common']}}\\n{{RULEBOOK['gm_guideline']}}\\n"
            f"You are the GM. Speak in {{lang}}.")

def system_sys_prompt() -> str:
    return (f"{{RULEBOOK['common']}}\\n{{RULEBOOK['system_guideline']}}\\n"
            f"You are the game system agent managing the game state.")
'''
    
    with open(output_path, 'w') as f:
        f.write(rule_template)
    
    return True

def run_game_simulation(rule_module: str, num_players: int = 5, 
                       api: str = "openai", model: str = "gpt-4o-mini", 
                       max_turns: int = 50) -> Dict:
    """
    Run a game simulation and capture the results.
    """
    try:
        # Create a temporary output file for the game log
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            log_file = f.name
        
        # Run the game simulation
        cmd = [
            sys.executable, 
            str(Path(__file__).parent / "sdg_core.py"),
            "--rules", rule_module,  # Just the module name
            "--players", str(num_players),
            "--api", api,
            "--model", model,
            "--out", log_file
        ]
        
        print(f"Running command: {' '.join(cmd)}")
        
        # Run with timeout to prevent hanging
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300,  # 5 minute timeout
            cwd=str(Path(__file__).parent)
        )
        
        if result.returncode != 0:
            print(f"Game failed with error: {result.stderr}")
            return {"success": False, "error": result.stderr, "dialogue": []}
        
        # Load the game log
        try:
            with open(log_file, 'r') as f:
                game_log = json.load(f)
        except:
            game_log = []
        
        # Clean up
        os.unlink(log_file)
        
        # Extract dialogue and game metrics
        dialogue = []
        game_completed = False
        winner = None
        turn_count = 0
        
        for entry in game_log:
            if entry.get("phase") == "message":
                dialogue.append({
                    "turn": entry.get("turn", 0),
                    "speaker": entry.get("speaker", ""),
                    "message": entry.get("msg", ""),
                    "is_dm": entry.get("is_dm", False)
                })
                turn_count = max(turn_count, entry.get("turn", 0))
            elif entry.get("phase") == "end":
                game_completed = True
                winner = entry.get("winner")
        
        return {
            "success": True,
            "game_completed": game_completed,
            "winner": winner,
            "turn_count": turn_count,
            "dialogue": dialogue,
            "total_messages": len(dialogue)
        }
        
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Game timed out", "dialogue": []}
    except Exception as e:
        return {"success": False, "error": str(e), "dialogue": []}

def evaluate_game_quality(new_game_results: Dict, baseline_results: Dict) -> Dict:
    """
    Evaluate the quality of the new game compared to baseline.
    This is a simplified version - in practice, you'd use an LLM to analyze dialogue quality.
    """
    
    metrics = {}
    
    # Basic completion metrics
    metrics["completion_rate"] = 1.0 if new_game_results.get("game_completed", False) else 0.0
    baseline_completion = 1.0 if baseline_results.get("game_completed", False) else 0.0
    
    # Turn count comparison (games that are too short or too long might be less engaging)
    new_turns = new_game_results.get("turn_count", 0)
    baseline_turns = baseline_results.get("turn_count", 10)
    
    # Ideal turn count is similar to baseline (around 10-30 turns typically)
    if baseline_turns > 0:
        turn_ratio = new_turns / baseline_turns
        # Score higher for games with reasonable length (0.5x to 2x baseline)
        if 0.5 <= turn_ratio <= 2.0:
            metrics["turn_quality"] = 1.0 - abs(1.0 - turn_ratio)
        else:
            metrics["turn_quality"] = 0.0
    else:
        metrics["turn_quality"] = 0.5
    
    # Message engagement (more messages per turn might indicate more engagement)
    new_msg_count = new_game_results.get("total_messages", 0)
    baseline_msg_count = baseline_results.get("total_messages", 1)
    
    if new_turns > 0 and baseline_turns > 0:
        new_msg_per_turn = new_msg_count / new_turns
        baseline_msg_per_turn = baseline_msg_count / baseline_turns
        
        if baseline_msg_per_turn > 0:
            msg_ratio = new_msg_per_turn / baseline_msg_per_turn
            metrics["engagement"] = min(1.0, msg_ratio)  # Cap at 1.0
        else:
            metrics["engagement"] = 0.5
    else:
        metrics["engagement"] = 0.0
    
    # Overall score (weighted combination)
    weights = {"completion_rate": 0.4, "turn_quality": 0.3, "engagement": 0.3}
    metrics["overall_score"] = sum(metrics[k] * weights[k] for k in weights.keys())
    
    # Determine if new game is better
    baseline_score = baseline_completion * 0.4 + 0.3 + 0.3  # Assume baseline has good turn quality and engagement
    metrics["beats_baseline"] = metrics["overall_score"] > baseline_score
    
    return metrics

def run_experiment():
    """
    Main experiment function for social deduction game testing.
    """
    args = parse_args()
    
    # Parse the idea if provided
    idea = None
    if args.idea:
        try:
            idea = json.loads(args.idea)
        except json.JSONDecodeError:
            print("Failed to parse idea JSON")
            return {"error": "Invalid idea format"}
    
    if not idea:
        # Default test idea
        idea = {
            "Name": "test_game",
            "Title": "Test Social Deduction Game",
            "Experiment": "A simple test game for validation"
        }
    
    print(f"Testing idea: {idea['Name']}")
    
    # Generate rule file
    rule_file_name = f"{idea['Name']}"
    rule_file_path = Path(__file__).parent / f"{rule_file_name}.py"
    rule_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    success = generate_rule_file(idea, str(rule_file_path))
    if not success:
        return {"error": "Failed to generate rule file"}
    
    # Test the new game
    print("Running new game simulation...")
    new_game_results = run_game_simulation(rule_file_name)  # Pass just the module name
    
    if not new_game_results["success"]:
        print(f"New game failed: {new_game_results.get('error', 'Unknown error')}")
        # Try to improve the rule file iteratively
        # This is where you'd use LLM to fix issues based on error messages
        return {"error": f"Game simulation failed: {new_game_results.get('error', '')}"}
    
    # Run baseline game for comparison
    print("Running baseline game simulation...")
    baseline_rule_module = f"sample_rules.{args.baseline_game}"
    baseline_results = run_game_simulation(baseline_rule_module)
    
    if not baseline_results["success"]:
        print("Warning: Baseline game failed, loading from file...")
        # Try to load from baseline file
        baseline_file = Path(__file__).parent / "run_0" / "baseline_game_results.json"
        if baseline_file.exists():
            with open(baseline_file, 'r') as f:
                baseline_results = json.load(f)
        else:
            baseline_results = {
                "success": True,
                "game_completed": True,
                "turn_count": 15,
                "total_messages": 45,
                "dialogue": []
            }
    
    # Evaluate game quality
    print("Evaluating game quality...")
    evaluation = evaluate_game_quality(new_game_results, baseline_results)
    
    results = {
        "idea": idea,
        "new_game_results": new_game_results,
        "baseline_results": baseline_results,
        "evaluation": evaluation,
        "success": new_game_results["success"] and new_game_results.get("game_completed", False)
    }
    
    # Convert to expected format
    formatted_results = {
        "game_completion_rate": {"means": evaluation["completion_rate"], "stds": 0.0},
        "turn_quality_score": {"means": evaluation["turn_quality"], "stds": 0.0},
        "engagement_score": {"means": evaluation["engagement"], "stds": 0.0},
        "overall_quality": {"means": evaluation["overall_score"], "stds": 0.0},
        "beats_baseline": {"means": 1.0 if evaluation["beats_baseline"] else 0.0, "stds": 0.0}
    }
    
    return formatted_results

def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True, parents=True)
    
    # Run experiment
    start_time = time.time()
    results = run_experiment()
    end_time = time.time()
    
    # Save results
    final_info = {
        "results": results,
        "runtime": end_time - start_time
    }
    
    with open(out_dir / "final_info.json", "w") as f:
        json.dump(final_info, f, indent=2)
    
    print(f"Experiment completed. Results saved to {out_dir / 'final_info.json'}")

if __name__ == "__main__":
    main()