---
phase: 05-scoring-parity-testing
plan: 03
subsystem: testing
tags: [pytest, oracle-parity, scoring, drf]

# Dependency graph
requires:
  - phase: 05-scoring-parity-testing
    plan: "01"
    provides: "scoring/tests/_parity_helpers.py: load_oracle_df, compare_scalar, POSITION_GROUPS, GROUPS_WITH_NULL_CS_TP, RMM_CS_TP_ATOL, TFM_RTOL"
provides:
  - "scoring/tests/test_parity_api_sample.py: Tier-2 per-request service + DRF endpoint parity on a seeded ~30-player stratified sample, with per-distinct-club memoization"
affects: [05-verifier]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Indirect pytest.mark.parametrize over a fixed, generous static index range, with the real DB-dependent sample resolved lazily inside the indirect fixture -- keeps 'one failing player = one failing test case' compatible with pytest-django's collection-time DB block"
    - "Module-scope sample-building fixture using django_db_blocker.unblock() (mirrors Plan 02's bulk_scored pattern), never a raw collection-time DB query"

key-files:
  created:
    - get-scouted-be/scoring/tests/test_parity_api_sample.py
  modified: []

key-decisions:
  - "Sample construction MUST run inside a fixture that depends on django_db_setup (module-scope 'sample' fixture using django_db_blocker.unblock()), never at collection time via a raw ORM query or a pytest_generate_tests hook -- verified live that pytest-django repoints the ORM connection from the dev DB to a fresh/empty test DB the moment the first django_db_setup-dependent fixture runs, so a collection-time-built sample would silently reference player ids the actual test-time connection can no longer see"
  - "Per-player parametrization uses pytest.mark.parametrize(..., indirect=True) over a fixed, generous static index range (SAMPLE_SLOTS=40, ENDPOINT_SLOTS=6) rather than a dynamically-sized list, since the real sample size can only be known after django_db_setup has run (i.e. inside a fixture, not at collection); unused slots skip cleanly via the same real_data_available-style message used elsewhere in the suite, while every present slot still reports as its own individual pytest pass/fail"
  - "score_population(pop, None) (own-current-club methodology) is the ONLY scored context computed and cached module-wide; every service's score_population import is patched to always return that same cached result regardless of the specific club_name argument the real service code passes in, since score_population(pop, own_club_name) and score_population(pop, None) yield an identical cs_tp row for that one player (both reduce to 'this player vs their own club') -- confirmed by reading get_compatibility/get_transfer_probability/get_financial_fit's own resolve_club_name+score_population call sites"

requirements-completed: []

# Metrics
duration: 55min
completed: 2026-07-24
---

# Phase 5 Plan 3: API-Sample Parity Summary

**Seeded ~30-player stratified sample driven through the real per-request `get_rmm`/`get_compatibility`/`get_financial_fit`/`get_transfer_probability`/`get_summary` service functions and 5 authenticated DRF endpoints, matched against the same oracle CSV Plan 02's bulk path diffs against.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-07-24T15:00:00Z
- **Completed:** 2026-07-24T15:55:00Z
- **Tasks:** 2 completed
- **Files modified:** 1

## Accomplishments

