# MIGRATION.md — Pasto Legal → Semente extraction map

Source: `/home/leandro/Code/pasto-legal` @ `develop` (c7e2c69b, Sep 2026).
Legend: **CORE** = move to `semente/` package · **DOMAIN** = stays in Pasto Legal app · **GRAY** = decide in Phase 2 · **DELETE** = remove.

---

## 1. CORE — domain-neutral, moves to `semente/`

| File | Notes |
|---|---|
| `app/core/step_factory.py` | Generic Agno step composition + history block builder. Rename `_agent_executor_factory` → public `agent_executor_factory`. |
| `app/models/persist_on_success_workflow.py` | `PersistOnSuccessWorkflow` — generic. |
| `app/steps/input_step.py` | Generic input pre-processing. |
| `app/steps/guardrails_step.py` | Generic guardrail step. |
| `app/steps/output_step.py` | Generic output/final-output step (TTS hook lives here). |
| `app/steps/summarization_step.py` | Generic running-summary step. |
| `app/steps/feedback/satisfaction.py` | Generic 1–5 satisfaction eval. |
| `app/steps/feedback/persona.py` | Generic persona tracking. |
| `app/steps/feedback/remediation.py` | Generic remediation + intent-router step name. |
| `app/steps/feedback/persist_feedback.py` | Generic feedback persistence. |
| `app/workflows/feedback_workflow.py` | Generic feedback sub-workflow. |
| `app/workflows/pasto_legal_workflow.py` | → `semente/workflows/base_workflow.py`. Onboarding check + parallel feedback/summarization + merge. Rename `pasto_legal_workflow` → `semente_workflow`. |
| `app/agents/welcoming_agent.py` | Terms onboarding — generic. |
| `app/agents/persona_agent.py` | Generic. |
| `app/agents/feedback_agent.py` | Generic. |
| `app/agents/summary_agent.py` | Generic. |
| `app/agents/media_agents.py` | Image-description + audio-transcription agents — generic, config-driven. |
| `app/agents/single_agent.py` | → `semente/agents/build_agent.py`. Shell is neutral; tool list + KB + skills come from `DomainSpec`. |
| `app/interfaces/whatsapp/router.py` | Generic WhatsApp webhook router (chunking `[PAUSA]`, debouncing, typing indicator). |
| `app/interfaces/whatsapp/helpers.py` | Generic WhatsApp helpers. |
| `app/interfaces/whatsapp/security.py` | Generic signature verification. |
| `app/interfaces/whatsapp/whatsapp.py` | Generic `Whatsapp` interface wrapper. |
| `app/interfaces/streamlit/streamlit_webapp.py` | Generic Streamlit entry (parameterize workflow import). |
| `app/interfaces/streamlit/debug_panel.py` | Generic debug panel (parameterize agent/tool imports). |
| `app/interfaces/streamlit/debug_helpers.py` | Generic. |
| `app/guardrails/pii_gate.py` | Generic PII/LGPD masking. |
| `app/hooks/pre_hooks.py` | **Split**: `validate_phone_authorization` + `validate_terms_acceptance` → CORE; `validate_car_selection` → DOMAIN (CAR-specific). |
| `app/hooks/tool_hooks.py` | Generic tool-hook texts. |
| `app/configs/config.py` | Generic pydantic-settings. **Move `GEE_*` vars to the `[gee]` extra** (domain). |
| `app/configs/prompts.py` | Generic i18n YAML loader — reuse as-is. |
| `app/configs/logging_config.py` | Generic. |
| `app/database/agno_db.py` | Generic Agno DB wiring. |
| `app/database/session.py` | Generic SQLAlchemy session. |
| `app/database/models.py` | All 4 models generic (`UserTermsAcceptance`, `NegativeFeedback`, `PositiveFeedback`, `AnalysisFeedback`). |
| `app/schemas/input_manager.py` | Generic. |
| `app/schemas/workflow_state.py` | Generic. |
| `app/schemas/user_persona.py` | Generic. |
| `app/schemas/user_mood.py` | Generic. |
| `app/services/audio/tts.py` | Generic TTS. |
| `app/services/transcription.py` | Generic transcription. |
| `app/tools/tts_tools.py` | Generic TTS shim. |
| `app/tools/version_tools.py` | Generic release-notes reader (text via prompts). |
| `app/tools/onboarding_tools.py` | Generic terms-acceptance tool. |
| `app/tools/feedback_tools.py` | Generic feedback persistence (PII masking included). |
| `app/tools/persona_tools.py` | Generic persona tools. |
| `app/main.py` | → `semente/build.py::build_app()` — assembles AgentOS + interfaces from manifest. |
| `app/configs/prompts/defaults/*.yml` | Neutral texts only (strip pasture/Embrapa content → domain `agents.yml`). |
| `tests/configs/test_prompts_loader.py` | Move with loader. |
| `tests/ee_scripts/test_pii_gate.py`, `test_pii_compliance.py` | Move with guardrail. |
| `tests/ee_scripts/test_text_wall_chunking.py` | Move with WhatsApp helpers. |
| `tests/ee_scripts/test_persona_calibration.py` | Move with persona step. |

