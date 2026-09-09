# Engines

Semente's engine is swappable. The engine powers the LLM loop (chat + tool
calling + structured output); everything else — orchestration, sessions,
knowledge, skills, guardrails, channels — is Semente-owned and engine-free.

## Selecting an engine

```yaml
# semente.yaml
engine: adk          # agno (default) | adk | pi | bare
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
| **bare** | Supported | Python, in-process | No framework — a litellm function-calling loop |
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

| Capability | agno | adk | bare | pi |
|---|---|---|---|---|
| Tool calling | ✓ | ✓ | ✓ | ~ (bridge) |
| Structured output | ✓ | ✓ | ✓ | ~ (JSON + validate) |
| Multimodal input | ✓ | ✓ | ✓ (images/audio) | ✓ (images) |
| Media output | ✓ | ✓ | ✓ | ~ |
| Session state in tools | ✓ | ✓ (tool_context) | ✓ (StateContext) | ~ |
| Knowledge (KB search) | ✓ (native) | ✓ (A-K) | ✓ (A-K) | ~ |
| Tool hooks | ✓ (native) | ✓ (A-H) | ✓ (A-H) | ~ |

## The bare backend

The `bare` engine is the end state of the engine port: once media (A-M),
hooks (A-H) and knowledge (A-K) live in Semente, an engine only has to run
the LLM loop. `semente/backends/bare/` does that with `litellm.completion` —
a client, not a framework — so there is no state/session/callback model to
fight. Model mapping: `google` → `gemini/<id>`, `ollama` → `ollama/<id>`,
any other provider string passes through (e.g. `openai/gpt-4o`).

## Writing a backend

Implement `EngineBackend` in `semente/backends/<name>/` and register it in
`semente/backends/registry.py`. See `semente/backends/agno/` as the reference
and `semente/backends/toolkit.py` for the shared tool-execution seam (media
bag, hook chain, schema).
