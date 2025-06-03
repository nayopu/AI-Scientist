import json
import os
import os.path as osp
import time
from typing import List, Dict, Union

import backoff
import requests

from ai_scientist.llm import get_response_from_llm, extract_json_between_markers, create_client, AVAILABLE_LLMS

# Removed S2_API_KEY since we're not using academic search anymore

idea_first_prompt = """{task_description}
<experiment.py>
{code}
</experiment.py>

Here are the game ideas that you have already generated:

'''
{prev_ideas_string}
'''

Come up with the next impactful and creative idea for social deduction games that you can feasibly implement with the code provided.
Note that you will not have access to any additional resources or external dependencies beyond what's provided.
Make sure your game idea is broadly appealing and has wider entertainment value beyond specific player groups.

Respond in the following format:

THOUGHT:
<THOUGHT>

NEW IDEA JSON:
```json
<JSON>
```

In <THOUGHT>, first briefly discuss your intuitions and motivations for the game idea. Detail your high-level design plan, necessary gameplay mechanics and ideal player experience. Justify how the game idea is different from the existing ones.

In <JSON>, provide the new game idea in JSON format with the following fields:
- "Name": A shortened descriptor of the idea. Lowercase, no spaces, underscores allowed.
- "Title": A title for the game, will be used for the manual writing.
- "Experiment": An outline of the game implementation. E.g. which mechanics need to be added, how gameplay will work, what roles exist, etc.
- "Interestingness": A rating from 1 to 10 (lowest to highest).
- "Feasibility": A rating from 1 to 10 (lowest to highest).
- "Novelty": A rating from 1 to 10 (lowest to highest).

Be cautious and realistic on your ratings.
This JSON will be automatically parsed, so ensure the format is precise.
You will have {num_reflections} rounds to iterate on the idea, but do not need to use them all.
"""

idea_reflection_prompt = """Round {current_round}/{num_reflections}.
In your thoughts, first carefully consider the quality, novelty, and feasibility of the game idea you just created.
Include any other factors that you think are important in evaluating the game idea.
Ensure the idea is clear and concise, and the JSON is the correct format.
Do not make things overly complicated.
In the next attempt, try and refine and improve your game idea.
Stick to the spirit of the original idea unless there are glaring issues.

Respond in the same format as before:
THOUGHT:
<THOUGHT>

NEW IDEA JSON:
```json
<JSON>
```

If there is nothing to improve, simply repeat the previous JSON EXACTLY after the thought and include "I am done" at the end of the thoughts but before the JSON.
ONLY INCLUDE "I am done" IF YOU ARE MAKING NO MORE CHANGES."""


