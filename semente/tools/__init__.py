"""Engine-neutral tool API — the surface domains use to declare tools.

``tool`` is a decorator that wraps the engine's tool decorator, converting
Semente-native ``ToolResult``/media to the engine's equivalents at the boundary.
Domains import from here (or the top-level ``semente`` package) and never from
the engine.
"""

from __future__ import annotations

import functools
import inspect
from typing import Callable

from semente.backends.agno.media import to_engine_result
from semente.tools.types import Audio, File, Image, ToolResult, Video

__all__ = [
    "tool",
    "ToolResult",
    "Image",
    "Video",
    "File",
    "Audio",
    "Calculator",
]


def tool(description: str | None = None, tool_hooks: list | None = None, **kwargs) -> Callable:
    """Decorator that declares a domain tool.

    Wraps the engine's tool decorator; the wrapped function returns a Semente
    ``ToolResult`` (or a plain str/dict), which is converted to the engine's
    result type before the engine sees it. The original signature is preserved
    so the engine's parameter injection (e.g. ``run_context``) keeps working.
    """
    from agno.tools import tool as agno_tool

    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kw):
                return to_engine_result(await func(*args, **kw))

            target = async_wrapper
        else:

            @functools.wraps(func)
            def wrapper(*args, **kw):
                return to_engine_result(func(*args, **kw))

            target = wrapper

        return agno_tool(description=description, tool_hooks=tool_hooks, **kwargs)(target)

    return decorator


# Calculator toolkit — engine-provided for now; becomes Semente-native when the
# tool layer is fully engine-free (Phase G/H).
from agno.tools.calculator import CalculatorTools as Calculator  # noqa: E402
