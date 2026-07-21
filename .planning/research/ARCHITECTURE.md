# Architecture Research

**Domain:** Django/DRF backend hosting CRUD APIs + a large pandas scoring engine + LLM integration (AI football scouting platform)
**Researched:** 2026-07-20
**Confidence:** HIGH (Django/DRF layering, service-layer, adapter patterns — well-established); MEDIUM (specific caching strategy — judgment call, no load data yet); HIGH (facts about `impact_model_v4.1.py`'s actual structure — verified by direct inspection)

## Source-of-Truth Finding: What `impact_model_v4.1.py` Actually Is

Before the architecture recommendations make sense, one fact from directly inspecting the file (`pixel-perfect-clone-60729/docs/impact_model_v4.1.py`, 15,747 lines) has to be stated plainly, because it changes the shape of "port the scoring engine" from a mechanical translation into a curation-plus-port job:

- It is a **flattened Jupyter notebook**, not an authored library. It opens with `# In[44]:` cell markers, has `import pandas as pd` / `import numpy as np` re-imported at least 8 separate times mid-file, and — critically — **the same function name is defined 3–4 times at different line numbers** (e.g. `classify_age_fit` at lines 1325 and 2698; `prepare_team_and_transfer_signal` at 7041, 11427, 11702, 12192; `player_transfer_history` at 7093, 11488, 11870, 12329; `build_general_market_shortlist` at 12776 and 13263; `get_role_scores_from_dataset` at 1055 and 3133). In a top-to-bottom script execution, **the last definition silently wins** — meaning large portions of the file are dead/superseded code that must not be ported as-is.
- It embeds actual **ML model training** (`from sklearn.ensemble import RandomForestRegressor`, `train_transfer_value_model()`, `build_club_requirement_prediction_model()`) alongside the deterministic scoring math — these are a different concern (trained artifacts needing versioning/serialization) from the pure-function impact calculators and should not be treated as "the same kind of thing" during the port.
- The core impact calculators (`_calc_gk_impact_raw`, `_calc_cb_impact_raw`, `_calc_fb_impact_raw`, `_calc_cmf_impact_raw`, `_calc_dmf_impact_raw`, `_calc_amf_impact_raw`, `_calc_winger_impact_raw`, `_calc_cf_impact_raw`) are the one genuinely clean, non-duplicated part: each takes `(row, row_idx, std_lookup)` and returns `(raw_impact, positive, negative, components_dict)`. These are good candidates for a direct, position-keyed strategy-pattern port.
- Almost every meaningful function — including ones that look "per-player" (`recommend_clubs_for_player`, `calculate_subjective_role_fit_for_player_to_team`, `full_player_transfer_analysis_with_role_fit`) — takes a **precomputed lookup or reference structure built from the whole dataset** as an argument: `std_lookup` (z-scores per metric per position, built once via `_build_std_lookup(df, metrics)` over the *entire* player population), `team_styles_df` / `build_team_style_vector()` (per-club role-demand vectors), and `build_team_position_reference()` (per-club, per-position stat averages). **No function in the file computes a single player's score in isolation from the rest of the dataset.** This is the single most important architectural constraint: "per-entity" scoring in Django cannot mean "load one player row and one club row and compute" — it means "hold cheap-to-refresh, precomputed population-level and club-level aggregates in a fast store, and do the O(1) row-level math against those aggregates on demand."

This directly determines the caching strategy recommended below (Pattern 2: Hybrid — precomputed aggregates + on-demand row-level math), and it means Phase "port scoring engine" must start with a **de-duplication/curation pass** (pick the authoritative version of each duplicated function, isolate the sklearn model-training code from the deterministic scoring code) before any Django porting work, not a blind copy of all 15,747 lines.

## Standard Architecture

### System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         pixel-perfect-clone-60729                        │
│                    (React/TanStack Start — out of scope,                 │
│                     but the shape of its 6 pages drives the API surface) │
└───────────────────────────────────┬────────────────────────────────────-┘
                                     │ REST (JSON) over HTTPS
┌────────────────────────────────────▼───────────────────────────────────┐
│                          Django Project (this milestone)                │
│ ┌───────────────────────────────────────────────────────────────────┐  │
│ │                    API Layer (DRF views/routers)                  │  │
│ │  players/, clubs/, transfers/, watchlist/, shortlists/,           │  │
│ │  squad_plans/, accounts/  — each app: models + serializers + views│  │
│ └───────────┬───────────────────────────────┬─────────────────────-┘  │
│             │ calls service functions        │ calls service functions │
│ ┌───────────▼─────────────┐   ┌───────────────▼──────────────────────┐ │
│ │   scoring/ (service      │   │      ai/ (LLM integration app)      │ │
│ │   layer over ported      │◄──│  NL search parsing, AI scout        │ │
│ │   impact_model_v4.1.py)  │   │  reports/insights — calls scoring/  │ │
│ │                          │   │  for grounding data, then an LLM    │ │
│ │  services/               │   │  adapter for generation             │ │
│ │   position_scorers.py    │   │  providers/openai_adapter.py        │ │
│ │   standardization.py     │   │  providers/anthropic_adapter.py     │ │
│ │   role_fit.py            │   │  providers/base.py (interface)      │ │
│ │   financial_fit.py       │   └──────────────────────────────────────┘ │
│ │   shortlist_generator.py │                                            │
│ └───────────┬──────────────┘                                            │
│             │ reads/writes                                              │
│ ┌───────────▼──────────────────────────────────────────────────────┐   │
│ │      Cache / precomputed-aggregate layer (Redis or DB tables)     │   │
│ │  std_lookup (z-scores per metric/position), team_style_vectors,   │   │
│ │  team_position_reference — rebuilt on data change, not per request│   │
│ └───────────┬─────────────────────────────────────────────────────-┘   │
│             │ reads                                                     │
│ ┌───────────▼──────────────────────────────────────────────────────┐   │
│ │                        PostgreSQL (core/, players/, clubs/)        │   │
│ │  Players, Clubs, Transfers, PlayerStats (per-position), Compat.   │   │
│ │  Scores, PlayerImpactScore (denormalized cache), Watchlist,       │   │
│ │  Shortlists, SquadPlans, Profiles, UserRoles                      │   │
│ └─────────────────────────────────────────────────────────────────-┘   │
└──────────────────────────────────────────────────────────────────────-─┘
             ▲
             │ one-time / repeatable ETL (management command)
┌────────────┴────────────────────────────────────────────────────────┐
│   Legacy sources (mined, not served live): API-Updated-/dataset/*.csv│
│   (Players.csv, Playstyles.csv, Positions/*.csv, Compatability       │
│   Scores/*.csv, transferdata final.csv), legacy MongoDB              │
└────────────────────────────────────────────────────────────────────-┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|-------------------------|
| `players/`, `clubs/`, `transfers/`, `watchlist/`, `shortlists/`, `squad_plans/`, `accounts/` | Standard CRUD domain apps — own their Django models, DRF serializers, ViewSets/routers, permissions | Thin views delegating to `.objects` querysets and, where scores are involved, to `scoring/` service calls — **no scoring math lives here** |
| `scoring/` | Owns the ported impact/compatibility/financial-fit/transfer-probability logic as a callable service layer, independent of HTTP | Plain Python service classes/functions (`services/`), no DRF/model imports beyond read-only queries; position-keyed strategy pattern for the 8 `_calc_*_impact_raw` calculators |
| `core/` (or `common/`) | Cross-app shared constants (POSITIONS, LEAGUE_MAPPING), shared serializer/pagination base classes, custom exceptions, base repository/service helpers | Small, no business logic itself |
| `ai/` | LLM-provider-agnostic layer: NL search → structured filter query, AI scout report / club insight generation | Adapter/interface pattern: `providers/base.py` defines an abstract interface (`generate(prompt, **kwargs) -> str/dict`), concrete adapters implement it per provider; `ai/` calls `scoring/` and `players/`/`clubs/` for grounding data before invoking the adapter |
| Cache / precomputed-aggregate layer | Holds the whole-dataset structures every scoring call needs (`std_lookup`, team style vectors, team position reference tables) so a single-entity request is O(1) lookup + row math, not an O(n) dataset scan | Redis (fast, ephemeral, rebuilt by a management command/Celery task on data change) *or* a dedicated Postgres "materialized aggregate" table if Redis is not yet provisioned — either way, **not** recomputed inline per request |
| PostgreSQL | System of record for all entities plus denormalized score fields (`Player.impact_score`, `Player.transfer_probability`, etc.) that are cheap to read on list/search pages | Django models, migrations; denormalized fields updated via a signal or explicit service call after scoring, not computed in the serializer |
| ETL / migration layer | One-time (and repeatable) import of CSVs (`API-Updated-/dataset/`) and legacy Mongo data into Postgres | Django management commands (`import_players`, `import_transfers`, `import_compatibility_scores`), idempotent, using the field-mapping knowledge already encoded in the legacy `utils/fieldMapper.js` as a reference |

## Recommended Project Structure

```
getscouted_backend/
├── manage.py
├── config/                       # Django project package (settings, root urls, wsgi/asgi)
│   ├── settings/
│   │   ├── base.py
│   │   ├── local.py
│   │   └── production.py
│   ├── urls.py                   # includes each app's urls under /api/v1/...
│   └── celery.py                 # if async recompute of aggregates is used
│
├── core/                         # Shared, no business logic of its own
│   ├── constants.py               # POSITIONS, LEAGUE_MAPPING, ROLE_NAMES
│   ├── permissions.py             # role-based DRF permission classes (scout/analyst/director/admin)
│   ├── pagination.py
│   ├── exceptions.py
│   └── models.py                  # abstract base models (TimestampedModel, etc.)
│
├── accounts/                      # Auth + roles (replaces JWT / disabled API-key / Supabase Auth)
│   ├── models.py                  # Profile, UserRole
│   ├── serializers.py
│   ├── views.py                   # login/refresh, profile endpoints
│   └── permissions.py
│
├── players/                       # Player CRUD + per-position stats + search/filter
│   ├── models.py                  # Player, PlayerPositionStats, Playstyle
│   ├── serializers.py
│   ├── views.py                   # ViewSets; delegate scoring reads to scoring/ services
│   ├── filters.py                 # django-filter FilterSets for search/filter endpoints
│   └── management/commands/
│       └── import_players.py      # ETL from CSV/Mongo
│
├── clubs/                         # Club CRUD + squad composition views
│   ├── models.py                  # Club, SquadPlan
│   ├── serializers.py
│   ├── views.py
│   └── management/commands/
│       └── import_clubs.py
│
├── transfers/                     # Transfer history, market averages
│   ├── models.py                  # TransferRecord
│   ├── serializers.py
│   ├── views.py
│   └── management/commands/
│       └── import_transfers.py
│
├── watchlist/  shortlists/        # Small, user-owned CRUD apps (mirror Supabase's watchlist/squad_plans)
│
├── scoring/                       # THE PORTED ENGINE — service layer, no HTTP/DRF imports inside services/
│   ├── models.py                  # PlayerImpactScore (denormalized cache), CompatibilityScore
│   ├── serializers.py             # Output shape for /api/scoring/* endpoints
│   ├── views.py                   # Thin: parse request -> call service -> serialize
│   ├── urls.py
│   ├── services/
│   │   ├── standardization.py     # _build_std_lookup / _std ported here; cache-aware
│   │   ├── position_scorers.py    # one class per position wrapping _calc_*_impact_raw (curated, de-duplicated)
│   │   ├── role_fit.py            # cosine-similarity role/style vectors (ported)
│   │   ├── financial_fit.py       # TFM / financial fit + age-curve adjustment
│   │   ├── transfer_probability.py# ported/wrapping the sklearn-trained model, versioned artifact
│   │   ├── team_reference.py      # build_team_position_reference / team style vectors (the cached aggregates)
│   │   └── shortlist_generator.py # orchestrates the above for batch/shortlist use cases
│   ├── ml_artifacts/              # serialized sklearn models (joblib), versioned, NOT retrained per request
│   └── tests/
│
├── ai/                             # LLM-provider-agnostic layer
│   ├── services/
│   │   ├── nl_search.py            # query -> structured filter dict, calls players/clubs filters
│   │   └── report_generator.py     # scout report / club insight, calls scoring/ for grounding
│   ├── providers/
│   │   ├── base.py                 # abstract LLMProvider interface
│   │   ├── openai_adapter.py       # concrete implementation (added when provider is chosen)
│   │   └── anthropic_adapter.py    # concrete implementation (added when provider is chosen)
│   ├── views.py
│   └── urls.py
│
└── etl/ (optional, or folded into each app's management/commands/)
    └── legacy_field_mapping.py     # port of API-Updated-/utils/fieldMapper.js logic
```

### Structure Rationale

- **One app per bounded entity (`players/`, `clubs/`, `transfers/`, `watchlist/`, `shortlists/`), one app for the cross-cutting capability (`scoring/`), one app for the cross-cutting integration (`ai/`).** This matches how the PRD's 6 pages actually consume data: pages need entity CRUD *and* scores *and* AI text, and those three concerns change at different rates and for different reasons — scoring logic changes because the football methodology changes, CRUD changes because of schema evolution, AI changes because of prompt/provider iteration. Keeping them in separate apps means a scoring-methodology bug fix never risks a CRUD regression and vice versa.
- **`scoring/services/` has zero DRF or HTTP imports.** This is the mechanism that prevents the exact failure mode implied by the question ("scoring logic tangled into views/serializers"): `scoring/views.py` is a thin adapter (parse request params → call a `services/` function → serialize the returned dataclass/dict). The `services/` functions are plain Python, directly unit-testable without spinning up DRF's request/response cycle — important given the existing codebase has **zero test coverage anywhere**, and the ported scoring logic (previously untested pandas code) is the highest-risk surface to get right.
- **`scoring/models.py` holds denormalized score fields as a genuine Django model (`PlayerImpactScore`), not just a cache.** This gives cheap list/search/sort queries (`Player.objects.order_by('-impactscore__value')`) without invoking pandas at all for the common "browse/filter many players" case, while the `services/` layer remains the single place that *computes* the number when it needs recomputing.
- **`ai/providers/` is separated from `ai/services/`.** `services/` contains the domain logic of *what* to ask the LLM for (prompt construction, grounding-data assembly from `scoring/` and `players/`/`clubs/`) and how to interpret the result; `providers/` contains *how* to talk to a specific vendor API. This is what makes the provider swappable later without touching NL-search or report-generation business logic — directly satisfies the PROJECT.md constraint that the concrete LLM provider is picked later.
- **ETL as Django management commands, not a separate service.** The dataset migration (CSVs + legacy Mongo → Postgres) is a one-time/repeatable batch job that belongs to each domain app that owns the target model (`players/management/commands/import_players.py` etc.), reusing Django's ORM and validation rather than a bespoke script — this also means the import logic is testable and re-runnable as the CSV/Mongo source data is corrected during the migration.

## Architectural Patterns

### Pattern 1: Service Layer (business logic out of views/serializers)

**What:** Views/ViewSets do request parsing, permission checks, and response shaping only. All business logic — including all scoring calls — lives in plain-Python service modules/classes that take and return plain Python types (dataclasses, dicts, or Django model instances), never `Request`/`Response` objects.
**When to use:** Everywhere scoring is invoked, and anywhere CRUD logic exceeds "query + serialize" (e.g. shortlist generation, squad-plan validation).
**Trade-offs:** Slightly more files/indirection for simple CRUD; pays off immediately for `scoring/` given its size and the fact it must be unit-tested without an HTTP layer.

**Example:**
```python
# scoring/views.py
class PlayerImpactView(APIView):
    def get(self, request, player_id):
        result = ImpactScoringService.score_player(player_id)   # plain call, no HTTP concerns inside
        return Response(PlayerImpactSerializer(result).data)

# scoring/services/position_scorers.py
class ImpactScoringService:
    @staticmethod
    def score_player(player_id: int) -> PlayerImpactResult:
        player = Player.objects.select_related("position_stats").get(id=player_id)
        std_lookup = StandardizationCache.get_or_build(player.main_position)  # from Pattern 2
        scorer = POSITION_SCORERS[player.main_position]                       # strategy pattern
        return scorer.calculate(player, std_lookup)
```

### Pattern 2: Hybrid Caching — Precomputed Population/Club Aggregates + On-Demand Row Math

**What:** Two distinct kinds of "expensive" exist in the ported engine and they need different treatment:
1. **Whole-dataset aggregates** (`std_lookup` z-scores across all players per position/metric, per-club role-demand vectors, per-club-per-position stat averages) are expensive (O(n) over the full player table) but change infrequently — only when the underlying dataset changes (new season import, new transfer data, a player's stats update). **Precompute and cache these** (Redis, or a `MaterializedAggregate` Postgres table), rebuilt via a management command or Celery task triggered on data-change, not on each API request.
2. **Per-entity row-level math** (a single player's impact components, a single player-vs-club cosine-similarity role fit, a single financial-fit calculation) is cheap (O(1) given the aggregates above) and should be **computed on demand** at request time using the cached aggregates — this is what actually makes "give me this one player's impact score against this one club" fast without a batch job.
3. **The final score numbers themselves** (`Player.impact_score`, `Player.transfer_probability`) should additionally be **denormalized onto the Player/Compatibility models** so that list/browse/search/sort endpoints (Dashboard, Shortlist pages) never invoke scoring math at all — they're pure DB reads. Recompute-and-write-back happens via the same on-demand service call, either synchronously on first request (cache-aside) or via a signal/task after data import.

**When to use:** `std_lookup` and team-reference structures → cache layer (Redis/materialized table), rebuilt on data change. Single-entity impact/role-fit/financial-fit calculation → on-demand service call against cached aggregates. List/search score display → denormalized DB field, written by the on-demand path.
**Trade-offs:** More moving parts than "just recompute everything on every request" (which is what the original pandas script effectively does per batch run and is too slow for a live per-entity endpoint) or "just precompute everything into a giant batch table" (which reintroduces the current spreadsheet-export mentality and goes stale between imports). The hybrid keeps single-player/single-club requests fast (no full-dataset scan) while keeping cross-entity comparisons (browse/sort/shortlist) fast too (no per-row pandas call on every page load).

**Example:**
```python
# scoring/services/standardization.py
class StandardizationCache:
    CACHE_KEY = "std_lookup:{position}"
    TTL = None  # invalidated explicitly, not time-based

    @classmethod
    def get_or_build(cls, position: str) -> dict:
        key = cls.CACHE_KEY.format(position=position)
        cached = cache.get(key)
        if cached is not None:
            return cached
        df = load_position_dataframe(position)     # pandas, but only run on cache miss
        lookup = _build_std_lookup(df, METRICS[position])  # ported function, unchanged
        cache.set(key, lookup)  # no TTL — invalidated by invalidate_on_data_change signal
        return lookup

# players/signals.py
@receiver(post_save, sender=PlayerPositionStats)
def invalidate_std_lookup(sender, instance, **kwargs):
    cache.delete(f"std_lookup:{instance.position}")
```

### Pattern 3: Adapter/Interface Pattern for LLM Provider Abstraction

**What:** An abstract base (`LLMProvider`, e.g. `ABC` with `generate_completion()`, `generate_structured()`) defines the contract `ai/services/` code depends on. Each concrete provider (OpenAI, Anthropic, etc.) implements the interface in its own adapter module. A factory/settings-driven resolver (`get_llm_provider()`) returns the configured implementation, so `nl_search.py` and `report_generator.py` never import a vendor SDK directly.
**When to use:** Any place the app calls out to an LLM — NL search parsing and AI report/insight generation both go through this same interface, even though their prompts differ.
**Trade-offs:** A small amount of upfront abstraction for a "single provider today" reality — justified here because PROJECT.md explicitly defers the concrete provider decision, so the interface must exist before the decision is made, not after.

**Example:**
```python
# ai/providers/base.py
class LLMProvider(ABC):
    @abstractmethod
    def generate_structured(self, prompt: str, schema: dict) -> dict: ...
    @abstractmethod
    def generate_text(self, prompt: str) -> str: ...

# ai/providers/__init__.py
def get_llm_provider() -> LLMProvider:
    name = settings.LLM_PROVIDER  # env-driven, e.g. "openai" | "anthropic" | "stub"
    return _PROVIDER_REGISTRY[name]()

# ai/services/nl_search.py
def parse_query_to_filters(query: str) -> dict:
    provider = get_llm_provider()
    return provider.generate_structured(NL_SEARCH_PROMPT.format(query=query), FILTER_SCHEMA)
```
A `stub`/`fake` provider implementing the same interface (returns canned or trivially-parsed output) lets `players/`, `clubs/`, and the rest of the app develop and test against `ai/` before a real provider key exists — directly useful given the 4-day soft deadline and the "concrete LLM provider is a later decision" constraint.

## Data Flow

### Request Flow — "Score this one player against this one club" (the core new capability)

```
GET /api/scoring/players/{id}/impact/?club_id={club_id}
    ↓
scoring/views.py (parses params, checks role permission)
    ↓
ImpactScoringService.score_player(player_id)
    ├─ StandardizationCache.get_or_build(position)   → cache hit (Redis) in steady state
    ├─ POSITION_SCORERS[position].calculate(player, std_lookup)  → O(1) row math (ported _calc_*_impact_raw)
    └─ write-through: Player.impact_score updated if stale (denormalized field)
    ↓
CompatibilityService.score_fit(player_id, club_id)
    ├─ TeamReferenceCache.get_or_build(club_id)       → cache hit (Redis) in steady state
    └─ cosine_similarity(role_vector(player), team_role_demand(club))  → O(1)
    ↓
scoring/serializers.py shapes response
    ↓
JSON response ← DRF
```

### Request Flow — Dataset Migration (must run before anything above works)

```
CSV files (API-Updated-/dataset/*.csv) + legacy MongoDB
    ↓ (management command, idempotent, chunked for the ~25MB Players.csv)
Field mapping / normalization (ported from utils/fieldMapper.js logic + _rename_columns_safe)
    ↓
Django ORM bulk_create/update_or_create → PostgreSQL (players, clubs, transfers, playstyles, compatibility_scores)
    ↓
Post-import signal/task: rebuild std_lookup + team_style_vectors + team_position_reference caches
    ↓
Post-import (optional, can be lazy): populate denormalized Player.impact_score for the initial dataset
```

### Request Flow — AI Scout Report Generation (depends on scoring existing)

```
POST /api/ai/reports/players/{id}/
    ↓
ai/views.py → ReportGeneratorService.generate(player_id, context)
    ├─ pulls player data (players/) 
    ├─ pulls impact/compatibility/financial-fit scores (scoring/ services — NOT recomputed, read denormalized/cached)
    ├─ builds a grounded prompt from real scores (prevents the LLM inventing numbers)
    └─ get_llm_provider().generate_text(prompt)
    ↓
Response persisted (optional) + returned as JSON
```

### Key Data Flows

1. **Migration → Cache warm-up → Live scoring:** the system is unusable for per-entity scoring until (a) Postgres has real player/club/transfer data and (b) the aggregate caches (`std_lookup`, team references) have been built at least once from that data. This is a hard dependency, not a nice-to-have ordering.
2. **Scoring → AI reports:** AI-generated scout reports/insights must read *real* computed scores (from `scoring/`, either the on-demand service or the denormalized field) as grounding context before calling the LLM — never let the LLM free-associate a player's impact number, or the "AI report" will contradict the "real" score shown elsewhere on the same page, which directly undermines the stated Core Value ("scores being right... is the product's credibility").

## Scaling Considerations

Given this is a 4-day-soft-deadline demo backend serving a known, bounded dataset (one CSV export's worth of players/clubs/transfers, not millions of live users), the realistic scaling axis is **dataset size and scoring-request volume**, not concurrent-user count.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Demo / small dataset (thousands of players, single-digit concurrent users) | In-process Django cache (`LocMemCache`) is fine instead of Redis; synchronous on-demand scoring is fine; denormalized fields can be populated lazily on first read |
| Growing dataset / multiple analysts using it concurrently | Move cache to Redis (shared across workers, survives process restarts); move aggregate rebuild (`std_lookup`, team references) to a Celery task triggered by data-import signals rather than inline in the request/import path; add DB indexes on `Player.main_position`, `Player.club_id`, filter fields used by NL search |
| Large historical dataset / many clubs' worth of shortlist generation running regularly | Batch shortlist generation (`shortlist_generator.py`, mirroring `external_target_shortlist_absolute_vectorized`) moves fully to async task queue (Celery/RQ) with progress tracking, since it is inherently a full-dataset vectorized pandas operation and shouldn't run in an HTTP request-response cycle regardless of dataset size |

### Scaling Priorities

1. **First bottleneck:** Recomputing `std_lookup`/team-reference aggregates synchronously inside a request path (e.g., on cache-miss during a spike of concurrent single-player score requests right after a data import). Fix: warm the cache proactively in the post-import management command/signal rather than relying purely on lazy cache-aside.
2. **Second bottleneck:** Full shortlist/batch generation endpoints (`generate-shortlist`, `team-analysis`) being called synchronously over HTTP for large candidate pools — these mirror the original script's `external_target_shortlist_absolute_vectorized()` batch behavior and are not "per-entity" in nature. Fix: keep these as explicitly async/background endpoints (return a job id, poll for result) rather than trying to force them into the same fast on-demand path as single-player scoring.

## Anti-Patterns

### Anti-Pattern 1: Scoring math inline in DRF views or serializers

**What people do:** Call pandas functions or replicate the `_calc_*_impact_raw` weighted-sum logic directly inside a `ViewSet.get_queryset()` or a serializer's `to_representation()`.
**Why it's wrong:** Makes the scoring logic untestable without spinning up the full DRF request cycle, duplicates logic across endpoints that need the same score (player detail page vs. shortlist vs. AI report), and re-introduces exactly the tangling the question is trying to avoid.
**Do this instead:** Views call `scoring/services/` functions; serializers only shape already-computed data.

### Anti-Pattern 2: Recomputing whole-dataset aggregates (`std_lookup`, team references) per request

**What people do:** Treat "per-entity scoring" as "just run the whole pandas script but filter the output to one player" — i.e., reload all CSVs/query all players and rebuild `std_lookup` on every API call.
**Why it's wrong:** This is exactly what the original script does for batch export, and it's O(n) over the entire player population per request — completely unworkable for a live "click a player, see their score" UI (this is precisely why the frontend currently falls back to a crude client-side JS heuristic instead of calling the real engine).
**Do this instead:** Pattern 2 above — precompute/cache the whole-dataset aggregates, do only the O(1) row-level math on demand.

### Anti-Pattern 3: Porting all 15,747 lines verbatim, including duplicate/superseded function definitions

**What people do:** Copy-paste the entire `.py` file into a Django app and start wiring imports.
**Why it's wrong:** As established above, the file has multiple same-named functions defined at different points (a notebook-exec artifact) where only the *last* definition is the one that was actually in effect when the script last ran successfully; porting all versions produces ambiguous/contradictory logic and makes debugging score discrepancies far harder in an already zero-test-coverage codebase.
**Do this instead:** Curate first — for each duplicated function name, identify and keep only the final/authoritative version (the one nearest the bottom of the file, cross-checked against the actual Excel export column headers `get_export_columns_for_position()` uses, since that's effectively the "shipped" behavior), then port that single version into `scoring/services/`.

### Anti-Pattern 4: Hard-coding a single LLM SDK call inside `ai/services/`

**What people do:** `import openai` directly inside `nl_search.py`/`report_generator.py` and call `openai.ChatCompletion.create(...)` inline.
**Why it's wrong:** Contradicts the explicit PROJECT.md constraint that the provider is not yet chosen; makes provider swap or A/B testing require touching business logic; makes testing require live API credentials.
**Do this instead:** Pattern 3 — provider behind an interface, resolved via settings/factory, with a stub/fake implementation for development and tests.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM provider (TBD — OpenAI/Anthropic/etc.) | Adapter pattern (`ai/providers/`), resolved by settings-driven factory | Provider choice deferred per PROJECT.md; build and test against a stub provider now |
| Postgres | Django ORM, standard `DATABASES` setting; Docker-friendly (12-factor `DATABASE_URL` env var) | Replaces both legacy MongoDB and the prototype's Supabase Postgres |
| Redis (recommended, optional at small scale) | `django-redis` cache backend for aggregate caching (Pattern 2) | Can be deferred to `LocMemCache` for the demo scale, but the cache-key/invalidation code should be written against Django's cache API (`django.core.cache`) so swapping backends is a settings change, not a code change |
| Legacy MongoDB / CSVs (`API-Updated-/dataset/`) | One-time/repeatable ETL via management commands, not a live integration | Explicitly out of scope to maintain per PROJECT.md — mined for data and reference logic only |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `players/`, `clubs/` ↔ `scoring/` | Direct Python function calls (service layer), same process | `scoring/services/` reads Player/Club model instances via the ORM but does not own their tables |
| `scoring/` ↔ Cache layer | Django cache API (`django.core.cache`) | Backend-swappable (LocMem → Redis) without touching `scoring/` code |
| `ai/` ↔ `scoring/`, `players/`, `clubs/` | Direct Python function calls for grounding data | `ai/` never computes scores itself — it only reads already-computed ones, keeping "the numbers are right" ownership solely in `scoring/` |
| `ai/services/` ↔ `ai/providers/` | Adapter interface (`LLMProvider` ABC) | The only boundary in the whole backend that crosses into external network calls to a third party at request time |
| Django backend ↔ `pixel-perfect-clone-60729` frontend | REST/JSON over HTTPS, versioned under `/api/v1/` | Out of scope to wire up in this milestone, but endpoint shapes should mirror what the frontend's existing Supabase queries and `src/lib/domain.ts` types expect, to minimize later integration friction |

## Suggested Build Order (Phase Dependencies)

This is the dependency graph the roadmap should reflect — later phases genuinely cannot be validated without earlier ones being real (not stubbed), given the Core Value is that scores must be *actually correct*:

1. **Data model + migration (`players/`, `clubs/`, `transfers/`, plus supporting `playstyles`/`compatibility_scores` tables) must exist and be populated with real data before the scoring engine port begins.** The scoring engine's inputs are specific columns/fields (main position, per-position raw stats, minutes played, market value, contract data) — without real rows in Postgres shaped correctly, the ported scorers can't be validated against anything, only unit-tested with synthetic fixtures.
2. **Scoring engine curation + port (`scoring/`) must exist, including the cache/aggregate layer, before AI report generation is built.** AI-generated reports are explicitly required to ground their text in real computed scores (Core Value: accuracy). Building `ai/report_generator.py` before `scoring/` is real would mean either blocking that work or building it against fake numbers that get thrown away — better to sequence it after.
3. **Auth/roles (`accounts/`) can be built in parallel with the data model work**, since it's largely independent (Profile/UserRole models, permission classes) but should land before any endpoint is exposed beyond local dev, since role-based access (scout/analyst/director/admin) is a stated requirement and DRF permission classes are cheap to retrofit onto views as they're built, but easy to forget if deferred.
4. **NL search (`ai/services/nl_search.py`) depends on the CRUD filter surface (`players/filters.py`, `clubs/filters.py`) existing first** — it translates natural language into the same structured filter parameters the standard filter/search endpoints accept, so those endpoints (and their filterable fields) need to be defined before NL search has something concrete to target.
5. **The LLM provider adapter interface (`ai/providers/base.py`) can and should be built early** (it's a small, low-risk abstraction) even though the concrete provider implementation is deferred — this lets `ai/services/` be developed and tested against a stub from day one without blocking on a provider decision, and avoids a late scramble to retrofit the abstraction after code already directly calls a vendor SDK.
6. **Denormalized score fields and cache warm-up are a finishing/optimization step**, not a blocker for correctness — get the on-demand `scoring/` service layer correct first (Pattern 1/2's compute path), then add the denormalized-field write-through and cache-warming once the numbers are verified right, since optimizing an unverified calculation just makes wrong numbers fast.

## Sources

- Direct inspection of `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` (function inventory via `grep -n "^def "`, duplicate-definition analysis, import analysis) — HIGH confidence, verified firsthand, 2026-07-20
- `.planning/codebase/ARCHITECTURE.md` and `.planning/codebase/STRUCTURE.md` (existing codebase map covering all three sub-projects and prior Django-port planning notes) — HIGH confidence, project-internal
- `.planning/PROJECT.md` — HIGH confidence, project-internal (requirements, constraints, scope)
- [Building a Robust Service Layer in Django with DRF (Medium)](https://medium.com/@abhinav.dobhal/building-a-robust-service-layer-in-django-with-drf-3a3fc6a841c6) — MEDIUM confidence, community pattern, consistent with multiple other sources found
- [drf-service-layer (PyPI/GitHub)](https://pypi.org/project/drf-service-layer/) — MEDIUM confidence, illustrates the pattern is common enough to have tooling, not itself required
- [Django Service Layers: Beyond Fat Models vs. Enterprise Patterns](https://simoncrowe.hashnode.dev/django-service-layers-beyond-fat-models-vs-enterprise-patterns) — MEDIUM confidence
- [Where to put business logic in Django? — Django Forum](https://forum.djangoproject.com/t/where-to-put-business-logic-in-django/282) — MEDIUM confidence, official community forum discussion
- [Django Performance and Optimization — Django official docs](https://docs.djangoproject.com/en/6.0/topics/performance/) — HIGH confidence, official docs
- [Django's cache framework — Django official docs](https://docs.djangoproject.com/en/6.0/topics/cache/) — HIGH confidence, official docs
- [django-computedfields documentation](https://django-computedfields.readthedocs.io/en/latest/manual.html) — MEDIUM confidence, illustrates denormalization pattern; not necessarily recommended as a dependency here given the calculation needs pandas/cache logic beyond simple field derivation
- [Understanding Cached Properties in Django (Medium)](https://medium.com/@esatyilmaz/introduction-c1306df1a84c) — LOW/MEDIUM confidence, single-source explainer, consistent with official docs

---
*Architecture research for: Django backend hosting DRF CRUD + pandas scoring engine + LLM layer (GetScouted)*
*Researched: 2026-07-20*
