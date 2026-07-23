---
phase: 04-scoring-engine-port
plan: 06
subsystem: api
tags: [drf, apiview, urls, jwt-auth, scoring]

# Dependency graph
requires:
  - phase: 04-scoring-engine-port (Plans 01-05)
    provides: rmm/compatibility/financial_fit/transfer_probability/summary service functions (all Http404 + null+reason-envelope-aware)
provides:
  - Five authenticated DRF endpoints under /api/scoring/ exposing RMM, Compatibility, Financial Fit, Transfer Probability, and the combined Player Profile summary
  - config/urls.py wiring for scoring.urls (the second API surface in the project besides accounts)
affects: [phase-05-parity-testing, phase-06-caching]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin APIView: validate (get_object_or_404) -> delegate to scoring.services.* -> Response(dict), zero scoring math in views"
    - "No explicit permission_classes -- relies on global DEFAULT_PERMISSION_CLASSES=[IsAuthenticated]"
    - "club_id as a path segment for player-scoped-to-club endpoints, but a query param on the combined /summary/ endpoint"

key-files:
  created:
    - get-scouted-be/scoring/views.py
    - get-scouted-be/scoring/urls.py
    - get-scouted-be/scoring/tests/test_views.py
  modified:
    - get-scouted-be/config/urls.py

key-decisions:
  - "Views call service functions and wrap the raw dict directly in Response() -- no serializer class from serializers.py (Plan 05) is invoked; the plan's literal task-2 action code specifies this shape and acceptance criteria only check for get_object_or_404 + from scoring.services, not serializer usage"
  - "Service calls are never wrapped in try/except -- Http404 (unknown player/club) and ValueError (reconstruction bugs) are left to propagate naturally to DRF's exception handler (404/500), never swallowed into a fabricated null response"
  - "test_views.py reuses the SAME module-scope real-data population caching pattern already established by test_services_summary.py/test_services_financial_fit.py (patching each service module's imported reconstruct_population/score_population names) so this file also pays the ~1min reconstruction cost at most once per distinct context, while still exercising the real view -> real service call chain end-to-end via APIClient"

patterns-established:
  - "Pattern: thin API-surface wiring for scoring.services.* -- config/urls.py include('scoring.urls') alongside include('accounts.urls'); scoring/urls.py path() list mirrors accounts/urls.py's structure"

requirements-completed: [SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05]

# Metrics
duration: 16min
completed: 2026-07-23
---

# Phase 4 Plan 6: DRF API Surface for the Scoring Engine Summary

**Five authenticated DRF endpoints (RMM, Compatibility, Financial Fit, Transfer Probability, combined Summary) wired under `/api/scoring/`, each a thin delegator to Plans 01-05's service layer with zero scoring math inline.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-07-23T23:04:00Z (approx, from prior plan's completion commit)
- **Completed:** 2026-07-23T23:17:03Z
- **Tasks:** 2
- **Files modified:** 4 (2 created + urls.py created + config/urls.py edited; plus test_views.py created in Task 1)

## Accomplishments

- All 5 endpoints (`/players/<id>/impact/`, `/players/<id>/clubs/<club_id>/compatibility/`, `.../financial-fit/`, `.../transfer-probability/`, `/players/<id>/summary/?club_id=<uuid>`) live under `/api/scoring/`, each returning a real computed score + breakdown from the Plan 01-05 service layer
- Every endpoint inherits the project's global `IsAuthenticated` + `JWTAuthentication` defaults with zero bespoke permission classes -- verified via a parametrized `test_endpoints_require_authentication` sweep across all 5 URLs
- Views stay strictly thin: `get_object_or_404` for player validation, `from scoring.services import ...` delegation, `Response(result)` -- no scoring math, no swallowed reconstruction errors
- End-to-end manual verification against the real 41,708-player dev DB via `manage.py shell`: real RMM score returned (200, ~13s reconstruction), 401 unauthenticated, 404 unknown player, 400 missing `club_id` on `/summary/`

## Task Commits

Each task was committed atomically:

1. **Task 1: Write failing DRF integration tests for all 5 endpoints + auth gate (RED)** - `11d7bcb` (test)
2. **Task 2: Implement the 5 views, wire scoring/urls.py and config/urls.py (GREEN)** - `ee6a185` (feat)

_TDD flow: RED (11d7bcb, routes unwired -> 404s) -> GREEN (ee6a185, all URLs wired, real+auth tests pass)._

## Files Created/Modified

- `get-scouted-be/scoring/views.py` - 5 thin `APIView` subclasses (`PlayerImpactView`, `CompatibilityView`, `FinancialFitView`, `TransferProbabilityView`, `PlayerScoreSummaryView`)
- `get-scouted-be/scoring/urls.py` - `path()` patterns for all 5 endpoints, named for `reverse()` lookups
- `get-scouted-be/config/urls.py` - added `path("api/scoring/", include("scoring.urls"))` alongside the existing `accounts.urls` include
- `get-scouted-be/scoring/tests/test_views.py` - `APIClient`-based integration tests: auth gate (parametrized over all 5 URLs), one real-data 200-path test per endpoint, unknown-player 404 test

## Decisions Made

- Followed the plan's literal Task 2 action code verbatim: views return `Response(service_function(...))` directly, no `serializers.py` (Plan 05) classes instantiated -- acceptance criteria and must_haves only required `get_object_or_404` + service-layer delegation, not serializer usage, so this was not treated as a gap needing a Rule-2 fix.
- Reused the exact module-scope real-data caching pattern from `test_services_summary.py`/`test_services_financial_fit.py` (patching `reconstruct_population`/`score_population` per service module) in the new `test_views.py`, so the 6 real-data endpoint tests pay the expensive reconstruction cost at most twice (once club-scoped, once club-agnostic for `/financial-fit/`) for the whole file rather than once per test, while still exercising the real view -> real service chain (no service-internal function is mocked).

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's provided code/action blocks; no Rule 1-4 auto-fixes were needed.

## Issues Encountered

- Initial `pytest` invocation used the system Python (no `sklearn` installed) instead of the project's `.venv` -- resolved by activating `.venv/bin/activate` before running tests; not a code defect, just an environment-activation step. No files changed as a result.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- SCORE-01 through SCORE-05's "exposed via API" clause is satisfied: all 5 scoring endpoints are reachable, authenticated, and return real computed values sourced from the faithfully-ported Plan 01-05 service layer.
- Full `scoring` test suite is green (53 passed, 36 skipped against the empty pytest-django test DB -- real-data assertions verified manually against the populated dev DB via `manage.py shell`, consistent with every other scoring test file's established convention).
- Phase 4 (scoring-engine-port) is functionally complete and ready for Phase 5's parity testing against the Phase 3 oracle snapshot -- the port is "correct-but-slow" (real reconstruction ~13s-1min per request), which Phase 6 (caching) is expected to address.
- No edits were made to any `scoring/characterization/` file in this plan.

---
*Phase: 04-scoring-engine-port*
*Completed: 2026-07-23*

## Self-Check: PASSED

All created files and both task commits verified present:
- FOUND: get-scouted-be/scoring/views.py
- FOUND: get-scouted-be/scoring/urls.py
- FOUND: get-scouted-be/scoring/tests/test_views.py
- FOUND: get-scouted-be/config/urls.py
- FOUND: .planning/phases/04-scoring-engine-port/04-06-SUMMARY.md
- FOUND: 11d7bcb (RED commit)
- FOUND: ee6a185 (GREEN commit)
