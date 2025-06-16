<h1 align="center">
  <a href="https://github.com/SakanaAI/AI-Scientist/blob/main/docs/logo_2.png">
    <img src="docs/logo_2.png" width="215" /></a><br>
  <b>The AI Scientist: Towards Fully Automated</b><br>
  <b>Open-Ended Scientific Discovery & Game Design 🧑‍🔬🎮</b><br>
</h1>

<p align="center">
  📚 <a href="https://arxiv.org/abs/2408.06292">[Paper]</a> |
  📝 <a href="https://sakana.ai/ai-scientist/">[Blog Post]</a> |
  📂 <a href="https://drive.google.com/drive/folders/1G7A0wTqfXVa-cpexjk0oaXakaSJwffEt">[Drive Folder]</a>
</p>

One of the grand challenges of artificial intelligence is developing agents capable of conducting scientific research, discovering new knowledge, and creating innovative designs. While frontier models have already been used to aid human scientists and designers—for example, for brainstorming ideas or writing code—they still require extensive manual supervision or are heavily constrained to specific tasks.

We're excited to introduce **The AI Scientist**, a comprehensive system for automated game design, enabling Foundation Models such as Large Language Models (LLMs) to create innovative social deduction games independently.

**The AI Scientist** generates comprehensive game manuals for social deduction games 🎮, including innovative mechanics, detailed role descriptions, and complete gameplay instructions. The game design template creates fully playable games with unique themes and balanced mechanics.

> **Note:**  
> **Caution!** This codebase will execute LLM-written code for game design and simulation. There are various risks and challenges associated with this autonomy, including the use of potentially dangerous packages, web access, and potential spawning of processes. Use at your own discretion.

<p align="center">
  <a href="https://github.com/SakanaAI/AI-Scientist/blob/main/example_papers/adaptive_dual_scale_denoising/adaptive_dual_scale_denoising.pdf"><img src="https://github.com/SakanaAI/AI-Scientist/blob/main/docs/anim-ai-scientist.gif" alt="Adaptive Dual Scale Denoising" width="80%" />
</a></p>

## Table of Contents

