"""Web Researcher sub-agent: Tavily search + web scraper for a single workstream."""
from __future__ import annotations

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
import os

from graph.state import SubAgentState
from prompts.research import RESEARCH_HUMAN
from prompts.subagents import WEB_RESEARCHER
from tools.context_store import get_context_index, store_context, summarize_context
from tools.tavily_search import tavily_search
from tools.web_scraper import web_scraper
from tools.thinking import think

WEB_TOOLS = [
    tavily_search,
    web_scraper,
    store_context,
    summarize_context,
    get_context_index,
    think
]


def web_researcher_node(state: SubAgentState) -> dict:
    """LangGraph node — researches a workstream via web search and scraping.

    Receives via Send:
        task     — ResearchTask
        question — top-level research question
    """
    task = state["task"]
    question = state["question"]

    print(f"[web_researcher] Starting agent for workstream: '{task['workstream']}'")

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
    agent = create_agent(llm, WEB_TOOLS, system_prompt=WEB_RESEARCHER)
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
