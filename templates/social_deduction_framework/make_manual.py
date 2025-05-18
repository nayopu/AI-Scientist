import json
import os
import os.path as osp

from ai_scientist.llm import create_client, get_response_from_llm


def main(model: str = "gpt-4o") -> None:
    base_dir = osp.dirname(__file__)
    with open(osp.join(base_dir, "config.json"), "r") as f:
        config = json.load(f)

    sections = config.get("sections", [])
    roles = config.get("roles", {})

    system_msg = (
        "You are an expert game designer. Write a concise and clear manual "
        "for a new social deduction game."
    )

    section_headers = "\n".join(f"# {s}" for s in sections)
    role_str = "\n".join(f"- {r}: {c}" for r, c in roles.items())

    prompt = (
        "Write a markdown game manual using the following sections in order:\n"
        f"{section_headers}\n\n"
        "Describe each role and its objectives. Here are the roles and counts:\n"
        f"{role_str}\n"
        "Keep the explanations short and easy to understand."
    )

    client, client_model = create_client(model)
    text, _ = get_response_from_llm(
        prompt, client=client, model=client_model, system_message=system_msg, temperature=0.5
    )

    manual_file = osp.join(base_dir, "manual.md")
    with open(manual_file, "w") as f:
        f.write(text)
    print(f"Wrote manual to {manual_file}")


if __name__ == "__main__":
    main()
