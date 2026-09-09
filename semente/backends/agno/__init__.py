"""Agno backend — the reference engine implementation.

Implements the Semente engine port (``EngineBackend``) on top of Agno. All
Agno imports for agent construction live here; the rest of Semente is
engine-free.
"""

from __future__ import annotations

from typing import Any

from agno.agent import Agent as AgnoAgent
from agno.media import Audio as EAudio
from agno.media import Image as EImage

from semente.backends.agno.media import to_engine_media
from semente.backends.base import Agent, AgentInput, AgentSpec, AgentTurn, EngineBackend
from semente.configs.config import config


def _build_model(spec_model):
    if spec_model is None:
        return config.model
    return config.build_model(spec_model.provider, spec_model.model_id)


class AgnoAgentAdapter:
    """Adapts an Agno Agent to the Semente ``Agent`` protocol."""

    def __init__(self, agent: AgnoAgent):
        self.agent = agent

    def run(self, input: AgentInput) -> AgentTurn:
        response = self.agent.run(
            input.text,
            images=[to_engine_media(i, EImage) for i in input.images] if input.images else None,
            audio=[to_engine_media(a, EAudio) for a in input.audio] if input.audio else None,
            user_id=input.user_id,
            session_state=input.session_state,
        )

        content = response.content
        structured = None
        if content is not None and not isinstance(content, str):
            structured = content.model_dump() if hasattr(content, "model_dump") else content
            content = ""

        return AgentTurn(
            content=content or "",
            structured=structured,
            images=response.images,
            videos=response.videos,
            audio=response.audio,
            files=response.files,
            metrics=response.metrics,
        )


class AgnoBackend(EngineBackend):
    name = "agno"

    def build_agent(self, spec: AgentSpec) -> Agent:
        agent = AgnoAgent(
            name=spec.name,
            tools=spec.tools,
            markdown=True,
            use_instruction_tags=False,
            instructions=spec.instructions,
            cache_callables=False,
            output_schema=spec.output_schema,
            use_json_mode=spec.output_schema is not None,
            knowledge=spec.knowledge,
            search_knowledge=spec.knowledge is not None,
            add_search_knowledge_instructions=spec.knowledge is not None,
            skills=spec.skills,
            model=_build_model(spec.model),
            add_datetime_to_context=True,
            timezone_identifier="America/Sao_Paulo",
            debug_mode=config.DEBUG_MODE,
        )
        return AgnoAgentAdapter(agent)

    def supports(self, capability: str) -> bool:
        return capability in {"structured_output", "multimodal_in", "media_out"}
