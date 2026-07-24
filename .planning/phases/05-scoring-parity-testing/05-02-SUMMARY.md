---
phase: 05-scoring-parity-testing
plan: 02
subsystem: testing
tags: [pandas, pytest, oracle-parity, scoring, bulk]

# Dependency graph
requires:
  - phase: 05-scoring-parity-testing
    plan: 01
    provides: "_parity_helpers.py: load_oracle_df, to_str_index, compare_series, compare_tfm_series, POSITION_GROUPS, GROUPS_WITH_NULL_CS_TP, RMM_CS_TP_ATOL, write_mismatch_report"
provides:
  - "scoring/tests/test_parity_bulk.py: Tier-1 full-population bulk-path parity for RMM/CS/TP/TFM, parametrized over the 10 real position groups, one score_population(pop, None) call for the whole module"
affects: [05-03-api-sample-parity, 05-04-edge-cases-parity, 05-05-verifier]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Module-scope django_db_blocker.unblock() gate for a once-per-module expensive real-DB bulk computation (mirrored independently by 05-04's test_parity_edge_cases.py in the same wave)"
    - "10-way @pytest.mark.parametrize(\"group\", POSITION_GROUPS) so pytest natively reports one pass/fail per real position group"

key-files:
  created:
    - get-scouted-be/scoring/tests/test_parity_bulk.py
  modified: []

key-decisions:
  - "bulk_scored is a single module-scope fixture depending on django_db_setup + django_db_blocker (not the function-scope real_data_available/db fixtures, which module-scope fixtures can't consume) -- runs reconstruct_population()+score_population(pop, None) exactly once for all 31 tests in the file"
  - "oracle_and_port is a second module-scope fixture that string-indexes the port's RMM/CS/TP Series via to_str_index() once, so every parametrized group test just slices/reindexes against pre-aligned Series rather than re-casting per group"
  - "CS/TP tests add an explicit both-sides-null assertion for GK/LB/RB (guarded by GROUPS_WITH_NULL_CS_TP) in addition to the both-null-passes comparator -- guards against a future regression silently fabricating CS/TP for those groups without failing a bare pass/fail check"
  - "TFM parity test reuses bulk_scored (no second reconstruct_population()/score_population() call); replicates generate_scoring_oracle.py Steps 3-4 exactly via financial_fit._merge_tfm_feature_columns + raw (log-scale) pipeline.predict(X) masked by _has_club_context; np.expm1 applied exactly once, solely to satisfy compare_tfm_series' money-scale contract"

requirements-completed: []

# Metrics
duration: 25min
completed: 2026-07-24
---

# Phase 5 Plan 2: Full-Population Bulk Parity Test Summary

**Tier-1 bulk-path parity test (`test_parity_bulk.py`) running the port's `reconstruct_population()`+`score_population(pop, None)` once over all ~41,708 real players, diffed against the committed oracle CSV, parametrized over the 10 real position groups for RMM/CS/TP plus one whole-population raw-log-scale TFM check -- all 31 tests pass against the real dev DB.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-24T14:40:00Z
- **Completed:** 2026-07-24T15:05:00Z
- **Tasks:** 2 completed
- **Files modified:** 1

## Accomplishments
- `bulk_scored` (module-scope fixture, `django_db_blocker.unblock()` pattern): runs `reconstruct_population()` + `score_population(pop, None)` exactly once for the whole file (~75-115s), skipping cleanly if the dev DB has no Player rows
- `oracle_and_port` (module-scope fixture): loads the oracle CSV once and string-indexes the port's RMM/CS/TP Series via the shared `to_str_index()` helper, fixing the UUID-vs-str alignment blocker documented in the plan's critical corrections
- `test_rmm_parity_per_group` / `test_cs_parity_per_group` / `test_tp_parity_per_group`: each `@pytest.mark.parametrize("group", POSITION_GROUPS)` over the 10 real position groups, giving pytest one native pass/fail per group per score (30 tests total) -- satisfies ROADMAP's explicit "reports pass/fail for every position group" clause
- CS/TP tests additionally assert both oracle and port are 100% null for GK/LB/RB (`GROUPS_WITH_NULL_CS_TP`), not just relying on the both-null comparator to pass silently
- `test_tfm_parity_bulk`: replicates `generate_scoring_oracle.py`'s Step 3-4 exactly -- merges the 4 upstream RMM/CS/TP columns via `financial_fit._merge_tfm_feature_columns`, builds features via `build_oracle_player_features`, calls raw (log-scale) `pipeline.predict(X)` masked by `_has_club_context`, then converts to money via the single `np.expm1` call feeding `compare_tfm_series`
- Verified end-to-end against the real 41,708-player dev DB (project `.venv` with sklearn installed, since the sandbox's default interpreter lacked it): **31/31 tests passed** (10 RMM + 10 CS + 10 TP + 1 TFM)

## Task Commits

Each task was committed atomically:

1. **Task 1: Module-scope bulk scoring fixture + RMM/CS/TP parity parametrized over 10 groups** - `073e373` (feat)
2. **Task 2: Bulk TFM parity (raw log-scale predict, replicating generate_scoring_oracle Step 3-4)** - `ce8acf6` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `get-scouted-be/scoring/tests/test_parity_bulk.py` - New Tier-1 bulk-path parity test: module-scope `bulk_scored`/`oracle_and_port` fixtures, 3 parametrized RMM/CS/TP tests (10 groups each), 1 whole-population TFM test

## Decisions Made
- Used `django_db_blocker.unblock()` directly (depending on `django_db_setup`/`django_db_blocker`) for the module-scope `bulk_scored` fixture rather than trying to force function-scope `db`/`real_data_available` fixtures into module scope -- the only way pytest-django supports a once-per-module expensive DB computation. A sibling Wave-2 plan (05-04, executing concurrently) independently arrived at the identical pattern for its own module-scope real-data gate, confirming this as the project's converged convention for heavy-real-data test files.
- All comparison/tolerance/id-cast logic is delegated entirely to `_parity_helpers` (Plan 01) -- no re-implementation of `np.isclose`, `.astype(str)`, or a position-group literal in this file, per the plan's explicit constraint.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Sandbox's default Python interpreter (pyenv 3.12.3) has no `scikit-learn` installed**
- **Found during:** Automated verification of Task 1/Task 2
- **Issue:** Running `pytest` with the system/pyenv Python succeeded for the RMM/CS/TP tests (which don't import sklearn) but would have failed the TFM test's `build_oracle_player_features` import chain (`tfm_model.py` imports `sklearn.compose.ColumnTransformer` etc.) with `ModuleNotFoundError`. The project's own `get-scouted-be/.venv` (already provisioned with sklearn 1.9.0, presumably by an earlier phase's setup) was available and unaffected.
- **Fix:** Ran verification via `get-scouted-be/.venv/bin/python -m pytest` instead of the ambient `pytest` on PATH. No code changes required -- this is purely an interpreter-selection issue in the execution environment, not a defect in the deliverable.
- **Files modified:** None
- **Verification:** `.venv/bin/python -m pytest scoring/tests/test_parity_bulk.py -q` -> 31 passed
- **Committed in:** N/A (verification-environment-only, no deliverable code affected)

---

**Total deviations:** 1 auto-fixed (1 blocking, verification-environment-only, no deliverable code affected)
**Impact on plan:** No scope creep -- `test_parity_bulk.py` matches the plan's spec exactly (fixtures, parametrization, string-casting, TFM replay); only the interpreter used to invoke pytest needed to be the project's own `.venv` (which already has all scientific-Python dependencies installed) rather than the ambient system Python.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required. (Verification requires the project's `get-scouted-be/.venv` with `scikit-learn` installed and a Postgres `getscouted` database populated via Phase 1's `import_all`, both of which were already present in this environment.)

## Next Phase Readiness
- `test_parity_bulk.py` is complete and green (31/31) against the real dev DB; SCORE-06 is NOT marked complete in REQUIREMENTS.md per this plan's explicit instruction -- it is only satisfied once all 4 plans of Phase 5 (bulk, API-sample, edge-cases, verifier) pass together.
- Plans 03 (API-sample) and 04 (edge-cases) were observed executing concurrently in the same Wave 2 (their test files, `test_parity_api_sample.py` and `test_parity_edge_cases.py`, already existed on disk mid-execution) -- no file conflicts with this plan's `test_parity_bulk.py`.
- No blockers for the remaining Phase 5 plans.

---
*Phase: 05-scoring-parity-testing*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/tests/test_parity_bulk.py
- FOUND: commit 073e373
- FOUND: commit ce8acf6
