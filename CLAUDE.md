# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Argus — a multi-agent deep research pipeline built with LangGraph, LangChain, and LangChain Deep Agents. An orchestrator decomposes a research question into parallel workstreams, dispatches them to specialist agents (web research, data analysis, domain expertise), reflects on whether the findings are sufficient, and iterates before a synthesizer writes the final markdown report. Code execution and file storage happen in an isolated Daytona sandbox.

## Setup & running

```bash
conda create -n deepresearch python=3.11
conda activate deepresearch
pip install -r requirements.txt
cp .env.example .env   # then fill in required keys
```

Required env vars (see `.env.example`): `DAYTONA_API_KEY`, `DAYTONA_API_URL`, `TAVILY_API_KEY`, plus the API key for whichever model provider you use (`ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` + `GOOGLE_PROJECT_ID` + `GOOGLE_GENAI_USE_VERTEXAI`, `OPENAI_API_KEY`, or `HUGGINGFACEHUB_API_TOKEN`). `MODEL_NAME` and `GOOGLE_API_KEY`/`GOOGLE_PROJECT_ID`/`GOOGLE_GENAI_USE_VERTEXAI` are read directly from the environment by sub-agent nodes regardless of `--model_provider` (see Architecture notes below), so Google credentials are effectively always required.

Run the agent:

```bash
python main.py
python main.py --model_provider anthropic --model_name claude-sonnet-4-20250514 --question "What are the latest breakthroughs in fusion energy?"
```

With no `--question`/`--model_provider`/`--model_name`, `main.py` prompts interactively. Every run provisions a Daytona sandbox at start and destroys it in a `finally` block on exit — if a run is killed hard (e.g. `kill -9`), the sandbox will leak and must be cleaned up manually via the Daytona dashboard/API.

There is no test suite, linter, or formatter configured in this repo currently.

## Architecture

### Graph flow (`graph/research_graph.py`)

```
START → orchestrator → [check_sufficient]
                          ├─ "router" → [route_workstreams fan-out via Send()]
                          │               ├─ web_researcher  ─┐
                          │               ├─ data_analyst    ─┤→ orchestrator (loop)
                          │               └─ domain_expert    ─┘
                          └─ "synthesizer" → END
```

- `graph/state.py` defines `ResearchState` (graph-level) and `SubAgentState` (per-Send payload: `task` + `question`). `findings` and `thought_log` use reducers (`operator.or_`, `operator.add`) so parallel specialist branches merge without clobbering each other.
- `graph/edges.py` holds the two routing functions: `check_sufficient` (stop after `MAX_ITERATIONS` from `config.py`, currently 3, or when the orchestrator sets `sufficient=True`) and `route_workstreams` (fans each `ResearchTask` out via `Send` to the node matching its `agent_type`, defaulting to `web_researcher` for unknown types).
- Every specialist node returns to `orchestrator`, which re-decomposes/reflects each iteration until sufficient or `MAX_ITERATIONS` is hit.

### Agents (`agents/`)

- **orchestrator.py** — decomposes the question into typed `ResearchTask` workstreams, or reflects and returns `{"sufficient": true}`. Uses `utils.get_llm(config.MODEL_PROVIDER, config.MODEL_NAME)`, so it honors CLI-selected provider/model.
- **web_researcher.py / data_analyst.py / domain_expert.py** — each is a `create_agent` ReAct loop over a per-role toolset (Tavily + scraper; code executor + yfinance; arxiv/Wikipedia/Tavily respectively), invoked once per `Send`ed workstream. All three findings-returning nodes extract a `think` tool-call result out of the message list to append to `thought_log`.
- **synthesizer.py** — final ReAct agent that reads the thought log and context manifest, selectively pulls artifacts, and writes the markdown report to `outputs/<timestamp>_<slug>.md`.

**Architecture quirk to know before editing model wiring**: `orchestrator.py` and `synthesizer.py` use `utils.get_llm()` and thus respect `config.MODEL_PROVIDER`/`config.MODEL_NAME` set from `--model_provider`/`--model_name`. The three specialist nodes (`web_researcher`, `data_analyst`, `domain_expert`) and `tools/thinking.py` and `tools/context_store.py` instead hardcode `ChatGoogleGenerativeAI` reading `os.environ['MODEL_NAME']`/`GOOGLE_API_KEY`/`GOOGLE_PROJECT_ID`/`GOOGLE_GENAI_USE_VERTEXAI` directly — multi-provider support is only partially wired through. If extending provider support, this is the inconsistency to resolve.

### State propagation pattern

Token-heavy raw data (web pages, search results, financial data) is never returned directly to agent context. The pattern, enforced via tool docstrings/prompts:

1. A data tool (`tavily_search`, `web_scraper`, `yfinance_data`, `arxiv_search`) fetches raw content.
2. `store_context(key, content, description)` (`tools/context_store.py`) persists it to the Daytona sandbox FS and registers it in a `context_manifest.json` index.
3. `summarize_context(key)` returns a compact LLM-generated summary for the agent's findings.
4. `get_context_index()` lets any agent (including cross-workstream) discover what's already been stored before fetching again.

`tools/artifact_store.py` is the lower-level named-file read/write primitive (module-level `_workspace` set once via `set_workspace()` in `main.py` before graph invocation); `tools/context_store.py` and the synthesizer build on top of it. `sandbox/artifact_manager.py` is the raw Daytona FS layer (`/home/daytona/artifacts/...`); `sandbox/executor.py` + `tools/code_executor.py` run arbitrary Python in the same sandbox.

### Reflection / thinking (`tools/thinking.py`)

- `think` — per-workstream tool called by specialist agents; returns a `ThoughtEntry` (agent, iteration, task, gaps, sufficient, confidence).
- `reflect` — called by the orchestrator across the full `thought_log` to decide `sufficient`/`gaps`/`confidence` for the next iteration.
- `gather_thoughts` — formats the thought log for the orchestrator/synthesizer to read.

### Prompts (`prompts/`)

Each agent's system/human prompt templates live in their own module (`decompose.py`, `research.py`, `subagents.py`, `synthesize.py`, `think.py`, `reflect.py`). `prompts/old/` holds superseded prompt versions kept for reference — not imported anywhere live.

### Model provider abstraction (`utils.py`)

`get_llm(model_provider, model_name)` validates the relevant API key against the provider's API *before* constructing the LangChain chat model (e.g. calls `anthropic.Anthropic(...).models.list()`), raising `LLMAuthenticationError` with structured context (provider, env var, reason, timestamp) on failure rather than surfacing a raw SDK exception. Supported providers: `anthropic`, `google`, `openai`, `huggingface`.
