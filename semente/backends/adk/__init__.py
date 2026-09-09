"""ADK backend — Google Agent Development Kit engine implementation.

Implements the Semente engine port on top of ``google-adk``.

Key adaptations (see MULTI_ENGINE.md §4.2):
- **Dynamic tools**: the agent (and its tool set) is built per run, resolving
  ``spec.tools`` callables against the run's session state — so Pasto Legal's
  registration-state tool switching works.
- **State seeding + sync-back**: the ADK session is seeded from Semente's
  ``input.session_state`` (the orchestrator's dict, by reference); after the
  run, ADK's state is written back into that dict in place, so tool mutations
  (terms acceptance, property registration) persist in the Semente store.
- **Tool adaptation**: Semente tools -> plain ADK functions; ``run_context`` is
  mapped to ADK's ``tool_context`` and stripped from the generated schema;
  agno toolkits (e.g. Calculator) are expanded.
- **Multimodal input**: Semente media -> ``genai`` content parts.

Known degradations (documented): knowledge/skills are not wired.
"""

from __future__ import annotations

import functools
import inspect
import json
import re
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


def _expand_tools(tools: list) -> list:
    """Expand agno toolkits (e.g. Calculator) into their member functions."""
    expanded = []
    for t in tools:
        functions = getattr(t, "functions", None)
        if isinstance(functions, dict):
            expanded.extend(functions.values())
        else:
            expanded.append(t)
    return expanded


def _new_media_bag() -> dict:
    return {"images": [], "videos": [], "audios": [], "files": []}


def _result_to_str(result, media_bag: dict) -> str:
    """Convert a tool result to the text ADK feeds back to the LLM, stashing
    any media artifacts in the per-run bag (A-M: media never enters the loop)."""
    if isinstance(result, ToolResult):
        if result.images:
            media_bag["images"].extend(result.images)
        if result.videos:
            media_bag["videos"].extend(result.videos)
        if result.audios:
            media_bag["audios"].extend(result.audios)
        if result.files:
            media_bag["files"].extend(result.files)
        return result.content
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        return json.dumps(result, default=str)
    return str(result)


class _ToolContextAdapter:
    """Exposes ``session_state`` over ADK's ToolContext (which has ``.state``)."""

    def __init__(self, tool_context):
        self._tc = tool_context

    @property
    def session_state(self):
        return getattr(self._tc, "state", None) or {}

    @property
    def user_id(self):
        return getattr(self._tc, "user_id", None)


class _StateContext:
    """Minimal Context for resolving dynamic tool lists against a state dict."""

    def __init__(self, session_state: dict):
        self.session_state = session_state


def _bind_args(sig, args, kwargs) -> dict:
    bound = sig.bind(*args, **kwargs)
    bound.apply_defaults()
    return dict(bound.arguments)


def _build_hook_chain(func, hooks, has_run_context):
    """Replicate agno's nested tool_hooks chain (middleware semantics).

    Innermost calls the raw function; each hook wraps the next and may either
    call ``function_call(**arguments)`` to continue the chain or return a value
    to short-circuit. Mirrors agno.tools.function._build_nested_execution_chain.
    """

    def entrypoint(args, ctx):
        if has_run_context:
            return func(**args, run_context=ctx)
        return func(**args)

    chain = entrypoint
    for hook in reversed(hooks):

        def make_wrapper(inner, hook):
            def wrapper(args, ctx):
                def next_func(**kwargs):
                    return inner(kwargs, ctx)

                # The rate-limit hook keys its cache on function_call.__name__.
                next_func.__name__ = getattr(func, "__name__", "tool")
                return hook(run_context=ctx, function_call=next_func, arguments=args)

            return wrapper

        chain = make_wrapper(chain, hook)
    return chain


def _adapt_tool(tool, media_bag: dict):
    func = _unwrap(tool)
    sig = inspect.signature(func)
    has_run_context = "run_context" in sig.parameters
    hooks = getattr(tool, "tool_hooks", None) or []

    # Schema the LLM sees: the original signature minus run_context.
    clean_sig = sig.replace(
        parameters=[p for p in sig.parameters.values() if p.name != "run_context"]
    )

    chain = _build_hook_chain(func, hooks, has_run_context)
    needs_ctx = has_run_context or bool(hooks)

    if not needs_ctx:

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            call_args = _bind_args(clean_sig, args, kwargs)
            return _result_to_str(chain(call_args, None), media_bag)

    else:

        @functools.wraps(func)
        def wrapper(*args, tool_context=None, **kwargs):
            ctx = _ToolContextAdapter(tool_context) if tool_context is not None else _StateContext({})
            call_args = _bind_args(clean_sig, args, kwargs)
            return _result_to_str(chain(call_args, ctx), media_bag)

    # ADK builds the tool schema from the signature; make it the clean one.
    wrapper.__signature__ = clean_sig
    return wrapper


