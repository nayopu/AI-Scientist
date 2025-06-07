import argparse
import json
import os
import os.path as osp
import re
import shutil
import subprocess
from typing import Optional, Tuple, Dict, List, Any
import glob
from pathlib import Path

# Import LLM utilities from the unified client (same as experiment.py)
from llm_client import get_llm_client

def create_llm_client():
    """Create LangChain LLM client using the same method as experiment.py"""
    try:
        from langchain_openai import ChatOpenAI
        from langchain_anthropic import ChatAnthropic
        
        # Get client from unified configuration
        client, model_name = get_llm_client()
        
        # Check if model supports temperature parameter
        # o3-mini and similar models don't support temperature
        supports_temperature = not (model_name.startswith("o3-") or model_name.startswith("o1-"))
        
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
        
        return llm_client, model_name
    except Exception as e:
        print(f"Error creating LLM client: {e}")
        raise e

def find_latest_rule_file(folder_name: str) -> str:
    """Find the latest run_x/rule.py file"""
    run_dirs = []
    for item in os.listdir(folder_name):
        if re.match(r'^run_\d+$', item):
            run_path = osp.join(folder_name, item)
            if osp.isdir(run_path):
                # Extract run number for sorting
                run_num = int(item.split('_')[1])
                run_dirs.append((run_num, run_path))
    
    # Sort by run number and get the latest one
    if not run_dirs:
        raise FileNotFoundError(f"No run_x directories found in {folder_name}")
    
    run_dirs.sort(key=lambda x: x[0], reverse=True)
    latest_run_dir = run_dirs[0][1]
    
    # Look for rule.py in the latest run directory
    rule_file = osp.join(latest_run_dir, "rule.py")
    if not osp.exists(rule_file):
        raise FileNotFoundError(f"Required rule.py file not found in latest run directory: {latest_run_dir}")
    
    return rule_file

def generate_rulebook(idea: Dict[str, Any], rule_file_path: str, template_tex_path: str, output_path: str, llm_client) -> bool:
    """Generate rulebook using single LLM call"""
    
    # Read rule file
    with open(rule_file_path, 'r', encoding='utf-8') as f:
        rule_content = f.read()
    
    # Read template
    with open(template_tex_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Create prompt for rulebook generation
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import SystemMessage
    
    prompt = f"""TASK: Generate a complete social deduction game rulebook in LaTeX format.

GAME INFORMATION:
Name: {idea.get("Name", "Custom Game")}
Title: {idea.get("Title", "Custom Social Deduction Game")}
Description: {idea.get("Experiment", "A new social deduction game")}

RULE FILE CONTENT:
```python
{rule_content}
```

TEMPLATE TO FILL:
```latex
{template_content}
```

INSTRUCTIONS:
1. Read the rule file to understand the game mechanics, roles, victory conditions, and gameplay flow
2. Fill in ALL placeholder sections in the template (marked with [TO BE FILLED])
3. Replace all bracketed placeholders with actual content based on the rule file
4. Use the Nier Automata style elements (nierbox, nierquote, etc.) appropriately
5. Create a complete, playable game manual that players can use to learn and play the game
6. Include detailed role descriptions, complete rules, and clear victory conditions
7. Make the content engaging and atmospheric while being clear and functional

OUTPUT: Return ONLY the complete LaTeX document with all placeholders filled in."""

    try:
        rulebook_generator = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a professional game designer creating a complete social deduction game rulebook. Generate clear, comprehensive, and engaging game documentation in LaTeX format using the Nier Automata template style."),
            ("human", "{prompt}")
        ]) | llm_client
        
        response = rulebook_generator.invoke({"prompt": prompt})
        
        # Extract content from response
        if hasattr(response, 'content'):
            generated_latex = response.content
        else:
            generated_latex = str(response)
        
        # Clean up the response (remove markdown code blocks if present)
        if "```latex" in generated_latex:
            generated_latex = generated_latex.split("```latex")[1].split("```")[0]
        elif "```" in generated_latex:
            generated_latex = generated_latex.split("```")[1].split("```")[0]
        
        # Write the generated rulebook
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(generated_latex.strip())
        
        print(f"Generated rulebook: {output_path}")
        return True
        
    except Exception as e:
        print(f"Error generating rulebook: {e}")
        return False

