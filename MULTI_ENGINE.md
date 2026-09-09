# MULTI_ENGINE.md — Level 2: the Engine Port (Agno ↔ ADK ↔ pi)

**Goal:** flip one line — `engine: adk` (or `pi`, or `agno`) in `semente.yaml` —
and the same domain, manifest, prompts, and channels run unchanged. Domains
stay engine-free (Level 1 guarantee); the engine becomes Semente's private,
swappable implementation detail.

**Companion docs:** `ENGINE_ABSTRACTION.md` (Level 1, ✅ done — this is its
Phase C, generalized from "hide Agno" to "swap Agno").

> **Status:** Phases F–J ✅ implemented — Agno, ADK, and pi backends all
> registered behind the port; the Semente orchestrator is engine-free. Phase K
> (CI matrix + golden tests) is the remaining hardening.

---

## 1. Two discoveries that make this tractable

**Discovery 1 — Semente is already stateless-friendly.** The workflow does
*not* rely on engine-side chat history. Every agent step receives its context
through Semente-owned machinery: `step_factory` injects a `<history_context>`
block (last N turns as text) and the summarization step maintains a
`<conversation_summary>` — both written into `session_state` and read by the
dynamic instruction builders. The engine's own session/history is largely
redundant. **Consequence:** the port does not need engines to agree on history
semantics; Semente feeds history in the prompt and owns the canonical store.

**Discovery 2 — Media doesn't need to flow through the LLM loop.** Today,
tools return `ToolResult(images=…, videos=…)` and Agno carries media through
`RunOutput` to the step output. Instead, Semente can own tool execution: a
wrapper calls each domain tool, stashes any media in a per-turn **MediaBag**,
and returns *only the text* to the LLM. The output step attaches MediaBag
content to the turn result. **Consequence:** every engine only ever sees
strings; media handling is identical across engines.

Everything else Semente does — orchestration, onboarding, feedback loop,
personas, summarization, PII guardrails, TTS (already direct `google-genai`,
engine-free), WhatsApp chunking/debouncing, Streamlit — is already
Semente-owned code. The port only has to cover **the LLM loop**.

---

## 2. Verified engine facts (checked, not assumed)

| | **Agno** 2.6.6 (current) | **ADK** (google-adk, Python) | **pi** (Earendil, Node/TS) |
|---|---|---|---|
| Runtime | Python, in-process | Python, in-process | **Node.js subprocess** — RPC mode: JSONL over stdio (`pi --mode rpc`); no Python SDK |
| Agent loop | `Agent` + `Team`/`Workflow` | `LlmAgent` + `Runner` | Agent loop inside pi; driven via `prompt` command + event stream |
| Custom tools | `@tool` decorator | plain Python functions (typed + docstring); `tool_context: ToolContext` auto-injected by param name | **TypeScript extensions only** (`pi.registerTool()`) — Python tools must be proxied |
| Dynamic instructions | callable `(RunContext) -> str` | `InstructionProvider: (ReadonlyContext) -> str` — direct analog; `{var}` state templating also available | prompt text per turn (Semente builds it) |
| Structured output | `output_schema=Pydantic` | `output_schema=Pydantic` (⚠ only with no-tools agents, or Gemini 3) | prompt-based JSON + Semente-side validation |
| Session/state | `RunContext.session_state`; Sqlite/PostgresDb | `Session.state` via SessionService (InMemory/DB/Vertex); state prefixes (`user:`, `temp:`) | pi session files; for us: **stateless** (`--no-session`), state lives in Semente |
| Media **in** | `agent.run(images=…, audio=…)` | multimodal content parts | RPC `prompt` supports images; audio: use Semente-owned STT first |
| Media **out** | `ToolResult` media → `RunOutput` | parts/artifacts | (moot — MediaBag) |
| History | engine sessions | engine sessions (`include_contents`) | (moot — Semente injects history) |
| Skills | `LocalSkills` (SKILL.md) | instruction includes | **same Agent Skills standard** (SKILL.md), auto-discovery — aligned |
| Fallback models | `fallback_models=` | manual | manual |

