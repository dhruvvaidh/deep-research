"""Tools for storing raw tool outputs to the sandbox filesystem and summarizing them.

Design intent:
    Token-heavy tool results (web pages, search results, financial data) are written
    to the Daytona FS via store_context().  Only a compact LLM-generated summary is
    ever returned to the agent — raw content never enters the context window unless
    explicitly requested.

    A JSON manifest file (context_manifest.json) acts as a directory that any agent
    can inspect with get_context_index() before deciding what to retrieve.

Usage pattern inside a ReAct agent:
    1. Call a data tool (tavily_search, web_scraper, yfinance_data, …)
    2. store_context("key", raw_result, "short description")
    3. summarize_context("key")  → compact summary to include in findings
    4. Optionally call get_context_index() to discover context from other agents
"""
from __future__ import annotations

import json
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool

import tools.artifact_store as _artifact_store_module

CONTEXT_DIR_PREFIX = "ctx_"
MANIFEST_FILENAME = "context_manifest.json"

_SUMMARIZE_PROMPT = (
    "You are a research assistant. Produce a concise but information-dense summary "
    "of the following raw research data. Preserve all key facts, figures, dates, and "
    "names. Do not add commentary or recommendations — just summarise the content.\n\n"
    "RAW DATA:\n{content}"
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _ws():
    return _artifact_store_module.get_workspace()


def _load_manifest(ws) -> dict:
    from sandbox.artifact_manager import read_artifact
    try:
        raw = read_artifact(ws, MANIFEST_FILENAME)
        return json.loads(raw)
    except Exception:
        return {}


def _save_manifest(ws, manifest: dict) -> None:
    from sandbox.artifact_manager import write_artifact
    write_artifact(ws, MANIFEST_FILENAME, json.dumps(manifest, indent=2))


def _context_filename(key: str) -> str:
    return f"{CONTEXT_DIR_PREFIX}{key}.txt"


# ---------------------------------------------------------------------------
# LangChain tools
# ---------------------------------------------------------------------------

@tool
def store_context(key: str, content: str, description: str = "") -> str:
    """Store raw tool output to the sandbox filesystem and register it in the context index.

    Call this immediately after any token-heavy tool (web_scraper, tavily_search,
    yfinance_data, arxiv_search, etc.) to persist the raw result without keeping it
    in the context window.

    Args:
        key:         Unique identifier for this piece of context (e.g. "climate_web_search").
                     Use snake_case, no spaces.
        content:     Raw text content to store (the full tool output).
        description: One-line description of what the content contains. Used by other
                     agents to decide whether to retrieve it.

    Returns:
        Confirmation message with storage key and character count.
    """
    from sandbox.artifact_manager import write_artifact

    ws = _ws()
    filename = _context_filename(key)
    write_artifact(ws, filename, content)

    manifest = _load_manifest(ws)
    manifest[key] = {
        "filename": filename,
        "description": description or "(no description)",
        "size_chars": len(content),
    }
    _save_manifest(ws, manifest)

    return (
        f"Context stored under key '{key}' ({len(content):,} chars). "
        f"Retrieve with summarize_context('{key}')."
    )


@tool
def summarize_context(key: str) -> str:
    """Read a stored context file and return a concise LLM-generated summary.

    The summary is compact enough to include in your findings without bloating
    the context window.  The raw file remains on disk for other agents to access.

    Args:
        key: The key used when the context was stored with store_context().
             Call get_context_index() to see all available keys.

    Returns:
        A concise summary of the stored content.
    """
    from sandbox.artifact_manager import read_artifact

    ws = _ws()
    filename = _context_filename(key)

    try:
        content = read_artifact(ws, filename)
    except Exception:
        return (
            f"No context found for key '{key}'. "
            "Use get_context_index() to see available keys."
        )

    llm = ChatGoogleGenerativeAI(
        model=os.environ['MODEL_NAME'],
        api_key=os.environ['GEMINI_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
    )
    response = llm.invoke(_SUMMARIZE_PROMPT.format(content=content))
    summary: str = response.content

    # Cache the summary back into the manifest so get_context_index() returns it
    manifest = _load_manifest(ws)
    if key in manifest:
        manifest[key]["summary"] = summary
        _save_manifest(ws, manifest)

    return summary


@tool
def save_dataset(key: str, csv_content: str, description: str = "") -> str:
    """Save a dataset as a CSV file in the sandbox and register it in the context index.

    Use this immediately after fetching any tabular or time-series data to persist it
    to disk so code_executor can read it by path — never pass raw data to the LLM.

    Args:
        key:         Unique identifier for this dataset (e.g. "aapl_price_history").
                     Use snake_case, no spaces.
        csv_content: Raw CSV string (header row + data rows).
        description: One-line description of the dataset (e.g. "AAPL daily OHLCV 1y").

    Returns:
        The sandbox file path to pass directly to code_executor
        (e.g. "/home/daytona/artifacts/aapl_price_history.csv").
    """
    from sandbox.artifact_manager import write_artifact

    ws = _ws()
    filename = f"{key}.csv"
    path = write_artifact(ws, filename, csv_content)

    manifest = _load_manifest(ws)
    manifest[key] = {
        "filename": filename,
        "description": description or "(no description)",
        "size_chars": len(csv_content),
        "type": "dataset",
        "path": path,
    }
    _save_manifest(ws, manifest)

    return path


@tool
def get_context_index() -> str:
    """Return the manifest of all context files stored in the sandbox.

    Use this to discover what raw data other agents (or your own earlier tool calls)
    have already stored, before deciding whether to fetch new data or summarise
    existing context.

    Returns:
        JSON string mapping keys to {filename, description, size_chars}.
        Returns an empty JSON object '{}' if nothing has been stored yet.
    """
    ws = _ws()
    manifest = _load_manifest(ws)
    if not manifest:
        return "{}"
    return json.dumps(manifest, indent=2)
