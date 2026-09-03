from __future__ import annotations

import json
import os
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from langchain.tools import tool
from prompts.think import THINK_PROMPT
from prompts.reflect import REFLECT_PROMPT
from graph.state import ThoughtEntry

llm = ChatGoogleGenerativeAI(
        model=os.environ['MODEL_NAME'],
        api_key=os.environ['GOOGLE_API_KEY'],
        project=os.environ['GOOGLE_PROJECT_ID'],
        vertexai=os.environ['GOOGLE_GENAI_USE_VERTEXAI']
    )


def strip_json_fences(text: str) -> str:
    """Strip a leading/trailing markdown code fence (```json ... ``` or ``` ... ```),
    since Gemini sometimes wraps JSON output in one despite prompt instructions not to."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()

@tool
def think(task: str, observations: str, manifest_index: dict) -> ThoughtEntry:
    """Reflect on whether current findings sufficiently answer the task.
    Returns gaps as concrete researchable questions if insufficient."""
    prompt = THINK_PROMPT.format(
        task=task,
        observations=observations,
        manifest_index=json.dumps(manifest_index, indent=2)
    )
    result = llm.invoke(prompt)
    raw = result.content
    if isinstance(raw, list):
        raw = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")
    return strip_json_fences(raw)

@tool
def reflect(
    question: str,
    thought_log: list[ThoughtEntry],
    manifest: dict,
) -> dict:
    """Assess whether the collective research across all workstreams is sufficient 
    to answer the original research question.

    Call this tool after all sub-agents have completed their workstreams.
    Pass the full thought_log from state and the context manifest from the sandbox.

    Returns:
        sufficient: bool — True if research is complete, False if gaps remain
        confidence: float — overall confidence across all workstreams (0.0 - 1.0)
        gaps: list[str] — concrete researchable questions that remain unanswered
        reasoning: str — cross-workstream explanation of the assessment
    """
    if not thought_log:
        return {
            "sufficient": False,
            "confidence": 0.0,
            "gaps": [question],
            "reasoning": "No research has been completed yet."
        }

    formatted_thoughts = "\n---\n".join(
        f"Agent: {entry['agent']}\n"
        f"Iteration: {entry['iteration']}\n"
        f"Task: {entry['task']}\n"
        f"Sufficient: {entry['sufficient']}\n"
        f"Confidence: {entry['confidence']}\n"
        f"Gaps: {', '.join(entry['gaps']) if entry['gaps'] else 'None'}"
        for entry in thought_log
    )

    result = llm.invoke(
        REFLECT_PROMPT.format(
            question=question,
            thought_log=formatted_thoughts,
            manifest=json.dumps(manifest, indent=2)
        )
    )

    raw = result.content
    if isinstance(raw, list):
        raw = "\n".join(b["text"] for b in raw if isinstance(b, dict) and b.get("type") == "text")
    raw = strip_json_fences(raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "sufficient": False,
            "confidence": 0.0,
            "gaps": [question],
            "reasoning": f"Failed to parse reflect response as JSON: {raw[:200]!r}",
        }

@tool
def gather_thoughts(thought_log: list[ThoughtEntry]) -> str:
    """Retrieve and format all thoughts from the thought log for reflection.
    
    Use this tool to read the collective research reflections from all 
    sub-agents before deciding whether further research is needed.
    """
    if not thought_log:
        return "No thoughts recorded yet. This is the first iteration."

    formatted = []
    for entry in thought_log:
        formatted.append(
            f"Agent: {entry['agent']}\n"
            f"Iteration: {entry['iteration']}\n"
            f"Task: {entry['task']}\n"
            f"Sufficient: {entry['sufficient']}\n"
            f"Confidence: {entry['confidence']}\n"
            f"Gaps: {', '.join(entry['gaps']) if entry['gaps'] else 'None'}\n"
        )

    return "\n---\n".join(formatted)