Key API notes verified from source/docs: ADK tools auto-wrap plain functions;
`ToolContext.state` mutations are event-tracked; ADK `output_schema` + tools
together is model-dependent (our structured-output agents — satisfaction,
persona, terms validator — use **no tools**, so they're safe). pi RPC framing
is strict JSONL on `\n` only (must not use Python `readline`, which splits on
U+2028/2029).

---

## 3. Architecture — what the port is

```
                    SEMENTE OWNS (engine-free)                ENGINE OWNS
┌────────────────────────────────────────────────────┐   ┌──────────────────┐
│ domain (tools, KB, skills, prompts)  [Level 1 ✓]    │   │                  │
│ orchestrator: Step/Condition/Parallel/Router/Runner │   │  the LLM loop:   │
│ canonical Session + history pairs (SQLAlchemy)      │──▶│  chat with tool  │
│ tool executor + MediaBag                            │   │  calling +       │
│ knowledge (chunk+embed+pgvector/chroma, absorbed)   │   │  structured out  │
│ skills (SKILL.md → instructions, absorbed)           │   │                  │
│ guardrails, personas, feedback, summarization, TTS  │   └──────────────────┘
│ channels: WhatsApp (FastAPI), Streamlit             │      ▲            ▲   ▲
└────────────────────────────────────────────────────┘      │            │   │
                                            semente/backends/agno │ adk │ pi
```

**The port is tiny on purpose.** Everything that made the old Level-3
estimation scary (workflow semantics, sessions, knowledge, skills) is
Semente-owned and therefore engine-independent. The engine contract covers
exactly three things:

### The contract (`semente/backends/base.py`)

```python
@dataclass
class ModelSpec:
    provider: str          # "google" | "ollama" | "anthropic" | …
    model_id: str

@dataclass
class AgentSpec:
    name: str
    instructions: Callable[[Context], str]      # semente Context protocol
    tools: Callable[[Context], list] | list     # semente-native ToolDef
    output_schema: type[BaseModel] | None        # structured output
    model: ModelSpec
    multimodal_in: bool = False                 # accept images/audio in input

@dataclass
class AgentInput:
    text: str
    images: list[bytes] | None = None
    audio: list[bytes] | None = None
    context: Context                            # session_state, user_id

@dataclass
class AgentTurn:
    content: str                                # final text
    structured: dict | None                     # when output_schema set
    usage: dict | None = None

class Agent(Protocol):
    def run(self, input: AgentInput) -> AgentTurn: ...

class EngineBackend(ABC):
    def build_agent(self, spec: AgentSpec) -> Agent: ...
    def supports(self, capability: str) -> bool: ...
```

That's the entire surface each backend implements. **Not in the port**
(because Semente owns them): orchestration, sessions/history, knowledge,
skills, media-out, TTS, fallback models (a Semente retry wrapper around
`Agent.run` tries `ModelSpec` primary → fallback — replacing Agno's
`fallback_models`, which the port loses anyway).

### Canonical flow per turn

1. `SessionStore` (Semente, SQLAlchemy — tables exist today) loads state +
   history pairs for `(user_id, session_id)`.
2. Orchestrator runs steps. Agent steps build `AgentInput` (with
   `<history_context>`/summary blocks baked into instructions by the existing
   `step_factory`) and call `backend_agent.run(...)`.
3. The **tool executor** intercepts every tool call: domain tool runs in
   Python, `ToolResult.media` → MediaBag, only `content` text returns to the
   engine.
4. Output step attaches MediaBag media; orchestrator persists state, the
   `(user, assistant)` pair, and media references.

### Skills & knowledge leave the port entirely

- **Skills:** absorb the SKILL.md loader into Semente (`semente.skills` reads
  `SKILL.md`, merges into instructions). Agno/pi both follow the same Agent
  Skills standard — but Semente doesn't need either; it's ~60 lines.
- **Knowledge:** absorb the current `pasto_legal_kb.py` machinery
  (chunk/embed/hash-sync, PgVector/ChromaDb fallback) as
  `semente.knowledge.build_knowledge()`; retrieval happens as a **tool**
  (`search_knowledge_base` becomes a plain Semente tool). No engine involved.

---

## 4. Backend designs

### 4.1 `semente/backends/agno/` — the reference implementation

The mapping is nearly 1:1 with today's code (that's the point — Phase H is a
*relocation*, not a rewrite):

| Port concept | Agno implementation |
|---|---|
| `AgentSpec.instructions` | `Agent(instructions=callable)` (already) |
| `AgentSpec.tools` | engine tools via the Agno `tool` decorator (via `adapters`) |
| `output_schema` | `Agent(output_schema=…, use_json_mode=True)` |
| `Agent.run` | `agent.run(input.text, images=, audio=, session_state=…)` → map `RunOutput` → `AgentTurn` |
| tool executor | Agno `ToolResult` → MediaBag adapter |
| structured `RunOutput.content` | `.content` is already the pydantic instance — `model_dump()` |

### 4.2 `semente/backends/adk/` — proves the port in-process

