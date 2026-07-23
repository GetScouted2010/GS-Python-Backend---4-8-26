---
phase: 04-scoring-engine-port
plan: 02
subsystem: api
tags: [django, pandas, service-layer, scoring]

# Dependency graph
requires:
  - phase: 04-scoring-engine-port
    provides: "04-01's reconstruct_population()/Population substrate and null_with_reason() envelope helper"
provides:
  - "get_rmm(player_id): real computed Player Impact (RMM) + full positive/negative/components/reliability breakdown for a single player, Http404 on unknown player"
  - "rmm_breakdown_from_scored(row): reusable breakdown builder from an already-scored pandas row, no re-reconstruction needed"
affects: [04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Service reads breakdown columns directly off add_player_impact's full output (never the oracle's thin RMM-only wrapper), so downstream endpoints get positive/negative/component/reliability data for free"

key-files:
  created:
    - get-scouted-be/scoring/services/rmm.py
    - get-scouted-be/scoring/tests/test_services_rmm.py
  modified: []

key-decisions:
  - "\"Impact Reliability\" is a categorical string (Very Low/Low/Medium/High from impact.py's _reliability_flag), not numeric -- passed through as-is rather than float()-coerced (the plan's illustrative code assumed a float; fixed against real data during Task 2's GREEN run)"
  - "get_rmm never calls compute_rmm_column -- it discards the component/positive/negative breakdown SCORE-05 requires; add_player_impact's full output is the only source of truth for this service"

patterns-established:
  - "rmm_breakdown_from_scored(row) is a pure function over an already-scored row -- Plan 05's summary endpoint can reuse it directly without a second add_player_impact pass"

requirements-completed: []

# Metrics
duration: 24min
completed: 2026-07-23
---

# Phase 4 Plan 02: RMM (Player Impact) Service Summary

**Request-facing `get_rmm(player_id)` service returning the real computed Player Impact score plus its full positive/negative/component/reliability breakdown, sourced strictly from `add_player_impact`'s output columns.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-23T17:41:00+01:00
- **Completed:** 2026-07-23T18:05:00+01:00
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `get_rmm(player_id)` reconstructs the population, runs `add_player_impact` over the whole `players_df`, matches the requested player (string-coercing both the UUID column and the URL-arrival string id), and returns the full breakdown dict -- or raises `Http404` if the player isn't in the population.
- `rmm_breakdown_from_scored(row)` is the pure, reusable breakdown builder: given any already-scored pandas row it returns `{"rmm", "positive", "negative", "components", "reliability"}` (unprefixed component keys) or the shared `null_with_reason("rmm", "insufficient_player_data")` envelope when `"Player Impact"` is NaN -- Plan 05's summary endpoint can call this directly without a second `add_player_impact` pass.
- Verified end-to-end against the real 41,708-player dataset: a real player's RMM breakdown resolves with numeric, unprefixed component keys, and an unknown random UUID raises `Http404`.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Write failing tests for the RMM service (RED)** - `90467d4` (test)
2. **Task 2: Implement the RMM service (GREEN)** - `c308796` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/scoring/services/rmm.py` - `get_rmm(player_id)` + `rmm_breakdown_from_scored(row)`, reading breakdown columns off `add_player_impact`'s output
- `get-scouted-be/scoring/tests/test_services_rmm.py` - real-player breakdown/component-key tests, Http404-on-unknown-player test, synthetic NaN-envelope and dict-shape tests for `rmm_breakdown_from_scored`

## Decisions Made
- `"Impact Reliability"` is a categorical string, not a float -- the plan's illustrative implementation code assumed `float(row["Impact Reliability"])`, which raised `ValueError: could not convert string to float: 'High'` against real data in Task 2's GREEN verification run. Fixed by passing the value through as-is (string or `None`) instead of coercing to float. This is a Rule 1 (auto-fix bug) correction to the plan's example code, not a deviation from the plan's intent.
- `get_rmm` never calls `compute_rmm_column` -- confirmed via grep in the acceptance criteria; only `add_player_impact`'s full output is read, preserving the component/positive/negative breakdown SCORE-05 requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] "Impact Reliability" is a string, not a float -- fixed the plan's illustrative float() coercion**
- **Found during:** Task 2 (GREEN verification against real data)
- **Issue:** The plan's suggested implementation code called `float(row["Impact Reliability"])`. `impact.py`'s `_reliability_flag` actually returns one of `"Very Low"/"Low"/"Medium"/"High"` (a categorical label based on minutes played), never a number. Running the real-player test raised `ValueError: could not convert string to float: 'High'`.
- **Fix:** `rmm_breakdown_from_scored` now returns `row["Impact Reliability"]` unchanged (or `None` if NaN) instead of `float(...)`. Updated the corresponding synthetic dict-shape test to use `"High"` instead of a fabricated float value.
- **Files modified:** `get-scouted-be/scoring/services/rmm.py`, `get-scouted-be/scoring/tests/test_services_rmm.py`
- **Verification:** `python -m pytest scoring/tests/test_services_rmm.py -x --reuse-db` -- 5/5 passed against the real dev dataset after the fix.
- **Committed in:** `c308796` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Necessary correctness fix surfaced only by testing against real data, exactly the kind of gap `real_data_available` real-dataset tests exist to catch. No scope creep -- the fix is scoped entirely to the reliability field's type handling.

## Issues Encountered
- Real-data pytest runs (`--reuse-db` against the 41,708-player dev dataset) took 5+ minutes each due to concurrent CPU/memory contention from other Phase 4 plans executing in parallel (03/04/05/06 waves running simultaneously against the same Postgres instance). Not a code issue; runs completed successfully once contention cleared.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plan 05 (summary endpoint) can `from scoring.services.rmm import get_rmm, rmm_breakdown_from_scored` and reuse `rmm_breakdown_from_scored` directly against its own already-scored rows without re-running `add_player_impact`.
- No changes were made to any file under `scoring/characterization/`.
- SCORE-01 and SCORE-05's RMM slice are functionally complete at the service layer; DRF endpoint wiring is out of scope for this plan (Plans 04-06 per the phase's parallel-plan split).

---
*Phase: 04-scoring-engine-port*
*Completed: 2026-07-23*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/services/rmm.py
- FOUND: get-scouted-be/scoring/tests/test_services_rmm.py
- FOUND: 90467d4 (test commit)
- FOUND: c308796 (feat commit)
