# Engine Abstraction Plan — decoupling domains from Agno

**Goal:** the Pasto Legal domain (and any Semente app) must have **zero imports
of Agno**. Semente becomes the only module that imports the agent framework.
Swapping Agno for another engine later would touch Semente internals only —
domains untouched.

**Source of truth:** `/home/leandro/Code/pasto-legal/domain/` @ Phase 4 state.

> **Status:** Level 1 (Phase B) ✅ implemented — the domain is agno-import-free.
> Level 2 (Phase C, native types + adapters) is planned but not started.

---

## 1. Coupling inventory

Exactly **8 Agno concepts, 14 files, ~40 import lines**. Nothing else leaks.

| # | Concept | Agno import | Where in the domain | How deeply used |
|---|---|---|---|---|
| 1 | **Logging** | `agno.utils.log` (`log_debug/info/warning/error`) | 11 files (all geospatial services, tools, KB, agent) | Trivial — pure functions |
| 2 | **RunContext** | `agno.run.RunContext` | 6 files (agent, tools, utils) | Type hint + attribute access: `session_state`, `user_id`, `messages` |
| 3 | **Tool decorator** | `agno.tools.tool` (`description=`, `tool_hooks=`) | 3 tool files | Decorator only |
| 4 | **ToolResult** | `agno.tools.function.ToolResult` (`content`, `images`, `videos`, `files`) | 3 tool files | Dataclass constructor |
| 5 | **Media types** | `agno.media.{Image, Video, File}` | 2 tool files | Dataclass constructors: `content`, `mime_type`, `format`, `filepath` |
| 6 | **Knowledge** | `agno.knowledge.*`, `agno.vectordb.{PgVector, ChromaDb}` | 1 file (`pasto_legal_kb.py`, 319L) | The entire KB construction — but the logic is generic |
| 7 | **Skills** | `agno.skills.{Skills, LocalSkills, SkillValidationError}` | 1 file (`domain/__init__.py`) | Factory call |
| 8 | **CalculatorTools** | `agno.tools.calculator.CalculatorTools` | 1 file (`agent.py`) | Toolkit instance |

The rest of the domain (schemas, geospatial services, boletim/PDF, mocks) is
pure Python + domain libs — **already agno-free except for logging**.

---

## 2. Strategy — three levels, take two

| Level | What | Cost | Verdict |
|---|---|---|---|
| **1 — Alias/re-export** | `semente` imports agno types and re-exports them under stable names. Domain imports only semente. Engine swap later still breaks domains (types pass through). | ~2 days | Necessary, not sufficient |
| **2 — Native types + adapters** ★ | Semente defines its own `Context` (Protocol), `ToolResult`, media dataclasses; converts at the boundary. Factories (`build_knowledge`, `load_skills`) hide engine objects. All agno imports concentrate in `semente/adapters/agno/`. | ~2–3 weeks | **Recommended** |
| **3 — Full engine abstraction** | Also abstract workflow, steps, agents, sessions, db — semente as a meta-framework over any engine. | Months, high risk | **Rejected** — see §7 |

Level 2 is the payoff point: domains hold only semente-native or opaque objects;
the engine is an implementation detail of the framework.

---

## 3. Target Domain API (what domains import after this)

```python
from semente import tool, ToolResult, Image, Video, File, Audio
from semente.context import Context as RunContext          # Protocol, see §4.2
from semente.logging import log_debug, log_info, log_warning, log_error
from semente.knowledge import build_knowledge
from semente.skills import load_skills
from semente.tools import Calculator
from semente.domain import DomainSpec
```

### Before / after — a tool (the only diff is the import source)

```python
# BEFORE (Phase 4 state)                          # AFTER
from agno.tools import tool                       from semente import tool, ToolResult, Image
from agno.tools.function import ToolResult        from semente.context import Context as RunContext
from agno.media import Image
from agno.run import RunContext

@tool(description=get_tool_description(...))      @tool(description=get_tool_description(...))
def get_temperature_forecast(                      def get_temperature_forecast(
    run_context: RunContext,                          run_context: RunContext,
) -> ToolResult:                                  ) -> ToolResult:
    ...                                                ...
    return ToolResult(content=txt,                return ToolResult(content=txt,
        images=[Image(content=buf.getvalue())])        images=[Image(content=buf.getvalue())])
```

### Before / after — the knowledge base (shrinks 319L → ~10L)

