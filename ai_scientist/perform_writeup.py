import argparse
import json
import os
import os.path as osp
import re
import shutil
import subprocess
from typing import Optional, Tuple
import glob

from ai_scientist.generate_ideas import search_web_content
from ai_scientist.llm import get_response_from_llm, extract_json_between_markers, create_client, AVAILABLE_LLMS


# GENERATE LATEX
def generate_latex(coder, folder_name, pdf_file, timeout=30, num_error_corrections=5):
    folder = osp.abspath(folder_name)
    cwd = osp.join(folder, "latex")  # Fixed potential issue with path
    writeup_file = osp.join(cwd, "template.tex")

    # Check all references are valid and in the references.bib file
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    cites = re.findall(r"\\cite[a-z]*{([^}]*)}", tex_text)
    references_bib = re.search(
        r"\\begin{filecontents}{references.bib}(.*?)\\end{filecontents}",
        tex_text,
        re.DOTALL,
    )
    if references_bib is None:
        print("No references.bib found in template.tex")
        return
    bib_text = references_bib.group(1)
    cites = [cite.strip() for item in cites for cite in item.split(",")]
    for cite in cites:
        if cite not in bib_text:
            print(f"Reference {cite} not found in references.")
            prompt = f"""Reference {cite} not found in references.bib. Is this included under a different name?
If so, please modify the citation in template.tex to match the name in references.bib at the top. Otherwise, remove the cite."""
            coder.run(prompt)

    # Check all included figures are actually in the directory.
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    referenced_figs = re.findall(r"\\includegraphics.*?{(.*?)}", tex_text)
    all_figs = [f for f in os.listdir(folder) if f.endswith(".png")]
    for figure in referenced_figs:
        if figure not in all_figs:
            print(f"Figure {figure} not found in directory.")
            prompt = f"""The image {figure} not found in the directory. The images in the directory are: {all_figs}.
Please ensure that the figure is in the directory and that the filename is correct. Check the notes to see what each figure contains."""
            coder.run(prompt)

    # Remove duplicate figures.
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    referenced_figs = re.findall(r"\\includegraphics.*?{(.*?)}", tex_text)
    duplicates = {x for x in referenced_figs if referenced_figs.count(x) > 1}
    if duplicates:
        for dup in duplicates:
            print(f"Duplicate figure found: {dup}.")
            prompt = f"""Duplicate figures found: {dup}. Ensure any figure is only included once.
If duplicated, identify the best location for the figure and remove any other."""
            coder.run(prompt)

    # Remove duplicate section headers.
    with open(writeup_file, "r") as f:
        tex_text = f.read()
    sections = re.findall(r"\\section{([^}]*)}", tex_text)
    duplicates = {x for x in sections if sections.count(x) > 1}
    if duplicates:
        for dup in duplicates:
            print(f"Duplicate section header found: {dup}")
            prompt = f"""Duplicate section header found: {dup}. Ensure any section header is declared once.
If duplicated, identify the best location for the section header and remove any other."""
            coder.run(prompt)

    # Iteratively fix any LaTeX bugs
    for i in range(num_error_corrections):
        # Filter trivial bugs in chktex
        check_output = os.popen(f"chktex {writeup_file} -q -n2 -n24 -n13 -n1").read()
        if check_output:
            prompt = f"""Please fix the following LaTeX errors in `template.tex` guided by the output of `chktek`:
{check_output}.

Make the minimal fix required and do not remove or change any packages.
Pay attention to any accidental uses of HTML syntax, e.g. </end instead of \\end.
"""
            coder.run(prompt)
        else:
            break
    compile_latex(cwd, pdf_file, timeout=timeout)
    compile_role_cards(cwd, timeout=timeout)


