import argparse
import sys
import os
from langchain.chat_models import ChatOpenAI

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
    ap = argparse.ArgumentParser()
    ap.add_argument("--rules", required=True)
    ap.add_argument("--players", type=int, default=5)
    ap.add_argument(
        "--model",
        type=str,
        default="openai:gpt-4o-mini",
        help="Model specification in format 'api:model_name'. "
             "Supported APIs: openai, openrouter, anthropic. "
             "Examples: 'openai:gpt-4o-mini', 'openrouter:llama-3.1-405b-instruct'",
    )
    ap.add_argument(
        "--gm-model",
        type=str,
        default=None,
        help="Model specification for GM (if different from players). "
             "Uses same format as --model.",
    )
    ap.add_argument("--lang", default="en")
    ap.add_argument("--out", default="game_log.json")
    args = ap.parse_args()
    
    # Parse model specifications
    try:
        api, model_name = parse_model_spec(args.model)
        if args.gm_model:
            gm_api, gm_model_name = parse_model_spec(args.gm_model)
        else:
            gm_api, gm_model_name = api, model_name
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    return args, api, model_name, gm_api, gm_model_name

def create_llm(api: str, model_name: str) -> ChatOpenAI:
    """
    Create an LLM instance based on the specified API and model name.
    
    Args:
        api: API source ('openai', 'openrouter', or 'anthropic')
        model_name: The name of the model to use
        
    Returns:
        A configured ChatOpenAI instance
        
    Raises:
        ValueError: If API source is invalid or required API key is missing
    """
    api = api.lower()
    
    if api == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_key=api_key
        )
    elif api == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required for OpenRouter API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/your-repo",
                "X-Title": "Social Deduction Game"
            }
        )
    elif api == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_base="https://api.anthropic.com/v1",
            openai_api_key=api_key
        )
    else:
        raise ValueError(f"Unsupported API source: {api}. Must be 'openai', 'openrouter', or 'anthropic'")

async def main_async():
    args, api, model_name, gm_api, gm_model_name = parse_arguments()
    
    try:
        # Create LLM instances with parsed values
        player_llm = create_llm(api, model_name)
        gm_llm = create_llm(gm_api, gm_model_name)
        system_llm = create_llm(gm_api, gm_model_name)
        
        # ... rest of the code ... 