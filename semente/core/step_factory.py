from typing import Optional, Dict, Any

from semente.backends.base import AgentInput
from semente.core.orchestrator import StepInput, StepOutput, Step
from semente.logging import log_error, log_debug

from semente.schemas.input_manager import InputManager


def _input_pre_processing(
    step_input: StepInput,
    session_state: Dict[str, Any],
    include_summary: bool,
    num_runs: Optional[int] = None,
) -> str:
    """Build the enriched input string for an agent step.

    Prepends the conversation summary (if available and requested) and a
    configurable number of history runs, then appends the current user input.

    Args:
        step_input: The step input containing the user message and history.
        session_state: The current session state dict.
        summary: Whether to include the running summary in the input.
        num_runs: Override for how many history runs to include.
            If None, uses ``runs_count`` from InputManager.

    Returns:
        The assembled input string for the agent.
    """
    input_manager = InputManager.model_validate(
        session_state.get("summary_state", {})
    )

    # Build the dynamic conversation history block and stash it in
    # session_state so the agent's dynamic instructions can read it.
    # The history grows/shrinks dynamically via input_manager.runs_count.
    effective_runs = num_runs if num_runs is not None else input_manager.runs_count
    history_msgs = step_input.get_workflow_history(num_runs=effective_runs)

    history_block = ""
    if history_msgs:
        history_block = "<iterações>"
        for idx, msg in enumerate(history_msgs):
            user_msg, assistant_msg = msg
            history_block += (
                f"\n[Iteração {idx}]\n"
                f"Usuário: {user_msg}\n"
                f"Assistente: {assistant_msg}\n"
            )
        history_block += "</iterações>"

    session_state["history_context"] = history_block

    # The running summary is already maintained in session_state by the
    # summarization step (session_state['conversation_summary']); it is
    # read directly by the agent's dynamic instructions, so we no longer
    # inject it into the input string here.
    _ = include_summary  # kept for signature compatibility; no longer used

    parts: list[str] = []

    text = list(step_input.previous_step_outputs.values())[-1].content or ""
    if text:
        parts.append(f"<input>\n{text}\n</input>")

    return "\n".join(parts)


def agent_executor_factory(
    agent,
    include_summary: bool = True,
    num_runs: Optional[int] = None,
):
    """Create a step executor that pre-processes input before running an agent.

    The executor assembles the input string via ``_input_pre_processing``
    (which prepends summary and history context), then runs the backend agent
    with the full session state so that agents with dynamic instructions can
    access up-to-date context.

    Args:
        agent: The backend ``Agent`` (port protocol) to run.
        summary: Whether to include the running summary in the input.
        num_runs: Override for how many history runs to include.

    Returns:
        A callable matching the ``StepExecutor`` signature
        ``(step_input, session_state) -> StepOutput``.
    """
    def _agent_executor(
        step_input: StepInput,
        session_state: Dict[str, Any],
    ) -> StepOutput:
        final_input = _input_pre_processing(
            step_input, session_state, include_summary, num_runs
        )

        try:
            user_id = step_input.workflow_session.user_id

            turn = agent.run(
                AgentInput(
                    text=final_input,
                    images=step_input.images or None,
                    audio=step_input.audio or None,
                    session_state=session_state,
                    user_id=user_id,
                )
            )
        except Exception as exc:
            log_error(f"agent failed: {exc}")
            return StepOutput(
                content="Desculpa, houve um erro durante a execução. Tente novamente mais tarde!"
            )

        return StepOutput(
            content=turn.content or "",
            images=turn.images,
            videos=turn.videos,
            audio=turn.audio,
            files=turn.files,
            metrics=turn.metrics,
        )

    return _agent_executor