from semente.backends.base import AgentSpec
from semente.backends.registry import get_backend
from semente.configs.prompts import get_agent_config
from semente.tools.onboarding_tools import accept_terms_and_conditions


def build_welcoming_agent(tts_enabled: bool = True):
    """Build the welcoming agent via the selected engine backend.

    ``tts_enabled`` controls whether the TTS tool is attached (manifest
    ``features.tts``). Prompts are loaded lazily so the language/prompts dir
    can be set before this is called.
    """
    welcoming_config = get_agent_config("welcoming_agent")

    tools = [accept_terms_and_conditions]
    if tts_enabled:
        from semente.tools.tts_tools import generate_speech

        tools.append(generate_speech)

    instructions_text = welcoming_config["instructions"].strip().format(
        terms_text=welcoming_config["terms_text"].strip()
    )

    spec = AgentSpec(
        name=welcoming_config["name"],
        instructions=lambda run_context: instructions_text,
        tools=tools,
    )
    return get_backend().build_agent(spec)
