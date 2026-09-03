"""Pulls the full run tree for every benchmark run out of LangSmith into readable JSON.

For each root_run_id recorded in benchmarks/results/run_manifest.json (written by
run_benchmark.py), fetches every run in that trace (orchestrator, each specialist,
nested tool/LLM calls) and writes a single JSON file per trace to
benchmarks/results/langsmith_export/<root_run_id>.json:

    {
      "root": {...},
      "runs": [
        {"run_id", "parent_run_id", "name", "run_type",
         "start_time", "end_time", "latency_seconds",
         "prompt_tokens", "completion_tokens", "total_tokens",
         "total_cost", "tags"},
        ...
      ]
    }

Usage:
    python scripts/langsmith_export.py
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

from langsmith import Client

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "benchmarks" / "results"
MANIFEST_PATH = RESULTS_DIR / "run_manifest.json"
EXPORT_DIR = RESULTS_DIR / "langsmith_export"

POLL_ATTEMPTS = 6
POLL_DELAY_SECONDS = 5


def _serialize_run(run) -> dict:
    latency = None
    if run.start_time and run.end_time:
        latency = (run.end_time - run.start_time).total_seconds()
    return {
        "run_id": str(run.id),
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "name": run.name,
        "run_type": run.run_type,
        "start_time": run.start_time.isoformat() if run.start_time else None,
        "end_time": run.end_time.isoformat() if run.end_time else None,
        "latency_seconds": latency,
        "prompt_tokens": run.prompt_tokens,
        "completion_tokens": run.completion_tokens,
        "total_tokens": run.total_tokens,
        "total_cost": float(run.total_cost) if run.total_cost is not None else None,
        "tags": run.tags,
    }


def export_trace(client: Client, project_name: str, root_run_id: str) -> dict | None:
    for attempt in range(1, POLL_ATTEMPTS + 1):
        try:
            root = client.read_run(root_run_id)
        except Exception as e:
            print(f"  [warn] read_run failed on attempt {attempt}: {e}")
            root = None

        if root is not None and root.end_time is not None:
            runs = list(client.list_runs(project_name=project_name, trace_id=root_run_id))
            return {
                "root": _serialize_run(root),
                "runs": [_serialize_run(r) for r in runs],
            }

        print(f"  [wait] trace {root_run_id} not fully ingested yet "
              f"(attempt {attempt}/{POLL_ATTEMPTS}), retrying in {POLL_DELAY_SECONDS}s...")
        time.sleep(POLL_DELAY_SECONDS)

    print(f"  [error] gave up waiting for trace {root_run_id} to finish ingesting")
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Export LangSmith run trees for the benchmark sweep")
    parser.add_argument("--manifest", default=str(MANIFEST_PATH))
    parser.add_argument("--project", default=os.environ.get("LANGSMITH_PROJECT"))
    parser.add_argument("--output-dir", default=str(EXPORT_DIR))
    args = parser.parse_args()

    if not args.project:
        print("[error] No LangSmith project configured. Set LANGSMITH_PROJECT or pass --project.")
        sys.exit(1)

    records = json.loads(Path(args.manifest).read_text())
    root_run_ids = [r["root_run_id"] for r in records if r.get("root_run_id")]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    client = Client()

    for i, root_run_id in enumerate(root_run_ids, start=1):
        out_path = output_dir / f"{root_run_id}.json"
        if out_path.exists():
            print(f"[{i}/{len(root_run_ids)}] SKIP {root_run_id} (already exported)")
            continue
        print(f"[{i}/{len(root_run_ids)}] Exporting {root_run_id} ...")
        trace = export_trace(client, args.project, root_run_id)
        if trace is None:
            continue
        out_path.write_text(json.dumps(trace, indent=2))
        print(f"[{i}/{len(root_run_ids)}] Wrote {out_path} ({len(trace['runs'])} runs)")

    print(f"\nLangSmith export complete. Files in {output_dir}")


if __name__ == "__main__":
    main()
