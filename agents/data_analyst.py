"""Data Analyst sub-agent: executes Python code in a Daytona sandbox to analyse structured data."""
from __future__ import annotations

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
import os

from graph.state import SubAgentState
from prompts.research import RESEARCH_HUMAN
from prompts.subagents import DATA_ANALYST
from tools.code_executor import code_executor
from tools.context_store import get_context_index, store_context, summarize_context, save_dataset
from tools.file_reader import file_reader
from tools.yfinance_tool import yfinance_data
from tools.thinking import think

DATA_TOOLS = [
    code_executor,
    yfinance_data,
    file_reader,
    save_dataset,
    store_context,
    summarize_context,
    get_context_index,
    think
]


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
        api_key=os.environ['GOOGLE_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
    )
    agent = create_agent(llm, DATA_TOOLS, system_prompt=DATA_ANALYST)
    result = agent.invoke({"messages": [{"role": "user", "content": human_content}]})

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        findings = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")
    else:
        findings = raw
    
    thought = None
    for message in result["messages"]:
        if hasattr(message, "name") and message.name == "think":
            raw_thought = message.content
            if isinstance(raw_thought, str):
                try:
                    thought = json.loads(raw_thought)
                except (json.JSONDecodeError, ValueError):
                    thought = None
            elif isinstance(raw_thought, dict):
                thought = raw_thought
            break
    return {"findings": {task["workstream"]: findings}, "thought_log": [thought] if thought else []}