| Port concept | ADK implementation |
|---|---|
| `AgentSpec.instructions` | `InstructionProvider: lambda ctx: spec.instructions(semente_ctx_from(ctx))` — direct analog; state read via `ctx.state` |
| `AgentSpec.tools` | **plain functions**: adapter generates `def wrapper(args…, tool_context=None)` per Semente ToolDef, remapping `run_context` ⇄ `tool_context` (ADK injects by *param name*, ours by *type* — the adapter closes the gap) |
| `output_schema` | `LlmAgent(output_schema=…)` — our structured agents are tool-free, so the ADK tools+schema limitation doesn't bite |
| `Agent.run` | `Runner(agent=…, session_service=InMemorySessionService)` per turn; pre-seed `session.state` from Semente state, run, read back `session.state` diff → apply to canonical store |
| media-in | `types.Part(inline_data=…)` content parts |
| models | `model="gemini-…"` string or `LiteLLM` for others (Ollama via LiteLLM) |

State diffing (ADK auto-tracks `tool_context.state` deltas) is the delicate
part — the adapter syncs Semente state → ADK session pre-run and merges
deltas post-run. Covered by parity tests.

### 4.3 `semente/backends/pi/` — the stress test (subprocess architecture)

pi is a Node runtime; custom tools are TypeScript. Design:

```
Semente (Python)                          pi (Node subprocess)
┌──────────────────────────┐  JSONL/RPC  ┌─────────────────────────────┐
│ PiBackend:               │────────────▶│ pi --mode rpc --no-session   │
│  spawn pi, parse events  │             │  + generated bridge.ts ext: │
│                          │             │   registerTool(each tool) →  │
│ Semente tool server:     │◀────────────│   HTTP POST to tool server  │
│  POST /tools/{name}      │  HTTP       │   returns JSON result        │
└──────────────────────────┘────────────▶└─────────────────────────────┘
```