# GENERATE IDEAS
def generate_ideas(
        base_dir,
        client,
        model,
        skip_generation=False,
        max_num_generations=20,
        num_reflections=5,
):
    if skip_generation:
        # Load existing ideas from file
        try:
            with open(osp.join(base_dir, "ideas.json"), "r") as f:
                ideas = json.load(f)
            print("Loaded existing ideas:")
            for idea in ideas:
                print(idea)
            return ideas
        except FileNotFoundError:
            print("No existing ideas found. Generating new ideas.")
        except json.JSONDecodeError:
            print("Error decoding existing ideas. Generating new ideas.")

    idea_str_archive = []
    with open(osp.join(base_dir, "seed_ideas.json"), "r") as f:
        seed_ideas = json.load(f)
    for seed_idea in seed_ideas:
        idea_str_archive.append(json.dumps(seed_idea))

    with open(osp.join(base_dir, "experiment.py"), "r") as f:
        code = f.read()

    with open(osp.join(base_dir, "prompt.json"), "r") as f:
        prompt = json.load(f)

    idea_system_prompt = prompt["system"]

    for _ in range(max_num_generations):
        print()
        print(f"Generating idea {_ + 1}/{max_num_generations}")
        try:
            prev_ideas_string = "\n\n".join(idea_str_archive)

            msg_history = []
            print(f"Iteration 1/{num_reflections}")
            text, msg_history = get_response_from_llm(
                idea_first_prompt.format(
                    task_description=prompt["task_description"],
                    code=code,
                    prev_ideas_string=prev_ideas_string,
                    num_reflections=num_reflections,
                ),
                client=client,
                model=model,
                system_message=idea_system_prompt,
                msg_history=msg_history,
            )
            ## PARSE OUTPUT
            json_output = extract_json_between_markers(text)
            assert json_output is not None, "Failed to extract JSON from LLM output"
            print(json_output)

            # Iteratively improve task.
            if num_reflections > 1:
                for j in range(num_reflections - 1):
                    print(f"Iteration {j + 2}/{num_reflections}")
                    text, msg_history = get_response_from_llm(
                        idea_reflection_prompt.format(
                            current_round=j + 2, num_reflections=num_reflections
                        ),
                        client=client,
                        model=model,
                        system_message=idea_system_prompt,
                        msg_history=msg_history,
                    )
                    ## PARSE OUTPUT
                    json_output = extract_json_between_markers(text)
                    assert (
                            json_output is not None
                    ), "Failed to extract JSON from LLM output"
                    print(json_output)

                    if "I am done" in text:
                        print(f"Idea generation converged after {j + 2} iterations.")
                        break

            idea_str_archive.append(json.dumps(json_output))
        except Exception as e:
            print(f"Failed to generate idea: {e}")
            continue

    ## SAVE IDEAS
    ideas = []
    for idea_str in idea_str_archive:
        ideas.append(json.loads(idea_str))

    with open(osp.join(base_dir, "ideas.json"), "w") as f:
        json.dump(ideas, f, indent=4)

    return ideas


# GENERATE IDEAS OPEN-ENDED
def generate_next_idea(
        base_dir,
        client,
        model,
        prev_idea_archive=[],
        num_reflections=5,
        max_attempts=10,
):
    idea_archive = prev_idea_archive
    original_archive_size = len(idea_archive)

    print(f"Generating idea {original_archive_size + 1}")

    if len(prev_idea_archive) == 0:
        print(f"First iteration, taking seed ideas")
        # seed the archive on the first run with pre-existing ideas
        with open(osp.join(base_dir, "seed_ideas.json"), "r") as f:
            seed_ideas = json.load(f)
        for seed_idea in seed_ideas[:1]:
            idea_archive.append(seed_idea)
    else:
        with open(osp.join(base_dir, "experiment.py"), "r") as f:
            code = f.read()
        with open(osp.join(base_dir, "prompt.json"), "r") as f:
            prompt = json.load(f)
        idea_system_prompt = prompt["system"]

        for _ in range(max_attempts):
            try:
                idea_strings = []
                for idea in idea_archive:
                    idea_strings.append(json.dumps(idea))
                prev_ideas_string = "\n\n".join(idea_strings)

                msg_history = []
                print(f"Iteration 1/{num_reflections}")
                text, msg_history = get_response_from_llm(
                    idea_first_prompt.format(
                        task_description=prompt["task_description"],
                        code=code,
                        prev_ideas_string=prev_ideas_string,
                        num_reflections=num_reflections,
                    )
                    + """
Completed ideas have an additional "Score" field which indicates the assessment by an expert game design reviewer.
This is on a standard 1-10 game quality scale.
Scores of 0 indicate the idea failed either during implementation, testing or reviewing.
""",
                    client=client,
                    model=model,
                    system_message=idea_system_prompt,
                    msg_history=msg_history,
                )
                ## PARSE OUTPUT
                json_output = extract_json_between_markers(text)
                assert json_output is not None, "Failed to extract JSON from LLM output"
                print(json_output)

                # Iteratively improve task.
                if num_reflections > 1:
                    for j in range(num_reflections - 1):
                        print(f"Iteration {j + 2}/{num_reflections}")
                        text, msg_history = get_response_from_llm(
                            idea_reflection_prompt.format(
                                current_round=j + 2, num_reflections=num_reflections
                            ),
                            client=client,
                            model=model,
                            system_message=idea_system_prompt,
                            msg_history=msg_history,
                        )
                        ## PARSE OUTPUT
                        json_output = extract_json_between_markers(text)
                        assert (
                                json_output is not None
                        ), "Failed to extract JSON from LLM output"
                        print(json_output)

                        if "I am done" in text:
                            print(
                                f"Idea generation converged after {j + 2} iterations."
                            )
                            break

                idea_archive.append(json_output)
                break
            except Exception as e:
                print(f"Failed to generate idea: {e}")
                continue

    ## SAVE IDEAS
    with open(osp.join(base_dir, "ideas.json"), "w") as f:
        json.dump(idea_archive, f, indent=4)

    return idea_archive


