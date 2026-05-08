"""Orchestrator node: decomposes a research question into typed, parallel workstreams."""
from __future__ import annotations

import json
import os

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

from graph.state import ResearchState
from prompts.decompose import DECOMPOSE_SYSTEM
from tools.thinking import reflect, gather_thoughts


def orchestrator_node(state: ResearchState) -> dict:
    """LangGraph node — decomposes the question or reflects on gaps between iterations.

    The prompt controls when reflect/gather_thoughts are called. The final agent
    output is either {"sufficient": true} or a JSON workstreams array.
    """
    iteration = state.get("iteration", 0)

    llm = ChatGoogleGenerativeAI(
        model=os.environ['MODEL_NAME'],
        api_key=os.environ['GEMINI_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
    )

    agent = create_agent(llm, [reflect, gather_thoughts], system_prompt=DECOMPOSE_SYSTEM)
    result = agent.invoke({
        "messages": [{
            "role": "user",
            "content": json.dumps({
                "question": state["question"],
                "iteration": iteration,
                "thought_log": state.get("thought_log", []),
                "context_manifest": state.get("manifest_index", {}),
            })
        }]
    })

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        raw = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")

    parsed = json.loads(raw)

    if isinstance(parsed, dict) and parsed.get("sufficient"):
        print(f"[orchestrator] Research sufficient. Moving to synthesizer.")
        return {"sufficient": True, "iteration": iteration}

    print(f"[orchestrator] Iteration {iteration + 1} — fanning out {len(parsed)} workstreams.")
    return {"sufficient": False, "workstreams": parsed, "iteration": iteration + 1}