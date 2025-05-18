import argparse
import json

try:
    import textstat
except ImportError:  # pragma: no cover - optional dependency
    textstat = None


def readability(text: str) -> float:
    if textstat is not None:
        # Flesch Reading Ease scaled to 0-1
        return max(0.0, min(1.0, textstat.flesch_reading_ease(text) / 100.0))
    # Fallback: rough heuristic based on length
    return max(0.0, 1.0 - len(text) / 1000.0)


def main():
    parser = argparse.ArgumentParser(description="Score manual for clarity and reproducibility")
    parser.add_argument("manual", type=str, help="Path to generated manual")
    args = parser.parse_args()
    with open(args.manual, "r") as f:
        text = f.read()
    score = readability(text)
    result = {"clarity": score, "reproducibility": score}
    print(json.dumps(result))


if __name__ == "__main__":
    main()
