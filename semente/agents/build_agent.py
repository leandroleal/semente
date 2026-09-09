"""Agent factory — builds the single agent from a DomainSpec.

The neutral shell: model, knowledge, skills, and the generic instruction
builder (persona + history/summary context blocks). Domain-specific dynamic
instructions and tool selection are supplied by the domain via
``DomainSpec.instructions`` and ``DomainSpec.tools`` (a list or a callable
``(run_context) -> list``).
"""

import textwrap
from typing import Any, Callable, Optional

from agno.agent import Agent
from agno.run import RunContext

from semente.configs.config import config
from semente.configs.prompts import get_agent_config
from semente.domain import DomainSpec
from semente.schemas.user_persona import UserPersona


def _resolve_model(manifest) -> Any:
    """Resolve the primary model: manifest override wins, else env config."""
    primary = (manifest.models or {}).get("primary") if manifest else None
    if primary:
        return config.build_model(
            primary.get("provider", config.PRIMARY_MODEL_PROVIDER),
            primary.get("id", config.PRIMARY_MODEL_ID),
        )
    return config.model


def _resolve_fallback(manifest) -> Any:
    """Resolve the fallback model: manifest override wins, else env config."""
    fb = (manifest.models or {}).get("fallback") if manifest else None
    if fb:
        return config.build_model(fb.get("provider"), fb.get("id"))
    return config.fallback_model


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


def _default_instructions(domain_spec: DomainSpec) -> Callable[[RunContext], str]:
    """Generic instruction builder: persona + context blocks + static default text."""
    agent_config = get_agent_config(domain_spec.agent_config)

    def instructions(run_context: RunContext) -> str:
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


def build_agent(domain_spec: DomainSpec, manifest: Any = None) -> Agent:
    """Assemble the single agent for a domain.

    Args:
        domain_spec: The domain's tools/knowledge/skills/instructions.
        manifest: Optional :class:`semente.manifest.Manifest` for model override.

    Returns:
        An Agno ``Agent`` ready to be wired into the workflow.
    """
    agent_config = get_agent_config(domain_spec.agent_config)

    tools = domain_spec.tools
    instructions = domain_spec.instructions or _default_instructions(domain_spec)

    return Agent(
        name=agent_config["name"],
        tools=tools,
        markdown=True,
        use_instruction_tags=False,
        instructions=instructions,
        cache_callables=False,
        knowledge=domain_spec.knowledge,
        search_knowledge=domain_spec.knowledge is not None,
        add_search_knowledge_instructions=domain_spec.knowledge is not None,
        skills=domain_spec.skills,
        model=_resolve_model(manifest),
        fallback_models=[_resolve_fallback(manifest)],
        add_datetime_to_context=True,
        # ponytail: hardcoded TZ; make configurable (env/manifest) when a non-BR app needs it.
        timezone_identifier="America/Sao_Paulo",
        debug_mode=config.DEBUG_MODE,
    )
