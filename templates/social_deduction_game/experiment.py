import argparse
import json
import os
import sys
import time
import asyncio
import tempfile
import shutil
from pathlib import Path
import importlib.util
import re
from typing import Dict, List, Any

# Add your experiment-specific imports here
import numpy as np

# Import LLM utilities from the unified client
from llm_client import get_llm_client

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
    
    Args:
        idea: Game idea dictionary with Name, Title, Experiment fields
        output_path: Path where to save the generated rule file
    """
    game_name = idea.get("Name", "custom_game")
    title = idea.get("Title", "Custom Social Deduction Game")
    description = idea.get("Experiment", "A new social deduction game")
    
    try:
        # Create LangChain LLM client using unified configuration
        from langchain_openai import ChatOpenAI
        
        # Get client from unified configuration
        client, model_name = get_llm_client()
        
        # Create LangChain wrapper for the configured client
        if "claude" in model_name:
            from langchain_anthropic import ChatAnthropic
            llm_client = ChatAnthropic(
                model=model_name,
                temperature=0.1,
                anthropic_api_key=client.api_key
            )
        else:
            # For OpenAI-compatible APIs (including OpenRouter, DeepSeek, etc.)
            llm_client = ChatOpenAI(
                model=model_name,
                temperature=0.1,
                openai_api_key=client.api_key,
                openai_api_base=getattr(client, 'base_url', None)
            )
        
        # Read werewolf.py as an example
        # Read all Python files in sample_rules directory and create a dictionary
        sample_rules_dir = Path(__file__).parent / "sample_rules"
        rule_examples = {}
        for rule_file in sample_rules_dir.glob("*.py"):
            with open(rule_file, 'r') as f:
                rule_examples[rule_file.stem] = f.read()
        
        rule_examples_str = '\n\n'.join([f"**{key}.py**\n```\n{rule_examples[key]}\n```" for key in rule_examples.keys()])
        # Create a detailed prompt for the LLM to generate the rule file
        prompt = f"""GAME IDEA TO IMPLEMENT:
Name: {game_name}
Title: {title}
Description: {description}

EXAMPLE STRUCTURES:
{rule_examples_str}

DETAILED REQUIREMENTS:

1. STRUCTURE: Follow the exact Python file structure shown in the werewolf.py example:
   - Import statements (json, random, typing)
   - RULEBOOK dictionary with 4 sections: common, role, gm_guideline, system_guideline
   - init_meta_pub(players) function
   - init_meta_priv(players) function  
   - assign_role(name, meta_priv) function
   - player_sys_prompt(name, role, lang) function
   - gm_sys_prompt(lang) function
   - system_sys_prompt() function

2. RULEBOOK CONTENT:
   - "common": Write complete public rules explaining victory conditions, all possible roles, phase sequence, and game mechanics
   - "role": Create specific role descriptions for each role in your game (no generic placeholders like [ROLE_1])
   - "gm_guideline": Detailed GM instructions for running the game, handling each phase, announcing results
   - "system_guideline": Instructions for the system agent to update game state and check win conditions

3. GAME MECHANICS: Implement the specific mechanics described in the game idea:
   - Define concrete roles mentioned in the description (e.g., if description mentions "Spy" and "Agent", create those exact roles)
   - Set up appropriate victory conditions based on the game concept
   - Create proper phase sequences that match the game flow described
   - Handle role assignments and team/faction relationships

4. ROLE IMPLEMENTATION:
   - Use the exact role names from the game description
   - Each role should have specific abilities and faction alignments
   - Set up teammate knowledge for faction-based roles
   - Include any special information or abilities described in the game idea

5. GAME STATE MANAGEMENT:
   - init_meta_pub: Set up public game state variables (phase, alive players, scores, etc.)
   - init_meta_priv: Handle role assignments, faction setup, and private information distribution
   - Ensure proper role distribution based on player count

6. PROMPT FUNCTIONS:
   - player_sys_prompt: Combine public rules + role description + player identity
   - gm_sys_prompt: Combine public rules + GM guidelines
   - system_sys_prompt: Provide system agent instructions

CRITICAL RULES:
- NO placeholder content like [ROLE_1], [FACTION_1] - use actual role names from the game idea
- NO generic roles - implement the specific roles described in the game concept
- Include complete victory conditions, not placeholders
- Write full rule descriptions, not outlines
- The file must be immediately playable without further editing

