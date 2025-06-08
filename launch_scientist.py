import argparse
import json
import multiprocessing
import os
import os.path as osp
import shutil
import sys
import time
import torch
from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model
from datetime import datetime

from ai_scientist.generate_ideas import generate_ideas, check_idea_novelty
from ai_scientist.llm import create_client, AVAILABLE_LLMS
from ai_scientist.perform_experiments import perform_experiments
from ai_scientist.perform_review import perform_review, load_paper, perform_improvement, perform_game_manual_review
from ai_scientist.perform_writeup import perform_writeup, generate_latex, perform_game_manual_writeup

NUM_REFLECTIONS = 3


def print_time():
    print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run AI scientist experiments")
    parser.add_argument(
        "--search-api",
        type=str,
        default="perplexity",
        choices=["perplexity", "openai", "duckduckgo"],
        help="Search API for novelty checking",
    )
    parser.add_argument(
        "--skip-idea-generation",
        action="store_true",
        help="Skip idea generation and use existing ideas",
    )
    parser.add_argument(
        "--skip-novelty-check", 
        action="store_true",
        help="Skip novelty checking of ideas",
    )
    parser.add_argument(
        "--experiment",
        type=str,
        default="social_deduction_game",
        help="Type of experiment to run",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run experiments in parallel",
    )
    parser.add_argument(
        "--writeup",
        type=str,
        default="latex",
        help="Writeup format to use",
    )
    parser.add_argument(
        "--improvement",
        action="store_true", 
        help="Enable writeup improvement",
    )
    parser.add_argument(
        "--docker",
        action="store_true",
        help="Use Docker for experiments",
    )
    parser.add_argument(
        "--docker-image",
        type=str,
        default="ai-scientist:latest",
        help="Docker image to use",
    )
    parser.add_argument(
        "--max-ideas",
        type=int,
        default=5,
        help="Maximum number of ideas to generate",
    )
    parser.add_argument(
        "--engine",
        type=str,
        default="semanticscholar",
        choices=["semanticscholar", "openalex"],
        help="Scholar engine to use for citations",
    )
    # Game-specific arguments
    parser.add_argument(
        "--num-players",
        type=int,
        default=5,
        help="Number of players in the social deduction game (default: 5)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=100,
        help="Maximum number of turns before game ends (default: 100)",
    )
    parser.add_argument(
        "--player-model",
        type=str,
        default="openrouter:deepseek/deepseek-r1-0528",
        help="Model specification for players in format 'api:model_name' (default: openrouter:deepseek/deepseek-r1-0528)",
    )
    parser.add_argument(
        "--gm-model",
        type=str,
        default=None,
        help="Model specification for GM in format 'api:model_name' (if different from players)",
    )
    return parser.parse_args()


def get_available_gpus(gpu_ids=None):
    if gpu_ids is not None:
        return [int(gpu_id) for gpu_id in gpu_ids.split(",")]
    return list(range(torch.cuda.device_count()))


def check_latex_dependencies():
    """
    Check if required LaTeX dependencies are installed on the system.
    Returns True if all dependencies are found, False otherwise.
    """
    import shutil
    import sys

    required_dependencies = ['pdflatex', 'chktex']
    missing_deps = []

    for dep in required_dependencies:
        if shutil.which(dep) is None:
            missing_deps.append(dep)
    
    if missing_deps:
        print("Error: Required LaTeX dependencies not found:", file=sys.stderr)
        return False
    
    return True
    
def worker(
        queue,
        base_dir,
        results_dir,
        writeup,
        improvement,
        gpu_id,
        use_docker,
        docker_image,
        experiment="social_deduction_game",
        engine="semanticscholar",
        num_players=5,
        max_turns=100,
        player_model="openrouter:deepseek/deepseek-r1-0528",
        gm_model=None,
):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    print(f"Worker {gpu_id} started.")
    
    # Get configured client once for this worker
    client, client_model = create_client()
    
    while True:
        idea = queue.get()
        if idea is None:
            break
        success = do_idea(
            base_dir,
            results_dir,
            idea,
            client,
            client_model,
            writeup,
            improvement,
            use_docker,
            docker_image,
            log_file=True,
            experiment=experiment,
            engine=engine,
            num_players=num_players,
            max_turns=max_turns,
            player_model=player_model,
            gm_model=gm_model,
        )
        print(f"Completed idea: {idea['Name']}, Success: {success}")
    print(f"Worker {gpu_id} finished.")


