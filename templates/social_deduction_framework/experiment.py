import argparse
import json
import os

from base_code.simulate import simulate_game

parser = argparse.ArgumentParser(description="Evaluate social deduction game rules")
parser.add_argument("--out_dir", type=str, default="run_0", help="Output directory")
parser.add_argument("--rules", type=str, default="rules.json", help="JSON file containing rule definition")


def main():
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    if os.path.exists(args.rules):
        with open(args.rules, "r") as f:
            rules = json.load(f)
    else:
        # Default rule set
        rules = {"num_players": 4, "imposters": 1}

    metrics = simulate_game(rules)
    with open(os.path.join(args.out_dir, "final_info.json"), "w") as f:
        json.dump({"GameMetrics": metrics}, f)


if __name__ == "__main__":
    main()
