# Semente — Framework Extraction Plan

**Goal:** Extract the domain-neutral AI-chat engine from `lapig-ufg/pasto-legal`
into **Semente** (org `semente-ai`), a multi-agent chat framework for land use &
agriculture. Pasto Legal becomes the first app grown from the seed.

**Source of truth:** `/home/leandro/Code/pasto-legal` @ `develop` (c7e2c69b, Sep 2026).

---

## 1. Audit: what is framework vs. what is pasture

### 1.1 Domain-neutral → becomes Semente core

| Area | Files | Why it's neutral |
|---|---|---|
| **Workflow engine** | `app/core/step_factory.py`, `app/models/persist_on_success_workflow.py` | Generic Agno step composition, input pre-processing, history block builder |
| **Pipeline steps** | `app/steps/{input,guardrails,output,summarization}.py`, `app/steps/feedback/*` (satisfaction, persona, remediation, persist) | Any chat app needs: input mgmt → guardrails → agent → output → feedback loop |
| **Root workflow** | `app/workflows/pasto_legal_workflow.py` | Onboarding check (terms acceptance) + parallel feedback/summarization + merge is app-agnostic |
| **Generic agents** | `app/agents/{welcoming,persona,feedback,summary}_agent.py` | Terms onboarding, persona tracking, feedback eval — no pasture content |
| **Single agent scaffold** | `app/agents/single_agent.py` | The shell is neutral: model + tools + KB + skills assembled from config; only the tool list and KB are domain |
| **Channel interfaces** | `app/interfaces/whatsapp/*` (router 456L, helpers 438L incl. `[PAUSA]` chunking/debouncing/typing indicator, security, signature verify), `app/interfaces/streamlit/*` | WhatsApp UX machinery has zero domain coupling |
| **Guardrails & hooks** | `app/guardrails/pii_gate.py` (192L), `app/hooks/{pre,tool}_hooks.py` | PII/LGPD masking is generic |
| **i18n prompt loader** | `app/configs/prompts.py` | Already a framework-grade component: YAML `agents.yml/tools.yml/hooks.yml`, `defaults/` fallback with warning-on-miss — reuse as-is |
| **Config** | `app/configs/config.py` (pydantic-settings: env, DB, model providers, S3) | Neutral; `GEE_*` vars move to the domain extra |
| **Database** | `app/database/{agno_db,session}.py`, `app/database/models.py` (`UserTermsAcceptance`, `NegativeFeedback`, `PositiveFeedback`, `AnalysisFeedback`) | All 4 models are app-generic |
| **Schemas** | `app/schemas/{input_manager,workflow_state,user_persona,user_mood}.py` | Neutral |
| **Services** | `app/services/{audio/tts,transcription}.py` | Voice I/O is generic |
| **Skills loading** | Agno `LocalSkills` pattern in `single_agent.py` | Neutral mechanism |
| **Tests (neutral)** | `tests/configs/test_prompts_loader.py`, `tests/ee_scripts/test_pii_*`, `test_text_wall_chunking.py`, `test_persona_calibration.py` | Move with their modules |

### 1.2 Domain-coupled → stays in the Pasto Legal app

| Area | Files |
|---|---|
| Geospatial services | `app/services/geospatial/*` (gee, sicar, pasture_cache, pasture_classification, season_forecast, geometry, image) |
| Domain tools | `app/tools/analysis_tools.py`, `property_tools.py`, `weather_tools.py`, `boletim`/`pdf`/`video` scripts |
| Knowledge base | `app/knowledge/pasto_legal_kb.py` + `docs/knowledge/` (Embrapa/pasture content) |
| Domain prompts | pasture/Embrapa text inside `agents.yml` (loaded via neutral loader) |
| Domain skill | `app/skills/property_analyst_agent/ua-calculator/` |
| Domain schemas | `app/schemas/{property_feature,property_stats}.py` |

### 1.3 Gray zone (decide in Phase 2)

- **Property registration flow** (`start_registration_by_car/coordinate/buffer/url`): the *flow* (property CRUD, user↔property link) is common to every land-use app → promote a `PropertyProvider` interface to core; SICAR/CAR lookup stays a Pasto Legal provider.
- **Weather tools** (`openmeteo`): useful to most ag apps → candidate for a Semente "toolbox" of optional tools.
- **TTS tool wrapper** (`tts_tools.py`): neutral wrapper around the neutral service → core.

---

## 2. Target architecture

```
semente/                          # framework package (pip installable)
├── core/                         # step_factory, PersistOnSuccessWorkflow, input manager
├── steps/                        # input, guardrails, output, summarization, feedback/*
├── workflows/                     # base_semente_workflow (onboarding + agent + feedback/summary merge)
├── agents/                        # welcoming, persona, feedback, summary + build_agent() factory
├── interfaces/
│   ├── whatsapp/                  # router, helpers (chunking/debounce), security
│   └── streamlit/
├── guardrails/                    # pii_gate
├── hooks/
├── services/                      # tts, transcription
├── database/                      # session, agno_db, base models (terms, feedback)
├── schemas/                        # workflow_state, user_persona, user_mood, input_manager
├── prompts/                        # i18n loader + defaults/ (neutral texts only)
└── domain/                         # the seam (see §3)
    ├── base.py                     # DomainSpec protocol/dataclass
    ├── property.py                 # PropertyProvider protocol + base Property CRUD tools
    └── tools.py                    # domain tool packaging helpers
```

