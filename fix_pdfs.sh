#!/bin/bash

# Script to fix PDF generation for AI Scientist experiments
# Compiles LaTeX files and places PDFs in correct locations

echo "🔧 Fixing PDF generation for social deduction game experiments..."

# Find all LaTeX directories in recent experiments
latex_dirs=$(find results/social_deduction_game -name "latex" -type d | sort)

for latex_dir in $latex_dirs; do
    # Extract experiment directory and name
    exp_dir=$(dirname "$latex_dir")
    exp_name=$(basename "$exp_dir" | sed 's/^[0-9_]*//') # Remove timestamp prefix
    
    echo "📄 Processing: $exp_name"
    
    # Check if template.tex exists
    if [ -f "$latex_dir/template.tex" ]; then
        # Compile LaTeX
        echo "  🔨 Compiling LaTeX..."
        cd "$latex_dir"
        
        # Run pdflatex (suppress output for cleaner logs)
        pdflatex -interaction=nonstopmode template.tex > /dev/null 2>&1
        
        # Check if PDF was generated
        if [ -f "template.pdf" ]; then
            # Copy to expected location
            cp template.pdf "../${exp_name}.pdf"
            echo "  ✅ Generated: ${exp_name}.pdf"
            
            # Also ensure template.pdf stays in latex dir for backup
            echo "  📋 Backup saved in latex/ directory"
        else
            echo "  ❌ Failed to generate PDF for $exp_name"
        fi
        
        cd - > /dev/null  # Return to original directory
    else
        echo "  ⚠️  No template.tex found in $latex_dir"
    fi
    
    echo ""
done

echo "🎉 PDF generation complete!"
echo ""
echo "Generated PDFs:"
find results/social_deduction_game -name "*.pdf" -not -path "*/latex/*" | sort 