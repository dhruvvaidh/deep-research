"""Drives the paid benchmark sweep: every question x every MAX_ITERATIONS setting.

For each (question, max_iterations) pair this provisions a fresh Daytona sandbox,
runs the full research pipeline, and appends one record to
benchmarks/results/run_manifest.json containing the LangSmith root run id, wall
clock time, final state summary, and a snapshot of the sandbox's
context_manifest.json (raw vs summarized content sizes).

Usage:
    python scripts/run_benchmark.py
    python scripts/run_benchmark.py --iterations 1,2,3 --questions benchmarks/questions.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

import config
from langchain_core.tracers.context import collect_runs
from sandbox.daytona_client import get_daytona_client, create_sandbox, destroy_sandbox
from sandbox.artifact_manager import read_artifact
from tools.artifact_store import set_workspace

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "benchmarks" / "results"
MANIFEST_PATH = RESULTS_DIR / "run_manifest.json"


def _load_manifest() -> list[dict]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text())
    return []


def _append_record(record: dict) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    records = _load_manifest()
    records.append(record)
    MANIFEST_PATH.write_text(json.dumps(records, indent=2))


def _find_root_run_id(traced_runs, expected_run_name: str) -> str | None:
    """collect_runs() can pick up stray parentless LLM calls (e.g. the module-level
    ChatGoogleGenerativeAI instances in tools/thinking.py and tools/context_store.py
    that call .invoke() directly) alongside the actual graph root. Prefer the run
    whose name matches the run_name we explicitly passed to graph.invoke(); fall back
    to the longest-running traced run, since the real graph execution always dominates
    those short, isolated LLM calls.
    """
    if not traced_runs:
        return None
    for r in traced_runs:
        if getattr(r, "name", None) == expected_run_name:
            return str(r.id)
    longest = max(traced_runs, key=lambda r: (r.end_time - r.start_time) if r.end_time and r.start_time else 0)
    return str(longest.id)


def _snapshot_context_manifest(sandbox) -> dict:
    try:
        raw = read_artifact(sandbox, "context_manifest.json")
        return json.loads(raw)
    except Exception as e:
        print(f"  [warn] could not read context_manifest.json: {e}")
        return {}


def run_one(question_id: str, question_text: str, max_iterations: int, model_provider: str, model_name: str) -> dict:
    config.MODEL_PROVIDER = model_provider
    config.MODEL_NAME = model_name
    config.MAX_ITERATIONS = max_iterations

    from graph.research_graph import graph  # compiled once, reused across all runs

    daytona_client = get_daytona_client()
    sandbox, _ = create_sandbox(daytona_client)
    set_workspace(sandbox)

    run_config = {
        "tags": ["benchmark", question_id, f"max_iter_{max_iterations}"],
        "metadata": {"question_id": question_id, "max_iterations": max_iterations},
        "run_name": f"benchmark_{question_id}_iter{max_iterations}",
    }

    try:
        start = time.perf_counter()
        with collect_runs() as cb:
            result = graph.invoke({"question": question_text}, config=run_config)
        wall_clock_seconds = time.perf_counter() - start

        root_run_id = _find_root_run_id(cb.traced_runs, run_config["run_name"])
        context_manifest_snapshot = _snapshot_context_manifest(sandbox)

        record = {
            "question_id": question_id,
            "max_iterations": max_iterations,
            "root_run_id": root_run_id,
            "wall_clock_seconds": wall_clock_seconds,
            "iteration_count_used": result.get("iteration"),
            "sufficient": result.get("sufficient"),
            "workstream_count": len(result.get("workstreams", []) or []),
            "report_chars": len(result.get("report", "") or ""),
            "thought_log": [
                {"agent": t.get("agent"), "iteration": t.get("iteration"), "confidence": t.get("confidence")}
                for t in (result.get("thought_log") or [])
            ],
            "context_manifest_snapshot": context_manifest_snapshot,
        }
        return record
    finally:
        destroy_sandbox(sandbox, daytona_client)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resume-metrics benchmark sweep")
    parser.add_argument("--questions", default=str(REPO_ROOT / "benchmarks" / "questions.json"))
    parser.add_argument("--iterations", default="1,2,3")
    parser.add_argument("--model-provider", default="google")
    parser.add_argument("--model-name", default=os.environ.get("MODEL_NAME"))
    args = parser.parse_args()

    questions = json.loads(Path(args.questions).read_text())
    iterations = [int(x) for x in args.iterations.split(",")]

    already_done = {(r["question_id"], r["max_iterations"]) for r in _load_manifest() if r.get("root_run_id")}

    total = len(questions) * len(iterations)
    done = 0
    for q in questions:
        for n in iterations:
            done += 1
            if (q["id"], n) in already_done:
                print(f"[{done}/{total}] SKIP {q['id']} @ max_iterations={n} (already in manifest)")
                continue
            print(f"[{done}/{total}] RUN  {q['id']} @ max_iterations={n} ...")
            t0 = time.perf_counter()
            try:
                record = run_one(q["id"], q["question"], n, args.model_provider, args.model_name)
                _append_record(record)
                print(f"[{done}/{total}] DONE {q['id']} @ max_iterations={n} "
                      f"in {time.perf_counter() - t0:.1f}s (root_run_id={record['root_run_id']})")
            except Exception as e:
                print(f"[{done}/{total}] FAIL {q['id']} @ max_iterations={n}: {e}")
                _append_record({
                    "question_id": q["id"],
                    "max_iterations": n,
                    "error": str(e),
                })

    print(f"\nBenchmark sweep complete. Results in {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
