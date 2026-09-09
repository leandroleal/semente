# Engines

Semente's engine is swappable. The engine powers the LLM loop (chat + tool
calling + structured output); everything else — orchestration, sessions,
knowledge, skills, guardrails, channels — is Semente-owned and engine-free.

## Selecting an engine

```yaml
# semente.yaml
engine: adk          # agno (default) | adk | pi
```

Or via environment variable:

```bash
export SEMENTE_ENGINE=adk
```

The same domain, manifest, prompts, and channels run unchanged.

## Backends

| Engine | Tier | Runtime | Notes |
|---|---|---|---|
| **agno** | Stable | Python, in-process | Reference implementation |
| **adk** | Supported | Python, in-process | Google Agent Development Kit |
| **pi** | Experimental | Node.js subprocess | RPC sidecar; tool bridge spike-gated |

## The contract

Each backend implements `semente.backends.base.EngineBackend`:

```python
class EngineBackend(ABC):
    def build_agent(self, spec: AgentSpec) -> Agent: ...
    def supports(self, capability: str) -> bool: ...
```

`AgentSpec` carries the name, instructions callable, tools, output schema,
model, knowledge, and skills. `Agent.run(AgentInput) -> AgentTurn` is the
single run primitive.

## Capability matrix

| Capability | agno | adk | pi |
|---|---|---|---|
| Tool calling | ✓ | ✓ | ~ (bridge) |
| Structured output | ✓ | ✓ | ~ (JSON + validate) |
| Multimodal input | ✓ | ✓ | ✓ (images) |
| Media output | ✓ | ~ | ~ |
| Session state in tools | ✓ | ✓ (tool_context) | ~ |

## Writing a backend

Implement `EngineBackend` in `semente/backends/<name>/` and register it in
`semente/backends/registry.py`. See `semente/backends/agno/` as the reference.

See `MULTI_ENGINE.md` for the full design and roadmap.