def compile_latex(cwd, pdf_file, timeout=30):
    print("GENERATING LATEX")

    commands = [
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["bibtex", "template"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
        ["pdflatex", "-interaction=nonstopmode", "template.tex"],
    ]

    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            print("Standard Output:\n", result.stdout)
            print("Standard Error:\n", result.stderr)
        except subprocess.TimeoutExpired:
            print(f"Latex timed out after {timeout} seconds")
        except subprocess.CalledProcessError as e:
            print(f"Error running command {' '.join(command)}: {e}")

    print("FINISHED GENERATING LATEX")

    # Attempt to move the PDF to the desired location
    template_pdf = osp.join(cwd, "template.pdf")
    try:
        if osp.exists(template_pdf):
            shutil.move(template_pdf, pdf_file)
            print(f"Successfully moved PDF to: {pdf_file}")
        else:
            print(f"Template PDF not found at: {template_pdf}")
            # Try alternative compilation without bibtex if first attempt failed
            print("Attempting simpler compilation...")
            subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "template.tex"],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            if osp.exists(template_pdf):
                shutil.move(template_pdf, pdf_file)
                print(f"Successfully moved PDF to: {pdf_file} (simple compilation)")
            else:
                print("Failed to generate PDF even with simple compilation")
    except Exception as e:
        print(f"Error moving PDF: {e}")
        # Try copying instead of moving as fallback
        if osp.exists(template_pdf):
            try:
                shutil.copy2(template_pdf, pdf_file)
                print(f"Successfully copied PDF to: {pdf_file}")
            except Exception as copy_error:
                print(f"Failed to copy PDF: {copy_error}")

def compile_role_cards(cwd, timeout=30):
    """Compile all role card LaTeX files in the directory using the D&D-style template."""
    print("GENERATING ROLE CARDS")
    
    # Find all role card tex files
    role_card_files = glob.glob(osp.join(cwd, "role_card_*.tex"))
    
    for role_card_file in role_card_files:
        filename = osp.basename(role_card_file)
        base_name = filename[:-4]  # Remove .tex extension
        
        print(f"Compiling role card: {filename}")
        
        try:
            # Run pdflatex multiple times for proper compilation
            commands = [
                ["pdflatex", "-interaction=nonstopmode", filename],
                ["pdflatex", "-interaction=nonstopmode", filename]  # Second pass for cross-references
            ]
            
            for command in commands:
                result = subprocess.run(
                    command,
                    cwd=cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout,
                )
            
            pdf_file = osp.join(cwd, f"{base_name}.pdf")
            if osp.exists(pdf_file):
                print(f"Successfully generated: {pdf_file}")
                
                # Also try to generate PNG for transparency if possible
                try:
                    subprocess.run(
                        ["convert", "-density", "300", f"{base_name}.pdf", f"{base_name}.png"],
                        cwd=cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        timeout=timeout,
                    )
                    png_file = osp.join(cwd, f"{base_name}.png")
                    if osp.exists(png_file):
                        print(f"Successfully generated PNG: {png_file}")
                except:
                    pass  # PNG generation is optional
            else:
                print(f"Failed to generate PDF for: {filename}")
                
        except subprocess.TimeoutExpired:
            print(f"Role card compilation timed out after {timeout} seconds: {filename}")
        except subprocess.CalledProcessError as e:
            print(f"Error compiling role card {filename}: {e}")
    
    print("FINISHED GENERATING ROLE CARDS")


per_section_tips = {
    "Abstract": """
- TL;DR of the paper
- What are we trying to do and why is it relevant?
- Why is this hard? 
- How do we solve it (i.e. our contribution!)
- How do we verify that we solved it (e.g. Experiments and results)

Please make sure the abstract reads smoothly and is well-motivated. This should be one continuous paragraph with no breaks between the lines.
""",
    "Introduction": """
- Longer version of the Abstract, i.e. of the entire paper
- What are we trying to do and why is it relevant?
- Why is this hard? 
- How do we solve it (i.e. our contribution!)
- How do we verify that we solved it (e.g. Experiments and results)
- New trend: specifically list your contributions as bullet points
- Extra space? Future work!
""",
    "Related Work": """
- Academic siblings of our work, i.e. alternative attempts in literature at trying to solve the same problem. 
- Goal is to "Compare and contrast" - how does their approach differ in either assumptions or method? If their method is applicable to our Problem Setting I expect a comparison in the experimental section. If not, there needs to be a clear statement why a given method is not applicable. 
- Note: Just describing what another paper is doing is not enough. We need to compare and contrast.
""",
    "Background": """
- Academic Ancestors of our work, i.e. all concepts and prior work that are required for understanding our method. 
- Usually includes a subsection, Problem Setting, which formally introduces the problem setting and notation (Formalism) for our method. Highlights any specific assumptions that are made that are unusual. 
- Note: If our paper introduces a novel problem setting as part of its contributions, it's best to have a separate Section.
""",
    "Method": """
- What we do. Why we do it. All described using the general Formalism introduced in the Problem Setting and building on top of the concepts / foundations introduced in Background.
""",
    "Experimental Setup": """
- How do we test that our stuff works? Introduces a specific instantiation of the Problem Setting and specific implementation details of our Method for this Problem Setting.
- Do not imagine unknown hardware details.
- Includes a description of the dataset, evaluation metrics, important hyperparameters, and implementation details.
""",
    "Results": """
- Shows the results of running Method on our problem described in Experimental Setup.
- Includes statements on hyperparameters and other potential issues of fairness.
- Only includes results that have actually been run and saved in the logs. Do not hallucinate results that don't exist.
- If results exist: compares to baselines and includes statistics and confidence intervals. 
- If results exist: includes ablation studies to show that specific parts of the method are relevant.
- Discusses limitations of the method.
- Make sure to include all the results from the experiments, and include all relevant figures.
""",
    "Conclusion": """
- Brief recap of the entire paper.
- To keep going with the analogy, you can think of future work as (potential) academic offspring.
""",
}

