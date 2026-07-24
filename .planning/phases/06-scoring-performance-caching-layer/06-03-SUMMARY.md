---
phase: 06-scoring-performance-caching-layer
plan: 03
subsystem: scoring
tags: [django, management-command, bulk_update, pandas, denormalization]

# Dependency graph
requires:
  - phase: 06-scoring-performance-caching-layer
    plan: "06-01"
    provides: "Player.impact_score/compatibility_score/financial_fit_score/transfer_probability_score nullable FloatFields + the reconstruct.py collision fix"
  - phase: 06-scoring-performance-caching-layer
    plan: "06-02"
    provides: "clear_scoring_caches() and get_tfm_pipeline() from scoring.services.population"
provides:
  - "recompute_scores management command -- the operator-triggered rebuild flow that populates the 4 denormalized Player score fields for the whole population"
  - "Live-verified real counts: impact_score 41707/41708 non-null, compatibility_score/transfer_probability_score 15051 non-null (26657 null by design, GK/LB/RB), financial_fit_score 41708/41708 non-null, money-scale range ~496K-26.4M"
affects: ["06-04", "07-crud"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Management command replicates generate_scoring_oracle.py's exact RMM-first orchestration (raw build_* + compute_* functions, not the Population/score_population wrapper) but writes to Player.bulk_update instead of a CSV, reusing only get_tfm_pipeline()'s memoized loader from Plan 02"

key-files:
  created:
    - get-scouted-be/scoring/management/commands/recompute_scores.py
    - get-scouted-be/scoring/tests/test_recompute_scores.py
  modified: []

key-decisions:
  - "recompute_scores.py reuses generate_scoring_oracle.py's raw building-block functions (compute_rmm_column, compute_cs_tp_for_pairs, build_players_df/build_role_scores_wide/build_team_styles_df/build_transfers_df, build_oracle_player_features) rather than Plan 02's Population/score_population/get_scored_population wrapper -- only get_tfm_pipeline() is reused from population.py, per the plan's explicit interface spec, keeping this command a faithful byte-for-byte replica of the proven oracle orchestration"
  - "clear_scoring_caches() called both before (fresh read, not a stale in-process cache) and after (next live request rebuilds) the atomic bulk_update write"
  - "financial_fit_score is stored money-scale via np.expm1(predicted_fee), matching financial_fit.py:118's identical unwrap -- never the raw log-scale TFM output"
  - "Test file's module-scope recompute_run fixture uses django_db_blocker.unblock() (matching test_parity_bulk.py's bulk_scored pattern) to invoke call_command, but each assertion test function additionally needs @pytest.mark.django_db to query Player.objects afterward -- the unblock() context only covers the fixture's own body, not downstream test functions"

patterns-established:
  - "A module-scope django_db_blocker.unblock() fixture that performs a DB write (not just a read) still requires downstream assertion test functions to carry their own @pytest.mark.django_db, since the unblock context closes when the fixture returns"

requirements-completed: []  # SCORE-07 not marked complete here -- only satisfied once the full phase (all 4 plans + verifier) passes

# Metrics
duration: 17min
completed: 2026-07-24
---

# Phase 6 Plan 3: recompute_scores Management Command Summary

**Added the `recompute_scores` management command that reruns generate_scoring_oracle.py's proven RMM-first orchestration over the full 41,708-player population and atomically bulk_updates the 4 denormalized own-club score fields onto Player, live-verified against the real dev DB (impact_score 41707/41708, compatibility_score/transfer_probability_score 15051/41708 non-null by design, financial_fit_score 41708/41708 money-scale ~496K-26.4M).**

## Performance

- **Duration:** 17 min
- **Started:** 2026-07-24T20:51:49+01:00 (prior plan's completion commit)
- **Completed:** 2026-07-24T21:08:46+01:00
- **Tasks:** 2/2 completed
- **Files modified:** 2 (both created)

## Accomplishments

- `python manage.py recompute_scores` is a registered, working command reusing `generate_scoring_oracle.py`'s exact RMM-first orchestration (RMM computed first and merged as `player_impact` before `compute_cs_tp_for_pairs`, which raises `ValueError` without it)
- `financial_fit_score` is written money-scale via `np.expm1(predicted_fee)`, matching `financial_fit.py:118`'s identical unwrap precedent
- All 4 Player fields are written via a single atomic `transaction.atomic()` + `bulk_update` (batch_size=1000, configurable via `--batch-size`) -- a live request never observes a half-written intermediate state
- `clear_scoring_caches()` is called both before (fresh read, no stale in-process cache) and after (next live request rebuilds) the write
- NaN is coerced to `None` (`pd.isna(v)` check) before assignment, so structurally-null scores (GK/LB/RB CS/TP) are written as real SQL NULL, never a fabricated 0
- Live-verified against the real 41,708-player dev DB via `python manage.py recompute_scores`:
  - `impact_score`: 41707 non-null
  - `compatibility_score`: 15051 non-null / 26657 null (GK/LB/RB by design)
  - `financial_fit_score`: 41708 non-null, range ~€496,104 - €26,436,188 (money-scale, confirmed none `< 100`)
  - `transfer_probability_score`: 15051 non-null (matches compatibility_score's null pattern, as expected since both derive from the same `compute_cs_tp_for_pairs` call)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement the recompute_scores management command** - `0539357` (feat)
2. **Task 2: Real-data test that recompute_scores populates the 4 Player fields with correct null-propagation** - `fd5ef7e` (test)

**Plan metadata:** (final commit below)

## Files Created/Modified

- `get-scouted-be/scoring/management/commands/recompute_scores.py` -- the `recompute_scores` BaseCommand: reconstructs the population, computes RMM/CS/TP/TFM in the oracle's exact order, converts TFM to money-scale, atomically bulk_updates the 4 Player fields, clears caches before and after
- `get-scouted-be/scoring/tests/test_recompute_scores.py` -- 3 real-data tests (population, null-propagation, money-scale sanity) behind a module-scope `django_db_blocker.unblock()` fixture that runs the command once

## Decisions Made

- Followed the plan's explicit interface spec literally: reused only `get_tfm_pipeline()` from `scoring.services.population` (Plan 02), not `reconstruct_population()`/`get_scored_population()`/`score_population()` -- the command instead calls the same raw `build_*`/`compute_*` functions `generate_scoring_oracle.py` calls directly, keeping it a faithful, independently-auditable replica of the proven oracle orchestration rather than an indirect wrapper
- `clear_scoring_caches()` is called at the very start (in case a prior request in the same process already primed `reconstruct_population`'s or `get_scored_population`'s cache) even though this command's own DataFrame reconstruction bypasses those caches entirely (it calls the raw `build_*` functions) -- this guards against any *other* code path in the same process reading stale cached data mid-command
- Per-player `Player(id=pid, ...)` instances are constructed with only the 4 score fields + pk set (not full rows fetched from the DB) to keep `bulk_update`'s memory footprint low across 41,708 rows

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test functions needed `@pytest.mark.django_db` in addition to the module-scope `django_db_blocker.unblock()` fixture**
- **Found during:** Task 2, first pytest run
- **Issue:** The `recompute_run` module-scope fixture correctly used `django_db_blocker.unblock()` to run `call_command("recompute_scores")`, but the downstream test functions (`test_recompute_scores_populates_all_four_fields`, etc.) queried `Player.objects` directly and failed with `RuntimeError: Database access not allowed` -- the unblock context only covers the fixture body itself, not the test functions that consume its return value (unlike `test_parity_bulk.py`'s pattern, where downstream tests only read already-fetched pandas objects, never touch the ORM again).
- **Fix:** Added `@pytest.mark.django_db` to each of the 3 test functions so pytest-django grants them their own DB access to query the already-written data.
- **Files modified:** `get-scouted-be/scoring/tests/test_recompute_scores.py`
- **Commit:** `fd5ef7e` (fixed before first commit of this file, not a separate commit)

### Process Note (not a Rule 1-4 deviation)

An initial local pytest run (before the `@pytest.mark.django_db` fix) unexpectedly took ~125s and appeared to process real-sized data before failing with the `RuntimeError`, suggesting a possibly-stale leftover test database from a prior session. Once fixed, subsequent runs consistently and quickly (<2s) skip cleanly against pytest's own isolated, empty `test_getscouted` database (verified: only `getscouted`, not `test_getscouted`, exists in Postgres after the run -- Django's default teardown destroys the test DB each session). This matches every other real-data test file in the codebase; live verification is done separately via `manage.py recompute_scores` against the real dev DB, as required by the plan's acceptance criteria.

**Total deviations:** 1 auto-fixed (Rule 1, test DB-access marker), 1 process note (transient/unreproduced timing anomaly, no functional impact -- final behavior confirmed correct and stable).

## Issues Encountered

None beyond the auto-fixed test-marker issue above.

## User Setup Required

None -- no external service configuration required. The command was run once against the real dev DB by this executor as part of verification (see Accomplishments); an operator would rerun `python manage.py recompute_scores` after any future data refresh (Phase 1 re-import, TFM retrain, etc).

## Next Phase Readiness

- The 4 denormalized Player score fields now hold real own-club values for the full population, ready for Plan 04's live-path timing/caching verification (list/browse/sort endpoints reading these plain indexed columns with no scoring math in the request cycle)
- `clear_scoring_caches()` is wired into the command's write path, so Plan 04 can verify the live in-process caches (`reconstruct_population`/`get_scored_population`) correctly rebuild against this freshly-written data on the next request
- No blockers for Plan 04

---

*Phase: 06-scoring-performance-caching-layer*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/management/commands/recompute_scores.py
- FOUND: get-scouted-be/scoring/tests/test_recompute_scores.py
- FOUND: 0539357 (Task 1 commit)
- FOUND: fd5ef7e (Task 2 commit)
