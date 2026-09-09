"""Semente — multi-agent AI chat framework for land use and agriculture.

Extracted from Pasto Legal (LAPIG/UFG). The domain-neutral engine lives here;
each application supplies a :class:`semente.domain.DomainSpec` (tools, knowledge,
skills) plus a ``semente.yaml`` manifest.

The public API below is the stable surface domains import from. Domains never
import the underlying agent engine (Agno) directly — see ENGINE_ABSTRACTION.md.
"""

__version__ = "0.2.0"

from semente.context import Context
from semente.domain import DomainSpec
from semente.logging import log_debug, log_error, log_info, log_warning
from semente.skills import load_skills
from semente.tools import Audio, Calculator, File, Image, ToolResult, Video, tool

__all__ = [
    "DomainSpec",
    "Context",
    "tool",
    "ToolResult",
    "Image",
    "Video",
    "File",
    "Audio",
    "Calculator",
    "load_skills",
    "log_debug",
    "log_info",
    "log_warning",
    "log_error",
    "__version__",
]
