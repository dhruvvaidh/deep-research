"""Orchestrator node: decomposes a research question into typed, parallel workstreams."""
from __future__ import annotations

import json
import os

from utils import get_llm
import config
from langchain.agents import create_agent

from graph.state import ResearchState
from prompts.decompose import DECOMPOSE_SYSTEM
from tools.thinking import reflect, gather_thoughts, strip_json_fences


def orchestrator_node(state: ResearchState) -> dict:
    """LangGraph node — decomposes the question or reflects on gaps between iterations.

    The prompt controls when reflect/gather_thoughts are called. The final agent
    output is either {"sufficient": true} or a JSON workstreams array.
    """
    iteration = state.get("iteration", 0)

    llm = get_llm(
        model_provider=config.MODEL_PROVIDER,
        model_name=config.MODEL_NAME,
    )

    agent = create_agent(llm, [reflect, gather_thoughts], system_prompt=DECOMPOSE_SYSTEM)
    input_payload = {
        "messages": [{
            "role": "user",
            "content": json.dumps({
                "question": state["question"],
                "iteration": iteration,
                "thought_log": state.get("thought_log", []),
                "context_manifest": state.get("manifest_index", {}),
            })
        }]
    }

    # The underlying model occasionally returns an empty/malformed response at this
    # tool-calling boundary (observed: Gemini finish_reason=MALFORMED_FUNCTION_CALL,
    # zero output tokens). Retry a couple of times before giving up.
    parsed = None
    last_error: Exception | None = None
    for attempt in range(1, 4):
        result = agent.invoke(input_payload)
        raw = result["messages"][-1].content
        if isinstance(raw, list):
            raw = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")
        raw = strip_json_fences(raw)
        try:
            parsed = json.loads(raw)
            break
        except json.JSONDecodeError as e:
            last_error = e
            print(f"[orchestrator] attempt {attempt}/3 returned unparseable output ({e}); retrying...")

    if parsed is None:
        print(f"[orchestrator] all attempts failed to produce parseable output ({last_error}); "
              f"treating research as sufficient rather than losing this run's progress.")
        return {"sufficient": True, "iteration": iteration}

    if isinstance(parsed, dict) and parsed.get("sufficient"):
        print(f"[orchestrator] Research sufficient. Moving to synthesizer.")
        return {"sufficient": True, "iteration": iteration}

    print(f"[orchestrator] Iteration {iteration + 1} — fanning out {len(parsed)} workstreams.")
    return {"sufficient": False, "workstreams": parsed, "iteration": iteration + 1}