"""Turns run_manifest.json + the LangSmith export into the three resume metrics:

  1. Context-store compression  — tokens/cost avoided by summarizing raw tool
     output on disk instead of returning it straight into agent context.
  2. Parallel fan-out speedup   — wall-clock saved by running specialist
     workstreams concurrently instead of sequentially, derived from LangSmith
     timestamps (no separate sequential run needed).
  3. Iteration cost/quality tradeoff — cost, latency, and self-reported
     confidence at MAX_ITERATIONS = 1, 2, 3.

Reads:
    benchmarks/results/run_manifest.json
    benchmarks/results/langsmith_export/<root_run_id>.json

Writes:
    benchmarks/results/metrics_summary.json
    benchmarks/results/metrics_summary.md

Usage:
    python scripts/analyze_metrics.py
"""
from __future__ import annotations

import json
import os
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from benchmarks.pricing import estimate_cost_usd

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "benchmarks" / "results"
MANIFEST_PATH = RESULTS_DIR / "run_manifest.json"
EXPORT_DIR = RESULTS_DIR / "langsmith_export"

CHARS_PER_TOKEN = 4.0  # documented heuristic fallback, English text
MODEL_NAME = os.environ.get("MODEL_NAME", "gemini-2.5-flash")

SPECIALIST_NAMES = {"web_researcher", "data_analyst", "domain_expert",
                     "web_researcher_node", "data_analyst_node", "domain_expert_node"}


def _load_json(path: Path):
    return json.loads(path.read_text()) if path.exists() else None


def _parse_time(s: str | None):
    return datetime.fromisoformat(s) if s else None


# ---------------------------------------------------------------------------
# Method 1: context-store compression
# ---------------------------------------------------------------------------

def _summarize_llm_tokens(trace: dict) -> tuple[int, int, int]:
    """Sum prompt/completion/total tokens of LLM calls made directly by summarize_context."""
    runs = trace["runs"]
    summarize_run_ids = {r["run_id"] for r in runs if r["name"] == "summarize_context"}
    prompt = completion = total = 0
    for r in runs:
        if r["run_type"] == "llm" and r["parent_run_id"] in summarize_run_ids:
            prompt += r["prompt_tokens"] or 0
            completion += r["completion_tokens"] or 0
            total += r["total_tokens"] or 0
    return prompt, completion, total