def do_idea(
        base_dir,
        results_dir,
        idea,
        client,
        client_model,
        writeup,
        improvement,
        use_docker=False,
        docker_image="ai-scientist:latest",
        log_file=False,
        experiment="social_deduction_game",
        engine="semanticscholar",
        num_players=5,
        max_turns=100,
        player_model="openrouter:deepseek/deepseek-r1-0528",
        gm_model=None,
):
    ## CREATE PROJECT FOLDER
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    idea_name = f"{timestamp}_{idea['Name']}"
    folder_name = osp.join(results_dir, idea_name)
    assert not osp.exists(folder_name), f"Folder {folder_name} already exists."
    destination_dir = folder_name
    shutil.copytree(base_dir, destination_dir, dirs_exist_ok=True)
    with open(osp.join(base_dir, "run_0", "final_info.json"), "r") as f:
        baseline_results = json.load(f)
    # Check if baseline_results is a dictionary before extracting means
    if isinstance(baseline_results, dict):
        # Safely extract means, handling cases where values don't have 'means' key
        processed_results = {}
        for k, v in baseline_results.items():
            if isinstance(v, dict) and "means" in v:
                processed_results[k] = v["means"]
            else:
                processed_results[k] = v
        baseline_results = processed_results
    exp_file = osp.join(folder_name, "experiment.py")
    vis_file = osp.join(folder_name, "plot.py")
    notes = osp.join(folder_name, "notes.txt")
    with open(notes, "w") as f:
        f.write(f"# Title: {idea['Title']}\n")
        f.write(f"# Experiment description: {idea['Experiment']}\n")
        f.write(f"## Run 0: Baseline\n")
        f.write(f"Results: {baseline_results}\n")
        f.write(f"Description: Baseline results.\n")
    if log_file:
        original_stdout = sys.stdout
        original_stderr = sys.stderr
        log_path = osp.join(folder_name, "log.txt")
        log = open(log_path, "a")
        sys.stdout = log
        sys.stderr = log
    try:
        print_time()
        print(f"*Starting idea: {idea_name}*")
        ## PERFORM EXPERIMENTS
        fnames = [exp_file, vis_file, notes]
        io = InputOutput(
            yes=True, chat_history_file=f"{folder_name}/{idea_name}_aider.txt"
        )
        if client_model == "deepseek-coder-v2-0724":
            main_model = Model("deepseek/deepseek-coder")
        elif client_model == "deepseek-reasoner":
            main_model = Model("deepseek/deepseek-reasoner")
        elif client_model == "llama3.1-405b" or client_model == "meta-llama/llama-3.1-405b-instruct":
            main_model = Model("openrouter/meta-llama/llama-3.1-405b-instruct")
        else:
            main_model = Model(client_model)
        coder = Coder.create(
            main_model=main_model,
            fnames=fnames,
            io=io,
            stream=False,
            use_git=False,
            edit_format="diff",
        )

        print_time()
        print(f"*Starting Experiments*")
        try:
            success = perform_experiments(
                idea,
                folder_name,
                coder,
                baseline_results,
                use_docker=use_docker,
                docker_image=docker_image,
                client=client,
                model=client_model,
                num_players=num_players,
                max_turns=max_turns,
                player_model=player_model,
                gm_model=gm_model,
            )
        except Exception as e:
            print(f"Error during experiments: {e}")
            print(f"Experiments failed for idea {idea_name}")
            return False

        if not success:
            print(f"Experiments failed for idea {idea_name}")
            return False

        print_time()
        print(f"*Starting Writeup*")
        ## PERFORM WRITEUP
        if writeup == "latex":
            writeup_file = osp.join(folder_name, "latex", "template.tex")
            fnames = [exp_file, writeup_file, notes]
            if client_model == "deepseek-coder-v2-0724":
                main_model = Model("deepseek/deepseek-coder")
            elif client_model == "deepseek-reasoner":
                main_model = Model("deepseek/deepseek-reasoner")
            elif client_model == "llama3.1-405b" or client_model == "meta-llama/llama-3.1-405b-instruct":
                main_model = Model("openrouter/meta-llama/llama-3.1-405b-instruct")
            else:
                main_model = Model(client_model)
            coder = Coder.create(
                main_model=main_model,
                fnames=fnames,
                io=io,
                stream=False,
                use_git=False,
                edit_format="diff",
            )
            try:
                # Check if this is a social deduction game experiment
                if "social_deduction" in base_dir or experiment == "social_deduction_game":
                    # Use game manual writeup instead of research paper
                    perform_game_manual_writeup(idea, folder_name, coder, client, client_model, engine=engine)
                else:
                    # Use standard research paper writeup
                    perform_writeup(idea, folder_name, coder, client, client_model, engine=engine)
            except Exception as e:
                print(f"Failed to perform writeup: {e}")
                return False
            print("Done writeup")
        else:
            raise ValueError(f"Writeup format {writeup} not supported.")

        print_time()
        print(f"*Starting Review*")
        ## REVIEW PAPER
        if writeup == "latex":
            try:
                # Get configured client for review
                review_client, review_model = create_client()
                
                if "social_deduction" in base_dir or experiment == "social_deduction_game":
                    # Use game manual review for social deduction games
                    manual_text = load_paper(f"{folder_name}/{idea['Name']}_manual.pdf")
                    review = perform_game_manual_review(
                        manual_text,
                        model=review_model,
                        client=review_client,
                        num_reflections=3,
                        num_fs_examples=1,
                        num_reviews_ensemble=3,
                        temperature=0.1,
                    )
                else:
                    # Use standard paper review for research papers
                    paper_text = load_paper(f"{folder_name}/{idea['Name']}.pdf")
                    review = perform_review(
                        paper_text,
                        model=review_model,
                        client=review_client,
                        num_reflections=5,
                        num_fs_examples=1,
                        num_reviews_ensemble=5,
                        temperature=0.1,
                    )
                # Store the review in separate review.txt file
                with open(osp.join(folder_name, "review.txt"), "w") as f:
                    f.write(json.dumps(review, indent=4))
            except Exception as e:
                print(f"Failed to perform review: {e}")
                return False

        ## IMPROVE WRITEUP
        if writeup == "latex" and improvement:
            print_time()
            print(f"*Starting Improvement*")
            try:
                perform_improvement(review, coder)
                generate_latex(
                    coder, folder_name, f"{folder_name}/{idea['Name']}_improved.pdf"
                )
                paper_text = load_paper(f"{folder_name}/{idea['Name']}_improved.pdf")
                
                # Get configured client for review
                improve_client, improve_model = create_client()
                review = perform_review(
                    paper_text,
                    model=improve_model,
                    client=improve_client,
                    num_reflections=5,
                    num_fs_examples=1,
                    num_reviews_ensemble=5,
                    temperature=0.1,
                )
                # Store the review in separate review.txt file
                with open(osp.join(folder_name, "review_improved.txt"), "w") as f:
                    f.write(json.dumps(review))
            except Exception as e:
                print(f"Failed to perform improvement: {e}")
                return False
        return True
    except Exception as e:
        print(f"Failed to evaluate idea {idea_name}: {str(e)}")
        return False
    finally:
        print("FINISHED IDEA")
        if log_file:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
            log.close()


