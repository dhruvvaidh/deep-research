"""LangGraph StateGraph wiring all agents together for the deep-research pipeline.

Flow:
    START
      └─ orchestrator              (decomposes question into typed workstreams)
           └─ [Send] per workstream, routed by agent_type:
                ├─ web_researcher  (Tavily + web scraper)
                ├─ data_analyst    (code executor + yfinance + file reader)
                └─ domain_expert   (arxiv + wikipedia + cross-referencing)
                     └─ synthesizer (reads all findings + artifacts → final report)
                          └─ END
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.data_analyst import data_analyst_node
from agents.domain_expert import domain_expert_node
from agents.orchestrator import orchestrator_node
from agents.synthesizer import synthesizer_node
from agents.web_researcher import web_researcher_node
from graph.edges import route_workstreams
from graph.state import ResearchState


def build_graph():
    """Assemble and compile the research StateGraph."""
    g = StateGraph(ResearchState)

    # Nodes
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("web_researcher", web_researcher_node)
    g.add_node("data_analyst", data_analyst_node)
    g.add_node("domain_expert", domain_expert_node)
    g.add_node("synthesizer", synthesizer_node)

    # Edges
    g.add_edge(START, "orchestrator")

    # Fan-out: orchestrator → specialist nodes (parallel, routed by agent_type)
    g.add_conditional_edges(
        "orchestrator",
        route_workstreams,
        ["web_researcher", "data_analyst", "domain_expert"],
    )

    # All specialists converge on synthesizer
    g.add_edge("web_researcher", "synthesizer")
    g.add_edge("data_analyst", "synthesizer")
    g.add_edge("domain_expert", "synthesizer")

    g.add_edge("synthesizer", END)

    return g.compile()


# Module-level compiled graph — import and invoke directly:
#   from graph.research_graph import graph
#   result = graph.invoke({"question": "..."})
graph = build_graph()