error_list = """- Unenclosed math symbols
- Only reference figures that exist in our directory
- LaTeX syntax errors
- Numerical results that do not come from explicit experiments and logs
- Repeatedly defined figure labels
- References to papers that are not in the .bib file, DO NOT ADD ANY NEW CITATIONS!
- Unnecessary verbosity or repetition, unclear text
- Results or insights in the `notes.txt` that have not yet need included
- Any relevant figures that have not yet been included in the text
- Closing any \\begin{{figure}} with a \\end{{figure}} and \\begin{{table}} with a \\end{{table}}, etc.
- Duplicate headers, e.g. duplicated \\section{{Introduction}} or \\end{{document}}
- Unescaped symbols, e.g. shakespeare_char should be shakespeare\\_char in text
- Incorrect closing of environments, e.g. </end{{figure}}> instead of \\end{{figure}}
"""

refinement_prompt = (
    """Great job! Now criticize and refine only the {section} that you just wrote.
Make this complete in this pass, do not leave any placeholders.

Pay particular attention to fixing any errors such as:
"""
    + error_list
)

second_refinement_prompt = (
    """Criticize and refine the {section} only. Recall the advice:
{tips}
Make this complete in this pass, do not leave any placeholders.

Pay attention to how it fits in with the rest of the paper.
Identify any redundancies (e.g. repeated figures or repeated text), if there are any, decide where in the paper things should be cut.
Identify where we can save space, and be more concise without weakening the message of the text.
Fix any remaining errors as before:
"""
    + error_list
)

# CITATION HELPERS
citation_system_msg = """You are an ambitious AI PhD student who is looking to publish a paper that will contribute significantly to the field.
You have already written an initial draft of the paper and now you are looking to add missing citations to related papers throughout the paper.
The related work section already has some initial comments on which papers to add and discuss.

Focus on completing the existing write-up and do not add entirely new elements unless necessary.
Ensure every point in the paper is substantiated with sufficient evidence.
Feel free to add more cites to a particular point if there is only one or two references.
Ensure no paper is cited without a corresponding reference in the `references.bib` file.
Ensure each paragraph of the related work has sufficient background, e.g. a few papers cited.
You will be given access to the Semantic Scholar API, only add citations that you have found using the API.
Aim to discuss a broad range of relevant papers, not just the most popular ones.
Make sure not to copy verbatim from prior literature to avoid plagiarism.

You will be prompted to give a precise description of where and how to add the cite, and a search query for the paper to be cited.
Finally, you will select the most relevant cite from the search results (top 10 results will be shown).
You will have {total_rounds} rounds to add to the references, but do not need to use them all.

DO NOT ADD A CITATION THAT ALREADY EXISTS!"""

citation_first_prompt = '''Round {current_round}/{total_rounds}:

You have written this LaTeX draft so far:

"""
{draft}
"""

Identify the most important citation that you still need to add, and the query to find the paper.

Respond in the following format:

THOUGHT:
<THOUGHT>

RESPONSE:
```json
<JSON>
```

In <THOUGHT>, first briefly reason over the paper and identify where citations should be added.
If no more citations are needed, add "No more citations needed" to your thoughts.
Do not add "No more citations needed" if you are adding citations this round.

In <JSON>, respond in JSON format with the following fields:
- "Description": A precise description of the required edit, along with the proposed text and location where it should be made.
- "Query": The search query to find the paper (e.g. attention is all you need).

Ensure the description is sufficient to make the change without further context. Someone else will make the change.
The query will work best if you are able to recall the exact name of the paper you are looking for, or the authors.
This JSON will be automatically parsed, so ensure the format is precise.'''

