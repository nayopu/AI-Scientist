import argparse
import json
import multiprocessing
import openai
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


def parse_model_spec(model_spec: str) -> tuple[str, str]:
    """
    Parse model specification string into (api, model_name) tuple.
    
    Args:
        model_spec: String in format 'api:model_name'
        
    Returns:
        Tuple of (api, model_name)
        
    Raises:
        ValueError: If format is invalid
    """
    try:
        api, model_name = model_spec.split(':', 1)
        api = api.lower()
        if api not in ['openai', 'openrouter', 'anthropic']:
            raise ValueError(f"Unsupported API: {api}")
        return api, model_name
    except ValueError:
        raise ValueError(
            "Model specification must be in format 'api:model_name'. "
            "Examples: 'openai:gpt-4o-mini', 'openrouter:llama-3.1-405b-instruct'"
        )


def parse_arguments():
    parser = argparse.ArgumentParser(description="Run AI scientist experiments")
    parser.add_argument(
        "--model",
        type=str,
        default="openai:gpt-4o-mini",
        help="Model specification in format 'api:model_name'. "
             "Supported APIs: openai, openrouter, anthropic. "
             "Examples: 'openai:gpt-4o-mini', 'openrouter:llama-3.1-405b-instruct', 'anthropic:claude-3-5-sonnet-20240620'",
    )
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
        "--max-parallel",
        type=int,
        default=4,
        help="Maximum number of parallel experiments",
    )
    parser.add_argument(
        "--max-ideas",
        type=int,
        default=5,
        help="Maximum number of ideas to generate",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=50,
        help="Maximum number of turns per game",
    )
    parser.add_argument(
        "--max-players",
        type=int,
        default=5,
        help="Maximum number of players per game",
    )
    parser.add_argument(
        "--max-games",
        type=int,
        default=3,
        help="Maximum number of games to run per idea",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Maximum number of retries for failed experiments",
    )
    parser.add_argument(
        "--max-time",
        type=int,
        default=3600,
        help="Maximum time in seconds to run experiments",
    )
    parser.add_argument(
        "--max-memory",
        type=int,
        default=8192,
        help="Maximum memory in MB to use for experiments",
    )
    parser.add_argument(
        "--max-cpu",
        type=int,
        default=4,
        help="Maximum number of CPU cores to use for experiments",
    )
    parser.add_argument(
        "--max-gpu",
        type=int,
        default=1,
        help="Maximum number of GPU devices to use for experiments",
    )
    parser.add_argument(
        "--max-disk",
        type=int,
        default=1024,
        help="Maximum disk space in MB to use for experiments",
    )
    parser.add_argument(
        "--max-network",
        type=int,
        default=100,
        help="Maximum network bandwidth in MB/s to use for experiments",
    )
    parser.add_argument(
        "--max-power",
        type=int,
        default=100,
        help="Maximum power consumption in watts to use for experiments",
    )
    parser.add_argument(
        "--max-cost",
        type=float,
        default=1.0,
        help="Maximum cost in USD to use for experiments",
    )
    parser.add_argument(
        "--max-carbon",
        type=float,
        default=1.0,
        help="Maximum carbon emissions in kg to use for experiments",
    )
    parser.add_argument(
        "--max-water",
        type=float,
        default=1.0,
        help="Maximum water usage in liters to use for experiments",
    )
    parser.add_argument(
        "--max-waste",
        type=float,
        default=1.0,
        help="Maximum waste generation in kg to use for experiments",
    )
    parser.add_argument(
        "--max-noise",
        type=float,
        default=1.0,
        help="Maximum noise level in dB to use for experiments",
    )
    parser.add_argument(
        "--max-light",
        type=float,
        default=1.0,
        help="Maximum light level in lux to use for experiments",
    )
    parser.add_argument(
        "--max-temperature",
        type=float,
        default=1.0,
        help="Maximum temperature in Celsius to use for experiments",
    )
    parser.add_argument(
        "--max-humidity",
        type=float,
        default=1.0,
        help="Maximum humidity in percent to use for experiments",
    )
    parser.add_argument(
        "--max-pressure",
        type=float,
        default=1.0,
        help="Maximum pressure in hPa to use for experiments",
    )
    parser.add_argument(
        "--max-wind",
        type=float,
        default=1.0,
        help="Maximum wind speed in m/s to use for experiments",
    )
    parser.add_argument(
        "--max-precipitation",
        type=float,
        default=1.0,
        help="Maximum precipitation in mm to use for experiments",
    )
    parser.add_argument(
        "--max-cloud-cover",
        type=float,
        default=1.0,
        help="Maximum cloud cover in percent to use for experiments",
    )
    parser.add_argument(
        "--max-visibility",
        type=float,
        default=1.0,
        help="Maximum visibility in km to use for experiments",
    )
    parser.add_argument(
        "--max-uv-index",
        type=float,
        default=1.0,
        help="Maximum UV index to use for experiments",
    )
    parser.add_argument(
        "--max-air-quality",
        type=float,
        default=1.0,
        help="Maximum air quality index to use for experiments",
    )
    parser.add_argument(
        "--max-pollen",
        type=float,
        default=1.0,
        help="Maximum pollen count to use for experiments",
    )
    parser.add_argument(
        "--max-mold",
        type=float,
        default=1.0,
        help="Maximum mold count to use for experiments",
    )
    parser.add_argument(
        "--max-dust",
        type=float,
        default=1.0,
        help="Maximum dust count to use for experiments",
    )
    parser.add_argument(
        "--max-pm2.5",
        type=float,
        default=1.0,
        help="Maximum PM2.5 count to use for experiments",
    )
    parser.add_argument(
        "--max-pm10",
        type=float,
        default=1.0,
        help="Maximum PM10 count to use for experiments",
    )
    parser.add_argument(
        "--max-o3",
        type=float,
        default=1.0,
        help="Maximum O3 count to use for experiments",
    )
    parser.add_argument(
        "--max-no2",
        type=float,
        default=1.0,
        help="Maximum NO2 count to use for experiments",
    )
    parser.add_argument(
        "--max-so2",
        type=float,
        default=1.0,
        help="Maximum SO2 count to use for experiments",
    )
    parser.add_argument(
        "--max-co",
        type=float,
        default=1.0,
        help="Maximum CO count to use for experiments",
    )
    parser.add_argument(
        "--max-nh3",
        type=float,
        default=1.0,
        help="Maximum NH3 count to use for experiments",
    )
    parser.add_argument(
        "--max-pb",
        type=float,
        default=1.0,
        help="Maximum Pb count to use for experiments",
    )
    parser.add_argument(
        "--max-hg",
        type=float,
        default=1.0,
        help="Maximum Hg count to use for experiments",
    )
    parser.add_argument(
        "--max-cd",
        type=float,
        default=1.0,
        help="Maximum Cd count to use for experiments",
    )
    parser.add_argument(
        "--max-as",
        type=float,
        default=1.0,
        help="Maximum As count to use for experiments",
    )
    parser.add_argument(
        "--max-cr",
        type=float,
        default=1.0,
        help="Maximum Cr count to use for experiments",
    )
    parser.add_argument(
        "--max-ni",
        type=float,
        default=1.0,
        help="Maximum Ni count to use for experiments",
    )
    parser.add_argument(
        "--max-cu",
        type=float,
        default=1.0,
        help="Maximum Cu count to use for experiments",
    )
    parser.add_argument(
        "--max-zn",
        type=float,
        default=1.0,
        help="Maximum Zn count to use for experiments",
    )
    parser.add_argument(
        "--max-mn",
        type=float,
        default=1.0,
        help="Maximum Mn count to use for experiments",
    )
    parser.add_argument(
        "--max-fe",
        type=float,
        default=1.0,
        help="Maximum Fe count to use for experiments",
    )
    parser.add_argument(
        "--max-ca",
        type=float,
        default=1.0,
        help="Maximum Ca count to use for experiments",
    )
    parser.add_argument(
        "--max-mg",
        type=float,
        default=1.0,
        help="Maximum Mg count to use for experiments",
    )
    parser.add_argument(
        "--max-na",
        type=float,
        default=1.0,
        help="Maximum Na count to use for experiments",
    )
    parser.add_argument(
        "--max-k",
        type=float,
        default=1.0,
        help="Maximum K count to use for experiments",
    )
    parser.add_argument(
        "--max-p",
        type=float,
        default=1.0,
        help="Maximum P count to use for experiments",
    )
    parser.add_argument(
        "--max-s",
        type=float,
        default=1.0,
        help="Maximum S count to use for experiments",
    )
    parser.add_argument(
        "--max-cl",
        type=float,
        default=1.0,
        help="Maximum Cl count to use for experiments",
    )
    parser.add_argument(
        "--max-f",
        type=float,
        default=1.0,
        help="Maximum F count to use for experiments",
    )
    parser.add_argument(
        "--max-br",
        type=float,
        default=1.0,
        help="Maximum Br count to use for experiments",
    )
    parser.add_argument(
        "--max-i",
        type=float,
        default=1.0,
        help="Maximum I count to use for experiments",
    )
    parser.add_argument(
        "--max-si",
        type=float,
        default=1.0,
        help="Maximum Si count to use for experiments",
    )
    parser.add_argument(
        "--max-b",
        type=float,
        default=1.0,
        help="Maximum B count to use for experiments",
    )
    parser.add_argument(
        "--max-al",
        type=float,
        default=1.0,
        help="Maximum Al count to use for experiments",
    )
    parser.add_argument(
        "--max-ti",
        type=float,
        default=1.0,
        help="Maximum Ti count to use for experiments",
    )
    parser.add_argument(
        "--max-v",
        type=float,
        default=1.0,
        help="Maximum V count to use for experiments",
    )
    parser.add_argument(
        "--max-cr",
        type=float,
        default=1.0,
        help="Maximum Cr count to use for experiments",
    )
    parser.add_argument(
        "--max-mn",
        type=float,
        default=1.0,
        help="Maximum Mn count to use for experiments",
    )
    parser.add_argument(
        "--max-fe",
        type=float,
        default=1.0,
        help="Maximum Fe count to use for experiments",
    )
    parser.add_argument(
        "--max-co",
        type=float,
        default=1.0,
        help="Maximum Co count to use for experiments",
    )
    parser.add_argument(
        "--max-ni",
        type=float,
        default=1.0,
        help="Maximum Ni count to use for experiments",
    )
    parser.add_argument(
        "--max-cu",
        type=float,
        default=1.0,
        help="Maximum Cu count to use for experiments",
    )
    parser.add_argument(
        "--max-zn",
        type=float,
        default=1.0,
        help="Maximum Zn count to use for experiments",
    )
    parser.add_argument(
        "--max-ga",
        type=float,
        default=1.0,
        help="Maximum Ga count to use for experiments",
    )
    parser.add_argument(
        "--max-ge",
        type=float,
        default=1.0,
        help="Maximum Ge count to use for experiments",
    )
    parser.add_argument(
        "--max-as",
        type=float,
        default=1.0,
        help="Maximum As count to use for experiments",
    )
    parser.add_argument(
        "--max-se",
        type=float,
        default=1.0,
        help="Maximum Se count to use for experiments",
    )
    parser.add_argument(
        "--max-br",
        type=float,
        default=1.0,
        help="Maximum Br count to use for experiments",
    )
    parser.add_argument(
        "--max-kr",
        type=float,
        default=1.0,
        help="Maximum Kr count to use for experiments",
    )
    parser.add_argument(
        "--max-rb",
        type=float,
        default=1.0,
        help="Maximum Rb count to use for experiments",
    )
    parser.add_argument(
        "--max-sr",
        type=float,
        default=1.0,
        help="Maximum Sr count to use for experiments",
    )
    parser.add_argument(
        "--max-y",
        type=float,
        default=1.0,
        help="Maximum Y count to use for experiments",
    )
    parser.add_argument(
        "--max-zr",
        type=float,
        default=1.0,
        help="Maximum Zr count to use for experiments",
    )
    parser.add_argument(
        "--max-nb",
        type=float,
        default=1.0,
        help="Maximum Nb count to use for experiments",
    )
    parser.add_argument(
        "--max-mo",
        type=float,
        default=1.0,
        help="Maximum Mo count to use for experiments",
    )
    parser.add_argument(
        "--max-tc",
        type=float,
        default=1.0,
        help="Maximum Tc count to use for experiments",
    )
    parser.add_argument(
        "--max-ru",
        type=float,
        default=1.0,
        help="Maximum Ru count to use for experiments",
    )
    parser.add_argument(
        "--max-rh",
        type=float,
        default=1.0,
        help="Maximum Rh count to use for experiments",
    )
    parser.add_argument(
        "--max-pd",
        type=float,
        default=1.0,
        help="Maximum Pd count to use for experiments",
    )
    parser.add_argument(
        "--max-ag",
        type=float,
        default=1.0,
        help="Maximum Ag count to use for experiments",
    )
    parser.add_argument(
        "--max-cd",
        type=float,
        default=1.0,
        help="Maximum Cd count to use for experiments",
    )
    parser.add_argument(
        "--max-in",
        type=float,
        default=1.0,
        help="Maximum In count to use for experiments",
    )
    parser.add_argument(
        "--max-sn",
        type=float,
        default=1.0,
        help="Maximum Sn count to use for experiments",
    )
    parser.add_argument(
        "--max-sb",
        type=float,
        default=1.0,
        help="Maximum Sb count to use for experiments",
    )
    parser.add_argument(
        "--max-te",
        type=float,
        default=1.0,
        help="Maximum Te count to use for experiments",
    )
    parser.add_argument(
        "--max-xe",
        type=float,
        default=1.0,
        help="Maximum Xe count to use for experiments",
    )
    parser.add_argument(
        "--max-cs",
        type=float,
        default=1.0,
        help="Maximum Cs count to use for experiments",
    )
    parser.add_argument(
        "--max-ba",
        type=float,
        default=1.0,
        help="Maximum Ba count to use for experiments",
    )
    parser.add_argument(
        "--max-la",
        type=float,
        default=1.0,
        help="Maximum La count to use for experiments",
    )
    parser.add_argument(
        "--max-ce",
        type=float,
        default=1.0,
        help="Maximum Ce count to use for experiments",
    )
    parser.add_argument(
        "--max-pr",
        type=float,
        default=1.0,
        help="Maximum Pr count to use for experiments",
    )
    parser.add_argument(
        "--max-nd",
        type=float,
        default=1.0,
        help="Maximum Nd count to use for experiments",
    )
    parser.add_argument(
        "--max-pm",
        type=float,
        default=1.0,
        help="Maximum Pm count to use for experiments",
    )
    parser.add_argument(
        "--max-sm",
        type=float,
        default=1.0,
        help="Maximum Sm count to use for experiments",
    )
    parser.add_argument(
        "--max-eu",
        type=float,
        default=1.0,
        help="Maximum Eu count to use for experiments",
    )
    parser.add_argument(
        "--max-gd",
        type=float,
        default=1.0,
        help="Maximum Gd count to use for experiments",
    )
    parser.add_argument(
        "--max-tb",
        type=float,
        default=1.0,
        help="Maximum Tb count to use for experiments",
    )
    parser.add_argument(
        "--max-dy",
        type=float,
        default=1.0,
        help="Maximum Dy count to use for experiments",
    )
    parser.add_argument(
        "--max-ho",
        type=float,
        default=1.0,
        help="Maximum Ho count to use for experiments",
    )
    parser.add_argument(
        "--max-er",
        type=float,
        default=1.0,
        help="Maximum Er count to use for experiments",
    )
    parser.add_argument(
        "--max-tm",
        type=float,
        default=1.0,
        help="Maximum Tm count to use for experiments",
    )
    parser.add_argument(
        "--max-yb",
        type=float,
        default=1.0,
        help="Maximum Yb count to use for experiments",
    )
    parser.add_argument(
        "--max-lu",
        type=float,
        default=1.0,
        help="Maximum Lu count to use for experiments",
    )
    parser.add_argument(
        "--max-hf",
        type=float,
        default=1.0,
        help="Maximum Hf count to use for experiments",
    )
    parser.add_argument(
        "--max-ta",
        type=float,
        default=1.0,
        help="Maximum Ta count to use for experiments",
    )
    parser.add_argument(
        "--max-w",
        type=float,
        default=1.0,
        help="Maximum W count to use for experiments",
    )
    parser.add_argument(
        "--max-re",
        type=float,
        default=1.0,
        help="Maximum Re count to use for experiments",
    )
    parser.add_argument(
        "--max-os",
        type=float,
        default=1.0,
        help="Maximum Os count to use for experiments",
    )
    parser.add_argument(
        "--max-ir",
        type=float,
        default=1.0,
        help="Maximum Ir count to use for experiments",
    )
    parser.add_argument(
        "--max-pt",
        type=float,
        default=1.0,
        help="Maximum Pt count to use for experiments",
    )
    parser.add_argument(
        "--max-au",
        type=float,
        default=1.0,
        help="Maximum Au count to use for experiments",
    )
    parser.add_argument(
        "--max-hg",
        type=float,
        default=1.0,
        help="Maximum Hg count to use for experiments",
    )
    parser.add_argument(
        "--max-tl",
        type=float,
        default=1.0,
        help="Maximum Tl count to use for experiments",
    )
    parser.add_argument(
        "--max-pb",
        type=float,
        default=1.0,
        help="Maximum Pb count to use for experiments",
    )
    parser.add_argument(
        "--max-bi",
        type=float,
        default=1.0,
        help="Maximum Bi count to use for experiments",
    )
    parser.add_argument(
        "--max-po",
        type=float,
        default=1.0,
        help="Maximum Po count to use for experiments",
    )
    parser.add_argument(
        "--max-at",
        type=float,
        default=1.0,
        help="Maximum At count to use for experiments",
    )
    parser.add_argument(
        "--max-rn",
        type=float,
        default=1.0,
        help="Maximum Rn count to use for experiments",
    )
    parser.add_argument(
        "--max-fr",
        type=float,
        default=1.0,
        help="Maximum Fr count to use for experiments",
    )
    parser.add_argument(
        "--max-ra",
        type=float,
        default=1.0,
        help="Maximum Ra count to use for experiments",
    )
    parser.add_argument(
        "--max-ac",
        type=float,
        default=1.0,
        help="Maximum Ac count to use for experiments",
    )
    parser.add_argument(
        "--max-th",
        type=float,
        default=1.0,
        help="Maximum Th count to use for experiments",
    )
    parser.add_argument(
        "--max-pa",
        type=float,
        default=1.0,
        help="Maximum Pa count to use for experiments",
    )
    parser.add_argument(
        "--max-u",
        type=float,
        default=1.0,
        help="Maximum U count to use for experiments",
    )
    parser.add_argument(
        "--max-np",
        type=float,
        default=1.0,
        help="Maximum Np count to use for experiments",
    )
    parser.add_argument(
        "--max-pu",
        type=float,
        default=1.0,
        help="Maximum Pu count to use for experiments",
    )
    parser.add_argument(
        "--max-am",
        type=float,
        default=1.0,
        help="Maximum Am count to use for experiments",
    )
    parser.add_argument(
        "--max-cm",
        type=float,
        default=1.0,
        help="Maximum Cm count to use for experiments",
    )
    parser.add_argument(
        "--max-bk",
        type=float,
        default=1.0,
        help="Maximum Bk count to use for experiments",
    )
    parser.add_argument(
        "--max-cf",
        type=float,
        default=1.0,
        help="Maximum Cf count to use for experiments",
    )
    parser.add_argument(
        "--max-es",
        type=float,
        default=1.0,
        help="Maximum Es count to use for experiments",
    )
    parser.add_argument(
        "--max-fm",
        type=float,
        default=1.0,
        help="Maximum Fm count to use for experiments",
    )
    parser.add_argument(
        "--max-md",
        type=float,
        default=1.0,
        help="Maximum Md count to use for experiments",
    )
    parser.add_argument(
        "--max-no",
        type=float,
        default=1.0,
        help="Maximum No count to use for experiments",
    )
    parser.add_argument(
        "--max-lr",
        type=float,
        default=1.0,
        help="Maximum Lr count to use for experiments",
    )
    parser.add_argument(
        "--max-rf",
        type=float,
        default=1.0,
        help="Maximum Rf count to use for experiments",
    )
    parser.add_argument(
        "--max-db",
        type=float,
        default=1.0,
        help="Maximum Db count to use for experiments",
    )
    parser.add_argument(
        "--max-sg",
        type=float,
        default=1.0,
        help="Maximum Sg count to use for experiments",
    )
    parser.add_argument(
        "--max-bh",
        type=float,
        default=1.0,
        help="Maximum Bh count to use for experiments",
    )
    parser.add_argument(
        "--max-hs",
        type=float,
        default=1.0,
        help="Maximum Hs count to use for experiments",
    )
    parser.add_argument(
        "--max-mt",
        type=float,
        default=1.0,
        help="Maximum Mt count to use for experiments",
    )
    parser.add_argument(
        "--max-ds",
        type=float,
        default=1.0,
        help="Maximum Ds count to use for experiments",
    )
    parser.add_argument(
        "--max-rg",
        type=float,
        default=1.0,
        help="Maximum Rg count to use for experiments",
    )
    parser.add_argument(
        "--max-cn",
        type=float,
        default=1.0,
        help="Maximum Cn count to use for experiments",
    )
    parser.add_argument(
        "--max-nh",
        type=float,
        default=1.0,
        help="Maximum Nh count to use for experiments",
    )
    parser.add_argument(
        "--max-fl",
        type=float,
        default=1.0,
        help="Maximum Fl count to use for experiments",
    )
    parser.add_argument(
        "--max-mc",
        type=float,
        default=1.0,
        help="Maximum Mc count to use for experiments",
    )
    parser.add_argument(
        "--max-lv",
        type=float,
        default=1.0,
        help="Maximum Lv count to use for experiments",
    )
    parser.add_argument(
        "--max-ts",
        type=float,
        default=1.0,
        help="Maximum Ts count to use for experiments",
    )
    parser.add_argument(
        "--max-og",
        type=float,
        default=1.0,
        help="Maximum Og count to use for experiments",
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
        model,
        client,
        client_model,
        writeup,
        improvement,
        gpu_id,
        use_docker,
        docker_image,
):
    os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
    print(f"Worker {gpu_id} started.")
    while True:
        idea = queue.get()
        if idea is None:
            break
        success = do_idea(
            base_dir,
            results_dir,
            idea,
            model,
            client,
            client_model,
            writeup,
            improvement,
            use_docker,
            docker_image,
            log_file=True,
        )
        print(f"Completed idea: {idea['Name']}, Success: {success}")
    print(f"Worker {gpu_id} finished.")