def generate_role_cards(idea: Dict[str, Any], rule_file_path: str, card_template_path: str, output_dir: str, llm_client, generated_images: Dict[str, str] = None) -> List[str]:
    """Generate role cards using single LLM call"""
    
    # Read rule file
    with open(rule_file_path, 'r', encoding='utf-8') as f:
        rule_content = f.read()
    
    # Read card template
    with open(card_template_path, 'r', encoding='utf-8') as f:
        template_content = f.read()
    
    # Create image filename mapping for roles
    import re
    image_mapping = {}
    if generated_images:
        for asset_key, filepath in generated_images.items():
            if asset_key.startswith('role_'):
                # Extract role name from asset key (e.g., 'role_mirror' -> 'MIRROR')
                role_key = asset_key[5:]  # Remove 'role_' prefix
                image_mapping[role_key.upper()] = filepath
                print(f"Image mapping: {role_key.upper()} -> {filepath}")
    
    # Create prompt for card generation
    from langchain.prompts import ChatPromptTemplate
    from langchain.schema import SystemMessage
    
    # Create image instructions
    image_list = "\n".join([f"   - {role}: {img}" for role, img in image_mapping.items()])
    image_instructions = f"""
AVAILABLE ROLE IMAGES:
{image_list}

Use the specific image filename for each role from the list above."""
    
    prompt = f"""TASK: Generate individual role card LaTeX files for a social deduction game.

GAME INFORMATION:
Name: {idea.get("Name", "Custom Game")}
Title: {idea.get("Title", "Custom Social Deduction Game")}
Description: {idea.get("Experiment", "A new social deduction game")}

RULE FILE CONTENT:
```python
{rule_content}
```

CARD TEMPLATE:
```latex
{template_content}
```

{image_instructions}

INSTRUCTIONS:
1. Analyze the rule file to identify ALL playable roles in the game
2. For each role, create a separate LaTeX file using the template
3. Replace these placeholders in each card:
   - {{ROLE_COMMAND}} - Use appropriate command (\\createrolecard, \\createtownrolecard, \\createmafiarolecard, \\createneutralrolecard)
   - {{ROLE_NAME}} - Exact role name from the rules, but REPLACE UNDERSCORES WITH SPACES (e.g., "DOUBLE_AGENT" becomes "DOUBLE AGENT")
   - {{ROLE_TYPE}} - Role alignment/faction (Town, Mafia, Neutral, etc.)
   - {{ROLE_IMAGE}} - Use the specific image filename for this role from the available images list above
   - {{OBJECTIVE}} - What this role is trying to achieve (1-2 sentences)
   - {{ABILITIES}} - Special abilities and when they can be used (2-3 sentences)
   - {{VICTORY_CONDITION}} - How this role wins (1-2 sentences)
   - {{STRATEGY}} - Tips for playing this role (2-3 sentences)
   - {{WARNINGS}} - Important warnings or notes (1-2 sentences)

4. Choose the appropriate role command based on alignment:
   - \\createtownrolecard for town/good roles (blue border)
   - \\createmafiarolecard for mafia/evil roles (red border)
   - \\createneutralrolecard for neutral roles (orange border)
   - \\createrolecard for generic roles

5. IMPORTANT: Avoid LaTeX special characters in all text content:
   - Replace underscores (_) with spaces in role names and descriptions
   - Avoid using: # $ % & {{ }} ^ ~ backslash in any text content
   - Use plain text descriptions without LaTeX special characters

OUTPUT FORMAT:
Return a JSON object with role cards:
{{
  "cards": [
    {{
      "filename": "role_card_detective.tex",
      "content": "complete LaTeX content for this card"
    }},
    {{
      "filename": "role_card_mafia.tex", 
      "content": "complete LaTeX content for this card"
    }}
  ]
}}

Generate cards for ALL roles found in the rule file."""

    try:
        from langchain.output_parsers.json import SimpleJsonOutputParser
        
        card_generator = ChatPromptTemplate.from_messages([
            SystemMessage(content="You are a professional game designer creating role cards for social deduction games. Generate complete LaTeX files for each game role using the provided template. Always respond with valid JSON."),
            ("human", "{prompt}")
        ]) | llm_client | SimpleJsonOutputParser()
        
        response = card_generator.invoke({"prompt": prompt})
        
        generated_files = []
        
        if isinstance(response, dict) and "cards" in response:
            for card_data in response["cards"]:
                filename = card_data.get("filename", "role_card_unknown.tex")
                content = card_data.get("content", "")
                
                if content:
                    output_file = osp.join(output_dir, filename)
                    with open(output_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    generated_files.append(output_file)
                    print(f"Generated role card: {output_file}")
        
        return generated_files
        
    except Exception as e:
        print(f"Error generating role cards: {e}")
        return []

def generate_card_images(rule_file_path: str, output_dir: str, num_cards: int) -> Dict[str, str]:
    """Generate images for role cards using AI image generation"""
    import sys
    sys.path.append(osp.dirname(osp.dirname(output_dir)))  # Go up to AI-Scientist directory
    from ai_scientist.image_generator import GameImageGenerator, create_game_config_from_rules
    
    image_generator = GameImageGenerator()
    
    # Create game config from rules
    game_config = create_game_config_from_rules(rule_file_path)
    print(f"Game config: {game_config}")
    
    # Generate role images
    assets = image_generator.generate_game_assets(game_config, output_dir)
    
    print(f"Generated {len(assets)} image assets")
    return assets

def compile_latex(cwd: str, pdf_file: str, timeout: int = 30):
    """Compile LaTeX documents to PDF"""
    print("COMPILING LATEX DOCUMENTS")

    # Compile main manual (manual.tex instead of template.tex)
    commands = [
        ["pdflatex", "-interaction=nonstopmode", "manual.tex"],
        ["pdflatex", "-interaction=nonstopmode", "manual.tex"],
    ]

    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout,
            )
            if result.returncode != 0:
                print(f"LaTeX command failed: {' '.join(command)}")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
        except subprocess.TimeoutExpired:
            print(f"LaTeX timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            print(f"Error running command {' '.join(command)}: {e}")

    # Move main PDF
    manual_pdf = osp.join(cwd, "manual.pdf")
    try:
        if osp.exists(manual_pdf):
            shutil.move(manual_pdf, pdf_file)
            print(f"Successfully moved main PDF to: {pdf_file}")
        else:
            print(f"Manual PDF not found at: {manual_pdf}")
    except Exception as e:
        print(f"Error moving main PDF: {e}")

    # Compile role cards
    print("COMPILING ROLE CARDS")
    role_card_files = glob.glob(osp.join(cwd, "role_card_*.tex"))
    
    for role_card_file in role_card_files:
        filename = osp.basename(role_card_file)
        base_name = filename[:-4]  # Remove .tex extension
        
        print(f"Compiling role card: {filename}")
        
        try:
            # Run pdflatex for role cards
            commands = [
                ["pdflatex", "-interaction=nonstopmode", filename],
                ["pdflatex", "-interaction=nonstopmode", filename]  # Second pass
            ]
            
            for command in commands:
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=timeout,
                )
            
            pdf_file_card = osp.join(cwd, f"{base_name}.pdf")
            if osp.exists(pdf_file_card):
                print(f"Successfully generated: {pdf_file_card}")
            else:
                print(f"Failed to generate PDF for: {filename}")
                
        except subprocess.TimeoutExpired:
            print(f"Role card compilation timed out: {filename}")
        except subprocess.CalledProcessError as e:
            print(f"Error compiling role card {filename}: {e}")

    print("FINISHED COMPILING LATEX DOCUMENTS")

