"""Data Analyst sub-agent: executes Python code in a Daytona sandbox to analyse structured data."""
from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
import os

from graph.state import SubAgentState
from prompts.research import RESEARCH_SYSTEM, RESEARCH_HUMAN
from tools.code_executor import code_executor
from tools.context_store import get_context_index, store_context, summarize_context, save_dataset
from tools.file_reader import file_reader
from tools.yfinance_tool import yfinance_data

DATA_TOOLS = [
    code_executor,
    yfinance_data,
    file_reader,
    save_dataset,
    store_context,
    summarize_context,
    get_context_index,
]

_SYSTEM = (
    RESEARCH_SYSTEM
    + "\n\nYou specialise in quantitative and financial analysis. Follow this workflow strictly:\n\n"
    "1. **Fetch data** — use yfinance_data to pull market data. It automatically saves the raw "
    "DataFrame as a CSV in the sandbox and returns the file path. Do NOT use the raw data in "
    "your context — only use the returned CSV path.\n"
    "2. **Analyse via code** — pass the CSV path to code_executor. Your Python code should read "
    "the CSV from that path (e.g. `pd.read_csv('/home/daytona/artifacts/aapl_1y_ohlcv.csv')`) "
    "and perform all computations. Never pass raw data directly in the code string.\n"
    "3. **Store other datasets** — if you produce new tabular data (e.g. computed results), use "
    "save_dataset(key, csv_string, description) to persist it and get back a path.\n"
    "4. **Store text context** — for non-tabular results (web search output, text summaries), "
    "call store_context(key, content, description) then summarize_context(key).\n"
    "5. **Check existing data** — call get_context_index() first to see what other agents have "
    "already stored before fetching new data."
)


def data_analyst_node(state: SubAgentState) -> dict:
    """LangGraph node — analyses structured data for a workstream inside a Daytona sandbox.

    Receives via Send:
        task     — ResearchTask
        question — top-level research question
    """
    task = state["task"]
    question = state["question"]

    print(f"[data_analyst] Starting agent for workstream: '{task['workstream']}'")

    human_content = RESEARCH_HUMAN.format(
        question=question,
        workstream=task["workstream"],
        description=task["description"],
        query=task["query"],
    )

    llm = ChatGoogleGenerativeAI(
        model=os.environ['MODEL_NAME'],
        api_key=os.environ['GEMINI_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
    )
    agent = create_agent(llm, DATA_TOOLS, system_prompt=_SYSTEM)
    result = agent.invoke({"messages": [{"role": "user", "content": human_content}]})

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        findings = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")
    else:
        findings = raw
    return {"findings": {task["workstream"]: findings}}
