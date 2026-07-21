---
phase: 01-data-foundation
plan: 06
subsystem: database
tags: [django, pandas, bulk_create, etl, import-report, players, melt]

# Dependency graph
requires:
  - phase: 01-data-foundation (Plan 05)
    provides: Player rows (41,708) with unique_id populated, players/tests/test_import.py (additive test file)
provides:
  - players/management/commands/import_position_roles.py (wide->long PlayerRoleScore import, idempotent upsert)
  - test_role_score_coverage appended to players/tests/test_import.py
  - Reviewed full-dataset import report (core/import_reports/Positions_20260721T013758Z.{json,md})
  - PlayerRoleScore table populated: 230,139 rows, 40 distinct sanitized role_names, 3,081 GK players confirmed at zero rows
affects: [01-07, 01-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wide->long normalization: pd.read_csv(nrows=0) to get per-file role columns dynamically (each of the 9 Positions/*.csv files has a different column set), then df.melt(id_vars=['UniqueID'], value_vars=role_columns, var_name='role_name_raw', value_name='score') per file, accumulating one PlayerRoleScore per (player, role)"
    - "sanitize_role_name(raw): strip parens, re.sub non-alnum runs to a single underscore, strip/lowercase -- keeps role_name_raw as the untouched original header alongside the sanitized role_name for traceability"
    - "Nullable Int64 dtype (not int64) for a natural-key join column when the source CSV may have blank trailing rows -- lets missing values be flagged and skipped per-row instead of crashing pd.read_csv entirely"
    - "Command tolerates a partial set of expected filenames (skips absent ones silently) rather than requiring all 9 Positions/*.csv files to be present -- exercised directly by the fixture-driven test"

key-files:
  created:
    - get-scouted-be/players/management/commands/import_position_roles.py
  modified:
    - get-scouted-be/players/tests/test_import.py
    - get-scouted-be/core/import_reports/Positions_20260721T013758Z.json (new)
    - get-scouted-be/core/import_reports/Positions_20260721T013758Z.md (new)

key-decisions:
  - "Fixed a real crash discovered only at full-scale: 3 of the 9 real Positions/*.csv files ('CM with league.csv', 'LB with league.csv', 'RB with league.csv') each have 2 all-NaN trailing rows. A plain int64 UniqueID dtype raised ValueError: Integer column has NA values. Switched to the nullable Int64 dtype and added a per-row pd.isna check that flags+skips (issue: missing_unique_id_blank_row) instead of crashing the whole file."
  - "The plan's manual-verification note estimated '~38,600 rows' for the full import, but that figure (also present in 01-RESEARCH.md's PlayerRoleScore Model section) describes the WIDE row count summed across all 9 files, not the LONG PlayerRoleScore row count the must_haves truths explicitly require ('one row per (player, role)'). Verified actual long-format total is 230,139 (matches the sum of each file's row-count x role-column-count, minus the 38 flagged blank rows) -- correct per the plan's own must_haves, just a stale estimate in the supporting docs, not a defect in this import."
  - "Test copies the CB fixture (positions_CB_sample.csv) into a temp dir under the exact real filename ('CB with league.csv') that FILE_TO_POSITION keys on, rather than pointing --positions-dir directly at core/tests/fixtures/ (whose files use descriptive fixture names, not the real dataset's literal filenames). This also exercises the command's tolerate-missing-files path for the other 8 absent filenames in the same test run."

patterns-established:
  - "Continues Plan 05's manual full-scale verification pattern: run the command against the real dataset via local Postgres, confirm counts/rates against 01-RESEARCH.md's verified figures, confirm idempotent re-run (0 created / N updated), commit one reviewed report artifact."

requirements-completed: [DATA-03]

# Metrics
duration: 18min
completed: 2026-07-21
---

# Phase 1 Plan 06: Position Role Score Import Summary

**import_position_roles Django management command that melts all 9 wide Positions/*.csv role files into 230,139 long PlayerRoleScore rows, resolves the player FK by UniqueID, sanitizes role headers while preserving the raw original, and confirms all 3,081 GK players correctly get zero rows.**

## Performance

- **Duration:** ~18 min
- **Started:** 2026-07-21T02:24:00Z (approx.)
- **Completed:** 2026-07-21T02:40:00Z
- **Tasks:** 2 completed
- **Files modified:** 3 (1 created, 1 test file appended, 1 reviewed report artifact pair)

## Accomplishments

- `import_position_roles` management command: for each of the 9 real Positions/*.csv filenames (mapped via a hardcoded `FILE_TO_POSITION` dict, including the irregularly-named `"FWD with league Updated.csv"` and `"LW with league2.csv"`), reads the header dynamically to discover that file's role columns, builds an explicit nullable dtype map, and uses `df.melt(...)` to turn the wide shape into long `(UniqueID, role_name_raw, score)` rows.
- Player FK resolved via an in-memory `{Player.unique_id: Player.id}` map (errors out with a clear message if the Player table is empty, mirroring Plan 05's Club-map pattern).
- `sanitize_role_name()` converts raw headers like `"Wide_Centre-Back_(LCB)"` -> `"wide_centre_back_lcb"` (strip parens, collapse non-alnum runs to a single underscore, lowercase) while `role_name_raw` keeps the untouched original string.
- Idempotent upsert via `PlayerRoleScore.objects.bulk_create(batch_size=5000, update_conflicts=True, unique_fields=['player','role_name'], update_fields=['score','role_name_raw','position_group'])`.
- Report explicitly states the GK zero-coverage expectation ("GK players have zero PlayerRoleScore rows by design -- there is no GK Positions/*.csv file") plus per-position row counts and any missing filenames, so a partial/absent file never looks like a silent failure.
- `test_role_score_coverage` (appended to `players/tests/test_import.py`, additive per Plan 05's note): copies the CB fixture into a temp dir under the real expected filename, asserts CB players (UniqueID 1, 2, 5, 7) each get >=1 role row, GK players (UniqueID 6, 14) get exactly 0, the LCB role row's `role_name`/`role_name_raw`/`position_group` are correct, and a re-run is idempotent. Full `players/tests/test_import.py` suite (4 tests) green.
- **Verified against the real, full-scale dataset**: 230,139 PlayerRoleScore rows created (0 unmatched UniqueIDs, 38 blank trailing rows flagged/skipped across 3 files), 3,081 GK players confirmed at exactly zero role rows (matches 01-RESEARCH.md's ~3,081 GK estimate), 40 distinct sanitized role_names across the 9 position groups. Re-running against the full dataset produced zero net PlayerRoleScore row change (0 created / 230,139 updated on re-run) -- idempotency confirmed at production scale.

## Task Commits

1. **Task 1: Build import_position_roles command (wide->long normalization, idempotent)** - `d07011d` (feat), plus a full-scale bug fix `b98bbb1` (fix) for blank trailing rows discovered during manual verification
2. **Task 2: Append test_role_score_coverage to players/tests/test_import.py** - `f5f88d3` (test)

**Plan metadata:** (this commit, next)

## Files Created/Modified

- `get-scouted-be/players/management/commands/import_position_roles.py` - The import command (dynamic per-file dtype discovery, melt-based wide->long normalization, player FK resolution, sanitize_role_name helper, idempotent bulk_create upsert, missing-file tolerance)
- `get-scouted-be/players/tests/test_import.py` - Added `test_role_score_coverage` (CB coverage, GK zero-coverage, sanitized role_name + raw preservation, idempotent re-run)
- `get-scouted-be/core/import_reports/Positions_20260721T013758Z.{json,md}` - Reviewed full-dataset import report artifact

## Decisions Made

- Switched `UniqueID`'s dtype from `int64` to the nullable `Int64` and added an explicit `pd.isna` check per row, because 3 of the 9 real Positions files have all-NaN trailing rows that would otherwise crash `pd.read_csv` entirely (see key-decisions above for full detail).
- Kept only the initial full-import run's report committed (230,139 created), discarding the subsequent idempotent-rerun report after reviewing it for the zero-net-change confirmation -- same one-committed-report convention as Plans 04/05.
- Test builds a temp positions directory with the real expected filename rather than pointing at `core/tests/fixtures/` directly, since the fixture's filename (`positions_CB_sample.csv`) intentionally differs from the real dataset's filename (`CB with league.csv`) that `FILE_TO_POSITION` keys on.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed crash on blank trailing rows in 3 real Positions/*.csv files**
- **Found during:** Manual full-scale verification (post-Task-1, before committing Task 1 as fully done)
- **Issue:** `"CM with league.csv"`, `"LB with league.csv"`, and `"RB with league.csv"` each have 2 all-NaN trailing rows in the real dataset. The explicit `dtype={"UniqueID": "int64"}` mapping used for `read_csv_full` raised `ValueError: Integer column has NA values in column 0`, crashing the entire file's import (and thus the whole command) rather than just those 6 rows.
- **Fix:** Changed the `UniqueID` dtype to nullable `"Int64"` and added a `pd.isna(raw_uid)` check per melted row that flags the issue (`add_field_issue("UniqueID", "missing_unique_id_blank_row")`) and skips just that row, matching this phase's established "flag, never crash" data-quality policy.
- **Files modified:** `get-scouted-be/players/management/commands/import_position_roles.py`
- **Verification:** Full test suite green (4/4); real full-dataset import completed end-to-end (230,139 rows, 38 blank rows flagged, 0 unmatched UniqueIDs) on both an initial run and an idempotent re-run.
- **Committed in:** `b98bbb1` (fix)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix -- without it the command could not complete a full-dataset run at all (3/9 files would crash). No scope creep; behavior otherwise matches the plan exactly.

## Issues Encountered

- The plan's `<verification>` section estimated "~38,600 rows" for a full-scale run; the actual result is 230,139 long-format `PlayerRoleScore` rows. This is not a defect -- the estimate (also present in 01-RESEARCH.md) describes the wide-format row count summed across the 9 files, while the plan's own `must_haves.truths` explicitly requires one row per (player, role) pair, which necessarily multiplies by each file's role-column count (4-7x). Verified the actual total reconciles exactly: sum(file_rows x role_columns) across all 9 files minus the 38 flagged blank rows = 230,139. Documented here rather than treated as a blocker since the must_haves truths (the authoritative spec) are fully satisfied.

## User Setup Required

None - no external service configuration required. (Same local Postgres instance from Plan 05 used for full-scale verification.)

## Next Phase Readiness

- `PlayerRoleScore` table is now fully populated from the real dataset (230,139 rows across 40 sanitized role_names / 9 position groups), player-FK-resolved, GK zero-coverage confirmed, ready for Plan 07 (compatibility scores) which follows the same wide->long normalization pattern at much larger scale (~8.1M rows) and for later phases needing "best-fit role per player" queries.
- No blockers identified.

---
*Phase: 01-data-foundation*
*Completed: 2026-07-21*

## Self-Check: PASSED

- FOUND: get-scouted-be/players/management/commands/import_position_roles.py
- FOUND: get-scouted-be/players/tests/test_import.py
- FOUND: get-scouted-be/core/import_reports/Positions_20260721T013758Z.json
- FOUND: .planning/phases/01-data-foundation/01-06-SUMMARY.md
- FOUND commit: d07011d (feat: import_position_roles command)
- FOUND commit: f5f88d3 (test: test_role_score_coverage)
- FOUND commit: b98bbb1 (fix: blank trailing rows + reviewed report)