def method1_context_compression(records: list[dict], traces: dict[str, dict]) -> dict:
    per_run = []
    for rec in records:
        manifest = rec.get("context_manifest_snapshot") or {}
        raw_chars_all = sum(v.get("size_chars", 0) for v in manifest.values())
        raw_chars_summarized = sum(
            v.get("size_chars", 0) for v in manifest.values() if "summary" in v
        )
        summary_chars = sum(len(v.get("summary", "")) for v in manifest.values() if "summary" in v)

        raw_tokens_est = raw_chars_all / CHARS_PER_TOKEN
        summary_tokens_est = summary_chars / CHARS_PER_TOKEN

        naive_cost_est = estimate_cost_usd(MODEL_NAME, prompt_tokens=raw_tokens_est, completion_tokens=0)

        trace = traces.get(rec.get("root_run_id"))
        summarization_cost_actual = None
        summarization_tokens_actual = None
        if trace:
            p, c, t = _summarize_llm_tokens(trace)
            summarization_tokens_actual = t
            summarization_cost_actual = estimate_cost_usd(MODEL_NAME, prompt_tokens=p, completion_tokens=c)

        savings_est = None
        if naive_cost_est is not None and summarization_cost_actual is not None:
            savings_est = naive_cost_est - summarization_cost_actual

        per_run.append({
            "question_id": rec["question_id"],
            "max_iterations": rec["max_iterations"],
            "keys_stored": len(manifest),
            "keys_summarized": sum(1 for v in manifest.values() if "summary" in v),
            "raw_chars_all": raw_chars_all,
            "raw_chars_summarized_subset": raw_chars_summarized,
            "summary_chars": summary_chars,
            "compression_ratio": (raw_chars_summarized / summary_chars) if summary_chars else None,
            "raw_tokens_est": raw_tokens_est,
            "summary_tokens_est": summary_tokens_est,
            "naive_cost_usd_est": naive_cost_est,
            "summarization_tokens_actual": summarization_tokens_actual,
            "summarization_cost_usd_actual": summarization_cost_actual,
            "net_savings_usd_est": savings_est,
        })

    ratios = [r["compression_ratio"] for r in per_run if r["compression_ratio"]]
    savings = [r["net_savings_usd_est"] for r in per_run if r["net_savings_usd_est"] is not None]

    return {
        "per_run": per_run,
        "aggregate": {
            "median_compression_ratio": statistics.median(ratios) if ratios else None,
            "total_net_savings_usd_est": sum(savings) if savings else None,
            "mean_net_savings_usd_per_run_est": statistics.mean(savings) if savings else None,
            "note": (
                "net_savings_usd_est is a conservative floor: it compares the cost of "
                "the real summarize_context LLM calls against the counterfactual cost of "
                "sending all stored raw content once as prompt tokens. It does not count "
                "that, in a naive design, uncompressed raw content would also be re-sent on "
                "every subsequent agent turn within the same ReAct loop -- so actual savings "
                "in a long-running agent are larger than this estimate."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Method 2: parallel fan-out speedup (derived from LangSmith timestamps)
# ---------------------------------------------------------------------------

def _cluster_concurrent(runs: list[dict]) -> list[list[dict]]:
    """Cluster runs whose [start,end] intervals overlap (interval-overlap clustering)."""
    timed = [r for r in runs if r["start_time"] and r["end_time"]]
    timed.sort(key=lambda r: r["start_time"])
    clusters: list[list[dict]] = []
    for r in timed:
        placed = False
        for cluster in clusters:
            cluster_end = max(_parse_time(x["end_time"]) for x in cluster)
            if _parse_time(r["start_time"]) < cluster_end:
                cluster.append(r)
                placed = True
                break
        if not placed:
            clusters.append([r])
    return clusters


def method2_parallel_speedup(records: list[dict], traces: dict[str, dict]) -> dict:
    per_run = []
    all_speedups = []
    for rec in records:
        trace = traces.get(rec.get("root_run_id"))
        if not trace:
            continue
        specialist_runs = [r for r in trace["runs"] if r["name"] in SPECIALIST_NAMES]
        clusters = [c for c in _cluster_concurrent(specialist_runs) if len(c) >= 2]

        run_speedups = []
        for cluster in clusters:
            latencies = [x["latency_seconds"] for x in cluster if x["latency_seconds"]]
            starts = [_parse_time(x["start_time"]) for x in cluster]
            ends = [_parse_time(x["end_time"]) for x in cluster]
            wall = (max(ends) - min(starts)).total_seconds()
            if wall > 0 and latencies:
                speedup = sum(latencies) / wall
                run_speedups.append(speedup)
                all_speedups.append(speedup)

        per_run.append({
            "question_id": rec["question_id"],
            "max_iterations": rec["max_iterations"],
            "concurrent_clusters": len(clusters),
            "cluster_sizes": [len(c) for c in clusters],
            "speedups": run_speedups,
        })

    return {
        "per_run": per_run,
        "aggregate": {
            "median_speedup": statistics.median(all_speedups) if all_speedups else None,
            "n_concurrent_clusters": len(all_speedups),
            "note": (
                "Speedup = sum(individual specialist latencies) / actual wall-clock span "
                "for specialist runs whose LangSmith start/end intervals overlap within the "
                "same trace. No separate sequential run was needed."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Method 3: iteration cost/quality tradeoff
# ---------------------------------------------------------------------------

def _trace_tokens_and_cost(trace: dict) -> dict:
    root = trace["root"]
    prompt, completion, total = root.get("prompt_tokens"), root.get("completion_tokens"), root.get("total_tokens")
    if not total:
        prompt = sum(r["prompt_tokens"] or 0 for r in trace["runs"] if r["run_type"] == "llm")
        completion = sum(r["completion_tokens"] or 0 for r in trace["runs"] if r["run_type"] == "llm")
        total = prompt + completion
    cost = root.get("total_cost")
    if cost is None:
        cost = estimate_cost_usd(MODEL_NAME, prompt_tokens=prompt or 0, completion_tokens=completion or 0)
    return {"prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": total, "cost_usd": cost}


def method3_iteration_tradeoff(records: list[dict], traces: dict[str, dict]) -> dict:
    by_iter: dict[int, list[dict]] = {}
    for rec in records:
        trace = traces.get(rec.get("root_run_id"))
        tok = _trace_tokens_and_cost(trace) if trace else {"prompt_tokens": None, "completion_tokens": None, "total_tokens": None, "cost_usd": None}
        confidences = [t["confidence"] for t in (rec.get("thought_log") or []) if t.get("confidence") is not None]
        by_iter.setdefault(rec["max_iterations"], []).append({
            "question_id": rec["question_id"],
            "wall_clock_seconds": rec.get("wall_clock_seconds"),
            "report_chars": rec.get("report_chars"),
            "mean_confidence": statistics.mean(confidences) if confidences else None,
            **tok,
        })

    summary = {}
    for n, runs in sorted(by_iter.items()):
        costs = [r["cost_usd"] for r in runs if r["cost_usd"] is not None]
        tokens = [r["total_tokens"] for r in runs if r["total_tokens"] is not None]
        walls = [r["wall_clock_seconds"] for r in runs if r["wall_clock_seconds"] is not None]
        confs = [r["mean_confidence"] for r in runs if r["mean_confidence"] is not None]
        summary[str(n)] = {
            "n_runs": len(runs),
            "mean_total_tokens": statistics.mean(tokens) if tokens else None,
            "mean_cost_usd": statistics.mean(costs) if costs else None,
            "mean_wall_clock_seconds": statistics.mean(walls) if walls else None,
            "mean_self_reported_confidence": statistics.mean(confs) if confs else None,
            "runs": runs,
        }

    return {
        "by_max_iterations": summary,
        "note": (
            "mean_self_reported_confidence comes from the orchestrator's own reflect/think "
            "tool output (0-1 self-assessment), not an external ground-truth quality judge."
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _render_markdown(summary: dict) -> str:
    lines = ["# Benchmark metrics summary", ""]

    lines += ["## Method 1 — Context-store compression", ""]
    agg1 = summary["method1_context_compression"]["aggregate"]
    lines.append(f"- Median compression ratio (raw chars / summary chars): "
                 f"{agg1['median_compression_ratio']:.1f}x" if agg1["median_compression_ratio"] else "- No data")
    if agg1["total_net_savings_usd_est"] is not None:
        lines.append(f"- Estimated cost avoided across all runs: ${agg1['total_net_savings_usd_est']:.4f} "
                     f"(${agg1['mean_net_savings_usd_per_run_est']:.4f}/run, conservative floor)")
    lines.append("")

    lines += ["## Method 2 — Parallel fan-out speedup", ""]
    agg2 = summary["method2_parallel_speedup"]["aggregate"]
    if agg2["median_speedup"] is not None:
        lines.append(f"- Median speedup across {agg2['n_concurrent_clusters']} concurrent specialist "
                     f"clusters: {agg2['median_speedup']:.2f}x")
    else:
        lines.append("- No concurrent specialist clusters found")
    lines.append("")

    lines += ["## Method 3 — Iteration cost/quality tradeoff", "",
              "| max_iterations | n_runs | mean tokens | mean cost (USD) | mean wall-clock (s) | mean confidence |",
              "|---|---|---|---|---|---|"]

    def _fmt(value, spec):
        return format(value, spec) if value is not None else "n/a"

    for n, row in summary["method3_iteration_tradeoff"]["by_max_iterations"].items():
        lines.append(
            f"| {n} | {row['n_runs']} | "
            f"{_fmt(row['mean_total_tokens'], '.0f')} | "
            f"{_fmt(row['mean_cost_usd'], '.4f')} | "
            f"{_fmt(row['mean_wall_clock_seconds'], '.1f')} | "
            f"{_fmt(row['mean_self_reported_confidence'], '.2f')} |"
        )
    return "\n".join(lines)


def main() -> None:
    records = _load_json(MANIFEST_PATH) or []
    records = [r for r in records if r.get("root_run_id")]

    traces = {}
    for rec in records:
        trace = _load_json(EXPORT_DIR / f"{rec['root_run_id']}.json")
        if trace:
            traces[rec["root_run_id"]] = trace

    summary = {
        "model": MODEL_NAME,
        "n_runs_analyzed": len(records),
        "n_traces_found": len(traces),
        "method1_context_compression": method1_context_compression(records, traces),
        "method2_parallel_speedup": method2_parallel_speedup(records, traces),
        "method3_iteration_tradeoff": method3_iteration_tradeoff(records, traces),
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "metrics_summary.json").write_text(json.dumps(summary, indent=2))
    (RESULTS_DIR / "metrics_summary.md").write_text(_render_markdown(summary))

    print(f"Wrote {RESULTS_DIR / 'metrics_summary.json'}")
    print(f"Wrote {RESULTS_DIR / 'metrics_summary.md'}")


if __name__ == "__main__":
    main()
