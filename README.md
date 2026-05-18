# Deep Research Agent

A multi-agent deep research pipeline built with **LangGraph**, **LangChain**, and **LangChain Deep Agents**, leveraging parallel specialist agents and sandboxed execution via Daytona.

---

## Table of Contents

- [Setup](#setup)
  - [1. Clone the Repository](#1-clone-the-repository)
  - [2. Environment Setup](#2-environment-setup)
    - [Daytona Sandbox](#daytona-sandbox)
    - [Model Providers](#model-providers)
    - [LangSmith Tracing](#langsmith-tracing)
    - [Tavily Search Engine](#tavily-search-engine)
    - [Install Dependencies](#install-dependencies)
  - [3. Run the Agent](#3-run-the-agent)

---

## Setup

### 1. Clone the Repository

```bash
git clone git@github.com:dhruvvaidh/deep-research.git deep-research
cd deep-research
```

---

### 2. Environment Setup

#### Daytona Sandbox

Create an account on [Daytona](https://app.daytona.io) and follow the setup instructions to provision a sandbox. The agent uses Daytona for isolated, shared code execution across specialist nodes.

> Copy `.env.example` to `.env` and fill in the required values as you complete each step below.

```bash
cp .env.example .env
```

---

#### Model Providers

##### Google AI Studio *(Required — used by tool calls and subagents)*

1. Set up a [GCP Console](https://console.cloud.google.com) project.
2. Go to [Google AI Studio](https://aistudio.google.com) and link your GCP project to generate an API key.
3. Add the key to `.env`:

```env
GOOGLE_API_KEY=your_google_api_key_here
```

##### Anthropic Console *(for Claude Models)*

1. Create an account on [Anthropic Console](https://console.anthropic.com).
2. Navigate to **API Keys** and generate a new key.
3. Add the key to `.env`:

```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

##### OpenAI API Platform *(for OpenAI Models)*

1. Create an account on [OpenAI API Platform](https://platform.openai.com).
2. Navigate to **API Keys** and generate a new key.
3. Add the key to `.env`:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

##### HuggingFace Hub *(for HuggingFace Models)*

1. Create an account on [HuggingFace Hub](https://huggingface.co).
2. Go to **Access Tokens** and create a fine-grained token with the appropriate permissions.
3. Add the token to `.env`:

```env
HUGGINGFACEHUB_API_TOKEN=your_huggingface_token_here
```

---

#### LangSmith Tracing (Optional)

1. Create an account on [LangSmith](https://smith.langchain.com).
2. Go to **Tracing** and create a new project.
3. Add the following to `.env`:

```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_langsmith_api_key_here
LANGCHAIN_PROJECT=your_project_name_here
```

---

#### Tavily Search Engine

1. Create an account on [Tavily](https://www.tavily.com).
2. Navigate to **API Keys** and generate a key.
3. Add the key to `.env`:

```env
TAVILY_API_KEY=your_tavily_api_key_here
```

---

#### Install Dependencies

Create and activate a new Conda environment, then install the required packages:

```bash
conda create -n deepresearch python=3.11
conda activate deepresearch
pip install -r requirements.txt
```

---

### 3. Run the Agent

Run the deep research agent interactively:

```bash
python main.py
```

Or pass your research query directly as a command-line argument(add your model_provider and model name):

```bash
python main.py --model_provider MODEL_PROVIDER --model_name MODEL_NAME --question "What are the latest breakthroughs in fusion energy?"
```