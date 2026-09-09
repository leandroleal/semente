"""The engine port — the contract every backend implements.

Semente owns everything except the LLM loop. A backend provides exactly three
things: model construction, agent construction, and the agent run primitive.
See MULTI_ENGINE.md for the full design.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from pydantic import BaseModel

from semente.context import Context


@dataclass
class ModelSpec:
    provider: str
    model_id: str


@dataclass
class AgentSpec:
    """Everything a backend needs to build one agent."""

    name: str
    instructions: Callable[[Context], str]
    tools: Callable[[Context], list] | list = field(default_factory=list)
    output_schema: type[BaseModel] | None = None
    model: ModelSpec | None = None
    multimodal_in: bool = False
    knowledge: Any = None
    skills: Any = None


@dataclass
class AgentInput:
    text: str
    images: list | None = None
    audio: list | None = None
    session_state: dict | None = None
    user_id: str | None = None


@dataclass
class AgentTurn:
    content: str
    structured: dict | None = None
    usage: dict | None = None
    images: list | None = None
    videos: list | None = None
    audio: list | None = None
    files: list | None = None
    metrics: dict | None = None


class Agent(Protocol):
    """One LLM loop with tools, structured output, and multimodal input."""

    def run(self, input: AgentInput) -> AgentTurn: ...


class EngineBackend(ABC):
    """A swappable agent engine (Agno, ADK, pi, …)."""

    name: str = "base"

    @abstractmethod
    def build_agent(self, spec: AgentSpec) -> Agent: ...

    def supports(self, capability: str) -> bool:
        """Capability probe (e.g. 'structured_output', 'multimodal_in')."""
        return False