Generate a complete, working Python rule file that implements this specific social deduction game idea. The output should be valid Python code ready to run."""

        # Get LLM response using LangChain API
        from langchain.prompts import ChatPromptTemplate
        from langchain.schema import SystemMessage
        
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are an experienced game designer. Please convert the given game idea into a complete social deduction game rule file. Follow the provided example structure exactly and implement specific game mechanics without using placeholders."),
            ("human", "{prompt}")
        ])
        
        chain = prompt_template | llm_client
        response = chain.invoke({"prompt": prompt})
        
        # Extract content from response
        if hasattr(response, 'content'):
            generated_code = response.content
        else:
            generated_code = str(response)
        
        # Clean up the response (remove markdown code blocks if present)
        if "```python" in generated_code:
            generated_code = generated_code.split("```python")[1].split("```")[0]
        elif "```" in generated_code:
            generated_code = generated_code.split("```")[1].split("```")[0]
        
        # Write the generated rule file
        with open(output_path, 'w') as f:
            f.write(generated_code.strip())
        
        print(f"Generated rule file using LLM ({model_name}): {output_path}")
        return True
        
    except Exception as e:
        print(f"Error generating rule file with LLM: {e}")
        raise e  # Re-raise the error instead of falling back

def run_game_simulation(rule_module: str, out_dir: str = None, num_players: int = 5, 
                       max_turns: int = 50) -> Dict:
    """
    Run a game simulation and capture the results.
    """
    try:
        # Import the run_game function from sdg_core
        from sdg_core import run_game
        
        # Use default output directory if not specified
        if out_dir is None:
            out_dir = "temp_game_logs"
        
        # Create output directory
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"Running game with rules: {rule_module}, players: {num_players}, output: {out_dir}")
        
        # Run the game directly using the run_game function
        # Note: We need to handle async function call
        try:
            import asyncio
            result = asyncio.run(run_game(
                rules_module=rule_module,
                num_players=num_players,
                api_source="openrouter",  # Default to OpenAI, could be made configurable
                model_name="deepseek/deepseek-r1-0528",  # Default model, could be made configurable
                out_dir=out_dir
            ))
        except Exception as e:
            return {"success": False, "error": f"Failed to run game: {str(e)}", "dialogue": []}
        
        # Check if game completed successfully
        if not result["success"]:
            return {"success": False, "error": result.get("error", "Unknown game error"), "dialogue": []}
        
        # Load the game summary log (for evaluation)
        summary_file = Path(out_dir) / "game_summary.txt"
        detailed_file = Path(out_dir) / "game_log.json"
        
        try:
            with open(summary_file, 'r') as f:
                game_summary_text = f.read()
            with open(detailed_file, 'r') as f:
                game_detailed = json.load(f)
        except Exception as e:
            return {"success": False, "error": f"Failed to load log files: {e}", "dialogue": []}
        
        # Parse information from summary text log
        dialogue = []
        game_completed = result["game_completed"]
        winner = result["winner"]
        turn_count = result["turn_count"]
        
        # Parse conversations from summary text
        lines = game_summary_text.split('\n')
        for line in lines:
            line = line.strip()
            # Match conversation lines like: [01] P3▶ALL: message
            # or [01] P3▶DM(P1,P2): message
            if line.startswith('[') and ']' in line and ('▶ALL:' in line or '▶DM(' in line):
                try:
                    # Extract turn number
                    turn_part = line.split(']')[0][1:]
                    turn = int(turn_part)
                    
                    # Extract speaker and message
                    rest = line.split('] ', 1)[1]
                    if '▶ALL:' in rest:
                        speaker = rest.split('▶ALL:')[0]
                        message = rest.split('▶ALL:', 1)[1].strip()
                        is_dm = False
                    elif '▶DM(' in rest:
                        speaker = rest.split('▶DM(')[0]
                        message = rest.split('): ', 1)[1].strip()
                        is_dm = True
                    else:
                        continue
                        
                    dialogue.append({
                        "turn": turn,
                        "speaker": speaker,
                        "message": message,
                        "is_dm": is_dm
                    })
                except (ValueError, IndexError):
                    continue
        
        return {
            "success": True,
            "game_completed": game_completed,
            "winner": winner,
            "turn_count": turn_count,
            "dialogue": dialogue,
            "total_messages": len(dialogue),
            "game_summary_text": game_summary_text
        }
        
    except ImportError as e:
        return {"success": False, "error": f"Failed to import sdg_core: {e}", "dialogue": []}
    except Exception as e:
        return {"success": False, "error": str(e), "dialogue": []}

def evaluate_game_quality(new_game_results: Dict, baseline_results: Dict, rule_file_path: str = None) -> Dict:
    """
    Evaluate the quality of the new game compared to baseline using both rule analysis and gameplay logs.
    This comprehensive version analyzes rule coherence, balance, and actual gameplay quality.
    """
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import SystemMessage
    from langchain.output_parsers.json import SimpleJsonOutputParser
    
    metrics = {}
    
    # Basic completion metrics (same as before)
    metrics["completion_rate"] = 1.0 if new_game_results.get("game_completed", False) else 0.0
    baseline_completion = 1.0 if baseline_results.get("game_completed", False) else 0.0
    
    # ═══════════════════════════════════════════════════════════════════════
    # RULE ANALYSIS - Analyze the generated game rules
    # ═══════════════════════════════════════════════════════════════════════
    
    rule_analysis = {}
    if rule_file_path and Path(rule_file_path).exists():
        try:
            # Read the generated rule file
            with open(rule_file_path, 'r', encoding='utf-8') as f:
                rule_content = f.read()
            
            # Create LLM for rule analysis using unified configuration
            try:
                from langchain_openai import ChatOpenAI
                from langchain_anthropic import ChatAnthropic
                
                # Get client from unified configuration
                client, model_name = get_llm_client()
                
                # Create LangChain wrapper for the configured client
                if "claude" in model_name:
                    llm = ChatAnthropic(
                        model=model_name,
                        temperature=0.1,
                        anthropic_api_key=client.api_key
                    )
                else:
                    # For OpenAI-compatible APIs
                    llm = ChatOpenAI(
                        model=model_name,
                        temperature=0.1,
                        openai_api_key=client.api_key,
                        openai_api_base=getattr(client, 'base_url', None)
                    )
                    
            except Exception:
                # Fallback to basic analysis if LLM unavailable
                rule_analysis = {"error": "LLM unavailable for rule analysis"}
            else:
                # LLM-based rule analysis
                rule_analyzer = ChatPromptTemplate.from_messages([
                    SystemMessage(content="""You are a game design expert analyzing social deduction game rules. 
