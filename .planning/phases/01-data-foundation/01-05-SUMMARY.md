---
phase: 01-data-foundation
plan: 05
subsystem: database
tags: [django, pandas, bulk_create, etl, import-report, players]

# Dependency graph
requires:
  - phase: 01-data-foundation (Plan 04)
    provides: core/import_utils.py (read_csv_chunks, ImportReport), Club rows via import_clubs_playstyles
provides:
  - players/management/commands/import_players.py (chunked, idempotent Player import)
  - players/tests/test_import.py (row-count, missing-field, idempotency tests -- additive file for Plan 06)
  - Reviewed full-dataset import report (core/import_reports/Players_20260721T012639Z.{json,md})
affects: [01-06, 01-07, 01-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Player upsert: bulk_create(update_conflicts=True, unique_fields=['unique_id'], update_fields=[all non-id/non-unique_id fields]) per chunk inside transaction.atomic()"
    - "report.add_field_issue monkey-patched once in Command.handle() to also track a flagged_uids set, so per-row helper functions only need a reference to `report`, not a second `flagged_uids` parameter"
    - "Real-data sentinel discovery: Contract_expires' 18% 'missing' rate in Players.csv is actually the literal string '0', not a blank cell -- correctly caught by the unparseable/strptime branch, not the isna/missing branch, with identical net effect (null + flagged, row kept)"

key-files:
  created:
    - get-scouted-be/players/management/__init__.py
    - get-scouted-be/players/management/commands/__init__.py
    - get-scouted-be/players/management/commands/import_players.py
    - get-scouted-be/players/tests/__init__.py
    - get-scouted-be/players/tests/test_import.py
  modified:
    - get-scouted-be/core/tests/fixtures/players_sample.csv

key-decisions:
  - "Fixed a call-site/signature mismatch discovered in the pre-existing (uncommitted) import_players.py: _build_player_kwargs required a `flagged_uids` positional arg that the call site never passed, which would have raised TypeError on every single row. Removed the redundant parameter -- report.add_field_issue is already monkey-patched in Command.handle() to track flagged_uids, so the per-row helper only needs `report`."
  - "Seeded players_sample.csv's UniqueID=1 row with real Total_Score/Total_Distance_per_90/Max_Speed_(km/h) values (previously all blank) so test_player_missing_field_handling can assert extended_stats + legacy_total_score against real fixture data at runtime, per the plan's explicit instruction."
  - "Committed one reviewed full-dataset import report (the initial 41,708-created run) per the one-committed-report convention set in Plan 04; the subsequent idempotent re-run's report was reviewed then discarded, not committed."

patterns-established:
  - "Manual full-scale verification for each Plan 05-09 import command: run against the real dataset via a live local Postgres, confirm field-issue rates match 01-RESEARCH.md's verified figures, confirm idempotent re-run produces zero net row change, commit one reviewed report artifact."

requirements-completed: [DATA-01, DATA-03, DATA-05]

# Metrics
duration: 25min
completed: 2026-07-21
---

# Phase 1 Plan 05: Player Import Summary

**Chunked, idempotent import_players Django management command that streams all 41,708 Players.csv rows, resolves the Club FK, packs 14 movement columns into extended_stats, parses DD/MM/YYYY contract dates, and flags every missing/dirty/outlier value without ever skipping a row.**

## Performance

- **Duration:** 25 min (resumed after an interruption; this session picked up from an existing-but-buggy uncommitted `import_players.py`)
- **Started:** 2026-07-21T01:05:00Z (approx., session resume)
- **Completed:** 2026-07-21T01:29:45Z
- **Tasks:** 2 completed
- **Files modified:** 6 (5 created, 1 fixture modified) + 1 reviewed report artifact (2 files)

## Accomplishments

- `import_players` management command: streams Players.csv via `read_csv_chunks` with fully explicit nullable dtypes, resolves `Player.club` from an in-memory `{Club.name: Club.id}` map built from Plan 04's `Club` rows, packs the 14 movement columns into `extended_stats` keyed by raw CSV column name, renames `Total_Score` to `legacy_total_score`, parses `Contract_expires` as `DD/MM/YYYY` explicitly, and idempotently upserts via `bulk_create(update_conflicts=True, unique_fields=['unique_id'])` inside `transaction.atomic()` per chunk.
- Data-quality flagging never skips a row: blank/zero `Market_value` -> null + flagged, `Foot` in `{'0','unknown'}` -> kept raw + flagged, blank `Position` -> flagged, `Age > 60` / negative `Market_value` -> flagged outlier (value kept), unparseable/missing `Contract_expires` -> null + flagged.
- **Fixed a critical bug in the pre-existing file before it could ever run**: `_build_player_kwargs` required a `flagged_uids` positional argument the call site never supplied, which would have raised `TypeError` on the very first row of any real import. Removed the redundant parameter (the monkey-patched `report.add_field_issue` in `Command.handle()` already tracks flagged rows) and cleaned up a dead no-op branch in that same wrapper.
- All 3 required tests green: `test_player_row_count`, `test_player_missing_field_handling` (including a runtime, not source-grep, assertion of `extended_stats["Max_Speed_(km/h)"]` / `extended_stats["Total_Distance_per_90"]` / `legacy_total_score` against a known fixture row), `test_reimport_idempotent`. Full suite (9 tests across clubs/players) green.
- **Verified against the real, full-scale dataset** (not just the fixture): imported all 41,708 rows in ~58s wall-clock, 0 unresolved club names, 8,475 rows flagged. Field-issue rates matched 01-RESEARCH.md's verified figures exactly: `Contract_expires` 18.03% (7,518 rows), `Market_value` 14.01% (5,844 rows), `Foot` invalid `'0'` 512 rows / `'unknown'` 287 rows, `Position` missing 1 row. Re-running against the full dataset produced **zero net Player row change** (41,708 before and after; 0 created / 41,708 updated on re-run), confirming idempotency at production scale.
- Discovered (not a bug, a real-data nuance): Players.csv's "missing" `Contract_expires` rows are encoded as the literal string `'0'`, not a blank cell -- correctly caught by the unparseable/`strptime`-failure branch rather than the `isna`/missing branch, with identical net effect (null + flagged, row kept).

## Task Commits

1. **Task 1: Build import_players command (chunked, idempotent, club-FK, extended_stats, outlier flagging)** - `e0891c0` (feat), plus a follow-up quote-style fix `4226d14` (fix) to match the plan's exact `unique_fields=['unique_id']` literal
2. **Task 2: Player import tests (row count, missing-field handling, idempotent re-run)** - `c9d05da` (test)
3. **Manual full-scale verification report** - `3a85d84` (chore)

**Plan metadata:** (this commit, next)

## Files Created/Modified

- `get-scouted-be/players/management/commands/import_players.py` - The import command (chunked read, club-FK resolution, extended_stats packing, contract-date parsing, outlier flagging, idempotent upsert)
- `get-scouted-be/players/management/__init__.py`, `get-scouted-be/players/management/commands/__init__.py` - Required package scaffolding for Django's management-command discovery
- `get-scouted-be/players/tests/test_import.py` - `test_player_row_count`, `test_player_missing_field_handling`, `test_reimport_idempotent`
- `get-scouted-be/players/tests/__init__.py` - Test package scaffolding
- `get-scouted-be/core/tests/fixtures/players_sample.csv` - Seeded UniqueID=1 with real `Total_Score`/`Total_Distance_per_90`/`Max_Speed_(km/h)` values so the extended_stats/legacy_total_score runtime assertion has real data to check
- `get-scouted-be/core/import_reports/Players_20260721T012639Z.{json,md}` - Reviewed full-dataset import report artifact

## Decisions Made

- Removed the redundant `flagged_uids` parameter from `_build_player_kwargs` rather than fixing the call site to pass it, since `Command.handle()` already monkey-patches `report.add_field_issue` to track flagged rows -- passing the same set through two paths would have been redundant, not just buggy.
- Kept only one reviewed full-dataset import report committed (the initial full-import run), matching the precedent set in Plan 04's SUMMARY; the subsequent idempotent-rerun report was reviewed for the zero-net-change confirmation and then discarded.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `_build_player_kwargs` call-site/signature mismatch (would have crashed on every row)**
- **Found during:** Task 1 review (pre-existing uncommitted file from an interrupted prior session)
- **Issue:** `_build_player_kwargs(row, club_id_map, report, flagged_uids)` required 4 positional args, but `Command.handle()` called it with only 3 (`_build_player_kwargs(row, club_id_map, report)`), which would raise `TypeError: missing 1 required positional argument: 'flagged_uids'` on the very first row processed.
- **Fix:** Removed the `flagged_uids` parameter from `_build_player_kwargs` and its internal `_flag` closure (the local `_flag` now only calls `report.add_field_issue(field, issue, sample_id=uid)`); `Command.handle()` already monkey-patches `report.add_field_issue` to track `flagged_uids` in its own scope, so no functionality was lost. Also removed a dead no-op `if field == "club" and issue == "unresolved_club_name": pass` branch in that same wrapper.
- **Files modified:** `get-scouted-be/players/management/commands/import_players.py`
- **Verification:** Full test suite green; real full-dataset import ran end-to-end (41,708 rows, 0 crashes) both on first run and on idempotent re-run.
- **Committed in:** `e0891c0` (Task 1 commit)

**2. [Rule 3 - Blocking] Matched the plan's literal `unique_fields=['unique_id']` quoting for its verification grep**
- **Found during:** Post-Task-1 verification against the plan's `<verification>` section, which greps for the single-quoted literal `unique_fields=['unique_id']`
- **Issue:** The code used double quotes (`unique_fields=["unique_id"]`), functionally identical but not matching the plan's exact grep pattern.
- **Fix:** Changed the quote style only; no behavior change.
- **Files modified:** `get-scouted-be/players/management/commands/import_players.py`
- **Committed in:** `4226d14` (fix)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking/verification-literal)
**Impact on plan:** The Rule 1 fix was essential -- without it the command could not run at all. The Rule 3 fix is cosmetic. No scope creep.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None - no external service configuration required. (A local Postgres instance at `localhost:5432/getscouted` was already configured and running; used for the manual full-scale verification.)

## Next Phase Readiness

- `Player` table is now fully populated from the real dataset (41,708 rows), club-FK-resolved, extended_stats/legacy_total_score populated, ready for Plan 06 (role-score coverage) to add to the same `players/tests/test_import.py` file and for Plan 07 (compatibility scores) to join against `Player.club`.
- No blockers identified.

---
*Phase: 01-data-foundation*
*Completed: 2026-07-21*

## Self-Check: PASSED

- FOUND: get-scouted-be/players/management/commands/import_players.py
- FOUND: get-scouted-be/players/tests/test_import.py
- FOUND: get-scouted-be/core/tests/fixtures/players_sample.csv
- FOUND: get-scouted-be/core/import_reports/Players_20260721T012639Z.json
- FOUND: .planning/phases/01-data-foundation/01-05-SUMMARY.md
- FOUND commit: e0891c0 (feat: import_players command)
- FOUND commit: c9d05da (test: Player import tests)
- FOUND commit: 4226d14 (fix: unique_fields quote-style)
- FOUND commit: 3a85d84 (chore: reviewed full-dataset report)
