"""Semente-owned workflow orchestrator — engine-free.

Replaces Agno's Workflow/Step/Condition/Parallel/Router with Semente-native
equivalents, mirroring the shapes the steps already rely on. The engine only
powers the agents; orchestration, history, and session state are Semente's.

See MULTI_ENGINE.md (Phase G).
"""

from __future__ import annotations

import json
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from semente.logging import log_debug, log_error


# ---------------------------------------------------------------------------
# StepOutput / StepInput
# ---------------------------------------------------------------------------

@dataclass
class StepOutput:
    content: str = ""
    images: Optional[list] = None
    videos: Optional[list] = None
    audio: Optional[list] = None
    files: Optional[list] = None
    metrics: Optional[dict] = None
    stop: bool = False
    success: bool = True
    steps: Optional[list["StepOutput"]] = None
    step_name: Optional[str] = None


@dataclass
class StepInput:
    input: Any = None
    previous_step_content: Optional[str] = None
    previous_step_outputs: "OrderedDict[str, StepOutput]" = field(default_factory=OrderedDict)
    images: list = field(default_factory=list)
    videos: list = field(default_factory=list)
    audio: list = field(default_factory=list)
    files: list = field(default_factory=list)
    workflow_session: Optional["WorkflowSession"] = None

    def get_input_as_string(self) -> Optional[str]:
        if self.input is None:
            return None
        if isinstance(self.input, str):
            return self.input
        if isinstance(self.input, (dict, list)):
            return json.dumps(self.input, indent=2, default=str)
        return str(self.input)

    def get_workflow_history(self, num_runs: Optional[int] = None) -> list[tuple[str, str]]:
        if not self.workflow_session:
            return []
        return self.workflow_session.get_workflow_history(num_runs=num_runs)

    def get_step_output(self, step_name: str) -> Optional[StepOutput]:
        if not self.previous_step_outputs:
            return None
        direct = self.previous_step_outputs.get(step_name)
        if direct:
            return direct
        return self._search_nested_steps(step_name)

    def _search_nested_steps(self, step_name: str) -> Optional[StepOutput]:
        for output in self.previous_step_outputs.values():
            found = _search_in_output(output, step_name)
            if found:
                return found
        return None


def _search_in_output(output: StepOutput, step_name: str) -> Optional[StepOutput]:
    if output.step_name == step_name:
        return output
    for child in output.steps or []:
        found = _search_in_output(child, step_name)
        if found:
            return found
    return None


def _has_stop_failure(output: StepOutput) -> bool:
    """Recursively check whether a step (or nested child) stopped with failure."""
    if output.stop and not output.success:
        return True
    return any(_has_stop_failure(child) for child in output.steps or [])


# ---------------------------------------------------------------------------
# Workflow session
# ---------------------------------------------------------------------------

@dataclass
class WorkflowSession:
    user_id: str
    session_id: str
    session_state: dict = field(default_factory=dict)
    runs: list[dict] = field(default_factory=list)  # [{user, assistant, ts}]

    def get_workflow_history(self, num_runs: Optional[int] = None) -> list[tuple[str, str]]:
        runs = self.runs if num_runs is None else self.runs[-num_runs:]
        return [(r.get("user", ""), r.get("assistant", "")) for r in runs]


# ---------------------------------------------------------------------------
# Step nodes
# ---------------------------------------------------------------------------

class Step:
    def __init__(self, name: str, executor: Callable):
        self.name = name
        self.executor = executor

    def execute(self, step_input: StepInput, session_state: dict) -> StepOutput:
        log_debug(f"Executing step: {self.name}")
        output = _call_executor(self.executor, step_input, session_state)
        if output is None:
            output = StepOutput(content="")
        output.step_name = self.name
        return output


class Condition:
    def __init__(self, name: str, evaluator: Callable, steps: list, else_steps: Optional[list] = None):
        self.name = name
        self.evaluator = evaluator
        self.steps = steps
        self.else_steps = else_steps or []

    def execute(self, step_input: StepInput, session_state: dict) -> StepOutput:
        log_debug(f"Evaluating condition: {self.name}")
        branch = self.steps if self.evaluator(step_input, session_state) else self.else_steps
        outputs = _run_steps(branch, step_input, session_state)
        return StepOutput(content="", steps=outputs, step_name=self.name)


class Parallel:
    def __init__(self, *steps: Step, name: str = "Parallel"):
        self.name = name
        self.steps = list(steps)

    def execute(self, step_input: StepInput, session_state: dict) -> StepOutput:
        log_debug(f"Executing parallel: {self.name}")
        outputs = _run_steps(self.steps, step_input, session_state)
        return StepOutput(content="", steps=outputs, step_name=self.name)


class Router:
    def __init__(self, name: str, selector: Callable, choices: list[Step]):
        self.name = name
        self.selector = selector
        self.choices = choices

    def execute(self, step_input: StepInput, session_state: dict) -> StepOutput:
        log_debug(f"Routing: {self.name}")
        selected = self.selector(step_input, session_state) or []
        chosen = [c for c in self.choices if c.name in selected]
        outputs = _run_steps(chosen, step_input, session_state)
        return StepOutput(content="", steps=outputs, step_name=self.name)