Evaluate the game rules on multiple dimensions and provide scores from 0.0 to 1.0.

Analysis dimensions:
1. RULE COHERENCE: Do the rules make logical sense and work together?
2. BALANCE: Are factions/roles fairly balanced? No overpowered roles?
3. STRATEGIC DEPTH: Do rules create interesting decisions and strategy?
4. CLARITY: Are rules clear and unambiguous?
5. INNOVATION: Does the game offer novel mechanics or interesting twists?
6. COMPLETENESS: Are all necessary rules and edge cases covered?

Respond with ONLY valid JSON matching this exact format:
{
  "rule_coherence": 0.85,
  "balance": 0.70,
  "strategic_depth": 0.80,
  "clarity": 0.90,
  "innovation": 0.60,
  "completeness": 0.75,
  "overall_rule_quality": 0.77,
  "reasoning": "Brief explanation of the analysis"
}"""),
                    ("human", "Analyze these social deduction game rules:\n\n{rule_content}")
                ]) | llm | SimpleJsonOutputParser()
                
                try:
                    rule_analysis = rule_analyzer.invoke({"rule_content": rule_content})
                    if not isinstance(rule_analysis, dict):
                        rule_analysis = {"error": "Invalid rule analysis response"}
                except Exception as e:
                    rule_analysis = {"error": f"Rule analysis failed: {str(e)}"}
        
        except Exception as e:
            rule_analysis = {"error": f"Failed to read rule file: {str(e)}"}
    else:
        rule_analysis = {"error": "Rule file not provided or not found"}
    
    # ═══════════════════════════════════════════════════════════════════════
    # GAMEPLAY ANALYSIS - Analyze actual gameplay logs
    # ═══════════════════════════════════════════════════════════════════════
    
    gameplay_analysis = {}
    
    # Basic statistical metrics (improved from original)
    new_turns = new_game_results.get("turn_count", 0)
    baseline_turns = baseline_results.get("turn_count", 10)
    new_msg_count = new_game_results.get("total_messages", 0)
    baseline_msg_count = baseline_results.get("total_messages", 1)
    
    # Turn count quality
    if baseline_turns > 0:
        turn_ratio = new_turns / baseline_turns
        if 0.5 <= turn_ratio <= 2.0:
            metrics["turn_quality"] = 1.0 - abs(1.0 - turn_ratio)
        else:
            metrics["turn_quality"] = 0.0
    else:
        metrics["turn_quality"] = 0.5
    
    # Message engagement
    if new_turns > 0 and baseline_turns > 0:
        new_msg_per_turn = new_msg_count / new_turns
        baseline_msg_per_turn = baseline_msg_count / baseline_turns
        
        if baseline_msg_per_turn > 0:
            msg_ratio = new_msg_per_turn / baseline_msg_per_turn
            metrics["engagement"] = min(1.0, msg_ratio)
        else:
            metrics["engagement"] = 0.5
    else:
        metrics["engagement"] = 0.0
    
    # ═══════════════════════════════════════════════════════════════════════
    # DIALOGUE QUALITY ANALYSIS - Analyze conversation quality with LLM
    # ═══════════════════════════════════════════════════════════════════════
    
    dialogue_analysis = {}
    if new_game_results.get("dialogue") and rule_file_path:
        try:
            # Get dialogue sample for analysis (last 20 messages for efficiency)
            dialogue = new_game_results["dialogue"][-20:] if len(new_game_results["dialogue"]) > 20 else new_game_results["dialogue"]
            dialogue_text = "\n".join([f"[{msg['turn']:02d}] {msg['speaker']}: {msg['message']}" for msg in dialogue])
            
            if dialogue_text.strip():
                try:
                    from langchain_openai import ChatOpenAI
                    from langchain_anthropic import ChatAnthropic
                    
                    # Get client from unified configuration
                    client, model_name = get_llm_client()
                    
                    # Create LangChain wrapper for the configured client
                    if "claude" in model_name:
                        llm = ChatAnthropic(
                            model=model_name,
                            temperature=0.1,
                            anthropic_api_key=client.api_key
                        )
                    else:
                        # For OpenAI-compatible APIs
                        llm = ChatOpenAI(
                            model=model_name,
                            temperature=0.1,
                            openai_api_key=client.api_key,
                            openai_api_base=getattr(client, 'base_url', None)
                        )
                    
                    dialogue_analyzer = ChatPromptTemplate.from_messages([
                        SystemMessage(content="""You are analyzing social deduction game dialogue quality.
