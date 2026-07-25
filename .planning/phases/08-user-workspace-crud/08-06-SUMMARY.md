---
phase: 08-user-workspace-crud
plan: 06
subsystem: api
tags: [django, drf, csv, streaminghttpresponse, workspace, clubs, pytest]

# Dependency graph
requires:
  - phase: 08-user-workspace-crud
    provides: "08-05's ClubDetailView.retrieve() override (RecentActivity logging) and 08-03's ShortlistViewSet + get_object()-based IsOwner enforcement"
provides:
  - "GET /api/workspace/shortlists/{id}/export/ -- streaming CSV of a shortlist's players (IsOwner-gated)"
  - "GET /api/clubs/{id}/export/ -- streaming CSV of a club profile + transfer aggregates (IsAuthenticated)"
  - "workspace app now included in pytest testpaths (previously silently excluded from the full suite)"
affects: [09-ai-layer, any-future-export-features]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Django docs' verbatim Echo + csv.writer + StreamingHttpResponse pattern for zero-buffering CSV export (no new dependency)"
    - "Export endpoints reuse existing read-layer serializers (PlayerListSerializer, ClubDetailSerializer) as the single source of truth for exported columns, so exports never drift from the API"

key-files:
  created:
    - get-scouted-be/workspace/tests/test_csv_export.py
  modified:
    - get-scouted-be/workspace/views.py
    - get-scouted-be/clubs/views.py
    - get-scouted-be/clubs/urls.py
    - get-scouted-be/pyproject.toml

key-decisions:
  - "Duplicated the small Echo helper class into clubs/views.py rather than importing it from workspace, keeping club-data concerns inside the clubs app (per plan's explicit instruction)"
  - "Club export route registered before the <uuid:pk>/ detail route in clubs/urls.py so the more specific /export/ path resolves correctly"
  - "Added workspace to pyproject.toml's pytest testpaths -- a real Phase-8-wide gap (never updated since the app was scaffolded in 08-01), discovered while satisfying this plan's own full-suite verification gate"

patterns-established:
  - "CSV export endpoints stream via StreamingHttpResponse + Echo + stdlib csv.writer, never buffering the whole file in memory"

requirements-completed: [CRUD-10]

# Metrics
duration: 8min
completed: 2026-07-25
---

# Phase 08 Plan 06: CSV Export (Shortlist + Club Report) Summary

**Streaming CSV export for Shortlists (IsOwner-gated, columns from PlayerListSerializer) and Club reports (IsAuthenticated, profile + transfer aggregates from ClubDetailSerializer), using Django's documented Echo/StreamingHttpResponse pattern with zero new dependencies.**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-25T06:56:55+01:00
- **Completed:** 2026-07-25T07:00:43+01:00
- **Tasks:** 3 completed (+ 1 auto-fixed blocking config gap)
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- `GET /api/workspace/shortlists/{id}/export/` streams a text/csv of a shortlist's players, IsOwner-gated via `self.get_object()`, columns exactly matching `PLAYER_EXPORT_COLUMNS` (drawn from `PlayerListSerializer`'s field set)
- `GET /api/clubs/{id}/export/` streams a text/csv of the club profile + transfer aggregates (`total_transfers`, `arrivals`, `departures`, `avg_market_value_at_transfer`, `total_market_value_at_transfer`), reusing `ClubDetailSerializer` so the exported numbers never diverge from the read API; IsAuthenticated only (club data isn't user-owned)
- Both responses stream via `StreamingHttpResponse` + a local `Echo` write-only buffer + stdlib `csv.writer` -- no whole-CSV buffering, no new dependency
- Discovered and fixed a real Phase-8-wide gap: `workspace` was never added to `pyproject.toml`'s pytest `testpaths`, so all of `workspace/tests/` had been silently excluded from every "full suite" run since 08-01; fixed as part of satisfying this plan's own final-gate verification requirement

## Task Commits

Each task was committed atomically:

1. **Task 1: Shortlist CSV export @action + Echo helper** - `a828c4d` (feat)
2. **Task 2: Club report CSV export view + route** - `aa52baa` (feat)
3. **Task 3: test_csv_export.py -- parse both CSVs, ownership + auth** - `0fd52c5` (test)
4. **Deviation fix: workspace missing from pytest testpaths** - `e162ea0` (fix)

**Plan metadata:** (pending) `docs(08-06): complete csv-export plan`

## Files Created/Modified
- `get-scouted-be/workspace/views.py` - Added `Echo` helper + `PLAYER_EXPORT_COLUMNS` + `ShortlistViewSet.export` @action
- `get-scouted-be/clubs/views.py` - Added local `Echo` helper + `ClubExportView` (StreamingHttpResponse of club profile + transfer aggregates)
- `get-scouted-be/clubs/urls.py` - Added `<uuid:pk>/export/` route ahead of the detail route; imports `ClubExportView`
- `get-scouted-be/workspace/tests/test_csv_export.py` - 5 tests: shortlist export parse/columns, shortlist ownership (404), club export parse/columns, Content-Disposition header, unauthenticated denial (401)
- `get-scouted-be/pyproject.toml` - Added `"workspace"` to pytest `testpaths`

## Decisions Made
- Duplicated the Echo helper into `clubs/views.py` rather than cross-app importing from `workspace`, per the plan's explicit instruction to keep club-data concerns inside the clubs app
- Registered `/api/clubs/{id}/export/` before the `<uuid:pk>/` detail route so the more specific path resolves first
- Fixed the `pyproject.toml` testpaths gap inline (Rule 3 -- blocking issue for this plan's own full-suite verification requirement) rather than deferring, since it silently affected every prior Phase 8 plan's "full suite green" claims

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added `workspace` to pytest's `testpaths`**
- **Found during:** Task 3 verification (running the full suite as this plan's final-gate check)
- **Issue:** `pyproject.toml`'s `testpaths` list (`clubs, players, transfers, core, accounts, scoring`) never included `workspace`, so `pytest` (no path argument) silently skipped the entire `workspace/tests/` directory -- all of Phase 8's tests, including this plan's new `test_csv_export.py` -- since the app was scaffolded in 08-01. Every prior Phase 8 plan's "full suite green" verification claim was actually only checking non-workspace apps.
- **Fix:** Added `"workspace"` to the `testpaths` list.
- **Files modified:** `get-scouted-be/pyproject.toml`
- **Verification:** `pytest` (no args) now collects and passes all 32 workspace tests alongside the pre-existing suite: 144 passed, 305 skipped, 0 failed (up from 112 passed/305 skipped when workspace was excluded).
- **Committed in:** `e162ea0`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary to make the plan's own "full suite green (final phase gate)" verification requirement actually true. No scope creep -- config-only, one-line fix.

## Issues Encountered
None beyond the testpaths gap documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 8 (user-workspace-crud) is now feature-complete: Watchlist, Shortlist (+ entries + export), SquadPlan, RecentActivity, and Club export all live under `/api/workspace/` and `/api/clubs/`
- Full backend test suite (144 passed, 305 skipped, 0 failed) is green, now correctly including all of `workspace/tests/`
- Phase 7's players/clubs tests (including 08-05's `ClubDetailView.retrieve()` RecentActivity override) confirmed intact -- `clubs/tests/` still 6 passed / 6 skipped
- Ready for Phase 8 goal-backward verification

---
*Phase: 08-user-workspace-crud*
*Completed: 2026-07-25*

## Self-Check: PASSED

All created/modified files confirmed present on disk; all 4 task/fix commits (a828c4d, aa52baa, 0fd52c5, e162ea0) confirmed present in git log.
