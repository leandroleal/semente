"""Media agents — image description and audio transcription (via the backend)."""

from semente.backends.base import AgentSpec
from semente.backends.registry import get_backend
from semente.configs.prompts import get_agent_config


_image_config = get_agent_config("image_description_agent")
_audio_config = get_agent_config("audio_transcription_agent")


image_description_agent = get_backend().build_agent(
    AgentSpec(
        name=_image_config["name"],
        instructions=lambda run_context: _image_config["instructions"].strip(),
        multimodal_in=True,
    )
)


audio_transcription_agent = get_backend().build_agent(
    AgentSpec(
        name=_audio_config["name"],
        instructions=lambda run_context: _audio_config["instructions"].strip(),
        multimodal_in=True,
    )
)