def on_backoff(details):
    print(
        f"Backing off {details['wait']:0.1f} seconds after {details['tries']} tries "
        f"calling function {details['target'].__name__} at {time.strftime('%X')}"
    )


# Academic paper search functionality removed - now using web search only
# Add web search function for game-related content
def search_web_games(query, result_limit=5):
    """Search the web for game-related content to check novelty"""
    try:
        # Use DuckDuckGo instant answer API for simple searches
        response = requests.get(
            "https://api.duckduckgo.com/",
            params={
                "q": f"{query} social deduction game board game mechanics",
                "format": "json",
                "no_redirect": "1",
                "no_html": "1"
            },
            timeout=10
        )
        
        if response.status_code in [200, 202]:  # Accept both 200 and 202
            data = response.json()
            results = []
            
            # Get related topics as search results
            related_topics = data.get("RelatedTopics", [])[:result_limit]
            for topic in related_topics:
                if isinstance(topic, dict) and "Text" in topic:
                    title = topic.get("FirstURL", "").split("/")[-1].replace("-", " ").title()
                    if not title:
                        title = "Related Topic"
                    results.append({
                        "title": title,
                        "snippet": topic["Text"],
                        "url": topic.get("FirstURL", "")
                    })
            
            # Also try to get abstract if available
            if data.get("Abstract"):
                results.insert(0, {
                    "title": data.get("AbstractSource", "Main Result"),
                    "snippet": data["Abstract"],
                    "url": data.get("AbstractURL", "")
                })
            
            # If still no results, provide a generic response
            if not results:
                results = [{
                    "title": "Search Query Analysis",
                    "snippet": f"Search performed for: '{query}'. Consider checking popular social deduction games like Mafia, Werewolf, The Resistance, Secret Hitler, or Avalon for similar mechanics. Also look into game databases like BoardGameGeek for comprehensive game listings.",
                    "url": "https://boardgamegeek.com"
                }]
                
            return results
        
        # If non-successful status code, return fallback
        return [{
            "title": "Search Query Analysis",
            "snippet": f"Search performed for: '{query}'. Consider checking popular social deduction games like Mafia, Werewolf, The Resistance, Secret Hitler, or Avalon for similar mechanics.",
            "url": "https://boardgamegeek.com"
        }]
        
    except Exception as e:
        print(f"Error in web search: {e}")
        # Return a fallback result even when search fails
        return [{
            "title": "Search Error - Manual Review Recommended",
            "snippet": f"Unable to search for '{query}' due to technical issues. Recommend manually checking BoardGameGeek, Wikipedia's list of social deduction games, or other game databases.",
            "url": "https://boardgamegeek.com"
        }]


novelty_system_msg = """You are an experienced game designer who is looking to create novel social deduction games.
You have a game idea and you want to check if it is novel or not. I.e., not overlapping significantly with existing games or already well explored mechanics.
Be a harsh critic for novelty, ensure there is a sufficient contribution in the idea for a new and interesting social deduction game.
You will be given access to web search to find relevant games and information to help you make your decision.
The search results will be presented to you.

You will be given {num_rounds} to decide on the novelty, but you do not need to use them all.
At any round, you may exit early and decide on the novelty of the idea.
Decide a game idea is novel if after sufficient searching, you have not found a game that significantly overlaps with your core mechanics and theme.
Decide a game idea is not novel, if you have found games that significantly overlap with your idea.

Focus on searching for:
1. Existing social deduction games with similar themes or mechanics
2. Board games, video games, or tabletop games with similar concepts
3. Game design patterns or mechanics that match your idea
4. Popular games in this genre

{task_description}
<experiment.py>
{code}
</experiment.py>
"""

