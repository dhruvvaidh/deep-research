"""Wrapper around the Daytona SDK for sandbox lifecycle management."""
from __future__ import annotations

import os
from daytona import Daytona, DaytonaConfig, CreateSandboxBaseParams, Sandbox


def get_daytona_client() -> Daytona:
    """Return a configured Daytona client using env vars."""
    config = DaytonaConfig(
        api_key=os.environ["DAYTONA_API_KEY"],
        api_url=os.environ.get("DAYTONA_API_URL"),
    )
    return Daytona(config)


def create_sandbox(daytona: Daytona | None = None):
    """Create a new Python sandbox and return the sandbox object."""
    client = daytona or get_daytona_client()
    sandbox = client.create(CreateSandboxBaseParams(language="python"))
    return sandbox, client


def destroy_sandbox(sandbox: Sandbox, daytona: Daytona | None = None) -> None:
    """Destroy a sandbox."""
    client = daytona or get_daytona_client()
    client.delete(sandbox)
