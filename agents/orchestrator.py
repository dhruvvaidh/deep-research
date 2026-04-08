"""Orchestrator node: decomposes a research question into typed, parallel workstreams."""
from __future__ import annotations

import json

from langchain_anthropic import ChatAnthropic
import os

from graph.state import ResearchState, ResearchTask
from prompts.decompose import decompose_prompt


def orchestrator_node(state: ResearchState) -> dict:
    """LangGraph node — uses an LLM to decompose the question into ResearchTask objects.

    Each task includes an agent_type field so the router can fan out to the correct
    specialist (web_researcher, data_analyst, or domain_expert).
    """
    llm = ChatAnthropic(model=os.environ['DECOMPOSE_MODEL_NAME'], temperature=0)
    chain = decompose_prompt | llm
    result = chain.invoke({"question": state["question"]})
    workstreams: list[ResearchTask] = json.loads(result.content)
    return {"workstreams": workstreams}
