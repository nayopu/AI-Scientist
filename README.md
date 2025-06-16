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

## Setting Up the Social Deduction Game Template

**Description:** This template focuses on designing innovative social deduction games with unique mechanics, roles, and gameplay phases. The AI Scientist generates game concepts, implements rule systems, and creates comprehensive game manuals.

**Setup Steps:**

1. **Create baseline game data:**

   ```bash
   # Set up Social Deduction Game baseline run
   cd templates/social_deduction_game
   python experiment.py --out_dir run_0
   python plot.py
   ```

2. **Configure search APIs (optional):**

   The template supports multiple search APIs for novelty checking:
   - **DuckDuckGo** (free, no API key required)
   - **Perplexity via OpenRouter** (requires `OPENROUTER_API_KEY`)
   - **OpenAI** (requires `OPENAI_API_KEY`)

   ```bash
   # For Perplexity search
   export OPENROUTER_API_KEY="YOUR OPENROUTER API KEY"
   
   # For OpenAI search
   export OPENAI_API_KEY="YOUR OPENAI API KEY"
   ```

## Run Social Deduction Game Experiments

**Note:** Please ensure the setup steps above are completed before running these experiments.

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

#### Different Search APIs
```bash
# Using DuckDuckGo (free, no API key required)
python launch_scientist.py --experiment social_deduction_game --max-ideas 2 --search-api duckduckgo

# Using Perplexity via OpenRouter
python launch_scientist.py --experiment social_deduction_game --max-ideas 2 --search-api perplexity

# Using OpenAI for enhanced search
python launch_scientist.py --experiment social_deduction_game --max-ideas 2 --search-api openai
```

### Generated Output Files

After running social deduction game experiments, you can expect the following files to be generated in the `results/` directory:

Each successful experiment creates a timestamped folder containing:

**Core Files:**
- `experiment.py` - Modified experimental code with implemented game ideas
- `rule.py` - Game rule implementations and mechanics
- `plot.py` - Visualization and plotting code
- `notes.txt` - Experiment log with baseline results and iterations
- `log.txt` - Complete execution log
- `[idea_name]_aider.txt` - AI assistant conversation history

**Game Development:**
- `game_results.json` - Comprehensive game testing results
- `game_logs/` - Directory containing detailed game session logs
- `player_interactions.json` - Analysis of player behavior patterns

**Game Manual:**
- `latex/template.tex` - LaTeX source for game manual
- `[idea_name]_manual.pdf` - Complete game manual with rules and instructions
- Game balance analysis and playtest results

**Testing Data:**
- Multiple game session logs with different player counts
- Statistical analysis of game outcomes
- Player experience feedback (simulated)

**Review and Evaluation:**
- `review.txt` - AI-generated game manual review in JSON format

#### Directory Structure Example

```
results/social_deduction_game/
├── 20241225_143052_InnovativeSpyGame/
│   ├── experiment.py
│   ├── rule.py
│   ├── plot.py
│   ├── notes.txt
│   ├── log.txt
│   ├── InnovativeSpyGame_aider.txt
│   ├── game_results.json
│   ├── game_logs/
│   │   ├── game_1_3players.json
│   │   ├── game_2_4players.json
│   │   └── ...
│   ├── latex/
│   │   └── template.tex
│   ├── InnovativeSpyGame_manual.pdf
│   ├── review.txt
│   └── *.png (various plots)
```

#### Success Indicators

- **Success: True** - All phases completed successfully
- **Success: False** - May indicate PDF generation issues, but core experiment may still be valid
- Check for the existence of final PDF and results files to confirm successful completion

### Command Line Arguments Reference

#### General Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--max-ideas` | int | `5` | Maximum number of ideas to generate |
| `--parallel` | int | `0` | Number of parallel processes to run |

#### Control Flow Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--skip-idea-generation` | flag | `False` | Skip idea generation and use existing ideas |
| `--skip-novelty-check` | flag | `False` | Skip novelty checking of ideas |

#### Search Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--search-api` | str | `"perplexity"` | Search API for novelty checking |

**Search API Options:**
- `duckduckgo` - Free, no API key required
- `perplexity` - Requires `OPENROUTER_API_KEY`
- `openai` - Requires `OPENAI_API_KEY`

#### Game-Specific Arguments

