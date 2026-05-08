"""CLI entry point for the deep-research agent.

Usage:
    python main.py --question "What are the latest advances in fusion energy?"
"""
from __future__ import annotations

import argparse
import os
import sys
from sandbox.daytona_client import get_daytona_client,create_sandbox,destroy_sandbox
from tools.artifact_store import set_workspace
from rich.console import Console
from rich.markdown import Markdown

from dotenv import load_dotenv

load_dotenv()
model_provider = "google"

def _check_env() -> None:
    required = ["ANTHROPIC_API_KEY", "TAVILY_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[error] Missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    if os.environ.get("LANGSMITH_TRACING", "").lower() == "true":
        project = os.environ.get("LANGSMITH_PROJECT", "(default)")
        print(f"[langsmith] Tracing enabled → project: {project}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Deep Research Agent")
    parser.add_argument(
        "--question",
        help="The research question to investigate.",
    )
    args = parser.parse_args()

    _check_env()

    if not args.question:
        args.question = input("Enter your research question: ").strip()
        if not args.question:
            print("[error] No question provided.")
            sys.exit(1)

    # Initializing Daytona
    daytona_client = get_daytona_client()
    sandbox,_ = create_sandbox(daytona_client)
    set_workspace(sandbox)
    # Import here so env vars are loaded before any LangChain/Anthropic init
    from graph.research_graph import graph

    print(f"\n[deep-research] Question: {args.question}\n")
    print("[deep-research] Running research pipeline...\n")

    result = graph.invoke({"question": args.question})

    report: str = result.get("report", "")
    if not report:
        print("[deep-research] No report generated.")
        sys.exit(1)

    console = Console()
    md = Markdown(report)
    print("\n" + "=" * 72)
    console.print(md)
    print("=" * 72 + "\n")
    print("[deep-research] Done. Report saved to outputs/")
    print("[deep-research] Destroying Sandbox")
    destroy_sandbox(sandbox,daytona_client)


if __name__ == "__main__":
    main()
