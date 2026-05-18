"""CLI entry point for the deep-research agent.

Usage:
    python main.py --question "What are the latest advances in fusion energy?"
"""
from __future__ import annotations

import argparse
import os
import sys
import config
from sandbox.daytona_client import get_daytona_client,create_sandbox,destroy_sandbox
from tools.artifact_store import set_workspace
from rich.console import Console
from rich.markdown import Markdown

from dotenv import load_dotenv

load_dotenv()

def _check_env() -> None:
    required = ["TAVILY_API_KEY"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        print(f"[error] Missing required environment variables: {', '.join(missing)}")
        print("Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    if os.environ.get("LANGSMITH_TRACING", "").lower() == "true":
        project = os.environ.get("LANGSMITH_PROJECT", "(default)")
        print(f"[langsmith] Tracing enabled → project: {project}")


def main() -> None:
    global model_provider, model_name
    parser = argparse.ArgumentParser(description="Deep Research Agent")

    model_group = parser.add_argument_group(
        title="--choose model and model provider",
        description="""
        Model Provider Options: google, openai, anthropic, huggingface
        Model Name should be provided as speficied by the provider
        """
    )
    model_group.add_argument(
        "--model_provider", 
        help="Enter the model provider name"
    )
    model_group.add_argument(
        "--model_name", 
        help="Enter the model name "
    )
    
    parser.add_argument(
        "--question",
        help="The research question to investigate.",
    )
    args = parser.parse_args()

    if not args.model_provider:
        args.model_provider = input("Enter the model provider name: (Options: [google, openai, anthropic, huggingface])").strip()

    if not args.model_name:
        args.model_name = input("Enter the model name:").strip()

    config.MODEL_PROVIDER = args.model_provider
    config.MODEL_NAME = args.model_name

    _check_env()

    if not args.question:
        args.question = input("Enter your research question: ").strip()
        if not args.question:
            print("[error] No question provided.")
            sys.exit(1)


    daytona_client = get_daytona_client()
    sandbox,_ = create_sandbox(daytona_client)
    set_workspace(sandbox)
    try:
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
    finally:
        print("[deep-research] Destroying Sandbox")
        destroy_sandbox(sandbox,daytona_client)


if __name__ == "__main__":
    main()