```
my-semente-app/                    # an app grown from the seed
├── domain/
│   ├── __init__.py                # exposes DomainSpec: tools, kb, skills, property_provider
│   ├── tools.py                    # e.g. pasture analysis, weather
│   ├── services/                   # e.g. gee.py, sicar.py
│   ├── knowledge/                   # markdown KB + vector index wiring
│   └── prompts/                      # localized agents.yml/tools.yml (domain instructions)
├── semente.yaml                   # app manifest (see §3)
├── .env                           # infra secrets (channels, DB, models, S3)
├── Dockerfile / compose.yaml
└── app.py                         # from semente import build_app; build_app(DomainSpec, manifest)
```

**Pasto Legal** = an app repo: keeps everything in §1.2, adds `domain/` + manifest,
imports `semente` as a dependency. Its operational behavior must not change (Phase 4 parity).

---

## 3. The domain seam (the one new abstraction)

One seam, config-driven — no plugin marketplace, no registry framework:

```python
# semente/domain/base.py
@dataclass
class DomainSpec:
    name: str                        # "Pasto Legal"
    tools: list                      # Agno tools for the single agent
    knowledge: Knowledge | None      # vector KB, or None
    skills: Skills | None
    property_provider: PropertyProvider | None   # None = no property registration
    domain_schemas: list[Type[BaseModel]]        # e.g. PropertyFeature, PropertyStats
```

```yaml
# semente.yaml — app manifest
name: pasto-legal
language: pt-BR                     # picks prompts/<lang>/ over defaults/
models:
  primary: {provider: google, id: gemini-3.5-flash-lite}
  fallback: {provider: ollama, id: gemma4:31b-cloud}
channels: [whatsapp, streamlit]
features:
  property_registration: true
  tts: true
  feedback_workflow: true
  summarization: true
  pii_guardrail: true
domain_module: domain               # import path to DomainSpec
```

`semente.build_app(DomainSpec, manifest)` assembles the workflow, steps, agents and
interfaces exactly as `pasto_legal_workflow.py` does today. `main.py`, the Streamlit
entry and the WhatsApp router read from the manifest instead of hardcoded imports.

**Deliberately NOT built** (YAGNI): multi-agent router/team support in core (Pasto Legal
itself dropped the router for a single agent — extract what exists), tool marketplace,
per-domain database schemas beyond property, auth/multi-tenant (single-app deployments).

---

## 4. Phases

### Phase 0 — Groundwork (½ day)
- Create GitHub org **`semente-ai`** (verify `semente-ai.github.io` is free by creating it).
- Repo `semente-ai/semente`, branch `develop` as default, ISSUE templates, CI skeleton.
- Decide license: **GPLv3** (mandated — pasto-legal is GPLv3, Semente is a derivative).
  Add header attribution note: "Semente was extracted from Pasto Legal (LAPIG/UFG)".
- Draft brand one-pager: logo seed motif, tagline *"Multi-agent AI chat for land use."*

**Exit:** org + empty repo with LICENSE, README stub, CI running a no-op.

### Phase 1 — Boundary freeze (2–3 days, code-light)
- Turn §1 audit into a PR-sized checklist: every file tagged CORE / DOMAIN / GRAY / DELETE.
- Delete dead weight before extraction (candidates: `.cache.sqlite` committed?, `.ipynb_checkpoints/`, `users_db.json`, `agent/`, `api/` top-level dirs — audit their use first).
- Tag pasto-legal `pre-semente-extraction` as regression reference.

**Exit:** the mapping table is a reviewed `MIGRATION.md` in the Semente repo.

### Phase 2 — Core extraction (2–3 weeks)
- Copy neutral modules into `semente/` package (§1.1), renaming `pasto_legal_*` → `semente_*`
  (`PersistOnSuccessWorkflow`, base workflow, KB wiring pattern).
- Split `pyproject.toml` deps:
  - core: agno, fastapi, uvicorn, sqlalchemy, pydantic, redis, google-genai, ollama, streamlit, pydub, reportlab (only if output step uses it — else move), s3fs, python-dotenv
  - extras: `semente[gee]` (earthengine-api, duckdb, geopandas, geemap, xarray, xee, zarr…), `semente[knowledge]` (chromadb or pgvector — pick ONE, drop the other), `semente[whatsapp]` if heavier deps appear.
- Deps cleanup: audit `pymongo`, `qdrant-client`, `lancedb`, `tantivy`, `pylance`, `a2a-sdk`, `bs4` — several are likely unused leftovers (verify, then drop; smaller surface = easier adoption).
- Implement `DomainSpec` + `PropertyProvider` + `build_app()`.
- Move neutral tests; they must pass with zero domain imports (import-linter rule or CI grep: `semente/` must not import `gee|sicar|pasture`).
- `pip install -e` from a local path into a scratch app to prove the package works outside pasto-legal.

