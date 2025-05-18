import json
import os.path as osp
import shutil
import subprocess
import sys
from subprocess import TimeoutExpired

MAX_ITERS = 4
MAX_RUNS = 5
MAX_STDERR_OUTPUT = 1500

coder_prompt = """Your goal is to implement the following idea: {title}.
The proposed experiment is as follows: {idea}.
You are given a total of up to {max_runs} runs to complete the necessary experiments. You do not need to use all {max_runs}.

First, plan the list of experiments you would like to run. For example, if you are sweeping over a specific hyperparameter, plan each value you would like to test for each run.

Note that we already provide the vanilla baseline results, so you do not need to re-run it.

For reference, the baseline results are as follows:

{baseline_results}

After you complete each change, we will run the command `python experiment.py --out_dir=run_i' where i is the run number and evaluate the results.
YOUR PROPOSED CHANGE MUST USE THIS COMMAND FORMAT, DO NOT ADD ADDITIONAL COMMAND LINE ARGS.
You can then implement the next thing on your list."""


# RUN EXPERIMENT
def run_experiment(
    folder_name: str,
    run_num: int,
    timeout: int = 7200,
    use_docker: bool = False,
    docker_image: str = "ai-scientist:latest",
):
    """Run ``experiment.py`` either locally or inside a Docker container.

    Parameters
    ----------
    folder_name : str
        Path to the experiment template folder.
    run_num : int
        Run index used for naming the output directory.
    timeout : int, optional
        Timeout for the process in seconds.
    use_docker : bool, optional
        If ``True``, execute the experiment inside ``docker_image`` with
        restricted resources.
    docker_image : str, optional
        Name of the Docker image to use when ``use_docker`` is ``True``.
    """
    cwd = osp.abspath(folder_name)
    if use_docker and shutil.which("docker") is None:
        raise EnvironmentError("Docker executable not found. Cannot use --docker")
    # COPY CODE SO WE CAN SEE IT.
    shutil.copy(
        osp.join(folder_name, "experiment.py"),
        osp.join(folder_name, f"run_{run_num}.py"),
    )

    # LAUNCH COMMAND
    if use_docker:
        command = [
            "docker",
            "run",
            "--rm",
            "--cpus",
            "1",
            "--memory",
            "2g",
            "--network",
            "none",
            "-v",
            f"{cwd}:/workspace",
            "--workdir",
            "/workspace",
            docker_image,
            "python",
            "experiment.py",
            f"--out_dir=run_{run_num}",
        ]
        run_cwd = None
    else:
        command = [
            "python",
            "experiment.py",
            f"--out_dir=run_{run_num}",
        ]
        run_cwd = cwd
    try:
        result = subprocess.run(
            command, cwd=run_cwd, stderr=subprocess.PIPE, text=True, timeout=timeout
        )

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            print(f"Run {run_num} failed with return code {result.returncode}")
            if osp.exists(osp.join(cwd, f"run_{run_num}")):
                shutil.rmtree(osp.join(cwd, f"run_{run_num}"))
            print(f"Run failed with the following error {result.stderr}")
            stderr_output = result.stderr
            if len(stderr_output) > MAX_STDERR_OUTPUT:
                stderr_output = "..." + stderr_output[-MAX_STDERR_OUTPUT:]
            next_prompt = f"Run failed with the following error {stderr_output}"
        else:
            with open(osp.join(cwd, f"run_{run_num}", "final_info.json"), "r") as f:
                results = json.load(f)
            results = {k: v["means"] for k, v in results.items()}

            next_prompt = f"""Run {run_num} completed. Here are the results:
{results}

Decide if you need to re-plan your experiments given the result (you often will not need to).

Someone else will be using `notes.txt` to perform a writeup on this in the future.
Please include *all* relevant information for the writeup on Run {run_num}, including an experiment description and the run number. Be as verbose as necessary.

Then, implement the next thing on your list.
We will then run the command `python experiment.py --out_dir=run_{run_num + 1}'.
YOUR PROPOSED CHANGE MUST USE THIS COMMAND FORMAT, DO NOT ADD ADDITIONAL COMMAND LINE ARGS.
If you are finished with experiments, respond with 'ALL_COMPLETED'."""
        return result.returncode, next_prompt
    except TimeoutExpired:
        print(f"Run {run_num} timed out after {timeout} seconds")
        if osp.exists(osp.join(cwd, f"run_{run_num}")):
            shutil.rmtree(osp.join(cwd, f"run_{run_num}"))
        next_prompt = f"Run timed out after {timeout} seconds"
        return 1, next_prompt