citation_second_prompt = """Search has recovered the following articles:

{papers}

Respond in the following format:

THOUGHT:
<THOUGHT>

RESPONSE:
```json
<JSON>
```

In <THOUGHT>, first briefly reason over the search results and identify which citation best fits your paper and the location is to be added at.
If none are appropriate, add "Do not add any" to your thoughts.

In <JSON>, respond in JSON format with the following fields:
- "Selected": A list of the indices of the selected papers to be cited, e.g. "[0, 1]". Can be "[]" if no papers are selected. This must be a string.
- "Description": Update the previous description of the required edit if needed. Ensure that any cites precisely match the name in the bibtex!!!

Do not select papers that are already in the `references.bib` file at the top of the draft, or if the same citation exists under a different name.
This JSON will be automatically parsed, so ensure the format is precise."""


def get_citation_aider_prompt(
        client, model, draft, current_round, total_rounds, engine="semanticscholar"
) -> Tuple[Optional[str], bool]:
    msg_history = []
    try:
        text, msg_history = get_response_from_llm(
            citation_first_prompt.format(
                draft=draft, current_round=current_round, total_rounds=total_rounds
            ),
            client=client,
            model=model,
            system_message=citation_system_msg.format(total_rounds=total_rounds),
            msg_history=msg_history,
        )
        if "No more citations needed" in text:
            print("No more citations needed.")
            return None, True

        ## PARSE OUTPUT
        json_output = extract_json_between_markers(text)
        assert json_output is not None, "Failed to extract JSON from LLM output"
        query = json_output["Query"]
        web_results = search_web_content(query, search_api=engine)
    except Exception as e:
        print(f"Error: {e}")
        return None, False

    if web_results is None or not web_results:
        print("No web results found.")
        return None, False

    # Format web results for display (different from academic papers)
    result_strings = []
    for i, result in enumerate(web_results):
        result_strings.append(
            """{i}: {title}\nURL: {url}\nContent: {snippet}""".format(
                i=i,
                title=result.get("title", "Unknown Title"),
                url=result.get("url", "No URL"),
                snippet=result.get("snippet", "No content available")
            )
        )
    results_str = "\n\n".join(result_strings)

    try:
        text, msg_history = get_response_from_llm(
            citation_second_prompt.format(
                papers=results_str,  # Use results_str for web content
                current_round=current_round,
                total_rounds=total_rounds,
            ),
            client=client,
            model=model,
            system_message=citation_system_msg.format(total_rounds=total_rounds),
            msg_history=msg_history,
        )
        if "Do not add any" in text:
            print("Do not add any.")
            return None, False
        ## PARSE OUTPUT
        json_output = extract_json_between_markers(text)
        assert json_output is not None, "Failed to extract JSON from LLM output"
        desc = json_output["Description"]
        selected_results = json_output["Selected"]
        selected_results = str(selected_results)

        # convert to list and create simple citations for web content
        if selected_results != "[]":
            selected_results = list(map(int, selected_results.strip("[]").split(",")))
            assert all(
                [0 <= i < len(web_results) for i in selected_results]
            ), "Invalid result index"
            
            # Create simple bibtex entries for web content
            bibtex_entries = []
            for idx in selected_results:
                result = web_results[idx]
                title = result.get("title", "Web Resource").replace("{", "").replace("}", "")
                url = result.get("url", "")
                # Create a simple bibtex entry
                key = f"web{idx}"
                bibtex = f"""@misc{{{key},
  title={{{title}}},
  url={{{url}}},
  note={{Accessed: \\today}}
}}"""
                bibtex_entries.append(bibtex)
            bibtex_string = "\n".join(bibtex_entries)
        else:
            return None, False

    except Exception as e:
        print(f"Error: {e}")
        return None, False

    # Add citation to draft
    aider_format = '''The following citations have just been added to the end of the `references.bib` file definition at the top of the file:
"""
{bibtex}
"""
You do not need to add them yourself.
ABSOLUTELY DO NOT ADD IT AGAIN!!!

Make the proposed change to the draft incorporating these new cites:
{description}

Use your judgment for whether these should be cited anywhere else.
Make sure that any citation precisely matches the name in `references.bib`. Change its name to the correct name in the bibtex if needed.
Ensure the citation is well-integrated into the text.'''

    aider_prompt = (
            aider_format.format(bibtex=bibtex_string, description=desc)
            + """\n You must use \cite or \citet to reference sources, do not manually type out titles or URLs."""
    )
    return aider_prompt, False


