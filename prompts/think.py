# prompts/think.py

THINK_PROMPT = """You are reflecting on the research findings from a single workstream as part of a larger research pipeline.

Your job is to honestly assess whether the findings from your assigned workstream are sufficient to contribute meaningfully to answering the overall research question.

You have access to:
- The workstream task you were assigned
- Your observations and findings from the research you performed
- The current context manifest showing what other agents have already stored

<task>
{task}
</task>

<observations>
{observations}
</observations>

<context_manifest>
{manifest_index}
</context_manifest>

Reflect carefully on the following:
- Does your research adequately address the workstream you were assigned?
- Are there gaps in your findings that another iteration could realistically fill?
- Does the context manifest show that other agents have already covered any of your gaps?

Respond ONLY with a valid JSON object matching this exact structure:
{{
    "agent": "<the agent type performing this reflection e.g. web_researcher, data_analyst, domain_expert>",
    "iteration": <current iteration number as an integer>,
    "task": "<the workstream identifier you were assigned>",
    "sufficient": <true or false>,
    "confidence": <float between 0.0 and 1.0 reflecting how thoroughly this workstream was covered>,
    "gaps": ["<concrete researchable question that remains unanswered>", "..."]
}}

Rules:
- sufficient must be a boolean — true only if your findings comprehensively address the workstream
- confidence must be a float between 0.0 and 1.0
- gaps must be a list of concrete, researchable questions — not vague statements. If there are no gaps, return an empty list []
- Do not include any text outside the JSON object
- Do not include markdown code fences
"""