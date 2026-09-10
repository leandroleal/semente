"""FallbackAgent: primary runs; on failure, retries once with the fallback."""

from semente.backends.base import AgentInput, AgentTurn, FallbackAgent


class _Boom:
    def run(self, input):
        raise RuntimeError("model unavailable")


class _Ok:
    def __init__(self, tag):
        self.tag = tag

    def run(self, input):
        return AgentTurn(content=self.tag)


def test_fallback_retries_on_failure():
    agent = FallbackAgent(_Boom(), _Ok("fallback"))
    turn = agent.run(AgentInput(text="hi"))
    assert turn.content == "fallback"


def test_primary_used_when_healthy():
    agent = FallbackAgent(_Ok("primary"), _Ok("fallback"))
    turn = agent.run(AgentInput(text="hi"))
    assert turn.content == "primary"


if __name__ == "__main__":
    test_fallback_retries_on_failure()
    test_primary_used_when_healthy()
    print("Fallback tests OK")
