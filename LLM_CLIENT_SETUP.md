# Unified LLM Client Setup

This document explains how to set up and use the unified LLM client for the AI Scientist project.

## Installation

1. Install the LLM client package in development mode:
```bash
pip install -e .
```

This installs the `llm-client` package from the current directory, making it available to all modules in the project.

## Configuration

The unified LLM client uses environment variables for configuration instead of CLI arguments or hardcoded values.

### Required Environment Variable

Set the `AI_SCIENTIST_MODEL` environment variable to specify which model and API provider to use:

```bash
export AI_SCIENTIST_MODEL="provider:model_name"
```

### Supported Providers and Examples

**Anthropic:**
```bash
export AI_SCIENTIST_MODEL="anthropic:claude-3-5-sonnet-20241022"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

**OpenAI:**
```bash
export AI_SCIENTIST_MODEL="openai:gpt-4o-mini"
export OPENAI_API_KEY="your-openai-api-key"
```

**OpenRouter:**
```bash
export AI_SCIENTIST_MODEL="openrouter:llama3.1-405b"
export OPENROUTER_API_KEY="your-openrouter-api-key"
```

**DeepSeek:**
```bash
export AI_SCIENTIST_MODEL="deepseek:deepseek-chat"
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

**Gemini:**
```bash
export AI_SCIENTIST_MODEL="gemini:gemini-1.5-pro"
export GEMINI_API_KEY="your-gemini-api-key"
```

## Usage

### Running the AI Scientist

Instead of using the `--model` argument, simply set the environment variable:

```bash
# Old way (no longer works):
# python launch_scientist.py --model "anthropic:claude-3-5-sonnet-20241022" --experiment nanoGPT_lite --num-ideas 2

# New way:
export AI_SCIENTIST_MODEL="anthropic:claude-3-5-sonnet-20241022"
export ANTHROPIC_API_KEY="your-api-key"
python launch_scientist.py --experiment nanoGPT_lite --max-ideas 2
```

### In Python Code

```python
from llm_client import get_llm_client, get_response_from_llm

# Get the configured client
client, model_name = get_llm_client()

# Use the unified interface
response, history = get_response_from_llm(
    msg="Hello, how are you?",
    system_message="You are a helpful assistant.",
    client=client,
    model=model_name
)
```

## Benefits

1. **Centralized Configuration**: All LLM settings are managed in one place
2. **Environment-based**: No more CLI arguments or hardcoded model names
3. **Consistent API**: Same interface across all project modules
4. **Easy Switching**: Change models by updating one environment variable
5. **Clean Code**: Removes hardcoded `openai.OpenAI()` calls throughout the codebase

## Migration Guide

### For Existing Code

The package provides backward compatibility through `ai_scientist.llm.create_client()`, but it now ignores the model parameter and uses environment variables instead.

### Removed CLI Arguments

- `--model` argument has been removed from `launch_scientist.py`
- `--api` and `--model` arguments removed from experiment scripts
- Use `AI_SCIENTIST_MODEL` environment variable instead

## Troubleshooting

### Missing Environment Variable
If you see: "Invalid AI_SCIENTIST_MODEL format"
- Make sure you set the environment variable correctly
- Use the format: `provider:model_name`

### Missing API Key
If you see: "Missing required configuration"
- Set the appropriate API key environment variable
- Check the provider-specific examples above

### Package Not Found
If you see: "ModuleNotFoundError: No module named 'llm_client'"
- Run `pip install -e .` from the project root directory
- Make sure you're in the correct virtual environment 