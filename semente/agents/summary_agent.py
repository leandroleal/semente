from agno.agent import Agent

from semente.configs.config import config
from semente.configs.prompts import get_agent_config


_summary_config = get_agent_config("summary_agent")


def get_instructions() -> str:
    return _summary_config["instructions"].strip()


summary_agent = Agent(
    name=_summary_config["name"],
    model=config.model,
    fallback_models=[config.fallback_model],
    instructions=get_instructions,
)