# RUN PLOTTING
def run_plotting(
    folder_name: str,
    timeout: int = 600,
    use_docker: bool = False,
    docker_image: str = "ai-scientist:latest",
):
    """Run ``plot.py`` either locally or inside a Docker container."""
    cwd = osp.abspath(folder_name)
    if use_docker and shutil.which("docker") is None:
        raise EnvironmentError("Docker executable not found. Cannot use --docker")
    if use_docker:
        command = [
            "docker",
            "run",
            "--rm",
            "--cpus",
            "1",
            "--memory",
            "2g",
            "--network",
            "none",
            "-v",
            f"{cwd}:/workspace",
            "--workdir",
            "/workspace",
            docker_image,
            "python",
            "plot.py",
        ]
        run_cwd = None
    else:
        command = [
            "python",
            "plot.py",
        ]
        run_cwd = cwd
    try:
        result = subprocess.run(
            command, cwd=run_cwd, stderr=subprocess.PIPE, text=True, timeout=timeout
        )

        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            print(f"Plotting failed with return code {result.returncode}")
            next_prompt = f"Plotting failed with the following error {result.stderr}"
        else:
            next_prompt = ""
        return result.returncode, next_prompt
    except TimeoutExpired:
        print(f"Plotting timed out after {timeout} seconds")
        next_prompt = f"Plotting timed out after {timeout} seconds"
        return 1, next_prompt


# PERFORM EXPERIMENTS
def perform_experiments(
    idea,
    folder_name,
    coder,
    baseline_results,
    *,
    use_docker: bool = False,
    docker_image: str = "ai-scientist:latest",
) -> bool:
    ## RUN EXPERIMENT
    current_iter = 0
    run = 1
    next_prompt = coder_prompt.format(
        title=idea["Title"],
        idea=idea["Experiment"],
        max_runs=MAX_RUNS,
        baseline_results=baseline_results,
    )
    while run < MAX_RUNS + 1:
        if current_iter >= MAX_ITERS:
            print("Max iterations reached")
            break
        coder_out = coder.run(next_prompt)
        print(coder_out)
        if "ALL_COMPLETED" in coder_out:
            break
        return_code, next_prompt = run_experiment(
            folder_name,
            run,
            use_docker=use_docker,
            docker_image=docker_image,
        )
        if return_code == 0:
            run += 1
            current_iter = 0
        current_iter += 1
    if current_iter >= MAX_ITERS:
        print("Not all experiments completed.")
        return False

    current_iter = 0
    next_prompt = """
Great job! Please modify `plot.py` to generate the most relevant plots for the final writeup. 

In particular, be sure to fill in the "labels" dictionary with the correct names for each run that you want to plot.

Only the runs in the `labels` dictionary will be plotted, so make sure to include all relevant runs.

We will be running the command `python plot.py` to generate the plots.
"""
    while True:
        _ = coder.run(next_prompt)
        return_code, next_prompt = run_plotting(
            folder_name,
            use_docker=use_docker,
            docker_image=docker_image,
        )
        current_iter += 1
        if return_code == 0 or current_iter >= MAX_ITERS:
            break
    next_prompt = """
Please modify `notes.txt` with a description of what each plot shows along with the filename of the figure. Please do so in-depth.

Somebody else will be using `notes.txt` to write a report on this in the future.
"""
    coder.run(next_prompt)

    return True
