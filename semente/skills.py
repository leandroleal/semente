"""Engine-neutral skills loader.

Loads markdown skills from a directory; returns ``None`` when the directory is
invalid or absent, so apps don't repeat the try/except dance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agno.skills import LocalSkills, SkillValidationError, Skills


def load_skills(path: str | Path) -> Any | None:
    """Load Agno Skills from a directory, or ``None`` on validation error."""
    try:
        return Skills(loaders=[LocalSkills(str(path))])
    except SkillValidationError:
        return None