def do_idea(
        base_dir,
        results_dir,
        idea,
        model,
        client,
        client_model,
        writeup,
        improvement,
        use_docker=False,
        docker_image="ai-scientist:latest",
        log_file=False,
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
        baseline_results = {k: v["means"] for k, v in baseline_results.items()}
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
        if model == "deepseek-coder-v2-0724":
            main_model = Model("deepseek/deepseek-coder")
        elif model == "deepseek-reasoner":
            main_model = Model("deepseek/deepseek-reasoner")
        elif model == "llama3.1-405b":
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
            if model == "deepseek-coder-v2-0724":
                main_model = Model("deepseek/deepseek-coder")
            elif model == "deepseek-reasoner":
                main_model = Model("deepseek/deepseek-reasoner")
            elif model == "llama3.1-405b":
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
            try:
                # Check if this is a social deduction game experiment
                if "social_deduction" in base_dir or args.experiment == "social_deduction_game":
                    # Use game manual writeup instead of research paper
                    perform_game_manual_writeup(idea, folder_name, coder, client, client_model, engine=args.engine)
                else:
                    # Use standard research paper writeup
                    perform_writeup(idea, folder_name, coder, client, client_model, engine=args.engine)
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
                if "social_deduction" in base_dir or args.experiment == "social_deduction_game":
                    # Use game manual review for social deduction games
                    manual_text = load_paper(f"{folder_name}/{idea['Name']}.pdf")
                    review = perform_game_manual_review(
                        manual_text,
                        model="gpt-4o-2024-05-13",
                        client=openai.OpenAI(),
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
                        model="gpt-4o-2024-05-13",
                        client=openai.OpenAI(),
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
                review = perform_review(
                    paper_text,
                    model="gpt-4o-2024-05-13",
                    client=openai.OpenAI(),
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
    
    # Parse model specification
    api, model_name = parse_model_spec(args.model)
    
    # Create client with parsed values
    client, client_model = create_client(model_name, api=api)

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

    with open(osp.join(base_dir, "ideas.json"), "w") as f:
        json.dump(ideas, f, indent=4)

    novel_ideas = [idea for idea in ideas if idea["novel"]]
    # novel_ideas = list(reversed(novel_ideas))

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
                    args.model,
                    client,
                    client_model,
                    args.writeup,
                    args.improvement,
                    gpu_id,
                    args.docker,
                    args.docker_image,
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
                    args.model,
                    client,
                    client_model,
                    args.writeup,
                    args.improvement,
                    args.docker,
                    args.docker_image,
                )
                print(f"Completed idea: {idea['Name']}, Success: {success}")
            except Exception as e:
                print(f"Failed to evaluate idea {idea['Name']}: {str(e)}")
                import traceback
                print(traceback.format_exc())
    print("All ideas evaluated.")