For social deduction game experiments:

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--max-turns` | int | `100` | Maximum turns before game ends |
| `--player-model` | str | `"openrouter:deepseek/deepseek-r1-0528"` | Model for players |
| `--gm-model` | str | `None` | Model for Game Master (if different) |
| `--num-game-runs` | int | `5` | Number of runs per game configuration |

**Important Notes:**
- Player count is automatically determined by experimental design (typically 3-8 players)
- Different runs test various player counts to explore group dynamics
- Use `--gm-model` to specify a different model for the Game Master role



## Frequently Asked Questions

**Why am I missing files when running social deduction game experiments?**

Ensure you have completed all the setup steps in the [Setting Up the Social Deduction Game Template](#setting-up-the-social-deduction-game-template) section before running experiments.

**Why has a game manual PDF not been generated?**

The AI Scientist finishes a game design idea with a success rate that depends on the foundation model and the complexity of the game concept. The highest success rates are observed with Claude Sonnet 3.5 and OpenAI's o3 models. If you encounter PDF generation issues, check the LaTeX compilation logs in the experiment directory.

**What is the cost of each game design idea generated?**

Game design experiments may vary in cost depending on the search API used (DuckDuckGo is free, while Perplexity and OpenAI have API costs). With OpenAI's o3 models, expect higher costs but better quality results. DeepSeek models provide a more cost-effective approach. A good place to look for new models is the [Aider leaderboard](https://aider.chat/docs/leaderboards/).

**How do I configure search APIs for game design novelty checking?**

The social deduction game template supports three search options:

1. **DuckDuckGo (Free):**
   ```bash
   python launch_scientist.py --experiment social_deduction_game --search-api duckduckgo
   ```
   No API key required.

2. **Perplexity via OpenRouter:**
   ```bash
   export OPENROUTER_API_KEY="your-openrouter-key"
   python launch_scientist.py --experiment social_deduction_game --search-api perplexity
   ```

3. **OpenAI Search:**
   ```bash
   export OPENAI_API_KEY="your-openai-key"
   python launch_scientist.py --experiment social_deduction_game --search-api openai
   ```

The system automatically falls back to DuckDuckGo if the specified API is unavailable.

**How do I customize game parameters for social deduction games?**

You can customize the game setup using the following arguments:
- `--max-turns N`: Set maximum turns before game ends (default: 100)
- `--player-model "api:model"`: Specify the model for players (default: "openrouter:deepseek/deepseek-r1-0528")
- `--gm-model "api:model"`: Specify a different model for the Game Master (optional)
- `--num-game-runs N`: Number of runs per game configuration (default: 5)

The number of players is automatically determined by the experimental design. Each run tests different player counts (3-8 players) to explore how group size affects game dynamics.

**Example (using recommended o3 models):**
```bash
export AI_SCIENTIST_MODEL="openai:o3"
export OPENAI_API_KEY="your-openai-key"

python launch_scientist.py --experiment social_deduction_game \
  --max-ideas 3 --max-turns 50 --player-model "openai:o3" \
  --gm-model "openai:o3" --search-api openai --num-game-runs 3
```

**Cost-effective alternative:**
```bash
export AI_SCIENTIST_MODEL="openrouter:deepseek/deepseek-r1-0528"
export OPENROUTER_API_KEY="your-openrouter-key"

python launch_scientist.py --experiment social_deduction_game \
  --max-turns 100 --player-model "openrouter:deepseek/deepseek-r1-0528" \
  --search-api duckduckgo --num-game-runs 5
```

**What if I have problems with web search APIs?**

The system uses web search APIs for game design novelty checking. DuckDuckGo is always available as a free fallback option. If you have issues with Perplexity or OpenAI APIs, the system will automatically fall back to DuckDuckGo search.

**How do I specify which model and API to use?**

The system uses environment variable configuration instead of command-line arguments:

1. **Set the model specification:**
   ```bash
   export AI_SCIENTIST_MODEL="provider:model_name"
   ```

2. **Set the corresponding API key:**
   ```bash
   export OPENAI_API_KEY="your-key"        # for OpenAI models
   export ANTHROPIC_API_KEY="your-key"     # for Anthropic models
   export OPENROUTER_API_KEY="your-key"    # for OpenRouter models
   export DEEPSEEK_API_KEY="your-key"      # for DeepSeek models
   export GEMINI_API_KEY="your-key"        # for Gemini models
   ```

3. **Run experiments without model arguments:**
   ```bash
   # Old way (no longer works):
   # python launch_scientist.py --model "openai:gpt-4o" --experiment social_deduction_game
   
   # New way:
   export AI_SCIENTIST_MODEL="openai:gpt-4o"
   python launch_scientist.py --experiment social_deduction_game
   ```

**Supported format examples:**
- `"openai:gpt-4o-mini"`
- `"openrouter:llama-3.1-405b-instruct"`
- `"anthropic:claude-3-5-sonnet-20241022"`
- `"deepseek:deepseek-chat"`
- `"gemini:gemini-1.5-pro"`

**Python Usage:**
```python
from llm_client import get_llm_client, get_response_from_llm

# Get the configured client (reads from environment variables)
client, model_name = get_llm_client()

# Use the unified interface
response, history = get_response_from_llm(
    msg="Hello, how are you?",
    system_message="You are a helpful assistant.",
    client=client,
    model=model_name
)
```


