"""Step factory tests — the agent-input extraction seam.

Regression test for the "must send twice" bug: sibling Parallel branches
(summarization, feedback) insert their outputs into previous_step_outputs
BEFORE the agent branch runs, so the agent's input must be read from the
input step's output by name — never from "the last output".
"""

from semente.core.orchestrator import StepInput, StepOutput, WorkflowSession
from semente.core.step_factory import _input_pre_processing


def _step_input(user_text: str) -> StepInput:
    session = WorkflowSession(user_id="u", session_id="s")
    si = StepInput(input=user_text, workflow_session=session)
    # What previous_step_outputs looks like when the agent branch runs:
    # input + guardrail, then the Parallel siblings (summarization, feedback).
    si.previous_step_outputs["Input Step"] = StepOutput(content=user_text)
    si.previous_step_outputs["Guardrail PII"] = StepOutput(content=user_text)
    si.previous_step_outputs["Summarization Step"] = StepOutput(content="")
    si.previous_step_outputs["Feedback Workflow"] = StepOutput(
        content='{"level": "3"}'  # sibling pollutes the dict with non-user text
    )
    return si


def test_agent_input_comes_from_input_step_not_last_sibling():
    out = _input_pre_processing(_step_input("qual a situação da pastagem?"), {}, True)
    assert out == "<input>\nqual a situação da pastagem?\n</input>"
    assert "level" not in out


def test_agent_input_falls_back_to_raw_input_without_input_step():
    session = WorkflowSession(user_id="u", session_id="s")
    si = StepInput(input="olá direto", workflow_session=session)
    si.previous_step_outputs["Feedback Workflow"] = StepOutput(content='{"level": "3"}')
    out = _input_pre_processing(si, {}, True)
    assert "olá direto" in out
    assert "level" not in out


if __name__ == "__main__":
    test_agent_input_comes_from_input_step_not_last_sibling()
    test_agent_input_falls_back_to_raw_input_without_input_step()
    print("Step factory tests OK")