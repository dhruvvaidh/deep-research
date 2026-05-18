"""Domain Expert sub-agent: academic reasoning and cross-referencing of findings."""
from __future__ import annotations

import json
from deepagents import CompiledSubAgent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent
import os

from graph.state import SubAgentState
from prompts.research import RESEARCH_HUMAN
from prompts.subagents import RESEARCHER
from tools.thinking import think
from tools.arxiv_search import arxiv_search
from tools.context_store import get_context_index, store_context, summarize_context
from tools.tavily_search import tavily_search
from tools.wikipedia import wikipedia_search

from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage


@wrap_tool_call
def handle_tool_errors(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        return handler(request)
    except Exception as e:
        
        return ToolMessage(
            content=f"Tool error: Please check your input and try again. ({str(e)})",
            tool_call_id=request.tool_call["id"]
        )

# Compiled react agent graph — exposes a 'messages' key in state (required by CompiledSubAgent)
_llm = ChatGoogleGenerativeAI(
        model=os.environ['MODEL_NAME'],
        api_key=os.environ['GOOGLE_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
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

    EXPERT_TOOLS = [arxiv_search,wikipedia_search,tavily_search,
                    store_context,summarize_context,get_context_index,think]

    _domain_expert_graph = create_agent(model = _llm,
                                        tools= EXPERT_TOOLS, 
                                        system_prompt=RESEARCHER, 
                                        middleware=[handle_tool_errors]
                                        )

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

    result = domain_expert_subagent["runnable"].invoke(
        {"messages": [{"role": "user", "content": human_content}]}
    )

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
