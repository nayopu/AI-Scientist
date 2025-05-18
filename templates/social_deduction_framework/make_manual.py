import argparse
import json


def make_markdown(rules, out_file):
    with open(out_file, "w") as f:
        f.write("# Game Manual\n\n")
        for key, value in rules.items():
            f.write(f"- **{key}**: {value}\n")


def main():
    parser = argparse.ArgumentParser(description="Generate Markdown manual from rules")
    parser.add_argument("--rules", type=str, default="rules.json")
    parser.add_argument("--out", type=str, default="manual.md")
    args = parser.parse_args()
    with open(args.rules, "r") as f:
        rules = json.load(f)
    make_markdown(rules, args.out)


if __name__ == "__main__":
    main()
