"""Domain Expert sub-agent: academic reasoning and cross-referencing of findings."""
from __future__ import annotations

from deepagents import CompiledSubAgent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
import os

from graph.state import SubAgentState
from prompts.research import RESEARCH_SYSTEM, RESEARCH_HUMAN
from tools.arxiv_search import arxiv_search
from tools.context_store import get_context_index, store_context, summarize_context
from tools.tavily_search import tavily_search
from tools.wikipedia import wikipedia_search

EXPERT_TOOLS = [
    arxiv_search,
    wikipedia_search,
    tavily_search,
    store_context,
    summarize_context,
    get_context_index,
]

_SYSTEM = (
    RESEARCH_SYSTEM
    + "\n\nYou are a domain expert. Use arxiv_search for peer-reviewed literature, "
    "wikipedia_search for background context, and tavily_search for recent developments. "
    "After each heavy tool call, immediately use store_context(key, raw_output, description) "
    "to persist the raw data off-context, then summarize_context(key) to get a compact summary. "
    "Call get_context_index() at the start to see what other agents have already stored — "
    "use summarize_context() to cross-reference their findings before drawing conclusions."
)

# Compiled react agent graph — exposes a 'messages' key in state (required by CompiledSubAgent)
_llm = ChatGoogleGenerativeAI(
        model=os.environ['MODEL_NAME'],
        api_key=os.environ['GEMINI_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
    )
_domain_expert_graph = create_agent(_llm, EXPERT_TOOLS, system_prompt=_SYSTEM)

# CompiledSubAgent spec — used as a tool by a parent deep agent, or invoked directly below
domain_expert_subagent = CompiledSubAgent(
    name="domain_expert",
    description=(
        "Academic and cross-domain research specialist. Searches arxiv, Wikipedia, and the web. "
        "Calls get_context_index() first to discover what other agents have already stored "
        "before beginning research."
    ),
    runnable=_domain_expert_graph,
)


def domain_expert_node(state: SubAgentState) -> dict:
    """LangGraph node — provides deep analytical reasoning for a workstream.

    Receives via Send:
        task     — ResearchTask
        question — top-level research question
    """
    task = state["task"]
    question = state["question"]

    print(f"[domain_expert] Starting agent for workstream: '{task['workstream']}'")

    human_content = RESEARCH_HUMAN.format(
        question=question,
        workstream=task["workstream"],
        description=task["description"],
        query=task["query"],
    )

    result = domain_expert_subagent["runnable"].invoke(
        {"messages": [{"role": "user", "content": human_content}]}
    )

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        findings = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")
    else:
        findings = raw
    return {"findings": {task["workstream"]: findings}}