if __name__ == "__main__":
    args = parse_arguments()
    
    # Print environment variable usage information
    print("LLM Configuration:")
    print(f"  Model: {os.environ.get('AI_SCIENTIST_MODEL', 'openai:gpt-4o-mini (default)')}")
    print("  Set AI_SCIENTIST_MODEL environment variable to change model")
    print("  Format: 'provider:model' (e.g., 'anthropic:claude-3-5-sonnet-20241022')")
    print()
    
    # Create client with environment variable configuration
    client, client_model = create_client()

    base_dir = osp.join("templates", args.experiment)
    results_dir = osp.join("results", args.experiment)
    ideas = generate_ideas(
        base_dir,
        client=client,
        model=client_model,
        skip_generation=args.skip_idea_generation,
        max_num_generations=args.max_ideas,
        num_reflections=NUM_REFLECTIONS,
    )
    if not args.skip_novelty_check:
        ideas = check_idea_novelty(
            ideas,
            base_dir=base_dir,
            client=client,
            model=client_model,
            search_api=args.search_api,
        )
    else:
        # If novelty checking is skipped, mark all ideas as novel
        for idea in ideas:
            # Safety check: only process dictionary items with required fields
            if isinstance(idea, dict) and 'Name' in idea:
                idea["novel"] = True

    with open(osp.join(base_dir, "ideas.json"), "w") as f:
        json.dump(ideas, f, indent=4)

    novel_ideas = [idea for idea in ideas if isinstance(idea, dict) and idea.get("novel", False)]
    # novel_ideas = list(reversed(novel_ideas))

    available_gpus = get_available_gpus()

    if args.parallel > 0:
        print(f"Running {args.parallel} parallel processes")
        queue = multiprocessing.Queue()
        for idea in novel_ideas:
            queue.put(idea)

        processes = []
        for i in range(args.parallel):
            gpu_id = available_gpus[i % len(available_gpus)]
            p = multiprocessing.Process(
                target=worker,
                args=(
                    queue,
                    base_dir,
                    results_dir,
                    args.writeup,
                    args.improvement,
                    gpu_id,
                    args.docker,
                    args.docker_image,
                    args.experiment,
                    args.engine,
                    args.num_players,
                    args.max_turns,
                    args.player_model,
                    args.gm_model,
                ),
            )
            p.start()
            time.sleep(150)
            processes.append(p)

        # Signal workers to exit
        for _ in range(args.parallel):
            queue.put(None)

        for p in processes:
            p.join()

        print("All parallel processes completed.")
    else:
        for idea in novel_ideas:
            print(f"Processing idea: {idea['Name']}")
            try:
                success = do_idea(
                    base_dir,
                    results_dir,
                    idea,
                    client,
                    client_model,
                    args.writeup,
                    args.improvement,
                    args.docker,
                    args.docker_image,
                    experiment=args.experiment,
                    engine=args.engine,
                    num_players=args.num_players,
                    max_turns=args.max_turns,
                    player_model=args.player_model,
                    gm_model=args.gm_model,
                )
                print(f"Completed idea: {idea['Name']}, Success: {success}")
            except Exception as e:
                print(f"Failed to evaluate idea {idea['Name']}: {str(e)}")
                import traceback
                print(traceback.format_exc())
    print("All ideas evaluated.")
