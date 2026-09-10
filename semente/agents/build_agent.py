"""Agent factory — builds the single agent from a DomainSpec.

The neutral shell: the generic instruction builder (persona + history/summary
context blocks) and the engine-port call. Domain-specific dynamic instructions
and tool selection are supplied by the domain via ``DomainSpec.instructions``
and ``DomainSpec.tools``. The actual agent is built by the selected engine
backend (see ``semente.backends``).
"""

import textwrap
from typing import Any, Callable

from semente.backends.base import AgentSpec, ModelSpec
from semente.backends.registry import get_backend
from semente.configs.config import config
from semente.configs.prompts import get_agent_config
from semente.domain import DomainSpec
from semente.schemas.user_persona import UserPersona


def persona_text(session_state) -> str:
    user_persona = session_state.get("user_persona", None)
    if user_persona is None:
        return get_agent_config("single_agent")["persona_fallback"].strip()
    try:
        if isinstance(user_persona, dict):
            user_persona = UserPersona.model_validate(user_persona)
        return str(user_persona)
    except Exception:
        return str(user_persona)


def context_blocks(session_state) -> str:
    """Build the <history_context> and <conversation_summary> blocks read
    from session_state, to be prepended to the agent instructions.
    """
    parts: list[str] = []

    history_context = session_state.get("history_context") or ""
    if history_context:
        parts.append(f"<history_context>\n{history_context}\n</history_context>")

    conversation_summary = session_state.get("conversation_summary") or ""
    if conversation_summary:
        parts.append(
            f"<conversation_summary>\n{conversation_summary}\n</conversation_summary>"
        )

    return "\n".join(parts)


def _default_instructions(domain_spec: DomainSpec) -> Callable[[Any], str]:
    """Generic instruction builder: persona + context blocks + static default text."""
    agent_config = get_agent_config(domain_spec.agent_config)

    def instructions(run_context) -> str:
        session_state = run_context.session_state or {}
        ctx_blocks = context_blocks(session_state)
        persona = persona_text(session_state)

        return textwrap.dedent(f"""\
            {ctx_blocks}

            <user-persona>
            {persona}
            </user-persona>

            {agent_config['instructions_default'].strip()}
        """).strip()

    return instructions


def _resolve_model_spec(manifest) -> ModelSpec | None:
    """Manifest model override, or None (backend falls back to env config)."""
    primary = (manifest.models or {}).get("primary") if manifest else None
    if primary:
        return ModelSpec(
            provider=primary.get("provider", "google"),
            model_id=primary.get("id", "gemini-3.5-flash-lite"),
        )
    return None


def _resolve_fallback_model_spec(manifest) -> ModelSpec | None:
    """Fallback model from manifest ``models.fallback``, else env config."""
    fb = (manifest.models or {}).get("fallback") if manifest else None
    if fb:
        return ModelSpec(
            provider=fb.get("provider", "google"),
            model_id=fb.get("id"),
        )
    if config.FALLBACK_MODEL_PROVIDER and config.FALLBACK_MODEL_ID:
        return ModelSpec(
            provider=config.FALLBACK_MODEL_PROVIDER,
            model_id=config.FALLBACK_MODEL_ID,
        )
    return None


def build_agent(domain_spec: DomainSpec, manifest: Any = None):
    """Assemble the single agent for a domain via the selected engine backend.

    Args:
        domain_spec: The domain's tools/knowledge/skills/instructions.
        manifest: Optional :class:`semente.manifest.Manifest` for model/engine override.

    Returns:
        A backend ``Agent`` (port protocol) ready to be wired into the workflow.
    """
    agent_config = get_agent_config(domain_spec.agent_config)

    spec = AgentSpec(
        name=agent_config["name"],
        instructions=domain_spec.instructions or _default_instructions(domain_spec),
        tools=domain_spec.tools,
        knowledge=domain_spec.knowledge,
        skills=domain_spec.skills,
        model=_resolve_model_spec(manifest),
    )

    engine = getattr(manifest, "engine", None) if manifest else None
    backend = get_backend(engine)
    primary = backend.build_agent(spec)

    fallback_spec = _resolve_fallback_model_spec(manifest)
    if fallback_spec is None:
        return primary

    from dataclasses import replace

    from semente.backends.base import FallbackAgent

    fallback = backend.build_agent(replace(spec, model=fallback_spec))
    return FallbackAgent(primary, fallback)