# Social deduction game manual section tips (Nier Automata style)
game_manual_section_tips = {
    "Title": """
- Should be catchy and descriptive of the game concept
- Include the core theme or unique mechanic
- Make it memorable and engaging
- Consider the target audience
- Use atmospheric and mysterious language when appropriate
""",
    "Game Overview": """
- Brief overview of the game concept and mechanics in a Nier Automata-style nierbox
- What makes this game unique in the social deduction genre
- Number of players and approximate play time
- Target audience and complexity level
- Key selling points that would attract players
""",
    "Introduction": """
- Welcome players to the game with an atmospheric quote
- Brief history or inspiration behind the game concept
- What players can expect from the experience
- Overview of how social deduction works in this context
- What makes this game different from others in the genre
""",
    "Game Foundation": """
- Detailed explanation of the core objective
- How players interact and what they're trying to achieve
- Basic game flow and structure
- Key concepts players need to understand
- Components and materials needed
""",
    "Characters and Roles": """
- Introduction to the role system
- Detailed description of each role in the game
- What each role is trying to achieve
- Special abilities and when they can be used
- How roles interact with each other
- Balancing information and strategy tips for each role
""",
    "Rules and Gameplay": """
- Step-by-step explanation of how a game progresses
- Different phases and what happens in each
- Detailed rules for all game mechanics
- How voting, discussion, and special abilities work
- Communication rules and restrictions
- Victory conditions and how each side wins
""",
    "Strategy and Mastery": """
- General strategy advice for all players
- Role-specific tips and tactics
- Common mistakes to avoid
- How to read other players and deduce information
- Balancing cooperation and competition
- Advanced variants and optional rules
""",
}

