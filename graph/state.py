from typing import TypedDict, Annotated, Literal
import operator


class ResearchTask(TypedDict):
    workstream: str
    description: str
    query: str
    agent_type: Literal["web_researcher", "data_analyst", "domain_expert"]


class ThoughtEntry(TypedDict):
    agent: str
    iteration: int
    task: str
    gaps: list[str]
    sufficient: bool
    confidence: float  # 0.0 - 1.0

class ResearchState(TypedDict):
    question: str
    iteration: int
    sufficient: bool  # set by orchestrator via reflect; True → go to synthesizer
    workstreams: list[ResearchTask]
    manifest_index: dict[str, str]
    thought_log: Annotated[list[ThoughtEntry], operator.add]
    findings: Annotated[dict, operator.or_]
    report: str

class SubAgentState(TypedDict):
    """Private state injected into each specialist via Send()"""
    task: ResearchTask     
    question: str
