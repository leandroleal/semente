from agno.agent import Agent

from semente.configs.config import config
from semente.configs.prompts import get_agent_config
from semente.tools.onboarding_tools import accept_terms_and_conditions


def build_welcoming_agent(tts_enabled: bool = True) -> Agent:
    """Build the welcoming agent.

    ``tts_enabled`` controls whether the TTS tool is attached (manifest
    ``features.tts``). Prompts are loaded lazily so the language/prompts dir
    can be set before this is called.
    """
    welcoming_config = get_agent_config("welcoming_agent")

    tools = [accept_terms_and_conditions]
    if tts_enabled:
        from semente.tools.tts_tools import generate_speech

        tools.append(generate_speech)

    return Agent(
        name=welcoming_config["name"],
        role=welcoming_config["role"],
        description=welcoming_config["description"],
        instructions=welcoming_config["instructions"].strip().format(
            terms_text=welcoming_config["terms_text"].strip()
        ),
        tools=tools,
        model=config.model,
        fallback_models=[config.fallback_model],
        debug_mode=config.DEBUG_MODE,
    )
