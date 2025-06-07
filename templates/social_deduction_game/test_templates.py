#!/usr/bin/env python3
"""
Test script for the new Nier Automata-style social deduction game templates.
This demonstrates the image generation and template compilation functionality.
"""

import os
import sys
import subprocess
from pathlib import Path

# Add the AI-Scientist directory to the path
sys.path.append(str(Path(__file__).parent.parent.parent))

def test_template_compilation():
    """Test basic template compilation without image generation."""
    print("Testing basic template compilation...")
    
    latex_dir = Path(__file__).parent / "latex"
    os.chdir(latex_dir)
    
    try:
        # Test basic template compilation
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "template.tex"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if PDF was generated (LaTeX can produce PDFs even with warnings)
        if os.path.exists("template.pdf"):
            print("✓ Template compilation successful")
        else:
            print("✗ Template compilation failed")
            print("Error output:", result.stderr)
            
    except Exception as e:
        print(f"✗ Template compilation error: {e}")

def test_role_card_template():
    """Test role card template compilation."""
    print("Testing role card template compilation...")
    
    latex_dir = Path(__file__).parent / "latex"
    os.chdir(latex_dir)
    
    # Create a sample role card
    sample_role_card = """\\documentclass[20pt,border=5pt,transparent]{standalone}
\\usepackage[english]{babel}
\\usepackage[utf8]{inputenc}
\\usepackage[singlelinecheck=false]{caption}
\\usepackage{lipsum}
\\usepackage{listings}
\\usepackage{shortvrb}
\\usepackage{stfloats}
\\usepackage[svgnames]{xcolor}
\\usepackage{tcolorbox}
\\usepackage{tikz}
\\tcbuselibrary{skins}
\\usepackage{afterpage}
\\usepackage{ifthen}

\\captionsetup[table]{labelformat=empty,font={sf,sc,bf,},skip=0pt}
\\MakeShortVerb{|}
\\lstset{%
  basicstyle=\\ttfamily,
  language=[LaTeX]{TeX},
  breaklines=true,
}

% Include custom command definitions for role cards
\\input{roleCardCommands.tex}
\\input{roleCardSettings.tex}

% Card sizing
\\newboolean{autosizing}
\\setboolean{autosizing}{true} 
\\newlength{\\cardwidth}
\\newlength{\\cardheight}
\\setlength{\\cardwidth}{5in}
\\setlength{\\cardheight}{7in}

\\begin{document}

\\begin{rolecardauto}{Village Detective}
    \\begin{center}
        \\begin{tcolorbox}[width=\\linewidth, boxrule=3.0pt, colframe=black, boxsep=0pt, top=0pt, bottom=0pt, left=0pt, right=0pt, enhanced, borderline={0.5mm}{0mm}{black}, interior style={fill overzoom image=img/paper.jpg, fill image opacity=1}]
            % Placeholder for role image
            \\vspace{2cm}
            \\begin{center}
            \\Large Detective Image Here
            \\end{center}
            \\vspace{2cm}
        \\end{tcolorbox}
    \\end{center}
    
    \\begin{lowerpartauto}
        \\RoleType{Town}
        \\RoleObjective{Find and eliminate all threats to the town}
        \\RoleAbilities{Once per night, you may investigate a player to learn their alignment}
        \\VictoryCondition{All mafia and harmful neutrals are eliminated}
        \\StrategyTip{Share your investigation results carefully - false claims are common}
        \\RoleWarnings{Be careful not to reveal yourself too early to the mafia}
    \\end{lowerpartauto}
\\end{rolecardauto}

\\end{document}"""
    
    try:
        # Write sample role card
        with open("role_card_test_detective.tex", "w") as f:
            f.write(sample_role_card)
        
        # Compile the role card
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "role_card_test_detective.tex"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # Check if PDF was generated (LaTeX can produce PDFs even with warnings)
        if os.path.exists("role_card_test_detective.pdf"):
            print("✓ Role card compilation successful")
        else:
            print("✗ Role card compilation failed")
            print("Error output:", result.stderr)
            
    except Exception as e:
        print(f"✗ Role card compilation error: {e}")

def test_image_generation():
    """Test image generation functionality (requires OpenAI API key)."""
    print("Testing image generation...")
    
    try:
        from ai_scientist.image_generator import GameImageGenerator, create_game_config_from_rules
        
        # Check if API key is available
        if not os.getenv('OPENAI_API_KEY'):
            print("⚠ OpenAI API key not found. Skipping image generation test.")
            print("  Set OPENAI_API_KEY environment variable to test image generation.")
            return
        
        generator = GameImageGenerator()
        
        # Test game config creation
        test_config = {
            'title': 'Test Social Deduction Game',
            'theme': 'fantasy',
            'setting': 'medieval village',
            'roles': [
                {'name': 'Detective', 'description': 'A keen investigator with a magnifying glass'},
                {'name': 'Villager', 'description': 'An innocent townsperson'}
            ]
        }
        
        # Test cover image generation (this will use API credits)
        print("Generating test cover image...")
        cover_path = generator.generate_cover_image(test_config)
        
        if cover_path:
            print(f"✓ Cover image generated: {cover_path}")
        else:
            print("✗ Cover image generation failed")
            
    except ImportError:
        print("⚠ Image generation module not available")
    except Exception as e:
        print(f"✗ Image generation error: {e}")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Social Deduction Game Template Test Suite")
    print("=" * 60)
    
    # Change to the script directory
    script_dir = Path(__file__).parent
    original_dir = os.getcwd()
    
    try:
        test_template_compilation()
        print()
        test_role_card_template()
        print()
        test_image_generation()
        
    finally:
        os.chdir(original_dir)
    
    print("\n" + "=" * 60)
    print("Test suite completed!")
    print("=" * 60)

if __name__ == "__main__":
    main() 