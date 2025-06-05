"""
Configuration management for LLM clients.
Reads model and API settings from environment variables.
"""

import os
from typing import Optional, Tuple


class LLMConfig:
    """Configuration class for LLM clients."""
    
    def __init__(self):
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment variables."""
        # Read model specification from environment
        # Format: API_PROVIDER:MODEL_NAME (e.g., "anthropic:claude-3-5-sonnet-20241022")
        model_spec = os.environ.get("AI_SCIENTIST_MODEL", "openai:gpt-4o-mini")
        
        try:
            self.api_provider, self.model_name = model_spec.split(":", 1)
            self.api_provider = self.api_provider.lower()
        except ValueError:
            raise ValueError(
                f"Invalid AI_SCIENTIST_MODEL format: '{model_spec}'. "
                "Expected format: 'provider:model' (e.g., 'anthropic:claude-3-5-sonnet-20241022')"
            )
        
        # Validate API provider
        supported_providers = ["openai", "anthropic", "openrouter", "deepseek", "bedrock", "vertex_ai", "gemini"]
        if not any(self.api_provider.startswith(provider) for provider in supported_providers):
            raise ValueError(
                f"Unsupported API provider: {self.api_provider}. "
                f"Supported providers: {supported_providers}"
            )
    
    @property
    def api_key_env_var(self) -> str:
        """Get the environment variable name for the API key."""
        if self.api_provider == "openai":
            return "OPENAI_API_KEY"
        elif self.api_provider == "anthropic":
            return "ANTHROPIC_API_KEY"
        elif self.api_provider == "openrouter":
            return "OPENROUTER_API_KEY"
        elif self.api_provider == "deepseek":
            return "DEEPSEEK_API_KEY"
        elif self.api_provider.startswith("bedrock"):
            return "AWS_REGION"  # Bedrock uses AWS credentials
        elif self.api_provider.startswith("vertex_ai"):
            return "GOOGLE_APPLICATION_CREDENTIALS"  # Vertex AI uses service account
        elif self.api_provider == "gemini":
            return "GEMINI_API_KEY"
        else:
            return f"{self.api_provider.upper()}_API_KEY"
    
    def get_api_key(self) -> Optional[str]:
        """Get the API key from environment variables."""
        return os.environ.get(self.api_key_env_var)
    
    def validate_config(self) -> bool:
        """Validate that required configuration is available."""
        if self.api_provider.startswith("bedrock"):
            # For Bedrock, check AWS region instead of API key
            return os.environ.get("AWS_REGION") is not None
        elif self.api_provider.startswith("vertex_ai"):
            # For Vertex AI, check service account credentials
            return os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") is not None
        else:
            # For other providers, check API key
            return self.get_api_key() is not None


# Global configuration instance
config = LLMConfig() 