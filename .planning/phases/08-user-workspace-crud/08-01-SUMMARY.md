---
phase: 08-user-workspace-crud
plan: 01
subsystem: database
tags: [django, drf, postgres, uuid, permissions, factory-boy, pytest]

# Dependency graph
requires:
  - phase: 07-core-crud-players-clubs
    provides: Player/Club models with UUID PKs that workspace FKs reference
  - phase: 02-auth-access-control
    provides: accounts.User (AUTH_USER_MODEL) + UserFactory/authenticated_client test fixtures
provides:
  - workspace Django app registered in INSTALLED_APPS
  - 5 workspace models (Watchlist, Shortlist, ShortlistEntry, SquadPlan, RecentActivity) with UUID PKs
  - IsOwner object-level DRF permission with polymorphic owner resolution
  - workspace/tests/conftest.py with player_factory/club_factory + re-exported auth fixtures
  - applied 0001_initial migration
affects: [08-02, 08-03, 08-04, 08-05, 08-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IsOwner permission resolves ownership via direct obj.user FK, falling back to obj.shortlist.user for child records without a direct owner FK"
    - "RecentActivity.target_id kept as a bare nullable UUIDField (not a FK) so future Player/Club deletion can never cascade-break activity logs"

key-files:
  created:
    - get-scouted-be/workspace/__init__.py
    - get-scouted-be/workspace/apps.py
    - get-scouted-be/workspace/models.py
    - get-scouted-be/workspace/permissions.py
    - get-scouted-be/workspace/migrations/__init__.py
    - get-scouted-be/workspace/migrations/0001_initial.py
    - get-scouted-be/workspace/tests/__init__.py
    - get-scouted-be/workspace/tests/conftest.py
  modified:
    - get-scouted-be/config/settings/base.py

key-decisions:
  - "workspace app registered as final INSTALLED_APPS entry after scoring, matching the codebase's additive-app convention"
  - "All 5 models use UUID PKs + Meta.constraints/indexes (UniqueConstraint/Index), never unique_together, matching players/clubs convention"
  - "RecentActivity.target_id is a bare nullable UUIDField, not a ForeignKey, per 08-RESEARCH.md Pitfall 2"

patterns-established:
  - "IsOwner: getattr(obj, 'user', None) with a shortlist.user fallback is the reusable polymorphic-ownership pattern for all workspace object-level permission checks"
  - "workspace/tests/conftest.py re-imports accounts.tests.conftest fixtures by name (UserFactory, authenticated_client, user_factory) to re-register them as usable pytest fixtures in this app, since conftest fixtures are not auto-shared cross-app"

requirements-completed: [CRUD-06, CRUD-07, CRUD-08, CRUD-09, CRUD-10]

# Metrics
duration: 10min
completed: 2026-07-25
---

# Phase 08 Plan 01: Workspace App Scaffold Summary

**Scaffolded the `workspace` Django app with 5 UUID-keyed user-owned models (Watchlist, Shortlist, ShortlistEntry, SquadPlan, RecentActivity), a polymorphic `IsOwner` object-level permission, and a test conftest with synthetic Player/Club factories — the Wave-0 foundation every downstream Phase 8 feature plan builds on.**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-07-25T05:17:05Z
- **Completed:** 2026-07-25T05:20:35Z
- **Tasks:** 3
- **Files modified:** 9 (8 created, 1 modified)

## Accomplishments
- `workspace` app scaffolded and registered in INSTALLED_APPS; `manage.py check` passes
- All 5 workspace models defined with UUID PKs, `UniqueConstraint`/`Index` Meta convention (no `unique_together`), `RecentActivity.target_id` as a bare nullable UUIDField
- `0001_initial` migration generated and applied cleanly against the existing schema; `makemigrations --check --dry-run` confirms no drift
- `IsOwner` permission resolves ownership via `obj.user`, falling back to `obj.shortlist.user` for `ShortlistEntry`
- `workspace/tests/conftest.py` re-exports `accounts` auth fixtures and adds `player_factory`/`club_factory` (with required `Player.unique_id` set) so downstream tests never need real CSV data
- Full existing test suite still green post-change: 112 passed, 305 skipped, 0 failed

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold workspace app + IsOwner permission + INSTALLED_APPS** - `638b4d7` (feat)
2. **Task 2: Define all 5 workspace models + generate initial migration** - `bebe6f1` (feat)
3. **Task 3: Workspace test conftest (fixtures for all downstream feature tests)** - `9d2262e` (test)

**Plan metadata:** (pending) - `docs(08-01): complete workspace app scaffold plan`

## Files Created/Modified
- `get-scouted-be/workspace/apps.py` - WorkspaceConfig AppConfig
- `get-scouted-be/workspace/permissions.py` - IsOwner object-level permission (polymorphic owner resolution)
- `get-scouted-be/workspace/models.py` - Watchlist, Shortlist, ShortlistEntry, SquadPlan, RecentActivity
- `get-scouted-be/workspace/migrations/0001_initial.py` - initial migration for all 5 models
- `get-scouted-be/workspace/tests/conftest.py` - player_factory/club_factory + re-exported accounts auth fixtures
- `get-scouted-be/config/settings/base.py` - added `"workspace"` to INSTALLED_APPS

## Decisions Made
- None beyond what the plan specified - followed plan as written, replicating players/clubs' UUID PK + UniqueConstraint/Index convention exactly.

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria (grep checks, `manage.py check`, `makemigrations --check --dry-run`, `migrate`, `pytest --collect-only`) passed on first attempt.

## Issues Encountered
- The ambient pyenv Python (`python` on PATH) lacks `sklearn`, which `scoring/urls.py`'s import chain requires for `manage.py check`/`makemigrations`/`migrate`/`pytest` to run at all (pre-existing, unrelated to this plan — noted in prior phase summaries, e.g. Phase 05's parity tests). Ran all verification commands via the project's existing `get-scouted-be/.venv` instead, which has the full dependency set; no code change was needed.
- `pytest workspace/tests/ --collect-only -q` exits with pytest's standard code 5 ("no tests collected"), not 0, since the conftest currently defines fixtures only and no test files yet (expected for a Wave-0 foundation plan — verified with `-v` that 0 items were collected with zero collection errors, confirming the conftest imports cleanly). The plan's literal "exits 0" acceptance wording doesn't match pytest's real exit-code semantics for an empty test directory, but the substantive intent (conftest imports without error) is satisfied.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `workspace/models.py`, `workspace/permissions.py`, and `workspace/tests/conftest.py` are ready to import for Plan 02 (Watchlist), 03 (Shortlists), 04 (Squad Plans), 05 (Recent Activity), and 06 (CSV export)
- No blockers identified

---
*Phase: 08-user-workspace-crud*
*Completed: 2026-07-25*

## Self-Check: PASSED

All 8 created files verified present on disk; all 3 task commit hashes (638b4d7, bebe6f1, 9d2262e) verified present in git log.
