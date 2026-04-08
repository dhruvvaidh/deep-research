from typing import TypedDict, Annotated, Literal
import operator


class ResearchTask(TypedDict):
    workstream: str
    description: str
    query: str
    agent_type: Literal["web_researcher", "data_analyst", "domain_expert"]


class ResearchState(TypedDict):
    question: str
    workstreams: list[ResearchTask]
    findings: Annotated[dict, operator.or_]   # keyed by workstream name
    report: str

class SubAgentState(TypedDict):
    """Private state injected into each specialist via Send()"""
    task: ResearchTask     
    question: str
