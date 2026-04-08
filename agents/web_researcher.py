"""Web Researcher sub-agent: Tavily search + web scraper for a single workstream."""
from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
import os

from graph.state import SubAgentState
from prompts.research import RESEARCH_SYSTEM, RESEARCH_HUMAN
from tools.context_store import get_context_index, store_context, summarize_context
from tools.tavily_search import tavily_search
from tools.web_scraper import web_scraper

WEB_TOOLS = [
    tavily_search,
    web_scraper,
    store_context,
    summarize_context,
    get_context_index,
]

_SYSTEM = (
    RESEARCH_SYSTEM
    + "\n\nYou specialise in web research. Use tavily_search to find relevant pages and "
    "web_scraper to extract full content. After each heavy tool call, immediately use "
    "store_context(key, raw_output, description) to persist the raw data to the sandbox "
    "filesystem — do NOT keep large raw results in your context. Then call "
    "summarize_context(key) to get a compact summary to include in your findings. "
    "Use get_context_index() to discover context already stored by other agents."
)


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
    agent = create_agent(llm, WEB_TOOLS, system_prompt=_SYSTEM)
    result = agent.invoke({"messages": [{"role": "user", "content": human_content}]})

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        findings = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")
    else:
        findings = raw
    return {"findings": {task["workstream"]: findings}}
