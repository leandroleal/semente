"""Engine-neutral tool API — the surface domains use to declare tools.

``tool`` is a decorator that wraps the engine's tool decorator, converting
Semente-native ``ToolResult``/media to the engine's equivalents at the boundary.
Domains import from here (or the top-level ``semente`` package) and never from
the engine.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any, Callable

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


def _media_to_engine(obj: Any, engine_cls: type) -> Any:
    """Convert one Semente media dataclass to the engine's media type."""
    if obj is None or isinstance(obj, engine_cls):
        return obj
    return engine_cls(**{k: v for k, v in vars(obj).items() if v is not None})


def _to_engine(result: Any) -> Any:
    """Convert a Semente ToolResult to the engine's ToolResult; pass others through."""
    if not isinstance(result, ToolResult):
        return result

    from agno.media import Audio as EAudio
    from agno.media import File as EFile
    from agno.media import Image as EImage
    from agno.media import Video as EVideo
    from agno.tools.function import ToolResult as EToolResult

    return EToolResult(
        content=result.content,
        images=[_media_to_engine(i, EImage) for i in result.images] if result.images else None,
        videos=[_media_to_engine(v, EVideo) for v in result.videos] if result.videos else None,
        audios=[_media_to_engine(a, EAudio) for a in result.audios] if result.audios else None,
        files=[_media_to_engine(f, EFile) for f in result.files] if result.files else None,
    )


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
                return _to_engine(await func(*args, **kw))

            target = async_wrapper
        else:

            @functools.wraps(func)
            def wrapper(*args, **kw):
                return _to_engine(func(*args, **kw))

            target = wrapper

        return agno_tool(description=description, tool_hooks=tool_hooks, **kwargs)(target)

    return decorator


# Calculator toolkit — engine-provided for now; becomes Semente-native when the
# tool layer is fully engine-free (Phase G/H).
from agno.tools.calculator import CalculatorTools as Calculator  # noqa: E402
