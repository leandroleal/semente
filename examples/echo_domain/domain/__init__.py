"""Echo domain — the minimal Semente app, used to prove the seam works.

One trivial tool, no knowledge base, no skills. Once Phase 2 copies the core
modules, this boots on Streamlit with zero domain code beyond this file.
"""

from semente import tool
from semente.domain import DomainSpec


@tool(description="Echo the given message back to the user.")
def echo(message: str) -> str:
    """Return the message unchanged."""
    return f"Echo: {message}"


domain_spec = DomainSpec(
    name="Echo Domain",
    tools=[echo],
)
