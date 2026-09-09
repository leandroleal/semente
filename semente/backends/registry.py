"""Engine backend registry — selects the backend by name.

``SEMENTE_ENGINE`` env var or the manifest ``engine`` field picks the backend
(``agno`` default; ``adk`` and ``pi`` land in later phases).
"""

from __future__ import annotations

import os

from semente.backends.base import EngineBackend


def get_backend(engine: str | None = None) -> EngineBackend:
    name = engine or os.getenv("SEMENTE_ENGINE", "agno")

    if name == "agno":
        from semente.backends.agno import AgnoBackend

        return AgnoBackend()

    raise ValueError(f"Unknown engine: {name!r} (available: agno)")