Rate the conversation on these dimensions (0.0 to 1.0):

1. STRATEGIC_THINKING: Do players show strategic reasoning and deduction?
2. ROLE_PLAYING: Do players act according to their roles and game mechanics?
3. SOCIAL_INTERACTION: Is there good back-and-forth discussion and information sharing?
4. RULE_COMPLIANCE: Do conversations follow the game rules and mechanics?
5. DECEPTION_QUALITY: If applicable, is deception/bluffing sophisticated?
6. INFORMATION_FLOW: Do players appropriately share and withhold information?

Respond with ONLY valid JSON:
{
  "strategic_thinking": 0.75,
  "role_playing": 0.80,
  "social_interaction": 0.70,
  "rule_compliance": 0.85,
  "deception_quality": 0.60,
  "information_flow": 0.75,
  "overall_dialogue_quality": 0.74,
  "reasoning": "Brief explanation"
}"""),
                        ("human", "Analyze this social deduction game dialogue:\n\nRULE CONTEXT:\n{rule_summary}\n\nDIALOGUE:\n{dialogue}")
                    ]) | llm | SimpleJsonOutputParser()
                    
                    # Extract rule summary for context
                    rule_summary = "No rule context available"
                    if rule_file_path and Path(rule_file_path).exists():
                        with open(rule_file_path, 'r', encoding='utf-8') as f:
                            rule_lines = f.readlines()
                            # Extract RULEBOOK common section for context
                            for i, line in enumerate(rule_lines):
                                if '"common"' in line:
                                    # Find the end of the common section
                                    for j in range(i+1, min(i+50, len(rule_lines))):
                                        if rule_lines[j].strip().startswith('"""') and j > i+1:
                                            rule_summary = "".join(rule_lines[i+2:j])
                                            break
                                    break
                    
                    dialogue_analysis = dialogue_analyzer.invoke({
                        "rule_summary": rule_summary,
                        "dialogue": dialogue_text
                    })
                    
                    if not isinstance(dialogue_analysis, dict):
                        dialogue_analysis = {"error": "Invalid dialogue analysis response"}
                        
                except Exception as e:
                    dialogue_analysis = {"error": f"Dialogue analysis failed: {str(e)}"}
            else:
                dialogue_analysis = {"error": "No dialogue to analyze"}
                
        except Exception as e:
            dialogue_analysis = {"error": f"Failed to analyze dialogue: {str(e)}"}
    else:
        dialogue_analysis = {"error": "No dialogue or rule file available"}
    
    # ═══════════════════════════════════════════════════════════════════════
    # INTEGRATED SCORING - Combine all analysis dimensions
    # ═══════════════════════════════════════════════════════════════════════
    
    # Combine scores with weights
    rule_score = rule_analysis.get("overall_rule_quality", 0.5) if "error" not in rule_analysis else 0.3
    dialogue_score = dialogue_analysis.get("overall_dialogue_quality", 0.5) if "error" not in dialogue_analysis else 0.3
    
    # Overall quality combining all dimensions
    weights = {
        "completion_rate": 0.25,
        "rule_quality": 0.30, 
        "dialogue_quality": 0.25,
        "turn_quality": 0.10,
        "engagement": 0.10
    }
    
    metrics["rule_quality"] = rule_score
    metrics["dialogue_quality"] = dialogue_score
    metrics["overall_score"] = (
        metrics["completion_rate"] * weights["completion_rate"] +
        rule_score * weights["rule_quality"] +
        dialogue_score * weights["dialogue_quality"] +
        metrics["turn_quality"] * weights["turn_quality"] +
        metrics["engagement"] * weights["engagement"]
    )
    
    # Enhanced baseline comparison
    baseline_score = baseline_completion * 0.25 + 0.75  # Assume baseline has good quality
    metrics["beats_baseline"] = metrics["overall_score"] > baseline_score
    
    # Store detailed analysis for debugging
    metrics["detailed_analysis"] = {
        "rule_analysis": rule_analysis,
        "dialogue_analysis": dialogue_analysis,
        "statistical_metrics": {
            "new_turns": new_turns,
            "baseline_turns": baseline_turns,
            "new_messages": new_msg_count,
            "baseline_messages": baseline_msg_count
        }
    }
    
    return metrics

