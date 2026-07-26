---
phase: 11-position-needs-squad-simulation
plan: 01
subsystem: api
tags: [django, drf, position-needs, squad-analysis, classification]

# Dependency graph
requires:
  - phase: 10-ai-grounded-report-generation
    provides: "clubs.services.position_needs_aggregate(club) -- the internal per-position ORM aggregation (squad_depth/avg_age/contracts_expiring_within_12mo) this plan layers a classification on top of"
provides:
  - "clubs.services.classify_position_needs(club) -- weak/at-risk/strong classification layered on Phase 10's aggregation, raw numbers preserved"
  - "GET /api/clubs/{id}/position-needs/ public authenticated endpoint (PositionNeedsView)"
affects: [11-02, squad-simulation, position-needs]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Classification-layer-over-aggregation: never re-query, spread raw stats + append a derived label ({**stats, 'classification': label})"

key-files:
  created:
    - get-scouted-be/clubs/tests/test_position_needs.py
    - get-scouted-be/clubs/tests/test_views_position_needs.py
  modified:
    - get-scouted-be/clubs/services.py
    - get-scouted-be/clubs/views.py
    - get-scouted-be/clubs/urls.py

key-decisions:
  - "classify_position_needs thresholds locked by 11-CONTEXT.md: weak if squad_depth<2; at-risk if depth>=2 AND (avg_age>30 OR expiring>=depth/2), checked in that order; strong otherwise"
  - "avg_age None guard is mandatory (Player.age is nullable) -- a None avg_age falls through to the contract-expiry check rather than raising"
  - "position-needs/ route placed above the <uuid:pk>/ catch-all (same pattern as export/ and insights/) to avoid being swallowed"

patterns-established:
  - "Classification layer reuses an existing aggregation via **stats spread rather than duplicating the ORM query -- precedent for any future derived-label feature over position_needs_aggregate"

requirements-completed: [PLAN-01]

# Metrics
duration: 12min
completed: 2026-07-26
---

# Phase 11 Plan 01: Position Needs Classification Endpoint Summary

**GET /api/clubs/{id}/position-needs/ returns a per-position weak/at-risk/strong classification layered on Phase 10's existing squad-depth/avg-age/contract-expiry aggregation, with raw numbers preserved alongside each label.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-26T07:15:00+01:00
- **Completed:** 2026-07-26T07:21:00+01:00
- **Tasks:** 2 completed
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments
- `classify_position_needs(club)` in `clubs/services.py` labels each position weak/at-risk/strong per the locked thresholds, reusing `position_needs_aggregate` (no second `.values()/.annotate()` query added)
- `PositionNeedsView` (GET) exposes the classification at `/api/clubs/{id}/position-needs/`, matching the existing `ClubExportView`/`ClubInsightsView` plain-`APIView` style (no explicit `permission_classes`, natural `Http404` via `get_object_or_404`)
- Route correctly placed above the `<uuid:pk>/` catch-all in `clubs/urls.py`
- 8 tests total (4 unit + 4 integration) all green; full `clubs` app suite has zero regression (25 passed, 6 skipped)

## Task Commits

Each task was committed atomically (TDD RED->GREEN combined into a single commit per task, per the plan's exact-code action blocks):

1. **Task 1: classify_position_needs service + unit tests** - `fe165d4` (test)
2. **Task 2: PositionNeedsView + URL route + integration tests** - `7a9011b` (feat)

**Plan metadata:** (pending) - docs: complete plan

## Files Created/Modified
- `get-scouted-be/clubs/services.py` - added `classify_position_needs(club)`, layered on `position_needs_aggregate`
- `get-scouted-be/clubs/tests/test_position_needs.py` - 4 unit tests (weak/at-risk-by-age/at-risk-by-contract/strong)
- `get-scouted-be/clubs/views.py` - added `PositionNeedsView` (GET)
- `get-scouted-be/clubs/urls.py` - added `position-needs/` route above the `<uuid:pk>/` catch-all
- `get-scouted-be/clubs/tests/test_views_position_needs.py` - 4 integration tests (success payload, route-not-swallowed, 404, 401)

## Decisions Made
- Thresholds and check order (weak -> at-risk -> strong) locked exactly as specified in 11-CONTEXT.md; no ambiguity required a judgment call.
- Used the project's `.venv` (`get-scouted-be/.venv`) to run pytest -- the ambient pyenv interpreter lacks the `anthropic` package required by `clubs/tests/conftest.py`'s autouse safety-net fixture, consistent with prior phases' documented environment note.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' exact code blocks (classify_position_needs implementation, PositionNeedsView, urls.py route) were used verbatim as specified in the plan's `<action>` sections.

## Issues Encountered
None - all 8 new tests passed on first implementation after confirming RED. No pre-existing test regressions surfaced (25 passed, 6 skipped, same skip reasons as before -- missing real dev-DB club data, unrelated to this plan).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `classify_position_needs(club)` is available for Plan 11-02 (squad simulation) to reuse if it needs before/after position-needs comparisons.
- Note: Plan 11-02 execution appears to be running concurrently (commit `c353a48` "test(11-02): add simulate_squad_change service with unit tests" observed interleaved in git history during this plan's execution) -- no conflict with this plan's files, both plans are wave 1 with no `depends_on` between them.

---
*Phase: 11-position-needs-squad-simulation*
*Completed: 2026-07-26*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (fe165d4, 7a9011b) verified present in git history.
