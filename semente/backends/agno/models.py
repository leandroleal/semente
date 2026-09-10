"""Agno model construction — the only place agno model classes are built.

``config`` resolves provider + id only (engine-neutral); this module turns that
into an agno model instance. Kept out of ``configs/config.py`` so importing
the config does not transitively import agno (unblocks ``engine: bare`` without
agno installed).
"""

from __future__ import annotations

from semente.configs.config import config


def build_model(provider: str, model_id: str):
    match provider:
        case "google":
            from agno.models.google import Gemini

            if config.GOOGLE_API_KEY is None:
                raise ValueError("GOOGLE_API_KEY environment variable must be set.")
            return Gemini(id=model_id, temperature=0.4, api_key=config.GOOGLE_API_KEY)
        case "ollama":
            from agno.models.ollama import Ollama

            if config.OLLAMA_API_KEY is None and config.OLLAMA_HOST is not None:
                raise ValueError("OLLAMA_API_KEY environment variable must be set.")
            return Ollama(id=model_id, host=config.OLLAMA_HOST, api_key=config.OLLAMA_API_KEY)
        case _:
            raise ValueError(f"Invalid model provider: {provider}")
