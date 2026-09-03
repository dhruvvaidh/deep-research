"""LangChain tool to read/write findings as named files in the Daytona sandbox FS."""
from __future__ import annotations

from langchain_core.tools import tool

# Module-level workspace reference set by the graph before tool invocation
_workspace = None


def set_workspace(workspace) -> None:
    """Set the active sandbox workspace for artifact operations."""
    global _workspace
    _workspace = workspace


def get_workspace():
    if _workspace is None:
        raise RuntimeError(
            "Artifact store has no active workspace. "
            "Call artifact_store.set_workspace(ws) before using this tool."
        )
    return _workspace


@tool
def write_artifact(name: str, content: str) -> str:
    """Write a named artifact (text file) to the sandbox filesystem.

    Args:
        name: Filename for the artifact (e.g. "market_trends.md").
        content: Text content to store.

    Returns:
        Confirmation message with the remote path.
    """
    from sandbox.artifact_manager import write_artifact as _write
    ws = get_workspace()
    path = _write(ws, name, content)
    return f"Artifact written to {path}"


@tool
def read_artifact(name: str) -> str:
    """Read a named artifact from the sandbox filesystem.

    Args:
        name: Filename of the artifact to read (e.g. "market_trends.md").

    Returns:
        Text content of the artifact, or an error message if it does not exist.
    """
    from sandbox.artifact_manager import read_artifact as _read
    ws = get_workspace()
    try:
        return _read(ws, name)
    except Exception:
        return (
            f"No artifact found named '{name}'. Use list_artifacts() or get_context_index() "
            "to see the exact stored filenames before retrying."
        )


@tool
def list_artifacts() -> str:
    """List all artifact filenames stored in the sandbox.

    Returns:
        Newline-separated list of artifact filenames.
    """
    from sandbox.artifact_manager import list_artifacts as _list
    ws = get_workspace()
    files = _list(ws)
    if not files:
        return "No artifacts found."
    return "\n".join(files)