1. [Introduction](#introduction)
2. [Requirements](#requirements)
   - [Installation](#installation)
   - [Unified LLM Client Configuration](#unified-llm-client-configuration)
   - [Web Search APIs (Game Design Novelty Checking)](#web-search-apis-game-design-novelty-checking)
3. [Setting Up the Social Deduction Game Template](#setting-up-the-social-deduction-game-template)
4. [Run Social Deduction Game Experiments](#run-social-deduction-game-experiments)
5. [Frequently Asked Questions](#frequently-asked-questions)

## Introduction

This guide focuses on the **Social Deduction Game** template for automated game design. This template enables The AI Scientist to generate innovative social deduction game ideas, implement game mechanics, and create comprehensive game manuals with detailed rules and balanced gameplay.

## Requirements

This code is designed to run on Linux systems. The social deduction game template works on CPU-only machines but GPU acceleration is recommended for better performance.

### Installation

```bash
conda create -n ai_scientist python=3.11
conda activate ai_scientist
# Install pdflatex for game manual generation
sudo apt-get install texlive-full

# Install PyPI requirements
pip install -r requirements.txt
```

**Note:** Installing `texlive-full` can take a long time. You may need to [hold Enter](https://askubuntu.com/questions/956006/pregenerating-context-markiv-format-this-may-take-some-time-takes-forever) during the installation.

### Unified LLM Client Configuration

The AI Scientist uses a unified LLM client system that supports multiple providers through environment variable configuration. This system eliminates the need for CLI model arguments and provides consistent model handling across all components.

#### Installation and Setup

1. **Install the LLM client package in development mode:**
   ```bash
   pip install -e .
   ```
   This installs the `llm-client` package from the current directory, making it available to all modules in the project.

2. **Configure the model using environment variables:**
   Set the `AI_SCIENTIST_MODEL` environment variable to specify which model and API provider to use:
   ```bash
   export AI_SCIENTIST_MODEL="provider:model_name"
   ```

#### Supported Providers and Configuration

The system supports the following format: `provider:model_name`

**OpenAI (GPT-4o, GPT-4o-mini, o1 models, o3-mini):**
```bash
export AI_SCIENTIST_MODEL="openai:gpt-4o-mini"
export OPENAI_API_KEY="your-openai-api-key"
```

**Note:** The system has enhanced compatibility with o3-mini and o3 models, including automatic handling of model-specific parameter requirements.

**Anthropic (Claude Sonnet 3.5):**
```bash
export AI_SCIENTIST_MODEL="anthropic:claude-3-5-sonnet-20241022"
export ANTHROPIC_API_KEY="your-anthropic-api-key"
```

##### Claude Models via Bedrock

For Claude models provided by [Amazon Bedrock](https://aws.amazon.com/bedrock/), please install these additional packages:

```bash
pip install anthropic[bedrock]
```

Next, specify a set of valid [AWS Credentials](https://docs.aws.amazon.com/cli/v1/userguide/cli-configure-envvars.html) and the target [AWS Region](https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-regions.html):

Set the environment variables: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION_NAME`.

##### Claude Models via Vertex AI

For Claude models provided by [Vertex AI Model Garden](https://cloud.google.com/model-garden?hl=en), please install these additional packages:

```bash
pip install google-cloud-aiplatform
pip install anthropic[vertex]
```

Next, set up valid authentication for a [Google Cloud project](https://cloud.google.com/vertex-ai/docs/authentication), for example by providing the region and project ID:

```bash
export CLOUD_ML_REGION="REGION"           # for Model Garden call
export ANTHROPIC_VERTEX_PROJECT_ID="PROJECT_ID"  # for Model Garden call
export VERTEXAI_LOCATION="REGION"         # for Aider/LiteLLM call
export VERTEXAI_PROJECT="PROJECT_ID"      # for Aider/LiteLLM call
```

**OpenRouter (Llama3.1, Perplexity Search):**
```bash
export AI_SCIENTIST_MODEL="openrouter:llama3.1-405b"
export OPENROUTER_API_KEY="your-openrouter-api-key"
```

OpenRouter also provides access to Perplexity's search capabilities for game design novelty checking.

**DeepSeek (deepseek-coder, deepseek-reasoner):**
```bash
export AI_SCIENTIST_MODEL="deepseek:deepseek-chat"
export DEEPSEEK_API_KEY="your-deepseek-api-key"
```

**Google Gemini:**
```bash
export AI_SCIENTIST_MODEL="gemini:gemini-1.5-pro"
export GEMINI_API_KEY="your-gemini-api-key"
```

We support Google Gemini models (e.g., "gemini-1.5-flash", "gemini-1.5-pro") via the [google-generativeai](https://pypi.org/project/google-generativeai) Python library.



#### Web Search APIs (Game Design Novelty Checking)

For game design templates, the system uses web search APIs to check novelty instead of academic literature search:

- **DuckDuckGo API** (free, no key required) - Used as fallback for all searches
- **Perplexity via OpenRouter** (requires `OPENROUTER_API_KEY`) - Advanced search capabilities
- **OpenAI** (requires `OPENAI_API_KEY`) - Knowledge-based search

```bash
# Optional - for enhanced search capabilities
export OPENROUTER_API_KEY="YOUR OPENROUTER API KEY"
export OPENAI_API_KEY="YOUR OPENAI API KEY"
```

## Run Social Deduction Game Experiments
**Description:** This template focuses on designing innovative social deduction games with unique mechanics, roles, and gameplay phases. The AI Scientist generates game concepts, implements rule systems, and creates comprehensive game manuals.


### Prerequisites

Before running experiments, make sure you have:

1. **Configured your model and API keys:**
   ```bash
   export AI_SCIENTIST_MODEL="openai:o3"
   export OPENAI_API_KEY="your-openai-api-key"
   ```

2. **Activated the environment:**
   ```bash
   conda activate ai_scientist
   ```

3. **Completed template setup** (see [Setting Up the Social Deduction Game Template](#setting-up-the-social-deduction-game-template))

### Basic Usage

The main entry point is `launch_scientist.py`. Instead of using model arguments, the system now uses environment variables for configuration:

```bash
# Basic example with recommended settings
python launch_scientist.py --experiment social_deduction_game --max-ideas 3 \
  --max-turns 50 --player-model "openai:o3" --gm-model "openai:o3" \
  --search-api openai --num-game-runs 3
```

#### Basic Game Design
```bash
# Simple social deduction game design
python launch_scientist.py --experiment social_deduction_game --max-ideas 2
```

#### Advanced Configuration
```bash
# High-quality game design with o3 models
python launch_scientist.py --experiment social_deduction_game --max-ideas 3 \
  --max-turns 50 --player-model "openai:o3" --gm-model "openai:o3" \
  --search-api openai --num-game-runs 3

# Cost-effective option with different models
python launch_scientist.py --experiment social_deduction_game --max-ideas 2 \
  --max-turns 100 --player-model "openrouter:deepseek/deepseek-r1-0528" \
  --search-api duckduckgo --num-game-runs 5

# Skip certain phases for faster iteration
python launch_scientist.py --experiment social_deduction_game --max-ideas 1 \
  --skip-novelty-check --skip-idea-generation
```

#### Command Line Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--max-ideas` | int | `5` | Number of ideas to generate |
| `--parallel` | int | `0` | Parallel processes |
| `--skip-idea-generation` | flag | `False` | Use existing ideas |
| `--skip-novelty-check` | flag | `False` | Skip novelty check |
| `--search-api` | str | `"perplexity"` | Search API (`duckduckgo`, `perplexity`, `openai`) |
| `--max-turns` | int | `100` | Game length |
| `--player-model` | str | `"openrouter:deepseek/deepseek-r1-0528"` | Player AI model |
| `--gm-model` | str | `None` | Game Master AI model |
| `--num-game-runs` | int | `5` | Runs per game |


### Generated Output Files

After running social deduction game experiments, you can expect the following files to be generated in the `results/` directory:

Each successful experiment creates a timestamped folder containing:

- `[idea_name]_manual.pdf` - Complete game manual with rules and instructions
- `latex/role_cards_combined.pdf` - Combined PDF containing all role cards for the game