- **Backend** spawns `pi --mode rpc --no-session --provider <p> --model <id>`
  (Ollama via pi's `models.json` custom providers — verified supported).
- **Bridge extension (generated):** at startup, Semente generates a small
  TypeScript extension from the DomainSpec tool list (name, description, JSON
  schema) into the app's `.pi/extensions/`; each registered tool POSTs
  `{session_id, args}` to Semente's tool server and returns the text result.
  Domain tools still run in **Python** — pi only routes calls.
- **Turn protocol:** send `prompt` (with base64 images when needed), consume
  events until `turn_end`, extract assistant text. Strict LF framing (no
  Python `readline` — it splits on U+2028/2029; the pi docs call this out).
- **State:** `--no-session` — Semente is the only state owner; history and
  state go in the prompt prelude (Discovery 1 makes this semantically
  equivalent to today).
- **Structured output:** Semente-side JSON extraction + pydantic validation +
  one retry (a `JsonOutputAgent` helper in `backends/base` shared by any
  backend lacking native support).
- **Degradations (honest):** Node runtime required; audio-in goes through
  Semente's transcription (genai-direct) first; one extra hop of latency per
  tool call; experimental support tier.

**Spike gate (Phase J):** before building the full backend, a 2–3 day spike
must prove: RPC round-trip + generated tool bridge + `turn_end` text
extraction works end-to-end with the echo domain. If the spike fails, pi ships
as "planned, deferred" and the port still stands on agno+ADK.

---

## 5. Phases

> Sequencing principle: **the orchestrator rewrite happens while Agno still
> powers the agents** — so behavior parity is verifiable at every step, and
> the port lands only after the engine-neutral core is proven.

### Phase F — Semente-owned primitives (1.5 wk)
- Native `ToolResult`/media dataclasses + **tool executor + MediaBag**
  (replaces the Level-1 re-exports; domains keep importing `semente` — the
  names don't change, the types underneath do).
- `semente.knowledge.build_knowledge()` — absorb the KB machinery
  (`pasto_legal_kb.py` → ~10 lines; hash-sync/chroma/pgvector become
  Semente's, tested as such).
- `semente.skills` — native SKILL.md loader merged into instructions.
- `semente/backends/base.py` — the contract (§3) frozen.
- **Exit:** echo + pasto-legal run on native types through Agno; domain purity
  still green.

### Phase G — Semente orchestrator (2.5 wk, the core rewrite)
- `semente/core/orchestrator`: `Step`, `Condition`, `Parallel`, `Router`,
  `Workflow`, `StepInput/StepOutput` mirroring today's shapes (proven by
  real usage), ~600 lines incl. the runner, history pairs, and the
  persist-on-success policy (already Semente code).
- Canonical `SessionStore` (SQLAlchemy; tables exist) + media references.
- Port the 10 steps mechanically (they're plain functions).
- **Agents still Agno** through Phase F's native types.
- **Exit (parity gate):** pasto-legal runs **on the Semente orchestrator**
  with Agno agents; scripted-conversation golden tests (onboarding,
  registration, analysis, feedback) byte-comparable in behavior to today.

### Phase H — Agno behind the port (1.5 wk)
- `semente/backends/agno/` implements the contract; **all** agno imports in
  Semente move into `backends/agno/` + `adapters/` (import-linter contract).
- Own FastAPI assembly replaces `agno.os.AgentOS`; WhatsApp
  `BaseInterface`/`RemoteAgent` session plumbing replaced by Semente
  `SessionStore`; Streamlit points at the orchestrator API
  (`run/get_session_state` equivalents).
- Fallback-models retry wrapper (Semente-side).
- **Exit:** zero agno imports outside `backends/agno/`; full parity again;
  `engine: agno` is now a config value, not an assumption.

### Phase I — ADK backend (1.5–2 wk)
- `semente/backends/adk/` per §4.2; `semente-agents[adk]` extra.
- **Exit:** `engine: adk` runs echo domain + pasto-legal golden tests;
  state-diff parity proven.

### Phase J — pi backend (2–3 wk, spike-gated)
- 2–3 day spike (§4.3 gate) → tool-bridge generator + RPC client +
  JSON event parser + tool server endpoint + `JsonOutputAgent`.
- **Exit:** `engine: pi` runs the echo domain (experimental tier);
  pasto-legal runs with documented degradations.

### Phase K — Matrix, docs, release (1 wk)
- CI matrix: golden scripted conversations × installed engines; capability
  degradation assertions; `check_domain_purity.sh` extended to also fail on
  agno imports outside `backends/` in Semente itself.
- Docs: "Engines" page (matrix, `engine:` config, tiers), Domain API page
  updated. Release **0.3.0**.

**Total ≈ 9–11 weeks part-time. MVP = agno + ADK (F–H + I + K) ≈ 6.5–8 weeks.**

---

## 6. Parity harness (the "seamless" guarantee)

Golden tests = scripted conversations with **mocked model responses** (each
backend adapter fakes the same model turns), asserting identical:
session-state trajectories, feedback-branch decisions, remediation
behavior, tool-call sequences, and output media. Run per engine in CI
(`SEMENTE_ENGINE=agno|adk|pi` matrix). This is what actually earns the word
"seamless" — not the import structure, the tests.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Orchestrator rewrite drifts from Agno semantics (history, nested outputs) | Phase G keeps Agno agents; 1:1 `StepInput/StepOutput` shapes; golden tests gate every phase |
| ADK state-diff sync loses a mutation | Pre-seed + post-merge diff assertions in parity tests; tools mutate only via `tool_context` (ADK-tracked) |
| ADK `output_schema`+tools model limitation | Our schema agents are tool-free (verified); CI asserts it |
| pi tool-bridge latency/failure | Spike gate first; tool server has timeouts + fallback text result; experimental tier, off by default |
| Agno 2.6.6 → 3.x churn | After Phase H, blast radius = `backends/agno/` only |
| Double session ownership confusion | Semente store is **canonical and only**; engine-side sessions are disabled/ignored (Agno `session_id` unused; ADK per-turn InMemory service; pi `--no-session`) |
| Audio-in on backends without STT | Input step's transcription moves to a Semento-owned genai-direct path (engine-free), used by all engines uniformly |
| JSONL framing bug in pi client (U+2028) | Dedicated framing unit test; hand-rolled line splitter over `recv` buffers |

## 8. Support tiers (honest)

| Engine | Tier | Notes |
|---|---|---|
| agno | **Stable** | reference implementation |
| adk | **Supported** | in-process; Google-ecosystem alignment (Vertex sessions optional) |
| pi | **Experimental** | Node sidecar + tool bridge; spike-gated |

## 9. Decisions needed from you

1. **Order:** ADK second (in-process, proves port fast) → pi third
   (stress test)? Or pi second (it's your daily tool, and it forces the port
   to be honest)?
2. **MVP scope:** agno+ADK first (≈7 wks) with pi gated behind the spike —
   or all three committed up front?
3. **Knowledge storage:** keep pgvector+chroma both (current), or pick one
   now that it's Semente-owned?
4. **AgentOS removal** (Phase H) changes deployment wiring (uvicorn entry
   stays the same; internals change) — OK to proceed without a feature flag?