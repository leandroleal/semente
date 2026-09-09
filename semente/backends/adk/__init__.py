"""ADK backend — Google Agent Development Kit engine implementation.

Implements the Semente engine port on top of ``google-adk``. Tools are adapted
from Semente-native functions; ``run_context`` is mapped to ADK's
``tool_context``.
"""

from __future__ import annotations

import functools
import inspect
from typing import Any

from semente.backends.base import Agent, AgentInput, AgentSpec, AgentTurn, EngineBackend
from semente.tools.types import ToolResult


def _unwrap(func):
    # agno Function wraps the entrypoint; semente.tool wraps the original func.
    if hasattr(func, "entrypoint"):
        func = func.entrypoint
    while hasattr(func, "__wrapped__"):
        func = func.__wrapped__
    return func


def _result_to_str(result) -> str:
    if isinstance(result, ToolResult):
        # ponytail: media is dropped for ADK for now; MediaBag lands later.
        return result.content
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        import json

        return json.dumps(result, default=str)
    return str(result)


class _ContextAdapter:
    """Exposes ``session_state`` over ADK's ToolContext (which has ``.state``)."""

    def __init__(self, tool_context):
        self._tc = tool_context

    @property
    def session_state(self):
        return getattr(self._tc, "state", {}) or {}

    @property
    def user_id(self):
        return getattr(self._tc, "user_id", None)


def _adapt_tool(tool):
    func = _unwrap(tool)
    sig = inspect.signature(func)
    has_run_context = "run_context" in sig.parameters

    if not has_run_context:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return _result_to_str(func(*args, **kwargs))

        return wrapper

    @functools.wraps(func)
    def wrapper(*args, tool_context=None, **kwargs):
        ctx = _ContextAdapter(tool_context) if tool_context is not None else None
        return _result_to_str(func(*args, run_context=ctx, **kwargs))

    return wrapper


class AdkAgentAdapter:
    def __init__(self, agent, app_name: str):
        self.agent = agent
        self.app_name = app_name

    def run(self, input: AgentInput) -> AgentTurn:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        session_service = InMemorySessionService()
        runner = Runner(agent=self.agent, app_name=self.app_name, session_service=session_service)

        content = types.Content(role="user", parts=[types.Part(text=input.text)])
        final_text = ""
        structured = None
        for event in runner.run(
            user_id=input.user_id or "default",
            session_id="semente",
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(p.text for p in event.content.parts if p.text)

        return AgentTurn(content=final_text, structured=structured)


def _sanitize_name(name: str) -> str:
    """ADK node names must be valid Python identifiers."""
    import re

    return re.sub(r"\W+", "_", name).strip("_") or "agent"


class AdkBackend(EngineBackend):
    name = "adk"

    def build_agent(self, spec: AgentSpec) -> Agent:
        from google.adk.agents import LlmAgent

        model = spec.model.model_id if spec.model else "gemini-2.5-flash"

        instruction = spec.instructions
        if not callable(instruction):
            instruction = lambda ctx: str(instruction)

        def instruction_provider(ctx):
            return instruction(_ContextAdapter(ctx))

        tools = [_adapt_tool(t) for t in (spec.tools if isinstance(spec.tools, list) else [])]

        agent = LlmAgent(
            model=model,
            name=_sanitize_name(spec.name),
            instruction=instruction_provider,
            tools=tools,
            output_schema=spec.output_schema,
        )
        return AdkAgentAdapter(agent, app_name=spec.name)

    def supports(self, capability: str) -> bool:
        return capability in {"structured_output", "multimodal_in"}
