#!/usr/bin/env python3
"""
Simple test script to verify PDF generation for AI Scientist experiments.
"""

import os
import subprocess
import sys
from pathlib import Path

def test_pdf_generation(experiment_path):
    """Test PDF generation for a given experiment directory."""
    exp_path = Path(experiment_path)
    latex_dir = exp_path / "latex"
    template_tex = latex_dir / "template.tex"
    
    print(f"🔍 Testing PDF generation for: {exp_path.name}")
    
    if not latex_dir.exists():
        print(f"❌ No latex directory found in {experiment_path}")
        return False
        
    if not template_tex.exists():
        print(f"❌ No template.tex found in {latex_dir}")
        return False
    
    print(f"📄 Found template.tex, attempting compilation...")
    
    # Change to latex directory and compile
    original_cwd = os.getcwd()
    try:
        os.chdir(latex_dir)
        
        # Run pdflatex
        result = subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "template.tex"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        template_pdf = latex_dir / "template.pdf"
        if template_pdf.exists():
            # Extract experiment name (remove timestamp prefix)
            exp_name = exp_path.name
            if len(exp_name) > 17 and exp_name[8] == '_':  # Has timestamp prefix
                exp_name = exp_name[17:]  # Remove timestamp
            
            # Copy to expected location
            target_pdf = exp_path / f"{exp_name}.pdf"
            import shutil
            shutil.copy2(template_pdf, target_pdf)
            
            print(f"✅ Successfully generated: {target_pdf}")
            return True
        else:
            print(f"❌ PDF generation failed")
            print(f"   stdout: {result.stdout[:200]}...")
            print(f"   stderr: {result.stderr[:200]}...")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ PDF compilation timed out")
        return False
    except Exception as e:
        print(f"❌ Error during PDF generation: {e}")
        return False
    finally:
        os.chdir(original_cwd)

def main():
    if len(sys.argv) != 2:
        print("Usage: python test_pdf_generation.py <experiment_directory>")
        print("Example: python test_pdf_generation.py results/social_deduction_game/20250606_105908_secret_syndicate")
        sys.exit(1)
    
    experiment_path = sys.argv[1]
    success = test_pdf_generation(experiment_path)
    
    if success:
        print("🎉 PDF generation test passed!")
        sys.exit(0)
    else:
        print("💥 PDF generation test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main() 