def _run_steps(steps: list, step_input: StepInput, session_state: dict) -> list[StepOutput]:
    outputs: list[StepOutput] = []
    for step in steps:
        output = step.execute(step_input, session_state)
        outputs.append(output)
        step_input.previous_step_outputs[step.name] = output
        if output.content:
            step_input.previous_step_content = output.content
        step_input.images.extend(output.images or [])
        step_input.videos.extend(output.videos or [])
        step_input.audio.extend(output.audio or [])
        step_input.files.extend(output.files or [])
    return outputs


def _call_executor(executor: Callable, step_input: StepInput, session_state: dict) -> StepOutput:
    """Call a step executor, passing only the args its signature accepts.

    Executors may take just ``step_input`` (e.g. input/guardrail/output steps)
    or ``(step_input, session_state)`` (e.g. agent/summarization/feedback steps).
    """
    import inspect

    sig = inspect.signature(executor)
    positional = [
        p
        for p in sig.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) >= 2:
        return executor(step_input, session_state)
    return executor(step_input)


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------

class Workflow:
    def __init__(self, name: str, steps: list, store: Optional["SessionStore"] = None):
        self.name = name
        self.steps = steps
        self.store = store

    def execute(self, step_input: StepInput, session_state: dict) -> StepOutput:
        """Run as a nested step (e.g. the feedback workflow inside a Parallel)."""
        log_debug(f"Executing nested workflow: {self.name}")
        outputs = _run_steps(self.steps, step_input, session_state)
        return StepOutput(content="", steps=outputs, step_name=self.name)

    def run(
        self,
        *,
        user_id: str,
        session_id: str,
        input: Any = None,
        images: Optional[list] = None,
        videos: Optional[list] = None,
        audio: Optional[list] = None,
        files: Optional[list] = None,
        session_state: Optional[dict] = None,
        stream: bool = False,
        stream_intermediate_steps: bool = False,
    ) -> StepOutput:
        if stream:
            # ponytail: streaming not yet implemented in the orchestrator; run
            # synchronously and return the complete result (Phase 2 of the fix).
            log_debug(
                "Workflow.run(stream=True): streaming not implemented; running synchronously."
            )
        session = self._load_session(user_id, session_id, session_state)
        step_input = StepInput(
            input=input,
            images=images or [],
            videos=videos or [],
            audio=audio or [],
            files=files or [],
            workflow_session=session,
        )

        outputs = _run_steps(self.steps, step_input, session.session_state)

        final = outputs[-1] if outputs else StepOutput(content="")
        self._persist(session, input, final)
        return final

    def _load_session(self, user_id: str, session_id: str, session_state: Optional[dict]) -> WorkflowSession:
        if self.store is not None:
            loaded = self.store.get(user_id, session_id)
            if loaded is not None:
                return WorkflowSession(
                    user_id=user_id,
                    session_id=session_id,
                    session_state=loaded.get("session_state", {}),
                    runs=loaded.get("runs", []),
                )
        return WorkflowSession(
            user_id=user_id,
            session_id=session_id,
            session_state=session_state or {},
        )

    def _persist(self, session: WorkflowSession, user_input: Any, final: StepOutput) -> None:
        if self.store is None:
            return
        # Persist-on-success policy: skip when a step stopped with failure
        # (e.g. the PII guardrail blocking a run).
        if _has_stop_failure(final):
            return
        user_text = user_input if isinstance(user_input, str) else str(user_input or "")
        session.runs.append({"user": user_text, "assistant": final.content or ""})
        self.store.save(
            session.user_id,
            session.session_id,
            session_state=session.session_state,
            runs=session.runs,
        )

    def get_session_state(self, user_id: Optional[str] = None, session_id: str = "") -> dict:
        if self.store is not None:
            loaded = self.store.get(user_id, session_id)
            if loaded is not None:
                return loaded.get("session_state", {})
        return {}


# ---------------------------------------------------------------------------
# Session store (SQLAlchemy-backed)
# ---------------------------------------------------------------------------

class SessionStore:
    """Canonical session persistence: state + history pairs per (user, session)."""

    def __init__(self, session_factory, model):
        self.session_factory = session_factory
        self.model = model

    def get(self, user_id: Optional[str], session_id: str) -> Optional[dict]:
        db = self.session_factory()
        try:
            query = db.query(self.model).filter(self.model.session_id == session_id)
            if user_id is not None:
                query = query.filter(self.model.user_id == user_id)
            record = query.first()
            if record is None:
                return None
            return {
                "session_state": record.session_state or {},
                "runs": record.runs or [],
            }
        finally:
            db.close()

    def save(self, user_id: str, session_id: str, session_state: dict, runs: list) -> None:
        db = self.session_factory()
        try:
            record = db.query(self.model).filter(
                self.model.session_id == session_id,
                self.model.user_id == user_id,
            ).first()
            if record is None:
                record = self.model(session_id=session_id, user_id=user_id)
                db.add(record)
            record.session_state = session_state
            record.runs = runs
            db.commit()
        except Exception as exc:
            db.rollback()
            log_error(f"SessionStore.save failed: {exc}")
        finally:
            db.close()

    def list_sessions(self, user_id: str) -> list[str]:
        """Return session ids for a user, most recently updated first."""
        db = self.session_factory()
        try:
            records = (
                db.query(self.model)
                .filter(self.model.user_id == user_id)
                .order_by(self.model.updated_at.desc())
                .all()
            )
            return [r.session_id for r in records]
        finally:
            db.close()
