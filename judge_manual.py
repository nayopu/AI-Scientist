import argparse
import json
import os.path as osp
import re

from ai_scientist.llm import create_client, get_response_from_llm, extract_json_between_markers

CONFIG_PATH = osp.join("templates", "social_deduction_framework", "config.json")
MANUAL_PATH = osp.join("templates", "social_deduction_framework", "manual.md")


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def check_sections(text: str, sections) -> bool:
    for section in sections:
        pattern = rf"^#+\s*{re.escape(section)}\s*$"
        if re.search(pattern, text, flags=re.MULTILINE) is None:
            return False
    return True


def check_roles(text: str, roles) -> bool:
    for role, count in roles.items():
        role_pattern = re.escape(role)
        count_pattern = str(count)
        if not re.search(role_pattern, text, re.IGNORECASE):
            return False
        # look for count near role
        around = rf"{role_pattern}.{{0,20}}{count_pattern}|{count_pattern}.{{0,20}}{role_pattern}"
        if re.search(around, text, re.IGNORECASE) is None:
            return False
    return True


def rate_manual(text: str, model: str = "gpt-4o"):
    client, client_model = create_client(model)
    system_msg = "You evaluate how clear and reproducible game manuals are."
    prompt = (
        "Rate the following manual for clarity and reproducibility on a scale from 0 to 1."\
        "\nRespond only with JSON as {\"clarity\": <float>, \"reproducibility\": <float>}."\
        "\n\nMANUAL:\n" + text
    )
    resp, _ = get_response_from_llm(
        prompt, client=client, model=client_model, system_message=system_msg, temperature=0
    )
    data = extract_json_between_markers(resp)
    if not isinstance(data, dict):
        try:
            data = json.loads(resp)
        except Exception:
            data = {"clarity": 0.0, "reproducibility": 0.0}
    return {
        "clarity": float(data.get("clarity", 0)),
        "reproducibility": float(data.get("reproducibility", 0)),
    }


def judge_manual(manual_path: str = MANUAL_PATH, model: str = "gpt-4o"):
    config = load_config()
    with open(manual_path, "r") as f:
        text = f.read()

    has_sections = check_sections(text, config.get("sections", []))
    roles_match = check_roles(text, config.get("roles", {}))
    scores = rate_manual(text, model=model)

    result = {
        "has_sections": has_sections,
        "roles_match": roles_match,
        **scores,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Judge the quality of a game manual")
    parser.add_argument("--manual", default=MANUAL_PATH, help="Path to manual.md")
    parser.add_argument("--model", default="gpt-4o", help="LLM model to use")
    args = parser.parse_args()
    judge_manual(args.manual, args.model)
