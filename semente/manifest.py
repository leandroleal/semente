"""App manifest — parsed ``semente.yaml``.

Kept in its own module (not in build.py) to avoid a circular import: the
workflow builder needs it, and build.py imports the workflow builder.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Manifest:
    """Parsed ``semente.yaml`` — app-level configuration."""

    name: str
    language: str = "en"
    domain_module: str = "domain"
    prompts_dir: str | None = None
    engine: str | None = None  # None -> SEMENTE_ENGINE env var -> "agno"
    channels: list[str] = field(default_factory=lambda: ["streamlit"])
    features: dict[str, bool] = field(default_factory=dict)
    models: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path) -> "Manifest":
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls(
            name=data.get("name", "semente-app"),
            language=data.get("language", "en"),
            domain_module=data.get("domain_module", "domain"),
            prompts_dir=data.get("prompts_dir"),
            engine=data.get("engine"),
            channels=data.get("channels", ["streamlit"]),
            features=data.get("features", {}),
            models=data.get("models", {}),
        )