def perform_game_manual_writeup(
        idea, folder_name, coder, cite_client, cite_model, num_cite_rounds=10, engine="semanticscholar"
):
    """
    Generate a game manual using Nier Automata-style template with OpenAI image generation.
    """
    import os.path as osp
    
    # Import image generation capabilities
    try:
        import sys
        sys.path.append(osp.dirname(osp.dirname(folder_name)))  # Go up to AI-Scientist directory
        from ai_scientist.image_generator import GameImageGenerator, create_game_config_from_rules
        image_generator = GameImageGenerator()
        generate_images = True
    except Exception as e:
        print(f"Image generation not available: {e}")
        generate_images = False
    
    # CURRENTLY ASSUMES LATEX
    title_overview_prompt = f"""We've provided the `latex/template.tex` file for a social deduction game manual using Nier Automata-style formatting. We will be filling it in section by section.

First, please fill in the "Title" and "Game Overview" sections of the manual. Note that this template uses a special nierbox for the game overview instead of a traditional abstract.

This is for the game idea: {idea['Title']}
Description: {idea['Experiment']}

Some tips are provided below:
{game_manual_section_tips["Title"]}
{game_manual_section_tips["Game Overview"]}

The title should be engaging and reflect the unique aspects of this social deduction game.
The game overview should be placed in the nierbox with title "Game at a Glance" and give readers a clear understanding of what the game is about, how many players it supports, and what makes it interesting.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
Update the cover image comment to show the path will be cover_image.png when generated.
"""
    coder_out = coder.run(title_overview_prompt)
    
    # Generate each section of the game manual (updated for Dragonbane structure)
    for section in [
        "Introduction",
        "Game Foundation", 
        "Characters and Roles",
        "Rules and Gameplay",
        "Strategy and Mastery",
    ]:
        section_prompt = f"""Please fill in the {section} section of the game manual using the Nier Automata template structure.

This is for the game idea: {idea['Title']}
Description: {idea['Experiment']}

Some tips are provided below:
{game_manual_section_tips[section]}

Important: Use the Nier Automata template elements like:
- nierbox for important information boxes
- nierquote for atmospheric quotes
- nierquotebox for special highlighted content
- wrapfigure with nierbox for side information
- proper atmospheric styling with the Nier Automata theme

Be sure to make this section complete and self-contained. Players should be able to understand and play the game based on this manual.
Focus on clarity, completeness, and ensuring players can actually reproduce and play this game.

IMPORTANT: When writing the {section} section, you have access to the generated game rule files (*.py files).
These contain the detailed game mechanics, role definitions, victory conditions, and implementation details.
Use the rule files to provide concrete details about the social deduction game that was created.

Before every paragraph, please include a brief description of what you plan to write in that paragraph in a comment.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
"""
        coder_out = coder.run(section_prompt)
        
        # Refinement prompt for each section
        refinement_prompt = f"""Great job! Now criticize and refine only the {section} section that you just wrote.
Make this complete in this pass, do not leave any placeholders.

Focus on:
- **Completeness** – can someone reproduce the game from this manual?
- **Clarity** – is it easy to understand for the target audience?
- **Conciseness** – avoid unnecessary verbosity while maintaining completeness
- **Nier Automata Style** – proper use of template elements and atmospheric theming

Pay particular attention to fixing any errors such as:
- Unclear or missing rules
- Inconsistent terminology
- Missing information needed to play
- Overly complex explanations
- Gaps in the game flow or mechanics
- Improper use of Nier Automata template elements
"""
        coder_out = coder.run(refinement_prompt)

    # Generate images if available
    if generate_images:
        try:
            # Find rule files to extract game information
            rule_files = []
            for py_file in glob.glob(osp.join(folder_name, "*.py")):
                if osp.basename(py_file) not in {'experiment.py', 'plot.py', '__init__.py'}:
                    rule_files.append(py_file)
            
            if rule_files:
                # Create game config from the first rule file
                game_config = create_game_config_from_rules(rule_files[0])
                
                # Update with idea information
                game_config['title'] = idea.get('Title', game_config['title'])
                
                # Generate images
                print("Generating game images...")
                assets = image_generator.generate_game_assets(game_config, folder_name)
                
                if assets:
                    print(f"Generated {len(assets)} image assets")
                    
                    # Update template to include cover image
                    if 'cover' in assets:
                        cover_prompt = f"""The cover image has been generated at {assets['cover']}. 
Please update the template.tex file to uncomment and use the cover image in the title page.
Replace the commented includegraphics line with the actual image inclusion."""
                        coder_out = coder.run(cover_prompt)
                        
        except Exception as e:
            print(f"Error generating images: {e}")

    # Generate role cards if we have role information
    try:
        role_card_prompt = f"""Now let's create individual role cards using the D&D-style role card template.

Based on the roles defined in the game manual and rule files, create a separate LaTeX file for each role card.
Name these files like role_card_[rolename].tex in the latex directory.

Each role card should include:
- Role name and type/alignment
- Generated role image (if available)
- Objective description
- Special abilities and powers
- Victory condition
- Strategy tip for playing the role
- Any warnings or important notes

Use one of these role card commands with these parameters:
\\createrolecard{{Role Name}}{{Role Type}}{{role_image.png}}{{Objective}}{{Abilities}}{{Victory}}{{Strategy}}{{Warnings}}
\\createtownrolecard{{Role Name}}{{Role Type}}{{role_image.png}}{{Objective}}{{Abilities}}{{Victory}}{{Strategy}}{{Warnings}} (Blue border)
\\createmafiarolecard{{Role Name}}{{Role Type}}{{role_image.png}}{{Objective}}{{Abilities}}{{Victory}}{{Strategy}}{{Warnings}} (Red border)
\\createneutralrolecard{{Role Name}}{{Role Type}}{{role_image.png}}{{Objective}}{{Abilities}}{{Victory}}{{Strategy}}{{Warnings}} (Orange border)

The role cards should be styled appropriately for each role type (town, mafia, neutral, etc.) using the color schemes defined in roleCardSettings.tex.

Create these as separate files so they can be compiled individually for printing and use during gameplay."""
        
        coder_out = coder.run(role_card_prompt)
        
    except Exception as e:
        print(f"Error creating role cards: {e}")

    # Add optional citations if needed (fewer for game manuals)
    for _ in range(min(num_cite_rounds, 3)):  # Limit citations for game manuals
        with open(osp.join(folder_name, "latex", "template.tex"), "r") as f:
            draft = f.read()
        prompt, done = get_citation_aider_prompt(
            cite_client, cite_model, draft, _, 3, engine=engine
        )
        if done:
            break
        if prompt is not None:
            # extract bibtex string
            bibtex_string = prompt.split('"""')[1]
            # insert this into draft before the "\end{filecontents}" line
            search_str = r"\end{filecontents}"
            draft = draft.replace(search_str, f"{bibtex_string}{search_str}")
            with open(osp.join(folder_name, "latex", "template.tex"), "w") as f:
                f.write(draft)
            coder_out = coder.run(prompt)

    ## FINAL REFINEMENT LOOP
    coder.run(
        """Great job! Now that there is a complete draft of the entire game manual, let's do a final refinement pass.

Focus on ensuring the manual is:
1. **Complete** - Players can learn and play the game from this manual alone
2. **Clear** - Rules and procedures are easy to understand
3. **Consistent** - Terminology and references are used consistently throughout
4. **Engaging** - The manual makes the game sound fun and interesting to play
5. **Nier Automata Style** - Proper use of template elements and atmospheric theming

Go through each section and make any final improvements needed. Pay special attention to:
- Making sure all game mechanics are clearly explained
- Ensuring role abilities are fully detailed using nierbox elements
- Verifying that victory conditions are unambiguous
- Checking that the game flow makes sense from start to finish
- Ensuring proper use of nierbox, nierquote, and wrapfigure environments
- Maintaining the atmospheric and mysterious tone throughout
"""
    )
    
    # Generate final PDF with both manual and role cards
    generate_latex(coder, folder_name, f"{folder_name}/{idea['Name']}_manual.pdf")


