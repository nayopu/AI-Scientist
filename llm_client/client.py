"""
Unified LLM client interface.
Provides a consistent API for different LLM providers.
"""

import json
import os
import re
from typing import Any, List, Tuple, Union

import anthropic
import backoff
import openai
import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from .config import config

MAX_NUM_TOKENS = 4096


def get_llm_client() -> Tuple[Any, str]:
    """
    Get the configured LLM client and model name.
    
    Returns:
        Tuple of (client, model_name)
        
    Raises:
        ValueError: If configuration is invalid or API key is missing
    """
    if not config.validate_config():
        raise ValueError(
            f"Missing required configuration for {config.api_provider}. "
            f"Please set {config.api_key_env_var} environment variable."
        )
    
    print(f"Using {config.api_provider} API with model {config.model_name}")
    
    if config.api_provider == "anthropic":
        return anthropic.Anthropic(), config.model_name
        
    elif config.api_provider.startswith("bedrock") and "claude" in config.model_name:
        client_model = config.model_name.split("/")[-1] if "/" in config.model_name else config.model_name
        return anthropic.AnthropicBedrock(), client_model
        
    elif config.api_provider.startswith("vertex_ai") and "claude" in config.model_name:
        client_model = config.model_name.split("/")[-1] if "/" in config.model_name else config.model_name
        return anthropic.AnthropicVertex(), client_model
        
    elif config.api_provider == "openai":
        return openai.OpenAI(), config.model_name
        
    elif config.api_provider == "deepseek":
        return openai.OpenAI(
            api_key=config.get_api_key(),
            base_url="https://api.deepseek.com"
        ), config.model_name
        
    elif config.api_provider == "openrouter":
        # Handle special cases for openrouter model naming
        model_name = config.model_name
        if model_name == "llama3.1-405b":
            model_name = "meta-llama/llama-3.1-405b-instruct"
        return openai.OpenAI(
            api_key=config.get_api_key(),
            base_url="https://openrouter.ai/api/v1"
        ), model_name
        
    elif config.api_provider == "gemini":
        return openai.OpenAI(
            api_key=config.get_api_key(),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
        ), config.model_name
        
    else:
        raise ValueError(f"Unsupported API provider: {config.api_provider}")


def extract_json_between_markers(llm_output: str) -> dict:
    """Extract JSON content from LLM output with various fallback strategies."""
    # Regular expression pattern to find JSON content between ```json and ```
    json_pattern = r"```json(.*?)```"
    matches = re.findall(json_pattern, llm_output, re.DOTALL)

    if not matches:
        # Fallback: Try to find any JSON-like content in the output
        json_pattern = r"\{.*?\}"
        matches = re.findall(json_pattern, llm_output, re.DOTALL)

    for json_string in matches:
        json_string = json_string.strip()
        try:
            parsed_json = json.loads(json_string)
            return parsed_json
        except json.JSONDecodeError:
            # Attempt to fix common JSON issues
            try:
                # Remove invalid control characters
                json_string_clean = re.sub(r"[\x00-\x1F\x7F]", "", json_string)
                parsed_json = json.loads(json_string_clean)
                return parsed_json
            except json.JSONDecodeError:
                continue  # Try next match

    return None  # No valid JSON found