def perform_simplified_writeup(idea: Dict[str, Any], folder_name: str) -> bool:
    """
    Simplified writeup generation using only 2 LLM calls plus image generation and LaTeX compilation.
    """
    try:
        print(f"Starting simplified writeup for: {idea['Name']}")
        
        # 1. Find latest rule file
        rule_file_path = find_latest_rule_file(folder_name)
        print(f"Found rule file: {rule_file_path}")
        
        # 2. Set up paths
        latex_dir = osp.join(folder_name, "latex")
        template_tex_path = osp.join(latex_dir, "template.tex")
        manual_tex_path = osp.join(latex_dir, "manual.tex")
        card_template_path = osp.join(latex_dir, "role_card_template.tex")
        
        if not osp.exists(template_tex_path):
            raise FileNotFoundError(f"Template not found: {template_tex_path}")
        if not osp.exists(card_template_path):
            raise FileNotFoundError(f"Card template not found: {card_template_path}")
        
        # 3. Create LLM client
        llm_client, model_name = create_llm_client()
        print(f"Using LLM model: {model_name}")
        
        # 4. Generate rulebook (LLM Call #1) - Save as manual.tex instead of overwriting template.tex
        print("Generating rulebook...")
        rulebook_success = generate_rulebook(
            idea, rule_file_path, template_tex_path, manual_tex_path, llm_client
        )
        
        if not rulebook_success:
            print("Failed to generate rulebook")
            return False
        
        # 5. Generate card images first (AI Image Generation)
        print("Generating card images...")
        generated_images = generate_card_images(rule_file_path, latex_dir, 0)  # num_cards not needed anymore
        
        # 6. Generate role cards with correct image filenames (LLM Call #2)
        print("Generating role cards...")
        generated_card_files = generate_role_cards(
            idea, rule_file_path, card_template_path, latex_dir, llm_client, generated_images
        )
        
        if not generated_card_files:
            print("Warning: No role cards generated")
        
        # 6. Compile LaTeX
        print("Compiling LaTeX documents...")
        pdf_file = f"{folder_name}/{idea['Name']}_manual.pdf"
        compile_latex(latex_dir, pdf_file)
        
        print(f"Writeup completed successfully! Generated files:")
        print(f"  - Main manual: {pdf_file}")
        print(f"  - Role cards: {len(generated_card_files)} cards")
        print(f"  - Images: {len(generated_images)} images")
        
        return True
        
    except Exception as e:
        print(f"Error in simplified writeup: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Simplified writeup generation for social deduction games")
    parser.add_argument("--folder", type=str, required=True, help="Folder containing the game experiment")
    parser.add_argument("--ideas_file", type=str, help="Path to ideas.json file")
    args = parser.parse_args()
    
    folder_name = args.folder.rstrip('/')
    
    # Load idea information
    ideas_file = args.ideas_file or osp.join(folder_name, "ideas.json")
    if not osp.exists(ideas_file):
        print(f"Ideas file not found: {ideas_file}")
        return
    
    with open(ideas_file, "r") as f:
        ideas = json.load(f)
    
    # Find the matching idea based on folder name
    idea_name = "_".join(osp.basename(folder_name).split("_")[2:])  # Extract idea name from folder
    idea = None
    for idea_data in ideas:
        if idea_data["Name"] in idea_name:
            idea = idea_data
            break
    
    if not idea:
        print(f"Idea not found for folder: {folder_name}")
        return
    
    print(f"Processing idea: {idea['Name']}")
    
    # Run simplified writeup
    success = perform_simplified_writeup(idea, folder_name)
    
    if success:
        print("Writeup generation completed successfully!")
    else:
        print("Writeup generation failed!")

if __name__ == "__main__":
    main()
