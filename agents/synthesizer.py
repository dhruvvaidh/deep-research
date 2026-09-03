"""Synthesizer agent: ReAct agent that interrogates the context store and research plan
to produce a final well-evidenced markdown report."""
from __future__ import annotations

import os
from datetime import datetime

from utils import get_llm
import config
from langchain.agents import create_agent

from graph.state import ResearchState
from prompts.synthesize import SYNTHESIZE_SYSTEM, SYNTHESIZE_HUMAN
from tools.context_store import get_context_index
from tools.artifact_store import read_artifact
from tools.thinking import gather_thoughts

SYNTH_TOOLS = [gather_thoughts, get_context_index, read_artifact]

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")


def synthesizer_node(state: ResearchState) -> dict:
    """LangGraph node — interrogates the context store then writes the final report.

    Process:
    1. Calls gather_thoughts to retrieve the full thought_log from state.
    2. Uses thoughts to reason about which artifacts are relevant.
    3. Reads context_manifest by calling get_context_index to get the index of available artifacts.
    4. Selectively calls read_artifact only on relevant files.
    5. Saves the final report to outputs/<timestamp>.md.
    """
    human_content = SYNTHESIZE_HUMAN.format(
        question=state["question"],
        thought_log=state.get("thought_log", []),
    )

    llm = get_llm(
        model_provider=config.MODEL_PROVIDER,
        model_name=config.MODEL_NAME,
    )
    agent = create_agent(llm, SYNTH_TOOLS, system_prompt=SYNTHESIZE_SYSTEM)
    input_payload = {"messages": [{"role": "user", "content": human_content}]}

    # The underlying model occasionally ends its turn with empty content instead of
    # the report (observed: finish_reason=STOP, zero output tokens). Retry rather than
    # silently persisting an empty report after a long, expensive ReAct loop.
    report = ""
    for attempt in range(1, 4):
        result = agent.invoke(input_payload)
        raw = result["messages"][-1].content
        if isinstance(raw, list):
            report = "\n".join(
                block["text"] for block in raw
                if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            report = raw or ""
        if report.strip():
            break
        print(f"[synthesizer] attempt {attempt}/3 returned an empty report; retrying...")

    if not report.strip():
        report = (
            "_Synthesis failed: the model returned an empty response after 3 attempts. "
            "Raw research findings are still available in the sandbox context store._"
        )

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_q = "".join(c if c.isalnum() or c in " _-" else "" for c in state["question"])[:60]
    filename = f"{timestamp}_{safe_q.replace(' ', '_')}.md"
    output_path = os.path.join(OUTPUT_DIR, filename)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"[synthesizer] Report saved → {output_path}")
    return {"report": report}