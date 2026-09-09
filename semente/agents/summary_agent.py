from semente.backends.base import AgentSpec
from semente.backends.registry import get_backend
from semente.configs.prompts import get_agent_config


_summary_config = get_agent_config("summary_agent")


summary_agent = get_backend().build_agent(
    AgentSpec(
        name=_summary_config["name"],
        instructions=lambda run_context: _summary_config["instructions"].strip(),
    )
)