novelty_prompt = '''Round {current_round}/{num_rounds}.
You have this social deduction game idea:

"""
{idea}
"""

The results of the last query are (empty on first round):
"""
{last_query_results}
"""

Respond in the following format:

THOUGHT:
<THOUGHT>

RESPONSE:
```json
<JSON>
```

In <THOUGHT>, first briefly reason over the game idea and identify any query that could help you make your decision.
Focus on the core mechanics, theme, and unique aspects of your game idea.
If you have made your decision, add "Decision made: novel." or "Decision made: not novel." to your thoughts.

In <JSON>, respond in JSON format with ONLY the following field:
- "Query": An optional search query to search for existing games (e.g. "time travel social deduction game", "corporate espionage board game", "quantum mechanics game"). You must make a query if you have not decided this round.

The query will work best if you search for specific game names, mechanics, or themes related to your idea.
This JSON will be automatically parsed, so ensure the format is precise.'''


def check_idea_novelty(
        ideas,
        base_dir,
        client,
        model,
        max_num_iterations=10,
        search_api="perplexity",
):
    with open(osp.join(base_dir, "experiment.py"), "r") as f:
        code = f.read()
    with open(osp.join(base_dir, "prompt.json"), "r") as f:
        prompt = json.load(f)
        task_description = prompt["task_description"]

    for idx, idea in enumerate(ideas):
        if "novel" in idea:
            print(f"Skipping idea {idx}, already checked.")
            continue

        print(f"\nChecking novelty of idea {idx}: {idea['Name']}")

        novel = False
        msg_history = []
        results_str = ""

        for j in range(max_num_iterations):
            try:
                text, msg_history = get_response_from_llm(
                    novelty_prompt.format(
                        current_round=j + 1,
                        num_rounds=max_num_iterations,
                        idea=idea,
                        last_query_results=results_str,
                    ),
                    client=client,
                    model=model,
                    system_message=novelty_system_msg.format(
                        num_rounds=max_num_iterations,
                        task_description=task_description,
                        code=code,
                    ),
                    msg_history=msg_history,
                )
                if "decision made: novel" in text.lower():
                    print("Decision made: novel after round", j)
                    novel = True
                    break
                if "decision made: not novel" in text.lower():
                    print("Decision made: not novel after round", j)
                    break

                ## PARSE OUTPUT
                json_output = extract_json_between_markers(text)
                assert json_output is not None, "Failed to extract JSON from LLM output"

                ## SEARCH FOR GAME CONTENT
                query = json_output["Query"]
                
                # Use the new web search functionality
                web_results = search_web_content(query, search_api=search_api, result_limit=5)
                if not web_results:
                    results_str = "No game-related content found."
                else:
                    result_strings = []
                    for i, result in enumerate(web_results):
                        result_strings.append(
                            """{i}: {title}\nURL: {url}\nContent: {snippet}""".format(
                                i=i,
                                title=result["title"],
                                url=result["url"],
                                snippet=result["snippet"]
                            )
                        )
                    results_str = "\n\n".join(result_strings)

            except Exception as e:
                print(f"Error: {e}")
                continue

        idea["novel"] = novel

    # Save results to JSON file
    results_file = osp.join(base_dir, "ideas.json")
    with open(results_file, "w") as f:
        json.dump(ideas, f, indent=4)

    return ideas


