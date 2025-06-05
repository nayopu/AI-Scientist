#!/usr/bin/env python3
"""
Script to generate baseline game logs using werewolf.py rules.
This creates the baseline data used for evaluation in experiment.py.
"""

import json
import asyncio
import sys
from pathlib import Path

# Add the parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent))

from templates.social_deduction_game.sdg_core import run_game

async def generate_baseline_log():
    """Generate a baseline game log using werewolf rules."""
    
    output_dir = "baseline_logs"
    Path(output_dir).mkdir(exist_ok=True)
    
    print("Generating baseline game log using werewolf.py...")
    
    try:
        # Run the werewolf game
        result = await run_game(
            rules_module="sample_rules.werewolf",
            num_players=5,  # Standard 5-player game
            api_source="openrouter",  # Using OpenRouter API
            model_name="deepseek/deepseek-r1-0528",  # Using DeepSeek model
            out_dir=output_dir
        )
        
        if result["success"]:
            print(f"✓ Baseline game completed successfully!")
            print(f"  - Game completed: {result['game_completed']}")
            print(f"  - Winner: {result['winner']}")
            print(f"  - Turn count: {result['turn_count']}")
            print(f"  - Logs saved to: {output_dir}/")
            
            # Save the result summary for use in experiment.py
            baseline_result = {
                "success": True,
                "game_completed": result["game_completed"],
                "turn_count": result["turn_count"],
                "winner": result["winner"],
                "total_messages": 0  # Will be calculated from logs
            }
            
            # Count messages from the log file
            try:
                with open(f"{output_dir}/game_summary.txt", 'r') as f:
                    summary_text = f.read()
                    # Count conversation lines
                    lines = summary_text.split('\n')
                    message_count = 0
                    for line in lines:
                        line = line.strip()
                        if line.startswith('[') and ']' in line and ('▶ALL:' in line or '▶DM(' in line):
                            message_count += 1
                    baseline_result["total_messages"] = message_count
                    print(f"  - Total messages: {message_count}")
            except Exception as e:
                print(f"  - Could not count messages: {e}")
            
            # Save baseline results for experiment.py to use
            with open("baseline_game_results.json", 'w') as f:
                json.dump(baseline_result, f, indent=2)
            
            print(f"✓ Baseline results saved to baseline_game_results.json")
            return True
            
        else:
            print(f"✗ Baseline game failed: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"✗ Error generating baseline: {e}")
        return False

def main():
    """Main function to run the baseline generation."""
    success = asyncio.run(generate_baseline_log())
    if not success:
        sys.exit(1)
    print("\n🎉 Baseline generation completed successfully!")

if __name__ == "__main__":
    main() 