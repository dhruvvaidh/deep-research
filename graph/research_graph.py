"""LangGraph StateGraph wiring all agents together for the deep-research pipeline.

Flow:
    START
      └─ orchestrator              (decomposes question into typed workstreams)
           └─ route_orchestrator   (fan-out or synthesize decision)
                ├─ web_researcher  ─┐
                ├─ data_analyst    ─┤─ converge back to orchestrator
                └─ domain_expert   ─┘
                      └─ orchestrator (reflect → re-research or synthesize)
                              └─ synthesizer
                                    └─ END

"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.data_analyst import data_analyst_node
from agents.domain_expert import domain_expert_node
from agents.orchestrator import orchestrator_node
from agents.synthesizer import synthesizer_node
from agents.web_researcher import web_researcher_node
from graph.edges import check_sufficient, route_workstreams
from graph.state import ResearchState


def router_node(state: ResearchState) -> dict:
    return {}


def build_graph():
    """Assemble and compile the research StateGraph."""
    g = StateGraph(ResearchState)

    # Nodes
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("router", router_node)
    g.add_node("web_researcher", web_researcher_node)
    g.add_node("data_analyst", data_analyst_node)
    g.add_node("domain_expert", domain_expert_node)
    g.add_node("synthesizer", synthesizer_node)

    # Edges
    g.add_edge(START, "orchestrator")

    # Stop or continue decision
    g.add_conditional_edges("orchestrator", check_sufficient, ["router", "synthesizer"])

    # Fan-out: router → specialist nodes (parallel, routed by agent_type)
    g.add_conditional_edges(
        "router",
        route_workstreams,
        ["web_researcher", "data_analyst", "domain_expert"],
    )

    # All specialists converge back on orchestrator
    g.add_edge("web_researcher", "orchestrator")
    g.add_edge("data_analyst", "orchestrator")
    g.add_edge("domain_expert", "orchestrator")

    g.add_edge("synthesizer", END)

    return g.compile()


graph = build_graph()
