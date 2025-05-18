import json
import os
from ai_scientist.perform_experiments import run_experiment


def create_dummy_experiment(tmp_path):
    script = tmp_path / "experiment.py"
    script.write_text(
        """import json, os, argparse
parser = argparse.ArgumentParser()
parser.add_argument('--out_dir')
args = parser.parse_args()
os.makedirs(args.out_dir, exist_ok=True)
with open(os.path.join(args.out_dir, 'final_info.json'), 'w') as f:
    json.dump({'metric': {'means': 0.5}}, f)
"""
    )
    return tmp_path


def test_run_experiment_success(tmp_path):
    folder = create_dummy_experiment(tmp_path)
    return_code, next_prompt = run_experiment(str(folder), 1, timeout=30)
    assert return_code == 0
    assert os.path.exists(folder / 'run_1' / 'final_info.json')
    assert 'Run 1 completed' in next_prompt
    assert 'metric' in next_prompt