# PERFORM WRITEUP
def perform_writeup(
        idea, folder_name, coder, cite_client, cite_model, num_cite_rounds=20, engine="semanticscholar"
):
    # CURRENTLY ASSUMES LATEX
    abstract_prompt = f"""We've provided the `latex/template.tex` file to the project. We will be filling it in section by section.

First, please fill in the "Title" and "Abstract" sections of the writeup.

Some tips are provided below:
{per_section_tips["Abstract"]}

Before every paragraph, please include a brief description of what you plan to write in that paragraph in a comment.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
"""
    coder_out = coder.run(abstract_prompt)
    coder_out = coder.run(
        refinement_prompt.format(section="Abstract")
        .replace(r"{{", "{")
        .replace(r"}}", "}")
    )
    for section in [
        "Introduction",
        "Background",
        "Method",
        "Experimental Setup",
        "Results",
        "Conclusion",
    ]:
        section_prompt = f"""Please fill in the {section} of the writeup. Some tips are provided below:
{per_section_tips[section]}

Be sure to use \cite or \citet where relevant, referring to the works provided in the file.
Do not cite anything that is not already in `references.bib`. Do not add any new entries to this.

Keep the experimental results (figures and tables) only in the Results section, and make sure that any captions are filled in.
In this pass, do not reference anything in later sections of the paper.

IMPORTANT: When writing the {section} section, you have access to the generated game rule files (*.py files).
These contain the detailed game mechanics, role definitions, victory conditions, and implementation details.
For the Method section: Describe the actual game rules and mechanics that were implemented.
For the Experimental Setup section: Reference how the game was configured and what specific rules were tested.
Use the rule files to provide concrete details about the social deduction game that was created.

Before every paragraph, please include a brief description of what you plan to write in that paragraph in a comment.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
"""
        coder_out = coder.run(section_prompt)
        coder_out = coder.run(
            refinement_prompt.format(section=section)
            .replace(r"{{", "{")
            .replace(r"}}", "}")
        )

    # SKETCH THE RELATED WORK
    section_prompt = f"""Please fill in the Related Work of the writeup. Some tips are provided below:

{per_section_tips["Related Work"]}

For this section, very briefly sketch out the structure of the section, and clearly indicate what papers you intend to include.
Do this all in LaTeX comments using %.
The related work should be concise, only plan to discuss the most relevant work.
Do not modify `references.bib` to add any new citations, this will be filled in at a later stage.

Be sure to first name the file and use *SEARCH/REPLACE* blocks to perform these edits.
"""
    coder_out = coder.run(section_prompt)

    # Fill paper with cites.
    for _ in range(num_cite_rounds):
        with open(osp.join(folder_name, "latex", "template.tex"), "r") as f:
            draft = f.read()
        prompt, done = get_citation_aider_prompt(
            cite_client, cite_model, draft, _, num_cite_rounds, engine=engine
        )
        if done:
            break
        if prompt is not None:
            # extract bibtex string
            bibtex_string = prompt.split('"""')[1]
            # insert this into draft before the "\end{filecontents}" line
            search_str = r"\end{filecontents}"
            draft = draft.replace(search_str, f"{bibtex_string}{search_str}")
            with open(osp.join(folder_name, "latex", "template.tex"), "w") as f:
                f.write(draft)
            coder_out = coder.run(prompt)

    coder_out = coder.run(
        refinement_prompt.format(section="Related Work")
        .replace(r"{{", "{")
        .replace(r"}}", "}")
    )

    ## SECOND REFINEMENT LOOP
    coder.run(
        """Great job! Now that there is a complete draft of the entire paper, let's refine each section again.
First, re-think the Title if necessary. Keep this concise and descriptive of the paper's concept, but try by creative with it."""
    )
    for section in [
        "Abstract",
        "Related Work",
        "Introduction",
        "Background",
        "Method",
        "Experimental Setup",
        "Results",
        "Conclusion",
    ]:
        coder_out = coder.run(
            second_refinement_prompt.format(
                section=section, tips=per_section_tips[section]
            )
            .replace(r"{{", "{")
            .replace(r"}}", "}")
        )

    generate_latex(coder, folder_name, f"{folder_name}/{idea['Name']}.pdf")