_MIME_BY_EXT = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    ".wav": "audio/wav", ".mp3": "audio/mpeg", ".ogg": "audio/ogg", ".mp4": "video/mp4",
}


def _media_part(obj: Any, fallback_mime: str) -> Any:
    """Convert one Semente media object to a genai Part."""
    from google.genai import types

    if obj is None:
        return None
    if hasattr(obj, "content") and obj.content:
        return types.Part.from_bytes(data=obj.content, mime_type=obj.mime_type or fallback_mime)
    if hasattr(obj, "filepath") and obj.filepath:
        from pathlib import Path

        p = Path(obj.filepath)
        return types.Part.from_bytes(
            data=p.read_bytes(), mime_type=obj.mime_type or _MIME_BY_EXT.get(p.suffix.lower(), fallback_mime)
        )
    if hasattr(obj, "url") and obj.url:
        return types.Part.from_uri(file_uri=obj.url, mime_type=obj.mime_type or fallback_mime)
    return None


class AdkAgentAdapter:
    """Builds the LlmAgent per run (dynamic tools) and seeds/syncs state."""

    def __init__(self, spec: AgentSpec, app_name: str):
        self.spec = spec
        self.app_name = app_name

    def _resolve_tools(self, session_state: dict, media_bag: dict) -> list:
        tools_or_callable = self.spec.tools
        if callable(tools_or_callable) and not isinstance(tools_or_callable, list):
            try:
                raw = tools_or_callable(_StateContext(session_state))
            except TypeError:
                raw = tools_or_callable()
        else:
            raw = tools_or_callable or []
        return [_adapt_tool(t, media_bag) for t in _expand_tools(list(raw))]

    def run(self, input: AgentInput) -> AgentTurn:
        from google.adk.agents import LlmAgent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        state = input.session_state if input.session_state is not None else {}
        media_bag = _new_media_bag()

        instruction = self.spec.instructions
        if not callable(instruction):
            instruction = lambda ctx: str(instruction)  # noqa: E731

        def instruction_provider(ctx):
            return instruction(_ToolContextAdapter(ctx))

        model = self.spec.model.model_id if self.spec.model else "gemini-2.5-flash"

        agent = LlmAgent(
            model=model,
            name=_sanitize_name(self.spec.name),
            instruction=instruction_provider,
            tools=self._resolve_tools(state, media_bag),
            output_schema=self.spec.output_schema,
        )

        session_service = InMemorySessionService()
        # Seed the ADK session from Semente's state (same dict, by reference).
        session = session_service.create_session(
            app_name=self.app_name,
            user_id=input.user_id or "default",
            state=dict(state),
        )
        runner = Runner(agent=agent, app_name=self.app_name, session_service=session_service)

        parts = [types.Part(text=input.text)] if input.text else []
        for img in input.images or []:
            part = _media_part(img, "image/png")
            if part:
                parts.append(part)
        for aud in input.audio or []:
            part = _media_part(aud, "audio/wav")
            if part:
                parts.append(part)
        content = types.Content(role="user", parts=parts or [types.Part(text="")])

        final_text = ""
        for event in runner.run(
            user_id=input.user_id or "default",
            session_id=session.id,
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                final_text = "".join(p.text for p in event.content.parts if p.text)

        # Sync ADK's (possibly tool-mutated) state back into Semente's dict.
        try:
            updated = session_service.get_session(
                app_name=self.app_name, user_id=input.user_id or "default", session_id=session.id
            )
            if updated is not None and getattr(updated, "state", None):
                state.clear()
                state.update({k: v for k, v in updated.state.items() if not k.startswith(("temp:",))})
        except Exception:
            pass

        structured = None
        if self.spec.output_schema and final_text:
            try:
                structured = json.loads(final_text)
            except json.JSONDecodeError:
                structured = None

        return AgentTurn(
            content=final_text,
            structured=structured,
            images=media_bag["images"] or None,
            videos=media_bag["videos"] or None,
            audio=media_bag["audios"] or None,
            files=media_bag["files"] or None,
        )


def _sanitize_name(name: str) -> str:
    """ADK node names must be valid Python identifiers."""
    return re.sub(r"\W+", "_", name).strip("_") or "agent"


class AdkBackend(EngineBackend):
    name = "adk"

    def build_agent(self, spec: AgentSpec) -> Agent:
        return AdkAgentAdapter(spec, app_name=spec.name)

    def supports(self, capability: str) -> bool:
        return capability in {"structured_output", "multimodal_in"}