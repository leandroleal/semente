"""Engine-neutral context passed to domain tools and instruction callables.

A structural Protocol: the engine's RunContext satisfies it by duck typing, so
no wrapping or conversion happens at runtime. Declares only what domains use.
"""

from __future__ import annotations

from typing import Any, Protocol


class Context(Protocol):
    """What a domain tool may access on the run context.

    The engine (Agno) injects its own RunContext, which structurally satisfies
    this protocol. Domains type-hint against ``Context`` and never import the
    engine.
    """

    session_state: dict[str, Any]
    user_id: str | None
    messages: Any