```python
# BEFORE: pasto_legal_kb.py builds the whole Agno KB by hand
# (embedder, chunking, PgVector/ChromaDb, hash sync — 319 lines)

# AFTER: domain/knowledge/__init__.py
from semente.knowledge import build_knowledge

knowledge = build_knowledge(docs_dir="docs/knowledge")
```
The generic machinery (markdown reader, hash-based sync, embedder choice,
pgvector/chroma fallback) is absorbed **into Semente** — it was never
pasture-specific.

### Before / after — skills & calculator

```python
# BEFORE (domain/__init__.py)                       # AFTER
from agno.skills import (LocalSkills,                from semente.skills import load_skills
    Skills, SkillValidationError)                   from semente.tools import Calculator
try:                                                 from semente.domain import DomainSpec
    skills = Skills(loaders=[LocalSkills("domain/skills/..."))
except SkillValidationError:
    skills = None                                    skills = load_skills("domain/skills/property_analyst_agent")
```

---

## 4. The seams in detail

### 4.1 `semente.logging` — logging (8 of 14 files)

Delegate to Agno's loggers internally (keeps the workflow log integration and
the rotating error file handler). Public surface: `log_debug, log_info,
log_warning, log_error` — plain functions.

```python
# semente/logging.py  (in adapters/agno/)
from agno.utils.log import log_debug, log_error, log_info, log_warning  # re-export
__all__ = ["log_debug", "log_info", "log_warning", "log_error"]
```
Migration: pure sed across 11 files. **Engine-swap upgrade path:** replace the
re-export with stdlib `logging` adapters.

### 4.2 `semente.context` — RunContext as a structural Protocol

No wrapping at runtime. Agno's `RunContext` is passed through untouched; the
domain type-hints against a Protocol it structurally satisfies (duck typing —
zero conversion cost).

```python
# semente/context.py
from typing import Any, Protocol

class Context(Protocol):
    """What a domain tool may access. The engine's RunContext satisfies this."""
    user_id: str | None
    session_id: str | None
    session_state: dict[str, Any]
    messages: Any  # conversation history (engine-shaped; read-only from tools)
```
The Protocol declares **only what the domain actually uses** (verified by
grep): `session_state`, `user_id`, `messages`, `session_id`. The migration sed
`from agno.run import RunContext` → `from semente.context import Context as
RunContext` keeps every signature in the domain unchanged.

**Risk note:** if the domain ever used `isinstance(x, RunContext)` this breaks
— verified it does not. CI guard (§9) keeps it that way.

### 4.3 `semente.tools` — tool decorator + native ToolResult/media

The most delicate seam. Two-step rollout:

**Step C1a (safe):** `semente.tool` delegates straight to Agno's decorator,
so decorated functions are genuine agno tools — no signature risk.

```python
# semente/tools/api.py
def tool(description: str | None = None, tool_hooks: list | None = None, **kw):
    from agno.adapters import agno_tool            # adapters/agno/
    return agno_tool(description=description, tool_hooks=tool_hooks, **kw)
```

