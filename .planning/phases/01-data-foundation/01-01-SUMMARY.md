---
phase: 01-data-foundation
plan: 01
subsystem: database
tags: [django, drf, postgres, psycopg3, django-environ, pandas, etl-planning]

# Dependency graph
requires: []
provides:
  - Runnable Django 5.2 project skeleton at get-scouted-be/ with split settings (base/local/production)
  - Postgres connection via django-environ's env.db() reading DATABASE_URL
  - Four registered apps (clubs, players, transfers, core) plus django.contrib.postgres, ready for Plan 03's models
  - DATASET_DIR setting pointing at repo-root API-Updated-/dataset/
  - get-scouted-be/docs/FIELD_MAPPING.md — canonical CSV -> Django field -> impact_model_v4.1.py internal-name mapping (DATA-05 prerequisite)
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07, 01-08, 01-09, phase-03-scoring-curation]

# Tech tracking
tech-stack:
  added: [Django 5.2, djangorestframework 3.17, psycopg3 (binary+pool), django-environ, pandas<3.0]
  patterns:
    - "Split settings package (config/settings/base.py -> local.py/production.py), not a single settings.py"
    - "Django model field names mirror CSV column names verbatim (Snake_Case_With_Caps), not Pythonified — locked per CONTEXT.md for 1:1 Phase 5 parity-testing traceability"
    - "Non-identifier/unused-by-scoring CSV columns isolated into a single Player.extended_stats JSONField, keyed by original CSV column-name string"

key-files:
  created:
    - get-scouted-be/manage.py
    - get-scouted-be/config/settings/base.py
    - get-scouted-be/config/settings/local.py
    - get-scouted-be/config/settings/production.py
    - get-scouted-be/config/urls.py
    - get-scouted-be/config/wsgi.py
    - get-scouted-be/config/asgi.py
    - get-scouted-be/clubs/apps.py
    - get-scouted-be/players/apps.py
    - get-scouted-be/transfers/apps.py
    - get-scouted-be/core/apps.py
    - get-scouted-be/requirements/base.txt
    - get-scouted-be/.env.example
    - get-scouted-be/docs/FIELD_MAPPING.md
  modified: []

key-decisions:
  - "Django field names mirror the CSV's exact Snake_Case_With_Caps column names verbatim (per CONTEXT.md), including for the ~121 valid-identifier Players.csv columns — no lowercase/Pythonify translation layer"
  - "Player.club FK is sourced from Team_within_selected_timeframe, not Team — verified via impact_model_v4.1.py's own internal rename of 'Team within selected timeframe' -> 'Team', confirming they represent the same concept"
  - "Total_Score renamed to legacy_total_score to prevent confusion with the real Phase 4-6 Impact RMM output"
  - "14 movement/physical CSV columns (not valid Python identifiers, none referenced by impact_model_v4.1.py) go into a single Player.extended_stats JSONField keyed by original CSV column-name string, not 14 sanitized fields"
  - "Discovered and documented a duplicate Aerial_duels_per_90 header in Players.csv (outfield block + GK block) not previously flagged anywhere — import code must handle both occurrences explicitly"

patterns-established:
  - "Pattern: FIELD_MAPPING.md as the single canonical CSV<->Django<->scoring-script naming reference — Phase 3+ import/scoring code should read from this doc rather than re-deriving mappings"

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04, DATA-05]

duration: 25min
completed: 2026-07-20
---

# Phase 1 Plan 1: Django Project Scaffolding + FIELD_MAPPING.md Summary

**Stood up a from-scratch Django 5.2/DRF-ready project at get-scouted-be/ (split settings, Postgres via django-environ, four apps) and produced the canonical FIELD_MAPPING.md documenting all 121 valid-identifier Players.csv columns against their impact_model_v4.1.py internal names, the 14-column extended_stats JSON block, derived Club fields, and the transferdata UniqueID-is-a-Club-id trap.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-20T17:54:00Z
- **Completed:** 2026-07-20T18:08:00Z
- **Tasks:** 2
- **Files modified:** 24 (23 scaffolding files + 1 FIELD_MAPPING.md)

## Accomplishments
- Runnable Django project skeleton under get-scouted-be/ — verified with `python manage.py check` (0 issues) against a real local Postgres 14 database, not just a syntax check
- Split settings (base/local/production) with django-environ's `env.db()` parsing DATABASE_URL, DATASET_DIR pointing at repo-root API-Updated-/dataset/, and django.contrib.postgres + clubs/players/transfers/core registered in INSTALLED_APPS
- Canonical FIELD_MAPPING.md (326 lines) capturing every known CSV/script naming divergence up front, plus two new findings not previously documented anywhere (duplicate Aerial_duels_per_90 header; confirmed transferdata UniqueID-as-Club-id trap with full evidence)

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold the Django project (config settings package + 4 apps + Postgres connection)** - `16d08a3` (feat)
2. **Task 2: Write FIELD_MAPPING.md (CSV column -> Django field -> scoring-script name)** - `01e8052` (docs)

