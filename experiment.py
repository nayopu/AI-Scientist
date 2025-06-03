from typing import Dict
import tempfile
import sys
from pathlib import Path

def run_game_simulation(rule_module: str, num_players: int = 5, 
                       model_spec: str = "openai:gpt-4o-mini",
                       max_turns: int = 50) -> Dict:
    """
    Run a game simulation and capture the results.
    
    Args:
        rule_module: Name of the rule module to use
        num_players: Number of players in the game
        model_spec: Model specification in format 'api:model_name'
        max_turns: Maximum number of turns to run
    """
    try:
        # Create a temporary output file for the game log
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            log_file = f.name
        
        # Run the game simulation
        cmd = [
            sys.executable, 
            str(Path(__file__).parent / "sdg_core.py"),
            "--rules", rule_module,
            "--players", str(num_players),
            "--model", model_spec,  # Pass the unified model spec
            "--out", log_file
        ]
        
        # ... rest of the code ... 