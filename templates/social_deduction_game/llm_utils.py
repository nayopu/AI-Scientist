"""
LLM Utilities for Social Deduction Game
--------------------------------------
Shared utilities for creating and managing LLM instances across different API providers.
"""

import os
from typing import Optional
from langchain_openai import ChatOpenAI

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def create_llm(api_source: str, model_name: str, temperature: float = 0.1) -> ChatOpenAI:
    """
    Create an LLM instance based on the specified API source and model name.
    
    Args:
        api_source: Either "openai" or "openrouter"
        model_name: The name of the model to use
        temperature: Temperature for the model (default: 0.1)
        
    Returns:
        A configured ChatOpenAI instance
        
    Raises:
        ValueError: If API source is invalid or required API key is missing
    """
    api_source = api_source.lower()
    temperature = 1.0 if model_name == "o3" else temperature
    if api_source == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_key=api_key,
            temperature=temperature
        )
    elif api_source == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required for OpenRouter API")
        return ChatOpenAI(
            model_name=model_name,
            openai_api_base="https://openrouter.ai/api/v1",
            openai_api_key=api_key,
            temperature=temperature,
            default_headers={
                "HTTP-Referer": "https://github.com/your-repo",  # Required by OpenRouter
                "X-Title": "Social Deduction Game"  # Optional but helpful
            }
        )
    else:
        raise ValueError(f"Unsupported API source: {api_source}. Must be 'openai' or 'openrouter'")

