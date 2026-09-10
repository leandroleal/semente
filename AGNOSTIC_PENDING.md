# AGNOSTIC_PENDING.md — remaining work for engine-agnosticity

Saved assessment (2026-09-09). Current state: tool types, orchestrator/state,
toolkit seam (media bag, hooks, schema), ADK parity A-M/A-H/A-K, and four
backends (agno, adk, bare, pi) are engine-agnostic. Pending, by priority:

## Real couplings

| # | Seam | File | What | Effort |
|---|---|---|---|---|
| 1 | `semente.tool()` wraps agno's decorator | `tools/__init__.py` | Native tool registry (description+hooks+schema, no agno) | ~1 day |
| 2 | `config.build_model` returns agno models (module-top import) | `configs/config.py` | Even `engine: bare` transitively requires agno; move model classes to `backends/agno/`, config resolves ModelSpec only | ~0.5 day |
| 3 | Knowledge stack is agno classes | `knowledge/__init__.py` | DECISION NEEDED: de-agno fully (~3-4 days) or document agno as an allowed KB library (0 days) | decision |
| 4 | Skills: agno LocalSkills; **A-S pending** — spec.skills ignored by ADK/bare | `skills.py` | Native SKILL.md reader + wire into adk/bare | ~0.5 day |
| 5 | TTS returns agno `Audio` | `services/audio/tts.py` | Return Semente `Audio` | hours |
| 6 | **A-F: model fallback** — manifest `models.fallback` parsed but discarded; regression on ALL engines | `backends/base.py`, `step_factory` | `AgentSpec.fallback_model` + Semente-level retry wrapper | ~1 day |
| 7 | Calculator = agno toolkit | `tools/__init__.py` | ~6 stdlib functions | hours |

## Dead / cosmetic

- `hooks/pre_hooks.py` — engine-coupled legacy, not wired into the orchestrator; delete or port `validate_phone_authorization` engine-free
- `services/transcription.py` — dead code constructing an agno Agent directly
- Type-hint-only `RunContext` imports (`persona_agent`, `feedback_agent`, `tool_hooks`) → Semente `Context`
- agno logger imports (`prompts.py`, `whatsapp/helpers.py` utils) — internalize

## Parity plan (ADK_PARITY.md)

- **A-P harness**: cross-engine golden tests (identical StepOutput shapes); real-key smokes (ADK media delivery, bare full flow — only dummy-key graceful-400 verified)
- **G6**: tool-call log on ADK/bare for the debug panel (cosmetic)

## pi backend (spike-gated)

Tool bridge (TS extension generator + Python tool server), shared process pool
(currently one Node process per agent — 8+), tools don't work at all.

## Streaming (Phase 2, all engines)

`Agent.stream()` protocol, orchestrator generator; pi natively streams,
litellm/ADK/agno all have streaming primitives.

## Recommended order

A-F → #2 (config decoupling, unblocks "bare without agno") → #1+#7+#4
(native tool layer + skills) → A-P harness → #3 decision → pi bridge → streaming.