## 2. DOMAIN — stays in Pasto Legal app

| File | Notes |
|---|---|
| `app/services/geospatial/gee.py` (1293L) | Earth Engine — the pasture moat. |
| `app/services/geospatial/sicar.py` (400L) | SICAR/CAR registry. |
| `app/services/geospatial/pasture_cache.py` | Pasture cache. |
| `app/services/geospatial/pasture_classification.py` | Pasture classification. |
| `app/services/geospatial/season_forecast.py` | Seasonal onset/end rasters. |
| `app/tools/analysis_tools.py` (539L) | Pasture analysis tools. |
| `app/tools/property_tools.py` (563L) | Property CRUD (SICAR/CAR + buffer/coordinate/URL). |
| `app/tools/weather_tools.py` (330L) | Weather (openmeteo). |
| `app/knowledge/pasto_legal_kb.py` + `docs/knowledge/*` | Embrapa/pasture KB. |
| `app/schemas/property_feature.py` | Property feature schema. |
| `app/schemas/property_stats.py` | Pasture stats schemas. |
| `app/utils/feature_utils.py` | Property feature lookup. |
| `app/utils/mock_development.py` | Dev mock for property tools. |
| `app/skills/property_analyst_agent/ua-calculator/` | UA calculator skill. |
| `app/configs/prompts/agents.yml`, `tools.yml`, `hooks.yml` (pt-BR) | Domain/localized texts. |
| `app/services/boletim_scripts.py`, `pdf_scripts.py` | Pasture bulletin/PDF. |
| `docs/release_notes/*`, `docs/workflow-diagrams.md` | Pasto Legal docs. |

## 3. GRAY — decide in Phase 2

| File | Question |
|---|---|
| `app/services/geospatial/geometry.py` | Generic geo ops (UTM zone, buffer) but imports `property_feature` schema. → Promote a `PropertyProvider` interface to core; keep impl in domain. |
| `app/services/geospatial/image.py` | Generic PIL corner-label drawing. → Promote to core if a second app needs map labels; else keep in domain. |
| `app/services/video.py` | Generic GIF→MP4. → Core candidate (WhatsApp video is channel-generic). |
| `app/tools/weather_tools.py` | Useful to most ag apps. → Candidate for a Semente optional toolbox. |
| Property registration flow | The *flow* (CRUD + user↔property link) is common to all land-use apps → `PropertyProvider` in core; SICAR impl stays domain. |

## 4. DELETE

| Path | Reason |
|---|---|
| `agent/` | Only `__pycache__` — stale refactor leftover. |
| `api/` | Only `__pycache__` — stale refactor leftover. |
| `.ipynb_checkpoints/` | Jupyter junk. |
| `users_db.json` | Dev artifact. |
| `tmp/`, `logs/` | Empty. |
| `.cache.sqlite` | Committed cache — should be gitignored. |
| `global-pasture-watch-f46d09d13b4e.json` | **SECURITY: GEE service-account private key committed to repo.** Rotate the key, remove from history, gitignore. |
| `.env` | **SECURITY: committed env file (995B, likely secrets).** Remove from history, gitignore. |

## 5. Dependency split (`pyproject.toml`)

**Core:** agno, fastapi, uvicorn, sqlalchemy, pydantic, pydantic-settings, redis, google-genai, ollama, streamlit, pydub, s3fs, python-dotenv, httpx, jinja2, rich, reportlab (only if output step needs it — verify), svglib (only for PDF — verify).

**Extras:**
- `semente[gee]`: earthengine-api, duckdb, geopandas, geemap, xarray, xee, zarr, affine, numpy, pyproj, shapely, PIL.
- `semente[knowledge]`: **pick one** — pgvector (prod path) or chromadb (dev). Drop the other.
- `semente[weather]`: openmeteo-requests, requests-cache, retry-requests.

**Audit for removal (likely unused):** pymongo, qdrant-client, lancedb, tantivy, pylance, a2a-sdk, bs4, fastembed, openai (if only Gemini/Ollama used), scikit-learn (dev group).

## 6. Renames

| Old | New |
|---|---|
| `pasto_legal_workflow` | `semente_workflow` |
| `PersistOnSuccessWorkflow` | keep name (already generic) |
| `pasto_legal_kb` | `domain_kb` (in app) |
| `single_agent` | `build_agent(domain_spec)` |
| `app.main` | `semente.build_app(domain_spec, manifest)` |