@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def get_batch_responses_from_llm(
        msg: str,
        system_message: str,
        print_debug: bool = False,
        msg_history: List[dict] = None,
        temperature: float = 0.75,
        n_responses: int = 1,
        client: Any = None,
        model: str = None,
) -> Tuple[List[str], List[List[dict]]]:
    """
    Get N responses from a single message, used for ensembling.
    
    Args:
        msg: The message to send
        system_message: System prompt
        print_debug: Whether to print debug information
        msg_history: Previous message history
        temperature: Temperature for response generation
        n_responses: Number of responses to generate
        client: LLM client (if None, uses configured client)
        model: Model name (if None, uses configured model)
    
    Returns:
        Tuple of (response_contents, new_message_histories)
    """
    if client is None or model is None:
        client, model = get_llm_client()
    
    if msg_history is None:
        msg_history = []

    # Route based on API provider and special model types
    if config.api_provider == "anthropic" or "claude" in model:
        # Anthropic models don't support n_responses, so generate individually
        content, new_msg_history = [], []
        for _ in range(n_responses):
            c, hist = get_response_from_llm(
                msg,
                system_message,
                print_debug=False,
                msg_history=msg_history,
                temperature=temperature,
                client=client,
                model=model,
            )
            content.append(c)
            new_msg_history.append(hist)
            
    elif "o1" in model or "o3" in model:
        # o1/o3 models have special handling regardless of provider
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        messages = [{"role": "user", "content": system_message}] + new_msg_history
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=1,
            max_completion_tokens=MAX_NUM_TOKENS,
            n=n_responses,
            seed=0,
        )
        content = [r.message.content for r in response.choices]
        new_msg_history = [
            new_msg_history + [{"role": "assistant", "content": c}] for c in content
        ]
        
    elif config.api_provider in ["openai", "openrouter", "gemini"] or 'gpt' in model:
        # OpenAI-compatible APIs that support n_responses
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                *new_msg_history,
            ],
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=n_responses,
            stop=None,
            seed=0,
        )
        content = [r.message.content for r in response.choices]
        new_msg_history = [
            new_msg_history + [{"role": "assistant", "content": c}] for c in content
        ]
        
    else:
        # For providers that don't support n_responses, generate individually
        content, new_msg_history = [], []
        for _ in range(n_responses):
            c, hist = get_response_from_llm(
                msg,
                system_message,
                print_debug=False,
                msg_history=msg_history,
                temperature=temperature,
                client=client,
                model=model,
            )
            content.append(c)
            new_msg_history.append(hist)

    if print_debug:
        print()
        print("*" * 20 + " LLM START " + "*" * 20)
        for j, msg in enumerate(new_msg_history[0]):
            print(f'{j}, {msg["role"]}: {msg["content"]}')
        print(content)
        print("*" * 21 + " LLM END " + "*" * 21)
        print()

    return content, new_msg_history


@backoff.on_exception(backoff.expo, (openai.RateLimitError, openai.APITimeoutError))
def get_response_from_llm(
        msg: str,
        system_message: str,
        print_debug: bool = False,
        msg_history: List[dict] = None,
        temperature: float = 0.75,
        client: Any = None,
        model: str = None,
) -> Tuple[str, List[dict]]:
    """
    Get a single response from the LLM.
    
    Args:
        msg: The message to send
        system_message: System prompt
        print_debug: Whether to print debug information
        msg_history: Previous message history
        temperature: Temperature for response generation
        client: LLM client (if None, uses configured client)
        model: Model name (if None, uses configured model)
    
    Returns:
        Tuple of (response_content, new_message_history)
    """
    if client is None or model is None:
        client, model = get_llm_client()
    
    if msg_history is None:
        msg_history = []

    # Route based on API provider rather than model name patterns
    if config.api_provider == "anthropic" or "claude" in model:
        new_msg_history = msg_history + [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": msg,
                    }
                ],
            }
        ]
        response = client.messages.create(
            model=model,
            max_tokens=MAX_NUM_TOKENS,
            temperature=temperature,
            system=system_message,
            messages=new_msg_history,
        )
        content = response.content[0].text
        new_msg_history = new_msg_history + [
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": content,
                    }
                ],
            }
        ]
        
    elif "o1" in model or "o3" in model:
        # o1/o3 models have special handling regardless of provider
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": system_message},
                *new_msg_history,
            ],
            temperature=1,
            max_completion_tokens=MAX_NUM_TOKENS,
            n=1,
            seed=0,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
        
    elif config.api_provider == "deepseek" and model in ["deepseek-chat", "deepseek-coder"]:
        # Only route to DeepSeek API if explicitly using deepseek provider
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                *new_msg_history,
            ],
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=1,
            stop=None,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
        
    elif config.api_provider == "deepseek" and model in ["deepseek-reasoner"]:
        # DeepSeek reasoner models have special handling
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                *new_msg_history,
            ],
            n=1,
            stop=None,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]
        
    else:
        # Default: Use OpenAI-compatible API for all other providers (OpenAI, OpenRouter, Gemini, etc.)
        new_msg_history = msg_history + [{"role": "user", "content": msg}]
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                *new_msg_history,
            ],
            temperature=temperature,
            max_tokens=MAX_NUM_TOKENS,
            n=1,
            stop=None,
            seed=0,
        )
        content = response.choices[0].message.content
        new_msg_history = new_msg_history + [{"role": "assistant", "content": content}]

    if print_debug:
        print()
        print("*" * 20 + " LLM START " + "*" * 20)
        for j, msg in enumerate(new_msg_history):
            print(f'{j}, {msg["role"]}: {msg["content"]}')
        print(content)
        print("*" * 21 + " LLM END " + "*" * 21)
        print()

    return content, new_msg_history 