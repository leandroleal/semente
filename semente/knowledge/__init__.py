"""Engine-neutral knowledge base surface.

Level 1: re-exports the engine's knowledge/vectordb classes under stable
Semente names, so a domain's KB module compiles without importing the engine.
Level 2 (see ENGINE_ABSTRACTION.md) replaces this with a ``build_knowledge``
factory that hides the engine entirely.
"""

from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.embedder.google import GeminiEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.chroma import ChromaDb
from agno.vectordb.distance import Distance
from agno.vectordb.pgvector import PgVector

__all__ = [
    "RecursiveChunking",
    "GeminiEmbedder",
    "Knowledge",
    "ChromaDb",
    "Distance",
    "PgVector",
]
