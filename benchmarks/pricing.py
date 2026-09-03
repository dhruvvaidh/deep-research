"""Per-token pricing for models used in the benchmark sweep.

Source: https://ai.google.dev/gemini-api/docs/pricing (paid tier, standard),
checked 2026-09-02. Gemini 2.5 Flash output price includes thinking tokens
(no separate thinking-token rate).

Prices are USD per 1,000,000 tokens.
"""
from __future__ import annotations

PRICING_PER_MILLION_TOKENS: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    """Return the USD cost for the given token counts, or None if the model is unpriced."""
    rates = PRICING_PER_MILLION_TOKENS.get(model)
    if rates is None:
        return None
    return (prompt_tokens / 1_000_000) * rates["input"] + (completion_tokens / 1_000_000) * rates["output"]
