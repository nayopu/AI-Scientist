"""
LLM Client Package
-----------------
Unified LLM client management for AI Scientist project.
Reads configuration from environment variables.
"""

from .client import get_llm_client, get_response_from_llm, get_batch_responses_from_llm
from .config import LLMConfig

__version__ = "1.0.0"
__all__ = ["get_llm_client", "get_response_from_llm", "get_batch_responses_from_llm", "LLMConfig"] 