# Stack Research

**Domain:** Django REST backend for an AI football scouting platform (serves a React/TanStack Start SPA, runs a ported pandas scoring engine live, integrates LLM APIs, Postgres-backed)
**Researched:** 2026-07-20
**Confidence:** HIGH (Django/DRF/Postgres core, versions verified via PyPI), MEDIUM (LLM interface libraries — fast-moving space), MEDIUM (pandas 3.0 compatibility risk — verified version exists, impact on the specific 15,700-line script is untested)

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Django | 5.2 LTS (5.2.x) | Web framework / ORM | 5.2 is the current LTS with support through ~April 2028 — the longest support runway of any current release. Django 6.0 (latest: 6.0.7) exists and is newer, but it is a non-LTS release with a much shorter support window and requires Python ≥3.12. For a backend intended to become the real production system (not a throwaway demo), LTS is the correct default. Verified: [Django 5.2 release notes](https://docs.djangoproject.com/en/6.0/releases/5.2/), [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/). |
| Django REST Framework (DRF) | 3.17.x (latest: 3.17.1) | REST API layer | This project is CRUD-dominant (Players, Clubs, Transfers, Watchlist, Shortlists, Squad Plans, Recent Activity, Profiles) and needs mature, battle-tested role-based permission handling. DRF's `ModelViewSet` + `router` pattern is still the fastest path to a full CRUD surface, and its ecosystem (`djangorestframework-simplejwt`, `django-filter`, `drf-spectacular`) is 10+ years deep, which matters given this codebase already has **zero test coverage** on the scoring logic (see CONCERNS.md) — you don't want to also be debugging an unfamiliar API framework. Django Ninja is a legitimate, faster, async-first alternative (see Alternatives below) but running two API frameworks side-by-side adds real complexity for no benefit here. |
| PostgreSQL | 16 or 17 | Primary datastore | Explicit project constraint (replaces MongoDB + Supabase). Use whichever major version your hosting target defaults to; both are current and psycopg 3 supports them identically. |
| psycopg | 3.2.x (latest: 3.3.4) | Postgres driver | Psycopg 3 (not psycopg2) is where the project should start — psycopg2 is in maintenance-only mode and receives no new features. Django has supported psycopg 3 since Django 4.2, and Django 5.1+ adds native connection pooling (`CONN_POOL` via `psycopg_pool`) when running psycopg 3, which matters here: the scoring engine will issue many small player/club lookups per request, and pooling avoids per-request connection overhead. Install as `psycopg[binary,pool]`. Verified: [psycopg docs — from psycopg2](https://www.psycopg.org/psycopg3/docs/basic/from_pg2.html), Django docs on `CONN_POOL`. |
| pandas | **pin to `>=2.2,<3.0`** during the port (last pre-3.0 series) | Runs the ported `impact_model_v4.1.py` scoring logic | Pandas 3.0 (released Jan 2026, current: 3.0.3) shipped real breaking changes (Copy-on-Write is now unconditional/no longer a settable option, default string dtype behavior changes, removal of long-deprecated APIs). `impact_model_v4.1.py` is 15,700 lines, untested, and full of defensive/silent-default column handling (per CONCERNS.md) — porting it against a pandas major version it was never written for is a high-risk unforced error. **Pin to the 2.x series for the initial port, get the scoring engine under test, then evaluate a 3.0 upgrade as a separate, deliberate piece of work.** |
| numpy | 2.x (latest: 2.5.1) | Vectorized math for the live-request scoring path | pandas 2.x already requires numpy ≥1.23; numpy 2.5.x is compatible. Numpy is also the right tool (not pandas) for the *live, per-request* part of the scoring service — see "Running the Scoring Engine" below. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| djangorestframework-simplejwt | 5.5.x (latest: 5.5.1) | JWT issuance/auth for DRF | Standard, actively maintained (Jazzband) JWT plugin for DRF. Supports Django 4.2–5.2 today. Use custom claims (`get_token()` override) to embed `role` (scout/analyst/director/admin) directly in the access token so permission checks don't require an extra DB hit per request; still validate role server-side via a custom `permissions.BasePermission`, never trust the claim alone for anything sensitive. |
| Celery | 5.6.x (latest: 5.6.3) | Background task queue | Needed for: (1) LLM calls that must never block a sync request thread (report generation), (2) periodic/batch recompute of the base Player Impact Score across the full ~41,700-row dataset, (3) bulk "score N players against this club" jobs for the AI Shortlist page. Celery is the standard choice here specifically because you need **both** scheduled/periodic jobs (`celery beat`) **and** ad-hoc async jobs (LLM calls) — lighter alternatives (Django-Q2, RQ, Django 6's native tasks framework) cover one or the other well but not both as maturely. |
| redis | 7.x | Celery broker + cache backend | Standard Celery broker; also back `django-redis` as the cache backend so precomputed feature vectors / compatibility scores can be cached between requests instead of recomputed. |
| django-redis | 7.0.x | Django cache backend on Redis | Cache the numpy feature matrices/vectors the live scoring path needs (see below) so a hot player/club pair doesn't re-hit Postgres + re-vectorize every request. |
| django-filter | 26.x (CalVer, latest: 26.1) | Declarative querystring filtering | Player/club search/filter endpoints (position, league, age range, market value range) — pairs directly with DRF's `DjangoFilterBackend`. |
| drf-spectacular | 0.30.x | OpenAPI schema generation | Auto-generates OpenAPI 3 schema from DRF views/serializers; gives the frontend team (and any future API consumers) a real contract instead of hand-written docs. Actively maintained, the de facto DRF choice today (drf-yasg is effectively unmaintained). |
| django-cors-headers | 4.9.x | CORS handling | Required since the API is consumed by a separately-hosted SPA (`pixel-perfect-clone-60729`, TanStack Start). Scope `CORS_ALLOWED_ORIGINS` explicitly; do not use `CORS_ALLOW_ALL_ORIGINS` even in the demo. |
| django-environ | 0.13.x | 12-factor env config | Project constraint calls for Docker/12-factor-friendly config. `django-environ` is the Django-native choice — parses `DATABASE_URL`/`REDIS_URL` directly into Django settings, avoiding hand-rolled `os.environ.get()` scattered through `settings.py`. |
| pydantic-ai | 2.13.x | Provider-agnostic LLM interface | See "LLM Interface" section below — this is the primary recommendation for both structured NL-search parsing and report generation. |
| gunicorn | 23.x | WSGI application server | Standard production WSGI server for Django; pair with `--workers` sized to CPU cores. No need for ASGI/Uvicorn/Daphne for v1 — see "What NOT to Use". |
| django-import-export | 4.x | *Not recommended for the initial bulk load* (listed for completeness) | Good for ongoing admin-mediated import/export UX later; not the right tool for the one-time 41,700-row CSV migration — see CSV migration section. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest + pytest-django | Test runner | Given CONCERNS.md flags **zero test coverage anywhere**, including on the untested 15,700-line scoring logic being ported — start the Django backend with tests from day one, especially scoring-equivalence tests (Python reference output vs ported Django output) and auth/permission tests. |
| factory_boy | Test data factories | Standard pairing with pytest-django for building Player/Club/Transfer fixtures without hand-writing JSON fixtures. |
| ruff | Lint + format | Fast, single-tool replacement for flake8+isort+black; standard default for new Python projects in 2025/2026. |
| django-debug-toolbar | Local dev query profiling | Critical here specifically because of the jsonb + scoring-query performance risk flagged in CONCERNS.md — use it to catch N+1 queries on player list/detail endpoints early. |

## Installation

```bash
# Core
pip install "django~=5.2.0" "djangorestframework~=3.17.0" "psycopg[binary,pool]~=3.3.0"

# Scoring engine port
pip install "pandas>=2.2,<3.0" "numpy~=2.5.0" scikit-learn

# Auth
pip install djangorestframework-simplejwt

# Background jobs / caching
pip install celery redis django-redis

# API surface
pip install django-filter drf-spectacular django-cors-headers

# Config
pip install django-environ

# LLM interface
pip install pydantic-ai

# WSGI server
pip install gunicorn

# Dev/test dependencies
pip install -D pytest pytest-django factory_boy ruff django-debug-toolbar
```

## Running the Scoring Engine (sync view vs Celery vs precomputed batch)

This is the highest-risk architectural decision in the stack, so it's called out explicitly rather than left to the roadmap phase:

**Precompute + store (batch job, not per-request):** The base Player Impact Score (RMM) is a function of a player's own stats plus position/league peer aggregates — it does *not* depend on request-specific parameters. Compute it as part of the CSV import / a nightly `celery beat` periodic task and **store it on the Player row** (or a `PlayerScore` table). Never recompute this per HTTP request.

**On-demand, request-time, but numpy — not pandas — in the hot path:** Compatibility Score (cosine-similarity role-fit) and Financial Fit (TFM) genuinely depend on request parameters (which club, which role, which negotiation inputs), so they can't be fully precomputed. But they should **not** run pandas DataFrame operations over the full dataset per request — that's the CONCERNS.md-flagged performance risk ("Pandas-based scoring on 41,700 records may be slow... no visible caching"). Instead: precompute and cache each player's feature vector (numpy array) once, cache club/role target vectors, and do the actual cosine-similarity comparison as a plain numpy dot-product inside the synchronous DRF view. That keeps single-pair scoring in the low milliseconds and is what makes it a genuinely "live, queryable" service rather than a batch report.

**Celery background task, not sync view:** Anything that (a) scores many players at once (e.g., AI Shortlist ranking a whole league against one club), (b) calls out to an LLM (network latency + provider variability, must not tie up a Gunicorn worker), or (c) re-runs the full-dataset batch recompute after a data import. Use Celery + Redis for these; expose a job-status endpoint or return cached results with a "recomputing" flag rather than blocking the request.

**What NOT to do:** Don't run `impact_model_v4.1.py`'s full-DataFrame batch functions (as currently written, over the entire 41,700-row dataset) inside a synchronous request/response cycle — this is exactly the pattern CONCERNS.md flags as a performance risk, and it will not "feel live" to a scout typing a search query.

## LLM Provider-Agnostic Interface

**Recommendation: `pydantic-ai`** as the primary interface, used for both use cases in scope:

- **NL search parsing (query → structured filters):** This is a structured-extraction problem — pydantic-ai's `Agent[DepsType, OutputType]` pattern lets you define the target filter schema as a Pydantic model and get validated, typed output back regardless of provider. Swapping providers (OpenAI → Anthropic → a cheaper model) is a one-line model-string change, which directly satisfies the "provider-agnostic interface" requirement in PROJECT.md without inventing a custom abstraction.
- **AI-generated report text:** Same `Agent`, just with a plain string/markdown output type instead of a structured schema; same provider-agnostic base.
- pydantic-ai supports OpenAI, Anthropic, Gemini, Groq, Mistral, Cohere, Bedrock, Azure, and others natively, plus a LiteLLM-backed model class for the long tail — so provider choice stays genuinely deferred (per PROJECT.md constraint) rather than hard-coded.

**Structure it as:** a small `llm/` app or module with (1) a `Provider` enum / settings-driven model string, (2) one `Agent` per use case (`search_parser_agent`, `report_writer_agent`) defined once at import time, (3) thin service functions (`parse_search_query(text) -> SearchFilters`, `generate_scout_report(player, context) -> str`) that views/Celery tasks call — nothing in the rest of the codebase should import an OpenAI/Anthropic SDK directly. This is what "provider-agnostic interface" concretely means in Django terms: one seam, everything else talks to the seam.

**Alternative:** `instructor` (3M+ monthly downloads, the most widely used structured-extraction library) if you decide you only need structured extraction and not the agent/tool-calling machinery pydantic-ai brings — it's lighter-weight and wraps the raw provider SDKs directly. Reasonable choice if the report-generation use case turns out to need no more than a plain completion call. `pydantic-ai` is still the better default here because the project needs *both* structured output (search) and general generation (reports) under one interface, and pydantic-ai covers both without adding a second library.

**Do not** hand-roll a custom multi-provider abstraction from scratch (e.g., writing your own `if provider == "openai": ... elif provider == "anthropic": ...` dispatcher) — this is a solved problem in 2025/2026 and reinventing it burns time you don't have against the 4-day soft deadline, while also being the exact kind of untested custom logic this codebase already has too much of (per CONCERNS.md).

## CSV-to-Postgres Data Migration

**Recommendation: custom Django management commands, not `django-import-export` and not raw `pandas.to_sql`.**

Pattern:
```
python manage.py import_players --csv API-Updated-/dataset/Players.csv --dry-run
python manage.py import_players --csv API-Updated-/dataset/Players.csv
```

1. Read the CSV with `pandas.read_csv(..., chunksize=2000)` — reuses the same cleaning/normalization logic already present in `impact_model_v4.1.py` (name normalization, league normalization, position mapping) instead of re-deriving it, which directly addresses the field-mapping-drift risk flagged in CONCERNS.md (`Team_within_selected_timeframe` vs `Team`, `Market_value` vs `Market Value`, position variants, etc.).
2. Validate each chunk (nulls, type coercion, required-field checks) and log/collect failures rather than crashing the whole import — CONCERNS.md explicitly flags that the legacy Mongoose schema required 100+ fields with no defaults, which made the old pipeline brittle; don't repeat that in Django (use nullable/defaulted model fields for anything not truly required).
3. Load each validated chunk with `Model.objects.bulk_create(objs, batch_size=2000, update_conflicts=True, unique_fields=[...], update_fields=[...])`. Django 4.1+'s `update_conflicts` support turns this into a single idempotent upsert statement per chunk — safe to re-run the whole command if the import fails partway or the source CSV is updated, with no manual "did this row already exist" logic. This is a large speed win over `save()`-per-row (real-world reports of 45x+ speedup on comparable CSV sizes) and is well within what 41,700 rows need — no COPY-based staging-table approach is necessary at this scale.
4. Wrap each chunk in `transaction.atomic()` (not one transaction for the whole file), so a failure partway through doesn't force a full restart and partial progress is visible/inspectable.

**When to reach for raw Postgres `COPY` instead:** only if `bulk_create` batching proves too slow in practice (it generally won't at ~42K rows). If needed later, psycopg 3 exposes `cursor.copy()` for high-throughput loads into a staging table, followed by a Django/SQL transform step into final tables — but this bypasses Django validation and should be a deliberate fallback, not the default.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| Django REST Framework | Django Ninja (Pydantic v2, async-first, FastAPI-like ergonomics) | If the project were greenfield with no CRUD/admin-heavy surface and a hard requirement for high-concurrency async endpoints, Ninja would be the stronger pick — less boilerplate, better perf under async load. Not recommended here because DRF's ecosystem maturity (simplejwt, filter, spectacular) and role-permission patterns are a better fit for this project's CRUD breadth, and running two API frameworks side by side (DRF for CRUD, Ninja for scoring/AI endpoints) adds cognitive and operational overhead this timeline can't absorb. |
| DRF alongside Django (same process) | FastAPI as a separate service, calling into Django via internal API or shared DB | Only justified at a scale where the scoring service needs independent deployment/scaling from the CRUD API, or a team wants pure-async FastAPI for the LLM/scoring endpoints specifically. For a single-team, single-deploy backend on a soft 4-day timeline, a second service is unnecessary operational surface — keep it one Django project. |
| psycopg 3 | psycopg2 | Only if pinned to an old Django version (<4.2) or a hosting platform without psycopg3 wheels for your target OS/arch — increasingly rare in 2026. |
| Celery + Redis | Django-Q2 / Django 6's native tasks framework | If the only need were "run this slow thing off the request thread" with no periodic/scheduled jobs, Django-Q2 (DB or Redis backed, less operational overhead than Celery) would be a lighter choice. Rejected here because the project needs both scheduled batch recompute (`celery beat`) and ad-hoc LLM jobs, which Celery covers more maturely than the lighter alternatives. |
| pydantic-ai | LiteLLM (thin unified completion API across 100+ providers) | If the LLM usage were *only* simple text completion with no structured extraction need, LiteLLM alone is a lighter, more minimal dependency. Since NL-search parsing specifically needs typed structured output, pydantic-ai (which also has a LiteLLM-backed model option for exotic providers) covers more of the requirement in one library. |
| pydantic-ai | instructor | If report generation turns out not to need agent/tool machinery, `instructor` is a lighter structured-extraction-only library with a larger install base. Reasonable substitute; not chosen as the primary recommendation only because it doesn't unify the "plain generation" report use case as cleanly. |
| Custom management command + `bulk_create(update_conflicts=True)` | `django-import-export` | Use `django-import-export` later for ongoing, admin-UI-mediated CSV re-imports/exports by non-engineers. Not suited to the initial one-time bulk migration of ~42K rows with custom field-mapping/cleaning logic. |
| Django 5.2 LTS | Django 6.0 | Choose 6.0 only if the team commits to staying current on Django releases and is already targeting Python ≥3.12 everywhere (including CI/hosting) — 6.0 does add a built-in tasks framework and CSP support that are nice-to-haves, but neither is required here since Celery already covers background tasks. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|--------------|
| psycopg2 for a new project | Maintenance-mode only, no new features; psycopg3 is where Django's own connection-pooling improvements (5.1+) land | psycopg 3 (`psycopg[binary,pool]`) |
| pandas 3.0.x for the initial port of `impact_model_v4.1.py` | Real breaking changes (Copy-on-Write now unconditional, string-dtype default changes) landed in the Jan 2026 3.0 release; porting 15,700 lines of untested, defensively-coded pandas logic straight onto a new major version compounds two risks at once | Pin `pandas>=2.2,<3.0` until the ported scoring engine has a test suite, then upgrade deliberately |
| Running full-dataset pandas scoring functions synchronously inside a DRF view | This is the exact performance risk CONCERNS.md already flags ("Pandas-based scoring on 41,700 records may be slow... no visible caching"); it will make search/compatibility endpoints feel slow, not "live" | Precompute base scores in a batch job; use cached numpy vectors + cosine similarity for the live per-pair request path; push true bulk scoring to Celery |
| Hand-rolled multi-provider LLM dispatcher (`if provider == "openai": ...`) | Reinvents a solved problem, untested by definition, and directly adds to the "zero test coverage" risk already flagged in this codebase | `pydantic-ai` (or `instructor`) behind a thin service-function seam |
| `django-import-export` for the one-time 42K-row initial migration | Designed for repeated, admin-UI-driven import/export workflows, not a one-time bulk load with custom cleaning/mapping logic reused from the existing pandas script; adds overhead without adding value for this specific job | Custom management command using `pandas.read_csv(chunksize=...)` + `bulk_create(update_conflicts=True)` |
| Supporting both a legacy JWT auth model *and* Supabase Auth tokens long-term in the new Django backend | CONCERNS.md documents 3 conflicting legacy auth models; carrying forward more than one indefinitely just re-imports that same fragility into the new system | Pick one: `djangorestframework-simplejwt` as the single Django-native auth model for the new backend; treat legacy JWT/Supabase tokens as a one-time user-migration problem (re-issue Django tokens on first login), not a permanent dual-auth system |
| ASGI/Uvicorn/Daphne + Django async views for v1 | Adds real complexity (async ORM caveats, async-safe middleware, mixed sync/async views) without a corresponding need — Celery already offloads the genuinely slow work (LLM calls, batch scoring), so the request path can stay synchronous | Gunicorn (WSGI) for the Django API; Celery workers for anything slow |
| Storing everything (including filterable, fixed-shape fields) as Postgres `jsonb` | CONCERNS.md explicitly flags this from the Supabase schema — `attributes jsonb` with no structure validation, no numeric-range constraints; anything the frontend filters/sorts on (pace, shooting, position, market value) belongs in typed, indexed columns | Normalize known/fixed/filterable fields into real model fields; reserve `JSONField` for genuinely variable data (e.g., LLM report metadata, sparse per-position extended stats), and add a `GinIndex` + app-level validation when jsonb is used |

## Postgres Driver/ORM Patterns for the jsonb-Heavy Schema

- Use `psycopg 3` as the driver (see Core Technologies above); it's what Django 5.x connection pooling is built on.
- Use `models.JSONField` (maps to native Postgres `jsonb`) only for genuinely variable-shape data — not as a default dumping ground. The Supabase reference schema's `attributes jsonb` with no structure validation is exactly the anti-pattern CONCERNS.md flags; don't carry it forward for anything the frontend needs to filter, sort, or range-query on.
- For the ~100+ per-position stat fields inherited from the legacy Mongo schema: don't blindly replicate either the "100+ required fields, one model per position" pattern (CONCERNS.md: "maintenance nightmare," "brittle validation") or a single giant jsonb blob. A single `Player` model with a `position` field plus nullable/defaulted core stat columns, and a `JSONField` reserved for the long tail of rarely-queried extended stats, balances queryability against schema bloat.
- Where `JSONField` is used, add `django.contrib.postgres.indexes.GinIndex` for containment/key lookups, and validate structure at the Django layer (custom `clean()`/serializer validation, or a library like `django-pydantic-field` if you want the JSON validated against a Pydantic model automatically) — Postgres `jsonb` itself enforces no schema, so CONCERNS.md's "no validation that attributes contains pace, shooting..." risk has to be closed in application code.
- Use `django.contrib.postgres.fields.ArrayField` for genuinely list-shaped data (e.g., a player's multiple eligible `Positions`) instead of comma-joined strings, which is what the legacy CSV/Mongo pipeline apparently did.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|------------------|-------|
| Django 5.2 | psycopg 3.1.8+ (recommend 3.3.x) | Django 4.2+ supports psycopg3; 5.1+ adds native pooling via `CONN_POOL` |
| Django 5.2 | djangorestframework-simplejwt 5.5.x | simplejwt 5.5.1 officially supports Django 4.2–5.2 |
| Django 5.2 | django-redis 7.0.0 | django-redis 7.0.0 supports Django 5.2 and 6.0, requires Python ≥3.10 |
| pandas <3.0 (2.2–2.x) | numpy 2.x | pandas 2.x is compatible with numpy 2.x; avoid pandas 3.0 for the reasons above regardless of numpy version |
| Celery 5.6.x | Redis | Celery 5.6.x pins Redis-server compatibility to ≤5.2.1 for the Redis transport — verify your Redis server/managed-Redis version against this before deploying |
| Python | Django 5.2: 3.10–3.14 · Django 6.0: 3.12+ | If choosing Django 6.0 instead of 5.2 LTS, confirm your hosting target and local dev environments are already on Python ≥3.12 |

## Sources

- [Django 5.2 release notes](https://docs.djangoproject.com/en/6.0/releases/5.2/) — LTS support window, HIGH confidence
- [Django 6.0 release notes](https://docs.djangoproject.com/en/6.0/releases/6.0/) — non-LTS support window, Python requirement, HIGH confidence
- PyPI JSON API (`pypi.org/pypi/<package>/json`) for `django`, `djangorestframework`, `psycopg`, `pandas`, `djangorestframework-simplejwt`, `pydantic-ai` — exact current versions, HIGH confidence (fetched directly, 2026-07-20)
- [psycopg3 docs — differences from psycopg2](https://www.psycopg.org/psycopg3/docs/basic/from_pg2.html) — psycopg2 vs psycopg3 recommendation, HIGH confidence
- [Celery 5.6 docs — Redis broker](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html) — Redis version compatibility, MEDIUM confidence (WebSearch-derived, not independently cross-checked against Celery changelog)
- WebSearch: "Django Ninja vs Django REST Framework 2025 2026" — ecosystem/maturity comparison, MEDIUM confidence (multiple aggregator sources agree, not an official DRF/Ninja doc)
- WebSearch: "PydanticAI vs LiteLLM vs instructor" — provider coverage and use-case differentiation, MEDIUM confidence (cross-checked against pydantic-ai's own docs listing supported providers)
- [pydantic-ai PyPI](https://pypi.org/project/pydantic-ai/) and [pydantic.dev/docs/ai](https://pydantic.dev/docs/ai/overview/) — provider list, agent model, HIGH confidence
- WebSearch: pandas 3.0 breaking changes (Copy-on-Write, string dtype) — MEDIUM confidence (derived from search summaries referencing pandas 3.0 whatsnew docs, not the whatsnew doc itself fetched directly — recommend the roadmap/build phase re-verify against `pandas 3.0.0 whatsnew` before any future pandas 3.0 upgrade)
- `.planning/codebase/CONCERNS.md` and `.planning/codebase/STACK.md` (this repo) — grounding for what existing risks the new stack must address

---
*Stack research for: Django REST backend, AI football scouting/recruitment platform*
*Researched: 2026-07-20*
