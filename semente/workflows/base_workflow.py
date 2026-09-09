"""Base workflow composition — the neutral orchestration engine.

Assembles the root workflow: onboarding check (terms acceptance) → parallel
feedback/summarization + the single agent → remediation merge → output.

Feature toggles (manifest ``features``) control which steps are included:
``pii_guardrail``, ``summarization``, ``feedback_workflow``, ``tts``.

``build_workflow(agent, manifest)`` builds the workflow for a given agent;
``get_workflow()`` loads the manifest + domain, applies the language prompts
dir, builds the agent, and returns a cached workflow singleton.

Prompt-loading modules (steps, agents, feedback workflow) are imported lazily
inside ``build_workflow`` so the language/prompts dir can be set first.
"""

import importlib
import os
from pathlib import Path
from typing import Any

from agno.workflow import Condition, Parallel, Step
from agno.workflow.types import StepInput

from semente.agents.build_agent import build_agent
from semente.configs.config import config
from semente.configs.prompts import set_prompts_dir
from semente.core.step_factory import agent_executor_factory
from semente.database.agno_db import db
from semente.database.models import UserTermsAcceptance
from semente.database.session import SessionLocal
from semente.domain import DomainSpec
from semente.manifest import Manifest
from semente.models.persist_on_success_workflow import PersistOnSuccessWorkflow
from semente.schemas.workflow_state import WorkflowState


def _needs_onboarding(step_input: StepInput, session_state: dict[str, Any]) -> bool:
    """Return True if the user needs to go through onboarding (terms not accepted)."""
    if session_state.get("workflow_state") is None:
        session_state["workflow_state"] = WorkflowState().model_dump()

    if session_state.get("terms_accepted"):
        return False

    user_id = session_state.get("user_id")
    if not user_id:
        return True

    db_session = SessionLocal()
    try:
        record = db_session.query(UserTermsAcceptance).filter(
            UserTermsAcceptance.user_id == user_id,
            UserTermsAcceptance.accepted == True,  # noqa: E712
        ).first()

        if record:
            session_state["terms_accepted"] = True
            return False

        return True
    finally:
        db_session.close()


def build_workflow(agent: Any, manifest: Manifest) -> PersistOnSuccessWorkflow:
    """Assemble the root workflow for a built agent, honoring feature toggles."""
    # Deferred imports — these modules load prompts at import time, so they
    # must be imported after the language/prompts dir has been applied.
    from semente.agents.welcoming_agent import build_welcoming_agent
    from semente.steps.feedback.remediation import (
        INTENT_ROUTER_STEP_NAME,
        remediation_check_step,
    )
    from semente.steps.guardrails_step import guardrails_step
    from semente.steps.input_step import input_step
    from semente.steps.output_step import output_step
    from semente.steps.summarization_step import summarization_step
    from semente.workflows.feedback_workflow import feedback_workflow

    features = manifest.features or {}

    steps: list[Any] = [input_step]
    if features.get("pii_guardrail", True):
        steps.append(guardrails_step)

    # Parallel branch: summarization + feedback (optional) + the single agent.
    parallel_steps: list[Any] = []
    if features.get("summarization", True):
        parallel_steps.append(summarization_step)
    if features.get("feedback_workflow", True):
        parallel_steps.append(feedback_workflow)
    parallel_steps.append(
        Step(
            name=INTENT_ROUTER_STEP_NAME,
            executor=agent_executor_factory(agent=agent, include_summary=True),
        )
    )

    welcoming_agent = build_welcoming_agent(tts_enabled=features.get("tts", True))

    steps.append(
        Condition(
            name="Onboarding Check",
            evaluator=_needs_onboarding,
            steps=[
                Step(
                    name="Welcoming Agent",
                    executor=agent_executor_factory(welcoming_agent, include_summary=False),
                ),
            ],
            else_steps=[
                Parallel(*parallel_steps, name="Feedback and Routing"),
                remediation_check_step,
            ],
        )
    )
    steps.append(output_step)

    return PersistOnSuccessWorkflow(
        name=f"{manifest.name} Workflow",
        db=db,
        debug_mode=config.DEBUG_MODE,
        add_workflow_history_to_steps=True,
        num_history_runs=1,
        steps=steps,
    )


def _load_domain(manifest: Manifest) -> DomainSpec:
    """Import the app's domain module and return its ``domain_spec``.

    The app's cwd is added to ``sys.path`` so the domain package (which lives
    next to ``semente.yaml``) is importable regardless of how the app is run.
    """
    import sys

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    module = importlib.import_module(manifest.domain_module)
    spec = getattr(module, "domain_spec", None)
    if spec is None:
        raise AttributeError(
            f"Domain module '{manifest.domain_module}' must expose a 'domain_spec' "
            "(a semente.domain.DomainSpec instance)."
        )
    return spec


def _apply_prompts(manifest: Manifest) -> None:
    """Point the prompts loader at the app's prompts dir.

    Priority: explicit ``prompts_dir``, then ``prompts/<language>/`` if it exists.
    """
    if manifest.prompts_dir:
        set_prompts_dir(Path.cwd() / manifest.prompts_dir)
    elif manifest.language and manifest.language.lower() != "en":
        lang_dir = Path.cwd() / "prompts" / manifest.language
        if lang_dir.exists():
            set_prompts_dir(lang_dir)


_workflow_cache: PersistOnSuccessWorkflow | None = None


def get_workflow(manifest_path: str | None = None) -> PersistOnSuccessWorkflow:
    """Load manifest + domain, apply language, build the agent and workflow, cache."""
    global _workflow_cache
    if _workflow_cache is not None:
        return _workflow_cache

    path = manifest_path or os.getenv("SEMENTE_MANIFEST", "semente.yaml")
    manifest = Manifest.load(path)
    _apply_prompts(manifest)
    domain_spec = _load_domain(manifest)
    agent = build_agent(domain_spec, manifest)
    _workflow_cache = build_workflow(agent, manifest)
    return _workflow_cache