- `_build_sample()`: seeded (`np.random.default_rng(42)`), stratified sample of ~31 (player_id, position_group) tuples drawn from the 10 clubs with the most players (bounds distinct `score_population`/`get_financial_fit` contexts), including 1 GK/LB/RB each and up to 4 players per non-null group (CB/CM/DMF/AMF/LW/RW/CF), preferring rows with a non-null oracle `cs` so the non-null assertions are actually exercised
- `test_rmm_service_parity` / `test_cs_service_parity` / `test_tp_service_parity` / `test_tfm_service_parity` / `test_summary_service_parity`: each sampled player individually parametrized (`pytest.mark.parametrize("player_case", range(40), indirect=True)`) through the real `get_*` service functions, compared to the oracle via the shared `compare_scalar` (TFM converted to money scale via `np.expm1` before comparison); GK/LB/RB explicitly asserted null on both sides (never a fabricated value)
- `test_endpoint_parity`: a handful of sampled players (1 GK/LB/RB + up to 4 non-null-group players) driven through all 5 real authenticated DRF endpoints (`/impact/`, `/compatibility/`, `/financial-fit/`, `/transfer-probability/`, `/summary/?club_id=`), asserting the response JSON matches the oracle; `test_endpoints_require_authentication` confirms an unauthenticated request still returns 401
- `reconstruct_population()`/`score_population(pop, None)` memoized module-wide (test_views.py's `_CACHE`/`_pop()`/`_scored()` pattern) so the whole ~31-player x 5-score parity sweep pays the ~90s reconstruction/scoring cost once, not per player
- **Verified live against the real dev DB** (via `manage.py shell`, since this sandbox's pytest test database is empty and every real-data test in this suite correctly skips against it): all 6 probed service-level players (GK/LB/RB/CB x3) passed RMM/CS/TP/TFM/summary parity, and all 5 probed endpoint-level players (GK + CB x4) passed all 5 endpoint checks plus the 401 unauthenticated check

## Task Commits

Each task was committed atomically:

1. **Task 1: Seeded stratified sample + memoized per-request service parity** - `0728026` (test)
2. **Task 2: DRF endpoint parity for a handful of sampled players** - `d99c56e` (test)

**Plan metadata:** (pending final commit)

## Files Created/Modified

- `get-scouted-be/scoring/tests/test_parity_api_sample.py` - New Tier-2 parity test: seeded stratified sample + memoized per-request service function parity (Task 1) and real authenticated DRF endpoint parity for a handful of those players (Task 2)

## Decisions Made

- Sample construction runs inside a module-scope `sample` fixture gated by `django_db_setup`/`django_db_blocker.unblock()`, never at collection time -- a collection-time raw ORM query would see the (populated) dev DB via Django's default connection settings, while the actual test bodies run against pytest-django's separate (usually empty) test DB after `django_db_setup` repoints the connection; building the sample against one DB and using those ids against a different DB's connection would silently produce spurious `DoesNotExist`/all-null mismatches. This was caught and fixed during this plan's own execution via a live probe.
- Per-player fan-out uses `pytest.mark.parametrize(..., indirect=True)` over a fixed, generous static index range (`SAMPLE_SLOTS=40`, `ENDPOINT_SLOTS=6`) with the real sample resolved lazily inside the indirect fixture, rather than building the parametrize list directly from a DB query at collection time (which pytest-django structurally disallows without deliberately unblocking a still-dev-DB-pointed connection, per the point above) -- this keeps the plan's "single failing player = single failing test case" requirement intact while staying correct regardless of which DB pytest-django actually ends up using.
- `score_population(pop, None)` is the only scored context ever computed/cached; every service module's `score_population` import is patched to always return that cached result regardless of the specific `club_name` the real code passes in, since for the ONE player under test, `score_population(pop, own_club_name)` and `score_population(pop, None)` compute an identical cs_tp row (both mean "this player vs their own current club").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Per-player `@pytest.mark.parametrize` cannot be built from a raw collection-time DB query under pytest-django**
- **Found during:** Task 1, while implementing the plan's literal `@pytest.mark.parametrize` over the sample suggestion
- **Issue:** Live-probed that pytest-django blocks all DB access at collection time (`RuntimeError: Database access not allowed`), and even bypassing that block via the internal `django_db_blocker` stash key at collection time queries the WRONG database -- Django's default connection still points at the dev DB at collection, but pytest-django repoints it to a separate (typically empty) test DB the moment the first `django_db_setup`-dependent fixture actually runs during test execution. A sample built at collection time and then looked up by id inside an actual `@pytest.mark.django_db` test body raised `Player.DoesNotExist` even though the same ids resolved fine moments earlier.
- **Fix:** Build the sample inside a module-scope fixture that depends on `django_db_setup`/`django_db_blocker` (mirroring Plan 02's `bulk_scored` pattern exactly), and use `pytest.mark.parametrize(..., indirect=True)` over a fixed static index range with the real sample resolved lazily per-slot inside `player_case`/`endpoint_case` -- both the sample and every score lookup then consistently use whichever DB pytest-django actually bound to for that test run.
- **Files modified:** `get-scouted-be/scoring/tests/test_parity_api_sample.py` (the whole fixture/parametrize structure, before any content was committed)
- **Verification:** Live-probed with a throwaway script confirming (a) collection-time raw queries fail, (b) a `django_db_setup`-gated module-scope fixture correctly sees the SAME (empty, in this sandbox) DB the actual test bodies see, and (c) the final indirect-parametrize design skips cleanly end-to-end (`pytest scoring/tests/test_parity_api_sample.py -q` -> `1 passed, 206 skipped`)
- **Committed in:** `0728026`, `d99c56e`

---

**Total deviations:** 1 auto-fixed (1 blocking, structural test-design fix -- no change to the underlying scoring logic being tested)
**Impact on plan:** No scope creep. The plan's literal `@pytest.mark.parametrize` suggestion was adapted to `indirect=True` over a static slot range to stay compatible with pytest-django's DB-connection lifecycle; every other must_have (seeded stratified sample, GK/LB/RB null propagation, memoized `score_population`, real service + DRF endpoint calls, `str(pid)` oracle lookups, `compare_scalar`-only comparisons) is implemented exactly as specified.

## Issues Encountered

- This sandbox's pytest test database has no migrated real data (every real-data test in the existing suite -- e.g. `test_views.py` -- also skips against it, confirmed before making any changes), so `pytest scoring/tests/test_parity_api_sample.py -q` in this environment exercises the skip path (`1 passed, 206 skipped`), which is an explicitly accepted pass condition per the plan's own verification/acceptance criteria ("exits 0 ... or skips cleanly on empty DB").
- To confirm the actual parity logic is correct (not just that it skips cleanly), the sample-building + per-service + per-endpoint logic was additionally run live against the REAL dev DB via `manage.py shell` (bypassing pytest's test-DB indirection entirely): 6 service-level players (GK, LB, RB, CB x3) and 5 endpoint-level players (GK + CB x4, plus the unauthenticated-401 check) all passed every RMM/CS/TP/TFM/summary/endpoint assertion, confirming the file's logic is correct against real data, not just well-formed.
- Noticed in passing (out of scope for this plan, not touched): `get-scouted-be/scoring/tests/test_parity_bulk.py` (Plan 02's deliverable) exists on disk but is untracked in git, and `get-scouted-be/scoring/tests/test_parity_edge_cases.py` (Plan 04's deliverable) is already committed (2 commits) despite `.planning/STATE.md` still showing "Plan: 2 of 4" / "Completed 05-01-PLAN.md" and no `05-02-SUMMARY.md`/`05-04-SUMMARY.md` existing yet -- these plans appear to have been executed out of band (parallel wave execution) without their own SUMMARY/STATE bookkeeping being finished. Left entirely untouched per this plan's scope boundary; flagged here for the orchestrator's visibility.

## User Setup Required

None - no external service configuration required. Running this suite against real data requires the dev DB's real migrated Player data to be reachable as pytest's active test database (either via `--reuse-db` against a test DB that was itself seeded with `manage.py import_all`, or an equivalent DATABASES/TEST configuration) -- outside this plan's scope, and every test in this file already degrades gracefully (skips) without it.

## Next Phase Readiness

- `test_parity_api_sample.py` is ready for the phase-level verifier alongside Plan 02's bulk suite and Plan 04's edge-case suite -- together they cover SCORE-06's bulk-path, per-request-path, and named-edge-case parity requirements.
- No blockers for this plan. The out-of-band state of Plans 02/04 noted above (untracked `test_parity_bulk.py`, missing `05-02-SUMMARY.md`/`05-04-SUMMARY.md`, stale `STATE.md` position) may need orchestrator attention before the phase can be marked complete, but does not block this plan's own deliverable.

---
*Phase: 05-scoring-parity-testing*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/tests/test_parity_api_sample.py
- FOUND: commit 0728026
- FOUND: commit d99c56e