def run_experiment(args=None):
    """
    Main experiment function for social deduction game testing.
    """
    if args is None:
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
    rule_file_path = Path(args.out_dir) / f"{rule_file_name}.py"
    rule_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    success = generate_rule_file(idea, rule_file_path)
    if not success:
        return {"error": "Failed to generate rule file"}
    
    # Test the new game
    print("Running new game simulation...")
    new_game_results = run_game_simulation(rule_file_name, args.out_dir)
    
    if not new_game_results["success"]:
        print(f"New game failed: {new_game_results.get('error', 'Unknown error')}")
        # Try to improve the rule file iteratively
        # This is where you'd use LLM to fix issues based on error messages
        return {"error": f"Game simulation failed: {new_game_results.get('error', '')}"}
    
    # Run baseline game for comparison
    print("Running baseline game simulation...")
    baseline_rule_module = f"sample_rules.{args.baseline_game}"
    baseline_out_dir = str(Path(args.out_dir) / "baseline")
    baseline_results = run_game_simulation(baseline_rule_module, baseline_out_dir)
    
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
    evaluation = evaluate_game_quality(new_game_results, baseline_results, str(rule_file_path))
    

    # Convert to expected format
    formatted_results = {
        "game_completion_rate": {"means": evaluation["completion_rate"], "stds": 0.0},
        "rule_quality_score": {"means": evaluation.get("rule_quality", 0.0), "stds": 0.0},
        "dialogue_quality_score": {"means": evaluation.get("dialogue_quality", 0.0), "stds": 0.0},
        "turn_quality_score": {"means": evaluation["turn_quality"], "stds": 0.0},
        "engagement_score": {"means": evaluation["engagement"], "stds": 0.0},
        "overall_quality": {"means": evaluation["overall_score"], "stds": 0.0},
        "beats_baseline": {"means": 1.0 if evaluation["beats_baseline"] else 0.0, "stds": 0.0},
        "detailed_analysis": evaluation.get("detailed_analysis", {})
    }
    
    return formatted_results

def main():
    args = parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True, parents=True)
    
    # Run experiment
    start_time = time.time()
    results = run_experiment(args)
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