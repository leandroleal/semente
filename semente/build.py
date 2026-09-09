"""Assemble a Semente application from a manifest.

The single entry point: loads the manifest, applies the prompts dir, imports
the domain, builds the agent + workflow, and wires the channels. The domain is
imported *inside* this function (after the prompts dir is set) so that
domain tools loading prompts at import time resolve correctly.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def build_app(manifest_path: str | Path | None = None) -> Any:
    """Build the ASGI app (AgentOS) for the app described by ``semente.yaml``.

    Args:
        manifest_path: Path to ``semente.yaml``. Defaults to the
            ``SEMENTE_MANIFEST`` env var or ``semente.yaml`` in the cwd.

    Returns:
        The FastAPI/ASGI app; serve with uvicorn or ``AgentOS.serve()``.
    """
    from semente.manifest import Manifest
    from semente.workflows.base_workflow import get_workflow
    from semente.interfaces.whatsapp import Whatsapp

    path = manifest_path or os.getenv("SEMENTE_MANIFEST", "semente.yaml")
    manifest = Manifest.load(path)
    workflow = get_workflow(path)

    interfaces = []
    if "whatsapp" in manifest.channels:
        interfaces.append(Whatsapp(workflow=workflow))

    from agno.os import AgentOS

    os = AgentOS(workflows=[workflow], interfaces=interfaces)
    return os.get_app()
