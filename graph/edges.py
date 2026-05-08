"""Conditional routing logic between LangGraph nodes.

The key routing decision is the fan-out from the orchestrator:
each ResearchTask is sent to the specialist node whose agent_type matches.
"""
from __future__ import annotations

from langgraph.types import Send

from graph.state import ResearchState, SubAgentState
from config import MAX_ITERATIONS

# Map agent_type values to the node names registered in the graph
AGENT_NODE_MAP: dict[str, str] = {
    "web_researcher": "web_researcher",
    "data_analyst": "data_analyst",
    "domain_expert": "domain_expert",
}

_DEFAULT_NODE = "web_researcher"


def check_sufficient(state: ResearchState) -> str:
    """Decide whether to synthesize or fan out another round of research."""
    iteration = state.get("iteration", 0)
    if iteration >= MAX_ITERATIONS or state.get("sufficient", False):
        return "synthesizer"
    return "router"


def route_workstreams(state: ResearchState) -> list[Send]:
    """Fan out each workstream to the appropriate specialist node in parallel.

    Falls back to web_researcher for any unknown agent_type.
    """
    return [
        Send(
            AGENT_NODE_MAP.get(task.get("agent_type", ""), _DEFAULT_NODE),
            SubAgentState(task=task, question=state["question"]),
        )
        for task in state["workstreams"]
    ]
    