# Remove search_for_papers function and replace with web search only
def search_web_content(query, search_api="perplexity", result_limit=5):
    """Search the web for game-related content using specified API"""
    if search_api == "perplexity":
        return search_perplexity(query, result_limit)
    elif search_api == "openai":
        return search_openai(query, result_limit)
    elif search_api == "duckduckgo":
        return search_web_games(query, result_limit)  # Use DuckDuckGo
    else:
        return search_web_games(query, result_limit)  # Fallback to DuckDuckGo

def search_perplexity(query, result_limit=5):
    """Search using Perplexity API via OpenRouter"""
    try:
        import openai
        
        # Use OpenRouter to access Perplexity
        client = openai.OpenAI(
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1"
        )
        
        search_prompt = f"""Search for information about: {query}
        
Focus on finding:
- Existing social deduction games with similar mechanics
- Board games or video games with related themes
- Game design concepts or mechanics
- Rules or gameplay elements

Provide a brief summary of relevant findings."""

        response = client.chat.completions.create(
            model="perplexity/llama-3.1-sonar-large-128k-online",
            messages=[
                {"role": "user", "content": search_prompt}
            ],
            max_tokens=1000
        )
        
        content = response.choices[0].message.content
        
        # Parse the response into structured format
        results = [{
            "title": "Perplexity Search Results",
            "snippet": content,
            "url": "https://perplexity.ai"
        }]
        
        return results
        
    except Exception as e:
        print(f"Error in Perplexity search: {e}")
        return []

def search_openai(query, result_limit=5):
    """Search using OpenAI's response capabilities"""
    try:
        import openai
        
        client = openai.OpenAI(
            api_key=os.environ.get("OPENAI_API_KEY")
        )
        
        search_prompt = f"""Based on your knowledge, provide information about existing games, mechanics, or concepts related to: {query}

Focus on:
- Social deduction games with similar themes or mechanics
- Board games, card games, or digital games with related concepts
- Game design patterns or mechanics that might overlap
- Popular games in this space

Format your response as a brief analysis of what already exists in this space."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": search_prompt}
            ],
            max_tokens=800
        )
        
        content = response.choices[0].message.content
        
        # Parse the response into structured format
        results = [{
            "title": "OpenAI Knowledge Search",
            "snippet": content,
            "url": "https://openai.com"
        }]
        
        return results
        
    except Exception as e:
        print(f"Error in OpenAI search: {e}")
        return []


if __name__ == "__main__":
    MAX_NUM_GENERATIONS = 32
    NUM_REFLECTIONS = 5
    import argparse

    parser = argparse.ArgumentParser(description="Generate AI scientist ideas")
    # add type of experiment (nanoGPT, Boston, etc.)
    parser.add_argument(
        "--experiment",
        type=str,
        default="nanoGPT",
        help="Experiment to run AI Scientist on.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-2024-05-13",
        choices=AVAILABLE_LLMS,
        help="Model to use for AI Scientist.",
    )
    parser.add_argument(
        "--skip-idea-generation",
        action="store_true",
        help="Skip idea generation and use existing ideas.",
    )
    parser.add_argument(
        "--check-novelty",
        action="store_true",
        help="Check novelty of ideas.",
    )
    parser.add_argument(
        "--search-api",
        type=str,
        default="perplexity",
        choices=["perplexity", "openai", "duckduckgo"],
        help="Search API to use for novelty checking (perplexity via OpenRouter, OpenAI, or DuckDuckGo).",
    )
    args = parser.parse_args()

    # Create client
    client, client_model = create_client(args.model)

    base_dir = osp.join("templates", args.experiment)
    results_dir = osp.join("results", args.experiment)
    ideas = generate_ideas(
        base_dir,
        client=client,
        model=client_model,
        skip_generation=args.skip_idea_generation,
        max_num_generations=MAX_NUM_GENERATIONS,
        num_reflections=NUM_REFLECTIONS,
    )
    if args.check_novelty:
        ideas = check_idea_novelty(
            ideas,
            base_dir=base_dir,
            client=client,
            model=client_model,
            search_api=args.search_api,
        )
