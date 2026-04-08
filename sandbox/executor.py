"""Run arbitrary Python code inside a Daytona sandbox."""
from __future__ import annotations

from sandbox.daytona_client import create_sandbox, destroy_sandbox


def run_code(code: str, reuse_workspace=None) -> dict:
    """
    Execute Python code in a Daytona sandbox.

    Args:
        code: Python source code to execute.
        reuse_workspace: Optional existing workspace to reuse (avoids spin-up cost).

    Returns:
        dict with keys: stdout, stderr, exit_code, workspace_id
    """
    workspace, client = (reuse_workspace, None) if reuse_workspace else create_sandbox()
    owned = reuse_workspace is None

    try:
        response = workspace.process.code_run(code)
        return {
            "stdout": response.result if hasattr(response, "result") else str(response),
            "stderr": getattr(response, "stderr", ""),
            "exit_code": getattr(response, "exit_code", 0),
            "workspace_id": workspace.id,
        }
    finally:
        if owned and client:
            destroy_sandbox(workspace, client)