**Exit:** Semente package installs and runs a **echo/demo domain** (one trivial tool, no KB) on Streamlit.

### Phase 3 — Config-driven assembly (1 week) ✅ DONE
- [x] `semente.yaml` manifest loading (pydantic-settings, same `.env` pattern as today).
- [x] Language handling: prompts loader already supports localized files — make `language:` select `prompts/<lang>/` with `defaults/` fallback (existing warning mechanism).
- [x] `build_app()` wires channels, features toggles (TTS off → tool not registered; property_registration off → CRUD tools absent).

**Exit:** demo app configurable via manifest only; zero code edits to flip features.

### Phase 4 — Pasto Legal parity (2 weeks, the critical phase) ✅ DONE (code side)
- [x] Refactor `lapig-ufg/pasto-legal` to consume `semente` (git dep first, PyPI later): move §1.2 into `domain/`, delete moved code, keep git history via plain moves + attribution note.
- [x] Port WhatsApp production path: `router.py` + `helpers.py` chunking/debouncing against Semente's workflow API.
- [x] Regression: run pasto-legal's own test suite against the Semente-backed build (imports updated mechanically; GEE-dependent tests need real credentials).
- [ ] Live smoke on Streamlit + ngrok WhatsApp (needs user's credentials).
- [ ] Behavior diff on scripted conversation set (needs live run).
- [ ] Keep pasto-legal on Agno 2.6.6 pin until parity is proven.

**Exit:** pasto-legal develop green on Semente; behavior diffs = zero on the scripted set.

### Phase 5 — Second seed proof (1 week)
- Build a minimal second domain from the template in ≤ 1 day of work (suggested: a
  **deforestation/land-use Q&A** chat using MapBiomas collections, or a **climate/weather
  advisory** chat reusing the weather tools — both reuse LAPIG assets).
- Every friction point found while doing it becomes a Semente issue. This is the real
  genericity test; don't publish without it.

**Exit:** second app demoed; friction issues filed and triaged.

### Phase 6 — Release & community (1 week)
- `semente-ai/semente-template` — app template repo (from the Phase 5 app, domain gutted).
- Docs at **semente-ai.github.io** (MkDocs): quickstart (3 steps to a new domain), manifest reference, DomainSpec API, "how Pasto Legal was built" as the showcase.
- PyPI: `semente-agents` 0.1.0 (reserve `semente-agents` + `semente-framework` names early in Phase 0).
- Announce: LAPIG blog + the iCS/Google.org network; Pasto Legal README links "Powered by Semente".

**Exit:** `pip install semente-agents`, docs live, template cloneable.

**Total: ~6–7 weeks part-time with a small team (2–3 devs).**

---

## 5. Key decisions & risks

| Decision | Choice | Rationale |
|---|---|---|
| Agent engine | Keep **Agno** (pinned 2.6.6) | Semente is an opinionated app framework, not a competitor to Agno. Don't rewrite the engine. Risk: Agno API churn → mitigation: thin wrappers in `semente.core` are the only files touching Agno internals |
| Repo topology | Semente repo + app repos consuming it | pasto-legal is live in testing; extract without breaking it |
| License | GPLv3, with prominent Pasto Legal/LAPIG attribution | Copyleft obligation from upstream; matches open-science mission. Note to adopters in README |
| Vector DB | Pick one (recommend pgvector — it's the prod path) | Supporting chromadb+pgvector both is maintenance cost with no user |
| Property model | `PropertyProvider` interface in core, SICAR impl in pasto-legal | Property registration is the one shared concept across ALL land-use apps |
| Multi-tenant/SaaS | Not now | Each app is single-purpose deployment; YAGNI until a second app needs it |

**Risks:**
1. **Parity regressions in Pasto Legal** (highest) — mitigate with Phase 4's scripted-conversation diff and by keeping pasto-legal's release cadence frozen during the swap.
2. **Agno breaking changes** — pin, wrap, and upgrade deliberately.
3. **Extraction scope creep** — the Phase 5 second app is the forcing function; anything a second app doesn't need doesn't ship in core.
4. **Prompts quality is invisible work** — the i18n loader is the framework's gem; document the localization story prominently, it's a differentiator.
5. **GEE as adoption barrier** — GEE must be an extra and fully optional (Phase 5 weather app proves a GEE-free domain works).

---

## 6. Immediate next actions (this week)

1. Create `semente-ai` org on GitHub + reserve PyPI names `semente-agents`, `semente-framework`.
2. Phase 1 tagging session on this repo — produce `MIGRATION.md` (I can generate the first draft from the §1 audit).
3. Open Semente issues for the GRAY-zone decisions (`PropertyProvider` scope, vector DB choice, unused-deps audit).
4. Confirm domain name plan: `semente-ai.github.io` now; evaluate `semente-ai.org` later (needs a manual availability check).