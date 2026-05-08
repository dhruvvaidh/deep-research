REFLECT_PROMPT = """You are assessing whether the collective research gathered across all workstreams is sufficient to answer the user's original research question.

You have access to:
1. The original research question
2. The thought log — reflections from each sub-agent on their individual workstream
3. The context manifest — a summary of all artifacts collected across all workstreams

Your job is to reason across ALL of these holistically. A workstream that looks insufficient in isolation may be covered by another agent's findings. Two workstreams that both appear sufficient may together still leave a critical gap.

Original question:
{question}

Thought log:
{thought_log}

Context manifest:
{manifest}

Assess the collective research and respond ONLY with a JSON object in this exact format:
{{
    "sufficient": <true or false>,
    "confidence": <float between 0.0 and 1.0>,
    "gaps": [<list of concrete researchable questions that remain unanswered>],
    "reasoning": "<explanation of your assessment across all workstreams>"
}}

Do not include any text outside the JSON object.
"""