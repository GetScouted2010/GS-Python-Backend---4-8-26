---
phase: 05-scoring-parity-testing
plan: 01
subsystem: testing
tags: [pandas, pytest, oracle-parity, scoring]

# Dependency graph
requires:
  - phase: 03-scoring-engine-curation-correctness-oracle
    provides: "generate_scoring_oracle management command + versioned oracle CSV (scoring_oracle_v1_*.csv)"
  - phase: 04-scoring-engine-port
    provides: "RMM/CS/TFM/TP service functions with the .astype(str) player_id-cast convention this plan centralizes"
provides:
  - "scoring/tests/_parity_helpers.py: find_latest_oracle_csv, load_oracle_df, to_str_index, compare_scalar, compare_series, compare_tfm_series, write_mismatch_report, POSITION_GROUPS, GROUPS_WITH_NULL_CS_TP, RMM_CS_TP_ATOL, TFM_RTOL"
  - "test_oracle_snapshot.py refactored to consume the shared find_latest_oracle_csv (no duplicated glob)"
affects: [05-02-bulk-parity, 05-03-api-sample-parity, 05-04-edge-cases-parity]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared, non-conftest test-helper module (_parity_helpers.py) imported directly by parity test files"
    - "Both-null-aware tolerance comparator: both-null passes, one-null is a hard failure, else abs/rel tolerance"
    - "UUID-object-dtype port index cast to str via to_str_index() before any oracle alignment"

key-files:
  created:
    - get-scouted-be/scoring/tests/_parity_helpers.py
  modified:
    - get-scouted-be/scoring/tests/test_oracle_snapshot.py
    - get-scouted-be/.gitignore

key-decisions:
  - "compare_tfm_series converts the oracle's log-scale tfm column to money scale via np.expm1 before applying the 0.1% relative tolerance, reconciling the CONTEXT.md 'money scale' policy with the verified log-scale oracle column"
  - "write_mismatch_report's output directory (scoring/tests/_parity_reports/) added to .gitignore proactively, since it will be populated by failing runs of Plans 02-04 and should never be committed"

patterns-established:
  - "Single source of truth for oracle discovery/loading/id-casting/tolerance comparison/mismatch reporting -- Plans 02-04 import from _parity_helpers rather than re-implementing any of it"

requirements-completed: [SCORE-06]

# Metrics
duration: 15min
completed: 2026-07-24
---

# Phase 5 Plan 1: Shared Parity Test Helpers Summary

**Shared pandas-based oracle-vs-port parity substrate (`_parity_helpers.py`) providing version-agnostic oracle discovery, 10-group position bucketing, a UUID-to-str id-cast normalizer, and a both-null-aware tolerance comparator with mismatch-report writer.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-24T12:00:00Z
- **Completed:** 2026-07-24T12:13:00Z
- **Tasks:** 2 completed
- **Files modified:** 3

## Accomplishments
- `find_latest_oracle_csv()` / `load_oracle_df()`: version-agnostic glob-based oracle discovery, with `position_group` derived via the port's own `normalise_position()` (no hand-rolled mapping) -- verified live against the real 41,708-row oracle CSV, confirming all 10 position groups present plus the expected garbage `"0"` row, and GK/LB/RB structurally 100% null on cs/transfer_probability
- `to_str_index()`: centralizes the load-bearing `.astype(str)` port-id-cast convention already used in every Phase 4 service, so parity files never re-derive it
- `compare_scalar()` / `compare_series()` / `compare_tfm_series()`: both-null-aware tolerance comparator (both null -> pass, one null -> hard failure, else abs tol 0.01 for RMM/CS/TP or rel tol 0.1% for TFM); `compare_tfm_series` reconciles the oracle's log-scale `tfm` column to money scale via `np.expm1` before comparing
- `write_mismatch_report()`: per-group mismatch-detail CSV writer for debuggable parity-test failures
- `test_oracle_snapshot.py` refactored to import the shared `find_latest_oracle_csv` -- existing suite still passes unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Oracle discovery + oracle-load-with-position-group + UUID->str index helpers** - `64db483` (feat)
2. **Task 2: Both-null-aware tolerance comparator + mismatch-report writer** - `4b51739` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `get-scouted-be/scoring/tests/_parity_helpers.py` - New shared module: oracle discovery/load, id-cast normalizer, tolerance comparator, mismatch-report writer
- `get-scouted-be/scoring/tests/test_oracle_snapshot.py` - Local `_find_latest_oracle_csv` removed in favor of the shared import
- `get-scouted-be/.gitignore` - Added `scoring/tests/_parity_reports/` (generated mismatch-report output, never committed)

## Decisions Made
- TFM tolerance is applied on money scale by converting the oracle's verified log-scale `tfm` column via `np.expm1` inside `compare_tfm_series`, rather than converting the port side to log scale -- keeps the 0.1% bound meaningful in the domain (money) CONTEXT.md specifies.
- Proactively gitignored the future `_parity_reports/` output directory now (Rule 2/3 scope) rather than waiting for Plan 02 to hit an untracked-file cleanup step.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Plan's literal ad-hoc verification snippet used `pandas.Index.eq()`, which doesn't exist in the installed pandas 2.3.2**
- **Found during:** Task 1 automated verification
- **Issue:** The plan's inline `<automated>` check (`to_str_index(s).index.map(type).eq(str).all()`) called `.eq()` on a `pandas.Index`, which raises `AttributeError` in pandas 2.3.2 (`Index` has no `.eq` method, only `Series` does)
- **Fix:** Ran the equivalent check with `all(t is str for t in to_str_index(s).index.map(type))` instead -- confirms the exact same invariant (every index element becomes `str`) without depending on the missing method. `to_str_index()`'s own implementation (`obj.set_axis(obj.index.astype(str))`) is unaffected; this only affected the throwaway verification command, not the deliverable code.
- **Files modified:** None (verification-command-only workaround)
- **Verification:** `ok` printed; equivalent assertion holds
- **Committed in:** N/A (not a code change)

---

**Total deviations:** 1 auto-fixed (1 blocking, verification-script-only, no deliverable code affected)
**Impact on plan:** No scope creep -- the deliverable `_parity_helpers.py` matches the plan's spec exactly; only the throwaway python -c verification incantation needed an environment-compatible substitute.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `_parity_helpers.py` is ready for Plans 02 (bulk parity), 03 (API-sample parity), and 04 (edge-cases parity) to import directly: oracle discovery/loading, id-casting, tolerance comparison, and mismatch reporting are all centralized.
- No blockers. The real oracle CSV (`scoring_oracle_v1_2026-07-22.csv`) is present in the repo and was used to live-verify `load_oracle_df()`'s position-group bucketing and null-column behavior during this plan's execution.

---
*Phase: 05-scoring-parity-testing*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/tests/_parity_helpers.py
- FOUND: get-scouted-be/scoring/tests/test_oracle_snapshot.py
- FOUND: commit 64db483
- FOUND: commit 4b51739
