import argparse
import json
import os
import sys
import time
import asyncio
import tempfile
import shutil
import re
from pathlib import Path
import importlib.util
from typing import Dict, List, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add your experiment-specific imports here
import numpy as np

# Import LLM utilities from the unified client
from llm_client import get_llm_client
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain.prompts import ChatPromptTemplate
from langchain.schema import SystemMessage
from langchain.output_parsers.json import SimpleJsonOutputParser

from sdg_core import run_game


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out_dir", type=str, required=True)
    parser.add_argument("--idea", type=str, help="JSON string of the idea to implement")
    parser.add_argument("--max_turns", type=int, default=100,
                        help="Maximum number of turns before game ends (default: 100)")
    parser.add_argument("--player_model", type=str, default="openrouter:deepseek/deepseek-r1-0528",
                        help="Model specification for players in format 'api:model_name' (default: openrouter:deepseek/deepseek-r1-0528)")
    parser.add_argument("--gm_model", type=str, default=None,
                        help="Model specification for GM in format 'api:model_name' (if different from players)")
    parser.add_argument("--num_game_runs", type=int, default=5,
                        help="Number of times to run each game configuration for statistical significance (default: 5)")
    # Legacy arguments for compatibility - these are handled by the unified client system
    parser.add_argument("--model", type=str, default=None,
                        help="Legacy model argument (handled by AI_SCIENTIST_MODEL env var)")
    parser.add_argument("--api", type=str, default=None,
                        help="Legacy API argument (handled by unified client)")
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
        # Get client from unified configuration
        client, model_name = get_llm_client()
        
        # Check if model supports temperature parameter
        # o3-mini and similar models don't support temperature
        supports_temperature = not (model_name.startswith("o3") or model_name.startswith("o1"))
        
        # Create LangChain wrapper for the configured client
        if "claude" in model_name:
            if supports_temperature:
                llm_client = ChatAnthropic(
                    model=model_name,
                    temperature=0.1,
                    anthropic_api_key=client.api_key
                )
            else:
                llm_client = ChatAnthropic(
                    model=model_name,
                    anthropic_api_key=client.api_key
                )
        else:
            # For OpenAI-compatible APIs (including OpenRouter, DeepSeek, etc.)
            base_url = getattr(client, 'base_url', None)
            # Convert URL object to string if needed
            if base_url is not None:
                base_url = str(base_url)
            
            if supports_temperature:
                llm_client = ChatOpenAI(
                    model=model_name,
                    temperature=0.1,
                    openai_api_key=client.api_key,
                    openai_api_base=base_url
                )
            else:
                llm_client = ChatOpenAI(
                    model=model_name,
                    openai_api_key=client.api_key,
                    openai_api_base=base_url
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
   - system_sys_prompt() function (NOTE: NO gm_sys_prompt function - GameSystem handles both GM and system roles)

2. RULEBOOK CONTENT:
   - "common": Write complete public rules explaining victory conditions, all possible roles, phase sequence, and game mechanics
   - "role": Create specific role descriptions for each role in your game (no generic placeholders like [ROLE_1])
   - "gm_guideline": Detailed GM instructions for running the game, handling each phase, announcing results, sending DMs to players
   - "system_guideline": Instructions for the GameSystem agent that acts as both GM and system manager

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
   - Use "GM" (not "GM_SYSTEM") as the key for GameSystem's private meta information
   - Ensure proper role distribution based on player count

6. PROMPT FUNCTIONS:
   - player_sys_prompt: Combine public rules + role description + player identity
   - system_sys_prompt: Combine public rules + GM guidelines + system guidelines (GameSystem acts as both GM and system manager)

7. GAMESYSTEM ARCHITECTURE:
   - The GameSystem agent acts as both GM and system manager
   - It decides when to speak as GM based on game state and player submissions
   - It can send DMs to specific players for role-specific information
   - It updates game state and checks win conditions
   - Response format includes: selected_messages, update_pub, update_priv, reason

8. SYSTEM_GUIDELINE REQUIREMENTS:
   - Must describe dual responsibilities: GM communication and system management
   - Include GM responsibilities: phase announcements, DM coordination, rule enforcement
   - Include system responsibilities: meta updates, win condition checks
   - Specify JSON response format with selected_messages array
   - Include examples of when to send DMs to players (investigation results, role coordination, etc.)

CRITICAL RULES:
- NO placeholder content like [ROLE_1], [FACTION_1] - use actual role names from the game idea
- NO generic roles - implement the specific roles described in the game concept
- Include complete victory conditions, not placeholders
- Write full rule descriptions, not outlines
- NO gm_sys_prompt function - only system_sys_prompt that combines both responsibilities
- Use "GM" (not "GM_SYSTEM") for private meta key
- The file must be immediately playable without further editing
- Follow the new GameSystem architecture where one agent handles both GM and system roles

Generate a complete, working Python rule file that implements this specific social deduction game idea. The output should be valid Python code ready to run with the new GameSystem architecture."""

        # Get LLM response using LangChain API
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

def run_game_simulation_single(rule_module: str, out_dir: str = None, num_players: int = 5, 
                              max_turns: int = 100, player_model: str = "openrouter:deepseek/deepseek-r1-0528",
                              gm_model: str = None, run_index: int = 0) -> Dict:
    """
    Run a single game simulation and capture the results.
    
    Args:
        rule_module: Name of the rules module to use
        out_dir: Directory to save game logs
        num_players: Number of players (default: 5)
        max_turns: Maximum number of turns (default: 100)
        player_model: Model specification for players in format "api:model_name" (default: "openrouter:deepseek/deepseek-r1-0528")
        gm_model: Model specification for GM in format "api:model_name" (if different from players)
        run_index: Index of this particular run for organizing output (default: 0)
    """
    try:
        # Use default output directory if not specified
        if out_dir is None:
            out_dir = f"temp_game_logs/run_{run_index}"
        else:
            out_dir = f"{out_dir}/run_{run_index}"
        
        # Create output directory
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"Running game with rules: {rule_module}, players: {num_players}, output: {out_dir}")
        
        # Run the game directly using the run_game function
        # Note: We need to handle async function call
        try:
            result = asyncio.run(run_game(
                rules_module=rule_module,
                num_players=num_players,
                player_model=player_model,
                gm_model=gm_model,
                out_dir=out_dir,
                max_turns=max_turns
            ))
        except Exception as e:
            return {"success": False, "error": f"Failed to run game: {str(e)}", "dialogue": []}
        
        # Check if game completed successfully
        if not result["success"]:
            return {"success": False, "error": result.get("error", "Unknown game error"), "dialogue": []}
        
        # Load the game summary JSON (new structured format)
        summary_json_file = Path(out_dir) / "game_summary.json"
        summary_text_file = Path(out_dir) / "game_summary.txt"
        
        try:
            # Load structured data from JSON
            with open(summary_json_file, 'r') as f:
                game_summary_data = json.load(f)
            
            # Load conversation text for LLM analysis
            with open(summary_text_file, 'r') as f:
                game_summary_text = f.read()
            
            return {
                "success": game_summary_data["success"],
                "game_completed": game_summary_data["game_completed"],
                "winner": game_summary_data["winner"],
                "turn_count": game_summary_data["turn_count"],
                "max_turns": game_summary_data.get("max_turns", max_turns),
                "max_turns_reached": game_summary_data.get("max_turns_reached", False),
                "total_messages": game_summary_data["total_messages"],
                "dialogue": [],  # Empty for now, raw text will be used for LLM analysis
                "game_summary_text": game_summary_text
            }
                
        except Exception as e:
            return {"success": False, "error": f"Failed to load log files: {e}", "dialogue": []}
        
    except ImportError as e:
        return {"success": False, "error": f"Failed to import sdg_core: {e}", "dialogue": []}
    except Exception as e:
        return {"success": False, "error": str(e), "dialogue": []}


def run_game_simulation_multiple(rule_module: str, out_dir: str = None, num_players: int = 5, 
                                max_turns: int = 100, player_model: str = "openrouter:deepseek/deepseek-r1-0528",
                                gm_model: str = None, num_runs: int = 5) -> Dict:
    """
    Run multiple game simulations in parallel and aggregate the results.
    
    Args:
        rule_module: Name of the rules module to use
        out_dir: Directory to save game logs
        num_players: Number of players (default: 5)
        max_turns: Maximum number of turns (default: 100)
        player_model: Model specification for players in format "api:model_name" (default: "openrouter:deepseek/deepseek-r1-0528")
        gm_model: Model specification for GM in format "api:model_name" (if different from players)
        num_runs: Number of times to run the game simulation (default: 5)
    
    Returns:
        Dict: Aggregated results including means, standard deviations, and individual run results
    """
    print(f"Starting {num_runs} parallel game simulations...")
    
    # Use default output directory if not specified
    if out_dir is None:
        out_dir = "temp_game_logs"
    
    # Create main output directory
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    
    all_results = []
    successful_results = []
    
    # Run simulations in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(num_runs, 4)) as executor:  # Limit concurrent runs to avoid overwhelming the system
        # Submit all tasks
        future_to_run = {
            executor.submit(
                run_game_simulation_single,
                rule_module=rule_module,
                out_dir=out_dir,
                num_players=num_players,
                max_turns=max_turns,
                player_model=player_model,
                gm_model=gm_model,
                run_index=i
            ): i for i in range(num_runs)
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_run):
            run_index = future_to_run[future]
            try:
                result = future.result()
                all_results.append(result)
                
                if result["success"]:
                    successful_results.append(result)
                    print(f"Run {run_index} completed successfully: {result.get('turn_count', 0)} turns")
                else:
                    print(f"Run {run_index} failed: {result.get('error', 'Unknown error')}")
                    
            except Exception as e:
                print(f"Run {run_index} encountered an exception: {str(e)}")
                all_results.append({"success": False, "error": f"Exception: {str(e)}", "run_index": run_index})
    
    # Check if we have any successful results
    if not successful_results:
        return {
            "success": False,
            "error": f"All {num_runs} simulation runs failed",
            "num_attempted": num_runs,
            "num_successful": 0,
            "raw_results": all_results
        }
    
    # Aggregate successful results
    game_completed_list = [r["game_completed"] for r in successful_results]
    turn_count_list = [r["turn_count"] for r in successful_results]
    total_messages_list = [r["total_messages"] for r in successful_results]
    max_turns_reached_list = [r.get("max_turns_reached", False) for r in successful_results]
    
    # Calculate aggregated statistics
    aggregated_results = {
        "success": True,
        "num_attempted": num_runs,
        "num_successful": len(successful_results),
        "success_rate": len(successful_results) / num_runs,
        
        # Game completion statistics
        "game_completed": {
            "mean": float(np.mean(game_completed_list)),
            "std": float(np.std(game_completed_list)),
            "count": len(game_completed_list)
        },
        
        # Turn count statistics
        "turn_count": {
            "mean": float(np.mean(turn_count_list)),
            "std": float(np.std(turn_count_list)),
            "min": float(np.min(turn_count_list)),
            "max": float(np.max(turn_count_list)),
            "count": len(turn_count_list)
        },
        
        # Message count statistics
        "total_messages": {
            "mean": float(np.mean(total_messages_list)),
            "std": float(np.std(total_messages_list)),
            "min": float(np.min(total_messages_list)),
            "max": float(np.max(total_messages_list)),
            "count": len(total_messages_list)
        },
        
        # Max turns reached statistics
        "max_turns_reached": {
            "mean": float(np.mean(max_turns_reached_list)),
            "std": float(np.std(max_turns_reached_list)),
            "count": len(max_turns_reached_list)
        },
        
        # Configuration used
        "config": {
            "num_players": num_players,
            "max_turns": max_turns,
            "player_model": player_model,
            "gm_model": gm_model,
            "num_runs": num_runs
        },
        
        # Raw individual results for detailed analysis
        "individual_results": successful_results,
        "all_results": all_results  # Include failed results too for debugging
    }
    
    # Save aggregated results to JSON file
    results_file = Path(out_dir) / "aggregated_results.json"
    with open(results_file, 'w') as f:
        json.dump(aggregated_results, f, indent=2)
    
    print(f"Completed {len(successful_results)}/{num_runs} simulations successfully")
    print(f"Average turn count: {aggregated_results['turn_count']['mean']:.2f} ± {aggregated_results['turn_count']['std']:.2f}")
    print(f"Average messages: {aggregated_results['total_messages']['mean']:.2f} ± {aggregated_results['total_messages']['std']:.2f}")
    
    return aggregated_results

def evaluate_game_quality(new_game_results: Dict, baseline_results: Dict, rule_file_path: str = None) -> Dict:
    """
    Evaluate the quality of the new game compared to baseline using both rule analysis and gameplay logs.
    This comprehensive version analyzes rule coherence, balance, and actual gameplay quality.
    """
   
    metrics = {}
    
    # Basic completion metrics (updated to consider max turns)
    new_game_completed = new_game_results.get("game_completed", False)
    new_max_turns_reached = new_game_results.get("max_turns_reached", False)
    baseline_completed = baseline_results.get("game_completed", False)
    baseline_max_turns_reached = baseline_results.get("max_turns_reached", False)
    
    # Give partial credit for reaching max turns (game didn't crash, just took too long)
    if new_game_completed:
        metrics["completion_rate"] = 1.0
    elif new_max_turns_reached:
        metrics["completion_rate"] = 0.7  # Partial credit for reaching max turns
    else:
        metrics["completion_rate"] = 0.0
    
    if baseline_completed:
        baseline_completion = 1.0
    elif baseline_max_turns_reached:
        baseline_completion = 0.7
    else:
        baseline_completion = 0.0
    
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
                # Get client from unified configuration
                client, model_name = get_llm_client()
                
                # Check if model supports temperature parameter
                supports_temperature = not (model_name.startswith("o3") or model_name.startswith("o1"))
                
                # Create LangChain wrapper for the configured client
                if "claude" in model_name:
                    if supports_temperature:
                        llm = ChatAnthropic(
                            model=model_name,
                            temperature=0.1,
                            anthropic_api_key=client.api_key
                        )
                    else:
                        llm = ChatAnthropic(
                            model=model_name,
                            anthropic_api_key=client.api_key
                        )
                else:
                    # For OpenAI-compatible APIs
                    base_url = getattr(client, 'base_url', None)
                    # Convert URL object to string if needed
                    if base_url is not None:
                        base_url = str(base_url)
                    
                    if supports_temperature:
                        llm = ChatOpenAI(
                            model=model_name,
                            temperature=0.1,
                            openai_api_key=client.api_key,
                            openai_api_base=base_url
                        )
                    else:
                        llm = ChatOpenAI(
                            model=model_name,
                            openai_api_key=client.api_key,
                            openai_api_base=base_url
                        )
                    
            except Exception as e:
                # Fallback to basic analysis if LLM unavailable
                rule_analysis = {"error": f"LLM unavailable for rule analysis: {str(e)}"}
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
    # Use game_summary_text instead of dialogue field which is usually empty
    game_summary = new_game_results.get("game_summary_text", "")
    if game_summary and rule_file_path:
        try:
            # Extract meaningful dialogue from game summary text
            dialogue_text = game_summary
            
            if dialogue_text.strip():
                try:
                    # Get client from unified configuration
                    client, model_name = get_llm_client()
                    
                    # Check if model supports temperature parameter
                    supports_temperature = not (model_name.startswith("o3") or model_name.startswith("o1"))
                    
                    # Create LangChain wrapper for the configured client
                    if "claude" in model_name:
                        if supports_temperature:
                            llm = ChatAnthropic(
                                model=model_name,
                                temperature=0.1,
                                anthropic_api_key=client.api_key
                            )
                        else:
                            llm = ChatAnthropic(
                                model=model_name,
                                anthropic_api_key=client.api_key
                            )
                    else:
                        # For OpenAI-compatible APIs
                        base_url = getattr(client, 'base_url', None)
                        # Convert URL object to string if needed
                        if base_url is not None:
                            base_url = str(base_url)
                        
                        if supports_temperature:
                            llm = ChatOpenAI(
                                model=model_name,
                                temperature=0.1,
                                openai_api_key=client.api_key,
                                openai_api_base=base_url
                            )
                        else:
                            llm = ChatOpenAI(
                                model=model_name,
                                openai_api_key=client.api_key,
                                openai_api_base=base_url
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
        if not game_summary:
            dialogue_analysis = {"error": "No game summary text available for analysis"}
        elif not rule_file_path:
            dialogue_analysis = {"error": "Rule file path not provided for analysis"}
        else:
            dialogue_analysis = {"error": "Unknown issue with dialogue analysis"}
    
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

def determine_num_players(out_dir: str, idea: Dict[str, Any] = None) -> int:
    """
    Determine the number of players for this experiment run based on the output directory.
    This allows different runs to test different player counts.
    """
    # Extract run number from output directory (e.g., "run_1" -> 1)
    run_match = re.search(r'run_(\d+)', out_dir)
    if run_match:
        run_num = int(run_match.group(1))
    else:
        run_num = 0  # Default for baseline or unknown format
    
    # Experimental design: vary player count based on run number
    # Run 0: Baseline (5 players) - this should already exist
    # Run 1: Test with 3 players (minimum for most social deduction games)
    # Run 2: Test with 4 players 
    # Run 3: Test with 6 players
    # Run 4: Test with 7 players
    # Run 5+: Test with 8 players (maximum for complexity)
    
    player_count_map = {
        0: 5,  # Baseline
        1: 3,  # Minimum players
        2: 4,  # Small group
        3: 6,  # Medium group
        4: 7,  # Large group
        5: 8,  # Maximum players
    }
    
    # For runs beyond 5, cycle through different player counts
    if run_num > 5:
        # Cycle through 3-8 players for additional runs
        player_counts = [3, 4, 5, 6, 7, 8]
        return player_counts[(run_num - 6) % len(player_counts)]
    
    return player_count_map.get(run_num, 5)  # Default to 5 if not found

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
    
    # Determine number of players based on experimental design
    num_players = determine_num_players(args.out_dir, idea)
    print(f"Testing idea: {idea['Name']} with {num_players} players (determined from run configuration)")
    
    # Handle rule file (generate only if it doesn't exist, use existing one otherwise)
    rule_file_name = 'rule'
    rule_file_path = Path(__file__).parent / f"{rule_file_name}.py"  # Place in same directory as experiment.py
    
    if not rule_file_path.exists():
        # Generate rule file only if it doesn't exist
        print(f"Generating new rule file: {rule_file_path}")
        success = generate_rule_file(idea, rule_file_path)
        if not success:
            return {"error": "Failed to generate rule file"}
    else:
        print(f"Using existing rule file: {rule_file_path}")
        # The rule file will be potentially modified by the coder system based on experimental results
    
    # Convert rule file name to module format  
    # Use simple module name since rule.py is in the same directory
    rule_module = rule_file_name
    # Test the new game with multiple runs for statistical significance
    print(f"Running {args.num_game_runs} game simulations in parallel...")
    aggregated_results = run_game_simulation_multiple(
        rule_module, 
        args.out_dir, 
        num_players=num_players,
        max_turns=args.max_turns,
        player_model=args.player_model,
        gm_model=args.gm_model,
        num_runs=args.num_game_runs
    )
    
    # Extract representative results for evaluation (use aggregated statistics)
    if aggregated_results["success"]:
        new_game_results = {
            "success": True,
            "game_completed": aggregated_results["game_completed"]["mean"] > 0.5,  # Majority completed
            "turn_count": int(aggregated_results["turn_count"]["mean"]),
            "max_turns": args.max_turns,
            "max_turns_reached": aggregated_results["max_turns_reached"]["mean"] > 0.5,  # Majority reached max turns
            "total_messages": int(aggregated_results["total_messages"]["mean"]),
            "dialogue": [],  # Empty for now, will use aggregated data for analysis
            "aggregated_stats": aggregated_results  # Include full aggregated statistics
        }
    else:
        new_game_results = aggregated_results  # Pass through the error
    
    if not new_game_results["success"]:
        print(f"New game failed: {new_game_results.get('error', 'Unknown error')}")
        # Try to improve the rule file iteratively
        # This is where you'd use LLM to fix issues based on error messages
        return {"error": f"Game simulation failed: {new_game_results.get('error', '')}"}
    
    # Load baseline game results from existing logs instead of running simulation
    print("Loading baseline game results from existing logs...")
    baseline_logs_dir = Path(__file__).parent / "run_0"
    
    try:
        # Load baseline game summary from JSON and text files
        baseline_summary_json_file = baseline_logs_dir / "game_summary.json"
        baseline_summary_text_file = baseline_logs_dir / "game_summary.txt"
        
        # Load structured data from JSON
        with open(baseline_summary_json_file, 'r') as f:
            baseline_summary_data = json.load(f)
        
        # Load conversation text for LLM analysis
        with open(baseline_summary_text_file, 'r') as f:
            baseline_summary_text = f.read()
        
        # Create baseline results
        baseline_results = {
            "success": baseline_summary_data["success"],
            "game_completed": baseline_summary_data["game_completed"],
            "winner": baseline_summary_data["winner"],
            "turn_count": baseline_summary_data["turn_count"],
            "max_turns": baseline_summary_data.get("max_turns", 100),
            "max_turns_reached": baseline_summary_data.get("max_turns_reached", False),
            "total_messages": baseline_summary_data["total_messages"],
            "dialogue": [],  # Empty for now, raw text will be used for LLM analysis
            "game_summary_text": baseline_summary_text
        }
        print(f"Loaded baseline results: {baseline_results['turn_count']} turns, {baseline_results['total_messages']} messages")
            
    except Exception as e:
        print(f"Warning: Failed to load baseline logs: {e}")
        baseline_results = {
            "success": True,
            "game_completed": True,
            "winner": "VILLAGERS", 
            "turn_count": 57,
            "max_turns": 100,
            "max_turns_reached": False,
            "total_messages": 45,
            "dialogue": [],
            "game_summary_text": ""
        }
    
    # Evaluate game quality independently for each run to get proper statistics
    print("Evaluating game quality for each individual run...")
    aggregated_stats = new_game_results.get("aggregated_stats", {})
    individual_results = aggregated_stats.get("individual_results", [])
    
    if not individual_results:
        # Fallback to single evaluation
        print("Warning: No individual results found, using aggregated evaluation")
        evaluation = evaluate_game_quality(new_game_results, baseline_results, str(rule_file_path))
        individual_evaluations = [evaluation]
    else:
        # Evaluate each individual game run separately
        individual_evaluations = []
        for i, individual_result in enumerate(individual_results):
            print(f"Evaluating game run {i+1}/{len(individual_results)}")
            evaluation = evaluate_game_quality(individual_result, baseline_results, str(rule_file_path))
            individual_evaluations.append(evaluation)
    
    # Calculate statistics across all evaluations
    if individual_evaluations:
        completion_rates = [e["completion_rate"] for e in individual_evaluations]
        rule_qualities = [e.get("rule_quality", 0.0) for e in individual_evaluations]
        dialogue_qualities = [e.get("dialogue_quality", 0.0) for e in individual_evaluations]
        turn_qualities = [e["turn_quality"] for e in individual_evaluations]
        engagement_scores = [e["engagement"] for e in individual_evaluations]
        overall_scores = [e["overall_score"] for e in individual_evaluations]
        beats_baseline_list = [1.0 if e["beats_baseline"] else 0.0 for e in individual_evaluations]
        
        # Calculate means and standard deviations
        evaluation_stats = {
            "game_completion_rate": {"means": float(np.mean(completion_rates)), "stds": float(np.std(completion_rates))},
            "rule_quality_score": {"means": float(np.mean(rule_qualities)), "stds": float(np.std(rule_qualities))},
            "dialogue_quality_score": {"means": float(np.mean(dialogue_qualities)), "stds": float(np.std(dialogue_qualities))},
            "turn_quality_score": {"means": float(np.mean(turn_qualities)), "stds": float(np.std(turn_qualities))},
            "engagement_score": {"means": float(np.mean(engagement_scores)), "stds": float(np.std(engagement_scores))},
            "overall_quality": {"means": float(np.mean(overall_scores)), "stds": float(np.std(overall_scores))},
            "beats_baseline": {"means": float(np.mean(beats_baseline_list)), "stds": float(np.std(beats_baseline_list))},
        }
    else:
        # Fallback if no evaluations
        evaluation_stats = {
            "game_completion_rate": {"means": 0.0, "stds": 0.0},
            "rule_quality_score": {"means": 0.0, "stds": 0.0},
            "dialogue_quality_score": {"means": 0.0, "stds": 0.0},
            "turn_quality_score": {"means": 0.0, "stds": 0.0},
            "engagement_score": {"means": 0.0, "stds": 0.0},
            "overall_quality": {"means": 0.0, "stds": 0.0},
            "beats_baseline": {"means": 0.0, "stds": 0.0},
        }

    # Extract statistical metrics from game runs if available
    turn_count_stats = aggregated_stats.get("turn_count", {"mean": new_game_results.get("turn_count", 0), "std": 0.0})
    message_stats = aggregated_stats.get("total_messages", {"mean": new_game_results.get("total_messages", 0), "std": 0.0})
    completion_stats = aggregated_stats.get("game_completed", {"mean": 1.0 if new_game_results.get("game_completed", False) else 0.0, "std": 0.0})
    max_turns_stats = aggregated_stats.get("max_turns_reached", {"mean": 1.0 if new_game_results.get("max_turns_reached", False) else 0.0, "std": 0.0})
    
    # Combine evaluation statistics with run statistics
    formatted_results = evaluation_stats.copy()
    formatted_results.update({
        # Statistical metrics from multiple runs
        "turn_count": {"means": turn_count_stats["mean"], "stds": turn_count_stats["std"]},
        "total_messages": {"means": message_stats["mean"], "stds": message_stats["std"]},
        "game_completed": {"means": completion_stats["mean"], "stds": completion_stats["std"]},
        "max_turns_reached": {"means": max_turns_stats["mean"], "stds": max_turns_stats["std"]},
        
        # Summary statistics
        "num_runs_attempted": aggregated_stats.get("num_attempted", 1),
        "num_runs_successful": aggregated_stats.get("num_successful", 1 if new_game_results.get("success", False) else 0),
        "success_rate": aggregated_stats.get("success_rate", 1.0 if new_game_results.get("success", False) else 0.0),
        
        "game_stats": {
            "num_players": num_players,
            "new_game_turns_mean": turn_count_stats["mean"],
            "new_game_turns_std": turn_count_stats["std"],
            "new_game_max_turns": new_game_results.get("max_turns", 100),
            "new_game_completed_rate": completion_stats["mean"],
            "new_game_max_turns_reached_rate": max_turns_stats["mean"],
            "total_runs": aggregated_stats.get("num_attempted", 1),
            "successful_runs": aggregated_stats.get("num_successful", 1 if new_game_results.get("success", False) else 0)
        },
        "detailed_analysis": individual_evaluations[-1].get("detailed_analysis", {}) if individual_evaluations else {},
        "aggregated_statistics": aggregated_stats,  # Include full aggregated stats for reference
        "individual_evaluations": individual_evaluations  # Include all individual evaluations for debugging
    })
    
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