if __name__ == "__main__":
    from aider.coders import Coder
    from aider.models import Model
    from aider.io import InputOutput
    import json

    parser = argparse.ArgumentParser(description="Perform writeup for a project")
    parser.add_argument("--folder", type=str)
    parser.add_argument("--no-writing", action="store_true", help="Only generate")
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-05-13",
        choices=AVAILABLE_LLMS,
        help="Model to use for AI Scientist.",
    )
    parser.add_argument(
        "--engine",
        type=str,
        default="semanticscholar",
        choices=["semanticscholar", "openalex"],
        help="Scholar engine to use.",
    )
    args = parser.parse_args()
    client, client_model = create_client(args.model)
    print("Make sure you cleaned the Aider logs if re-generating the writeup!")
    folder_name = args.folder
    idea_name = osp.basename(folder_name)
    exp_file = osp.join(folder_name, "experiment.py")
    vis_file = osp.join(folder_name, "plot.py")
    notes = osp.join(folder_name, "notes.txt")
    model = args.model
    writeup_file = osp.join(folder_name, "latex", "template.tex")
    ideas_file = osp.join(folder_name, "ideas.json")
    
    # Find and include the generated rule file(s)
    rule_files = []
    
    # Load ideas to get the idea name
    with open(ideas_file, "r") as f:
        ideas = json.load(f)
    for idea in ideas:
        if idea["Name"] in idea_name:
            print(f"Found idea: {idea['Name']}")
            # Look for rule file with idea name
            rule_file = osp.join(folder_name, f"{idea['Name']}.py")
            if osp.exists(rule_file):
                rule_files.append(rule_file)
                print(f"Found rule file: {rule_file}")
            break
    
    # Also look for any other Python files that might be rule files
    # (excluding experiment.py, plot.py, and other standard files)
    excluded_files = {'experiment.py', 'plot.py', '__init__.py'}
    for py_file in glob.glob(osp.join(folder_name, "*.py")):
        if osp.basename(py_file) not in excluded_files and py_file not in rule_files:
            # Check if this looks like a rule file by looking for common patterns
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # Look for typical rule file patterns
                    if any(pattern in content for pattern in ['RULEBOOK', 'init_meta_pub', 'player_sys_prompt', 'assign_role']):
                        rule_files.append(py_file)
                        print(f"Found additional rule file: {py_file}")
            except Exception:
                pass  # Skip files we can't read
    
    if idea["Name"] not in idea_name:
        raise ValueError(f"Idea {idea_name} not found")
    
    # Include rule files in the files accessible to the AI coder
    fnames = [exp_file, writeup_file, notes] + rule_files
    print(f"Files accessible to AI coder: {fnames}")
    
    io = InputOutput(yes=True, chat_history_file=f"{folder_name}/{idea_name}_aider.txt")
    if args.model == "deepseek-coder-v2-0724":
        main_model = Model("deepseek/deepseek-coder")
    elif args.model == "llama3.1-405b":
        main_model = Model("openrouter/meta-llama/llama-3.1-405b-instruct")
    else:
        main_model = Model(model)
    coder = Coder.create(
        main_model=main_model,
        fnames=fnames,
        io=io,
        stream=False,
        use_git=False,
        edit_format="diff",
    )
    if args.no_writing:
        generate_latex(coder, args.folder, f"{args.folder}/test.pdf")
    else:
        try:
            # Check if this is a social deduction game template
            if "social_deduction_game" in folder_name:
                print("Detected social deduction game template, using Nier Automata-style game manual format")
                perform_game_manual_writeup(idea, folder_name, coder, client, client_model, engine=args.engine)
            else:
                print("Using traditional research paper format")
                perform_writeup(idea, folder_name, coder, client, client_model, engine=args.engine)
        except Exception as e:
            print(f"Failed to perform writeup: {e}")
