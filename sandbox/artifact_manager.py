"""Helpers to read and write named artifacts on a Daytona sandbox filesystem."""
from __future__ import annotations

ARTIFACT_DIR = "/home/daytona/artifacts"


def write_artifact(workspace, name: str, content: str) -> str:
    """Write a string artifact to the sandbox filesystem. Returns the remote path."""
    remote_path = f"{ARTIFACT_DIR}/{name}"
    # Ensure directory exists then write the file
    workspace.process.exec(f"mkdir -p {ARTIFACT_DIR}")
    workspace.fs.upload_file(content.encode(),remote_path)
    return remote_path


def read_artifact(workspace, name: str) -> str:
    """Read a named artifact from the sandbox filesystem. Returns its text content."""
    remote_path = f"{ARTIFACT_DIR}/{name}"
    data = workspace.fs.download_file(remote_path)
    if isinstance(data, bytes):
        return data.decode()
    return str(data)


def list_artifacts(sandbox) -> list[str]:
    """List artifact filenames present in the sandbox artifact directory."""
    files = sandbox.fs.list_files(ARTIFACT_DIR)
    return [f.name for f in files if not f.is_dir]