**Step C1b (native results):** define semente-native dataclasses and convert
inside a decorator wrapper, preserving the function signature
(`functools.wraps` + explicit `__signature__` re-export, tested against
Agno's introspection — Agno injects `run_context` by inspecting parameters).

```python
# semente/tools/types.py (agno-free)
@dataclass class Image:  filepath=None; content: bytes|None=None; mime_type=None; format=None
@dataclass class Video:  filepath=None; content: bytes|None=None; mime_type=None; format=None
@dataclass class File:   filepath=None; content: bytes|None=None; mime_type=None; name=None
@dataclass class Audio:  filepath=None; content: bytes|None=None; mime_type=None; transcript=None
@dataclass class ToolResult:
    content: str|None=None; images: list|None=None; audios: list|None=None
    videos: list|None=None; files: list|None=None
```
```python
# adapters/agno/tools.py — the ONLY place that imports agno.tools.function
def to_engine(result):   # semente ToolResult/media → agno ToolResult/media, field by field
    ...
```
A tool may return `str`, `dict`, or a semente `ToolResult`; the wrapper
normalizes. Field-fidelity is unit-tested per media type (content, mime_type,
`format` on Video — used by `generate_biomass_video`; `transcript` on Audio).

### 4.4 `semente.knowledge` — absorb the KB module

`pasto_legal_kb.py` is 95% generic: markdown glob, content-hash sync, chunking,
Gemini embedder (reuses `GOOGLE_API_KEY`), PgVector-when-configured /
ChromaDb-when-dev fallback, `synchronize()`. Only `_kb_dir` is domain-specific.

```python
# semente/knowledge/__init__.py (public, agno-free)
def build_knowledge(docs_dir, *, language: str = "pt", chunk_size=..., sync=True) -> Knowledge: ...
def synchronize(kb, docs_dir) -> bool: ...
```
Implementation lives in `semente/knowledge/_impl.py` + `adapters/agno/` (the
agno Knowledge/embedder/vectordb construction). Config knobs the domain needs
today are exposed as parameters — nothing more (YAGNI).

### 4.5 `semente.skills` — factory

```python
def load_skills(path) -> Skills | None:
    """Loads markdown skills from a directory; None if invalid/absent."""
```
Absorbs the try/except `SkillValidationError` dance from every app's
`domain/__init__.py`.

### 4.6 `semente.tools.Calculator`

Wrap Agno's `CalculatorTools` (Phase B). Optional later: a ~30-line native
calculator (add/sub/mul/div/pow/sqrt) if we want the tool layer fully
engine-free. Keep the wrapper until a second engine exists — one
implementation, no interface churn (ponytail rule).

### 4.7 DomainSpec — opaque fields

`DomainSpec.tools` holds semente-decorated tools, `.knowledge`/`.skills` hold
factory outputs, `.instructions` a `Callable[[Context], str]`. The framework's
`build_agent` adapts to Agno internally (it already does the assembly). The
domain never sees an agno type — including in type hints.

---

## 5. Adapter architecture — where Agno imports live after this

```
semente/
├── adapters/agno/          # ALL engine-facing construction concentrates here
│   ├── tools.py            # agno tool decorator, ToolResult/media conversion
│   ├── knowledge.py        # agno Knowledge/embedder/vectordb building
│   ├── skills.py           # agno Skills/LocalSkills
│   └── logging.py          # agno log re-export
├── context.py              # agno-free Protocol
├── logging.py              # re-exports adapters.agno.logging
├── tools/                  # tool decorator + native types (agno-free public)
├── knowledge/              # build_knowledge public API (impl delegates)
├── skills.py               # load_skills (delegates)
└── ...core...              # workflow/steps/agents/interfaces — freely use agno
```

Rule: **core engine modules may import agno directly** (they *are* the engine
binding). Public API modules and anything a domain can import go through
`adapters/agno/` or are agno-free. When Agno 3.0 breaks APIs, one directory
absorbs the damage.

---

## 6. Phases

### Phase A — Contract freeze (½ day) ✅ inventory done
- Freeze the §3 API surface (names + signatures) as this document.
- Add `scripts/check_domain_purity.sh` (§9) — red on the current domain.

**Exit:** the script exists and fails (14 files listed).

### Phase B — Alias layer, migrate the domain (2–3 days)
- Create `semente/context.py` (Protocol), `semente/logging.py`, `semente/tools`
  (delegating `tool` + `Calculator`), `semente/skills.py`, `semente/knowledge`
  (temporary: expose the agno Knowledge class re-exported so the KB file
  compiles unchanged).
- Mechanical sed over the 14 domain files (mapping table below); run
  py_compile + import smoke with GEE mocked.

| `from agno...` | becomes |
|---|---|
| `agno.run import RunContext` | `semente.context import Context as RunContext` |
| `agno.tools import tool` | `semente import tool` |
| `agno.tools.function import ToolResult` | `semente import ToolResult` |
| `agno.media import Image/Video/File/Audio` | `semente import Image/Video/File/Audio` |
| `agno.utils.log import ...` | `semente.logging import ...` |
| `agno.skills import ...` | `semente.skills import load_skills` |
| `agno.tools.calculator import CalculatorTools` | `semente.tools import Calculator` |

**Exit:** `check_domain_purity.sh` green; workflow builds; echo domain + pasto
legal parity test green. *(Domain has zero agno imports — Level 1 done.)*

### Phase C — Native types + adapters (2 weeks, the real abstraction)
1. **C1** — native `ToolResult`/media dataclasses + signature-preserving
   wrapper + `to_engine()` conversion; unit tests: each media field round-trips
   (incl. `Video(... format="mp4")`, `Audio(transcript=...)`); integration test:
   an echo-image tool flows through the real workflow and the WhatsApp router
   receives the agno-shaped result.
2. **C2** — Context Protocol lands for real (already in place from B; verify
   with mypy on the domain).
3. **C3** — absorb the KB: move the generic machinery to
   `semente/knowledge/`; `pasto_legal_kb.py` → 10-line factory call. Test
   parity: hash-sync behavior, pgvector branch (requires PGVECTOR_* test
   instance) and chroma branch.
4. **C4** — `load_skills` + `Calculator` final form; update DomainSpec
   docstrings/annotations to semente-native types.

**Exit:** domain holds only semente-native/opaque objects; all tests green.

### Phase D — Parity & cleanup (2–3 days)
- Full pasto-legal parity run (GEE-mocked import + live smoke on your
  credentials); scripted-conversation diff.
- Update `tests/` agno imports (2 files today: prompts loader, boletim tool).
- Update docs: new "Domain API" page; ENGINE_ABSTRACTION linked from the guide.

### Phase E — Enforcement & release (1 day)
- CI gate: domain-purity check + **import-linter** contract: forbidden
  `domain → agno`; `semente.*` public modules → `semente.adapters.agno` only.
- Version bump `0.2.0`; changelog entry.

**Total: ~3–4 weeks part-time.** (Level 1 alone is days — the plan front-loads
it so you're agno-import-free quickly, then deepens the seam.)

---

## 7. What we deliberately do NOT abstract (and why)

- **Workflow/steps/agents/Team internals** — Semente *is* the opinionated
  engine; hiding it behind a meta-interface recreates the framework-agnosticism
  problem Agno itself already solved for us.
- **AgentOS / WhatsApp `BaseInterface` / FastAPI wiring** — channel plumbing,
  core concern.
- **Session/db/models (`SqliteDb`, `PostgresDb`, `Gemini`, `Ollama`)** — already
  behind `semente.configs.config.build_model` and the DB factory; domains never
  touch them (verified: zero hits in `domain/`).

Abstraction debt ceiling: if a second engine (LangGraph, ADK, homegrown) is
ever adopted, Phase C's adapters are the only rewrite surface.

---

## 8. Risks & mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Agno injects `run_context` by signature inspection; a wrapper may hide parameters | Tools lose context/state access | C1 keeps `functools.wraps` + explicit `__signature__`; integration test asserts `session_state` write from inside a wrapped tool |
| Media field fidelity lost in conversion (e.g. `Video.format`, `Audio.transcript`) | Broken WhatsApp sends | Field-by-field conversion tests before migration; TTS path (transcript) is already covered by the chunking test |
| Agno RunContext doesn't structurally satisfy the Protocol (renamed attrs) | Mypy errors / runtime AttributeError in domain | Protocol declares only the 4 attrs actually used; smoke test calls a real tool |
| KB absorb changes pgvector/chroma selection | Q&A breaks silently | Port the existing KB tests; add a pgvector-instance CI job (or pin to chroma in CI, pgvector in staging) |
| `agno==2.6.6` API churn on upgrade | Framework-wide breakage | All engine imports funneled to `adapters/agno/` — single blast radius; keep the pin until Phase C done |
| Hooks protocol (`(run_context, function_call, arguments)`) is engine-flavored | Third-party domain hooks couple to engine shape | Document the hook signature as semente's own protocol in `semente/hooks`; hooks live in core today |

---

## 9. CI enforcement

```bash
# scripts/check_domain_purity.sh — fails if any app-domain imports agno
#!/usr/bin/env bash
hits=$(grep -rE "^\s*(from|import)\s+agno" domain/ examples/ 2>/dev/null)
if [ -n "$hits" ]; then echo "✖ agno imports found in domain:"; echo "$hits"; exit 1; fi
echo "✓ domain is engine-free"
```

Plus an **import-linter** contract in CI: `domain` must not depend on `agno`;
`semente` public modules must depend on `semente.adapters.agno` only for
engine types.

---

## 10. Immediate next actions

1. Approve Level 2 scope (or stop at Level 1 for now — it's a valid
   standalone milestone: "no agno imports in domain").
2. Phase B sed migration (I can generate the exact per-file diff).
3. Schedule Phase C1 (ToolResult/media adapters + tests) — the only genuinely
   new engineering in this plan.