**Plan metadata:** (this commit) `docs(01-01): complete plan`

## Files Created/Modified
- `get-scouted-be/manage.py` - Django entrypoint, default settings module config.settings.local
- `get-scouted-be/config/settings/base.py` - Shared settings: INSTALLED_APPS, DATABASES via env.db(), DATASET_DIR, DEFAULT_AUTO_FIELD
- `get-scouted-be/config/settings/local.py` - DEBUG=True, ALLOWED_HOSTS=['*']
- `get-scouted-be/config/settings/production.py` - DEBUG=False, ALLOWED_HOSTS from env, hosting-deferred placeholder comment
- `get-scouted-be/config/urls.py`, `wsgi.py`, `asgi.py` - minimal admin-only URLconf, WSGI/ASGI entrypoints
- `get-scouted-be/clubs/apps.py`, `players/apps.py`, `transfers/apps.py`, `core/apps.py` - AppConfig for each of the four data apps (models deferred to Plan 03)
- `get-scouted-be/requirements/base.txt` - Django>=5.2,<5.3, djangorestframework>=3.15,<3.18, psycopg[binary,pool]>=3.2, django-environ>=0.11, pandas>=2.2,<3.0
- `get-scouted-be/.env.example`, `.gitignore` - local dev env template and standard Python/Django ignores
- `get-scouted-be/docs/FIELD_MAPPING.md` - canonical CSV -> Django -> impact_model_v4.1.py field mapping deliverable

## Decisions Made
- Django field names mirror CSV column names exactly (locked per CONTEXT.md) — confirmed this holds cleanly for 121 of 135 Players.csv columns; the remaining 14 (movement/physical block) are not valid identifiers and go into `extended_stats` JSONField instead
- Verified via direct grep of the 15,747-line impact_model_v4.1.py (not assumed) which of the 121 stat columns the scoring script actually references, and under what literal string — 85 columns have a confirmed script-internal name, 25 are confirmed genuinely unreferenced (mostly raw-count columns where the script only uses the `_per_90` rate form)
- Ran a live `python manage.py check` against a real local Postgres 14 database (created `getscouted` DB/role locally) as a bonus verification beyond the plan's required `ast.parse` check — confirms the settings actually connect, not just parse

## Deviations from Plan

None - plan executed exactly as written. Both discretionary discoveries below were captured as documentation (part of Task 2's deliverable), not code changes, so they don't count as Rule 1-3 auto-fixes:
- Duplicate `Aerial_duels_per_90` CSV header (outfield + GK blocks) — documented in FIELD_MAPPING.md §1b for Plan 03/import commands to handle explicitly.
- Confirmed (with fresh evidence) the transferdata `UniqueID`-is-a-Club-id trap already flagged by RESEARCH.md — restated with full verification detail in FIELD_MAPPING.md §4/§5.

## Issues Encountered
- Local Postgres instance (Postgres 14.18, not the 16/17 targeted by STACK.md) was already running on this machine under a `MAC`-owned role set; created a `postgres` superuser role and `getscouted` database matching the plan's default `DATABASE_URL` so `manage.py check` could be verified end-to-end. Postgres 14 vs 16/17 is not expected to be a blocker for Phase 1 (no version-specific features are used yet) — noting here in case a later phase relies on a Postgres 16/17-specific feature.

## User Setup Required

**External services require manual configuration for local development.** Per this plan's `user_setup` frontmatter:
- A local Postgres 16/17 instance (or the 14.18 instance already present, which currently works) with a `getscouted` database and `DATABASE_URL` matching `get-scouted-be/.env.example`'s format.
- Copy `get-scouted-be/.env.example` to `get-scouted-be/.env` and fill in `SECRET_KEY`/`DATABASE_URL` for local dev (this was already validated to work end-to-end during this plan's execution, but the `.env` file itself is gitignored and must be recreated locally by anyone else running this project).

## Next Phase Readiness
- `get-scouted-be/` is ready for Plan 03 (models) — INSTALLED_APPS, DATABASES, and DATASET_DIR are all in place; `manage.py check` passes cleanly against a real Postgres connection.
- FIELD_MAPPING.md is ready to be the single reference for Plan 03's model field names and Phase 3's scoring-engine port — no further field-name research should be needed for the 121 mapped Players.csv columns, the 14 extended_stats columns, the derived Club fields, or the Transfer fields.
- No blockers identified for Plan 02 (next plan in the wave sequence).

---
*Phase: 01-data-foundation*
*Completed: 2026-07-20*

## Self-Check: PASSED

All created files verified present on disk (manage.py, config/settings/base.py, docs/FIELD_MAPPING.md, requirements/base.txt, clubs/apps.py, players/apps.py, transfers/apps.py, core/apps.py). Both task commits (`16d08a3`, `01e8052`) verified present in git log.
