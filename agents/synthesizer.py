"""Synthesizer agent: ReAct agent that interrogates the context store and research plan
to produce a final well-evidenced markdown report."""
from __future__ import annotations

import os
from datetime import datetime

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

from graph.state import ResearchState
from prompts.synthesize import SYNTHESIZE_SYSTEM, SYNTHESIZE_HUMAN
from tools.context_store import get_context_index

SYNTH_TOOLS = [get_context_index]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


def synthesizer_node(state: ResearchState) -> dict:
    """LangGraph node — interrogates the context store then writes the final report.

    Process:
    1. Formats the research plan (workstreams) and specialist findings for the prompt.
    2. Runs a ReAct agent that calls get_context_index() and summarize_context() to
       ground conclusions in raw artifact evidence before writing.
    3. Saves the final report to outputs/<timestamp>.md.
    """
    workstreams: list[dict] = state.get("workstreams") or []
    findings: dict[str, str] = dict(state.get("findings") or {})

    workstreams_text = "\n\n".join(
        f"**{ws['workstream']}** ({ws['agent_type']})\n"
        f"Goal: {ws['description']}\n"
        f"Query: {ws['query']}"
        for ws in workstreams
    )

    findings_text = "\n\n".join(
        f"### {workstream}\n{content}" for workstream, content in findings.items()
    )

    human_content = SYNTHESIZE_HUMAN.format(
        question=state["question"],
        workstreams_text=workstreams_text,
        findings_text=findings_text,
    )

    llm = ChatGoogleGenerativeAI(
        model=os.environ['MODEL_NAME'],
        api_key=os.environ['GEMINI_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
    )
    agent = create_agent(llm, SYNTH_TOOLS, system_prompt=SYNTHESIZE_SYSTEM)
    result = agent.invoke({"messages": [{"role": "user", "content": human_content}]})

    raw = result["messages"][-1].content
    if isinstance(raw, list):
        report = "\n".join(
            block["text"] for block in raw
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        report = raw

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_q = "".join(c if c.isalnum() or c in " _-" else "" for c in state["question"])[:60]
    filename = f"{timestamp}_{safe_q.replace(' ', '_')}.md"
    output_path = os.path.join(OUTPUT_DIR, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[synthesizer] Report saved → {output_path}")
    return {"report": report}
