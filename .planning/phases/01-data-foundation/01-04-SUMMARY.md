---
phase: 01-data-foundation
plan: 04
subsystem: database
tags: [django, pandas, bulk_create, etl, import-report, club-derivation]

# Dependency graph
requires:
  - phase: 01-data-foundation (Plan 02)
    provides: pytest-django test framework, core/tests/conftest.py, seeded fixture CSVs
  - phase: 01-data-foundation (Plan 03)
    provides: Club, Player, PlayerRoleScore, PlayerClubCompatibility, Transfer models + migrations
provides:
  - core/import_utils.py (read_csv_chunks, read_csv_full, resolve_dataset_path, ImportReport)
  - clubs/management/commands/import_clubs_playstyles.py (Club derivation + upsert)
  - Reusable ETL pattern (chunked/full CSV read, ImportReport JSON+MD write) for Plans 05-09
affects: [01-05, 01-06, 01-07, 01-08, 01-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ImportReport accumulator: add_field_issue groups by (field, issue) with capped sample_ids, add_section for free-form named metrics, write() produces JSON + Markdown from the same dict"
    - "Explicit-dtype-only CSV reads: read_csv_chunks/read_csv_full both raise ValueError on an empty/missing dtype mapping, never let pandas infer"
    - "Club derivation: mode League per club with sorted()-based alphabetical tie-break; clubs_with_ambiguous_league (any club with >1 distinct League value) tracked separately from tied_clubs (genuine mode ties where the tie-break actually decides the outcome)"
    - "Root-level conftest.py re-exports core/tests/conftest.py's fixture_dir so every app's test dir (clubs/tests/, players/tests/, etc.) can use it despite being a pytest-conftest sibling, not descendant"

key-files:
  created:
    - get-scouted-be/core/import_utils.py
    - get-scouted-be/core/tests/test_import_report.py
    - get-scouted-be/clubs/management/commands/import_clubs_playstyles.py
    - get-scouted-be/clubs/tests/test_club_derivation.py
    - get-scouted-be/conftest.py
  modified:
    - get-scouted-be/core/tests/fixtures/players_sample.csv
    - get-scouted-be/core/tests/fixtures/README.md

key-decisions:
  - "clubs_with_ambiguous_league counts any club with more than one distinct League value (len(counter) > 1), matching the plan's literal spec and 01-RESEARCH.md's verified 525/1059 (49.6%) figure -- kept genuine mode ties (tied_clubs, where the alphabetical tie-break decision actually changes the winner) as a separate, smaller tracked list"
  - "Added a root-level get-scouted-be/conftest.py re-exporting fixture_dir, since pytest only auto-discovers a conftest.py's fixtures for descendant test directories, not siblings -- clubs/tests/, players/tests/, transfers/tests/ all need this going forward"
  - "Added 2 rows (UniqueID 82/83, club 'Sevilla') to players_sample.csv for a genuine 1-1 tied League split, since the existing fixture only had a clear 4-1 mode (Manchester City) with no true tie to exercise the alphabetical tie-break path"

patterns-established:
  - "Every future import command (Plans 05-09) reuses core.import_utils.ImportReport + read_csv_chunks/read_csv_full/resolve_dataset_path rather than hand-rolling its own report or CSV-reading logic"

requirements-completed: [DATA-02, DATA-05]

# Metrics
duration: 12min
completed: 2026-07-20
---

# Phase 1 Plan 04: Import Infrastructure + Club Derivation Summary

**Built the shared ImportReport/CSV-reader ETL foundation and the first import command: idempotent Club derivation (mode-League with alphabetical tie-break, ~77%-null playing-style join) from Players.csv + Playstyles.csv, verified against the real 41,708-row/1,060-club dataset.**

## Performance

- **Duration:** 12 min (commits 21:21-21:32 local time)
- **Started:** 2026-07-20T20:21:00Z (approx.)
- **Completed:** 2026-07-20T20:32:22Z
- **Tasks:** 2 completed (+ 1 deviation fix commit)
- **Files modified:** 10 (5 created new for import_utils/test, 5 created/modified for the club command + tests + fixtures + conftest)

## Accomplishments

- `core/import_utils.py`: chunked/full CSV readers that refuse to run without an explicit `dtype=` mapping, `resolve_dataset_path` for DATASET_DIR-relative paths (including subpaths), and `ImportReport` -- an accumulator that groups field issues by `(field, issue)` with a rate and a 10-id-capped sample, accepts free-form named sections, and writes matching JSON + Markdown artifacts.
- `import_clubs_playstyles` management command: derives one `Club` per distinct `Team_within_selected_timeframe`, with `league` = mode `League` (alphabetical tie-break via `sorted()`), joins in Playstyles.csv's 8 style floats + `source_unique_id` for the clubs it covers, and idempotently upserts via `bulk_create(update_conflicts=True, unique_fields=['name'])`.
- Verified against the **real, full-scale dataset** (not just the fixture): 1,060 distinct clubs (1,059 from Players.csv + 1 Playstyles-only name, `Borussia M_gladbach`), 525 ambiguous-league clubs (exact match to 01-RESEARCH.md's verified 49.6% figure), 106 genuine mode ties, 22.6% playing-style coverage -- and re-running the command against the full dataset produced **zero net Club row change** (1,060 before and after), confirming idempotency at production scale, not just on the small fixture.
- All 6 tests green: `test_report_shape` + 2 supporting `ImportReport` tests, and `test_league_mode` / `test_playing_style_coverage` / `test_club_idempotent` for the club command.

## Task Commits

1. **Task 1: Build core/import_utils.py (chunked reader + ImportReport accumulator)** - `6bb9c8e` (feat)
2. **Task 2: Build import_clubs_playstyles command + derivation tests** - `e86cdce` (feat)
3. **Deviation fix: correct clubs_with_ambiguous_league metric definition** - `5fb6a19` (fix)

_No plan-metadata commit yet -- see final commit below._

## Files Created/Modified

- `get-scouted-be/core/import_utils.py` - `read_csv_chunks`/`read_csv_full` (explicit-dtype-only), `resolve_dataset_path`, `ImportReport` (add_field_issue, set_counts, add_section, to_dict, write)
- `get-scouted-be/core/tests/test_import_report.py` - `test_report_shape` + 2 supporting tests for the report accumulator
- `get-scouted-be/clubs/management/commands/import_clubs_playstyles.py` - Club derivation + upsert command, `--players-csv`/`--playstyles-csv`/`--report-dir` options
- `get-scouted-be/clubs/tests/test_club_derivation.py` - `test_league_mode`, `test_playing_style_coverage`, `test_club_idempotent`
- `get-scouted-be/conftest.py` (new) - re-exports `fixture_dir` at repo root so every app's tests can use it
- `get-scouted-be/core/tests/fixtures/players_sample.csv` (modified) - added a genuinely tied-league club ("Sevilla", 1-1 split) needed for `test_league_mode`'s tie-break assertion
- `get-scouted-be/core/tests/fixtures/README.md` (modified) - documented the new fixture rows
- `get-scouted-be/core/import_reports/Players_20260720T202933Z.json` / `.md` - the reviewed report from the final full-dataset verification run (committed per 01-RESEARCH.md's Open Question 3 recommendation)

## Decisions Made

- `clubs_with_ambiguous_league` = count of clubs with **any** >1 distinct League value (not just clubs where the *mode* is tied) -- matches the plan's explicit `len(counter) > 1` spec and reconciles exactly with 01-RESEARCH.md's verified 525/1,059 figure. Genuine mode ties (where the alphabetical tie-break actually decides the winner) are tracked separately as `tied_clubs`.
- Added a repo-root `conftest.py` re-exporting `fixture_dir`, since pytest's conftest fixture scoping only covers descendant directories of a conftest.py's location, and `clubs/tests/` is a sibling of `core/tests/`, not a descendant.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] players_sample.csv had no genuinely tied-league club**
- **Found during:** Task 2 (writing `test_league_mode`)
- **Issue:** The plan's behavior spec requires asserting a deliberately-tied club's league resolves via alphabetical tie-break, but the existing fixture's only ambiguous club (Manchester City, 4 PL rows vs. 1 La Liga row) has a clear mode, not a tie.
- **Fix:** Added 2 rows (UniqueID 82, 83; club "Sevilla") with a genuine 1-1 League split (`Bundesliga (Germany)` vs. `La Liga (Spain)`), documented in `fixtures/README.md`. Verified all rows still have the correct 135-column count.
- **Files modified:** `core/tests/fixtures/players_sample.csv`, `core/tests/fixtures/README.md`
- **Verification:** `test_league_mode` asserts `Club.objects.get(name="Sevilla").league == "Bundesliga (Germany)"`
- **Committed in:** `e86cdce` (Task 2 commit)

**2. [Rule 3 - Blocking] core/tests/conftest.py's fixture_dir not visible to clubs/tests/**
- **Found during:** Task 2 (first test run)
- **Issue:** `pytest` raised `fixture 'fixture_dir' not found` -- pytest only auto-discovers a conftest.py's fixtures for test files in the same or a descendant directory, and `clubs/tests/` is a sibling of `core/tests/`, not a descendant, despite Plan 01-02's stated intent that every app's import tests could use it immediately.
- **Fix:** Added `get-scouted-be/conftest.py` re-exporting `fixture_dir` from `core.tests.conftest`, making it visible repo-wide.
- **Files modified:** `get-scouted-be/conftest.py` (new)
- **Verification:** `pytest clubs/tests/test_club_derivation.py -x -q` passes
- **Committed in:** `e86cdce` (Task 2 commit)

**3. [Rule 1 - Bug] clubs_with_ambiguous_league undercounted**
- **Found during:** Manual full-scale verification run against the real dataset
- **Issue:** Initial implementation only counted genuine mode ties (`len(winners) > 1`), producing 106 -- a large undercount against 01-RESEARCH.md's verified 525/1,059 (49.6%) figure for clubs with any ambiguous League value. The plan's own action step explicitly defines this metric as `len(counter) > 1`.
- **Fix:** Split tracking into `ambiguous_clubs` (any club with >1 distinct League value -- the report metric) and `tied_clubs` (genuine mode ties, still logged individually as tie-break evidence).
- **Files modified:** `clubs/management/commands/import_clubs_playstyles.py`
- **Verification:** Re-ran against the real Players.csv/Playstyles.csv -- `clubs_with_ambiguous_league` now reports exactly 525, matching research.
- **Committed in:** `5fb6a19`

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All three were necessary for the plan's stated behavior/acceptance criteria to actually hold (a real tie-break test case, cross-app fixture visibility, and a report metric matching its own spec). No scope creep -- no architectural changes, no new models, no new dependencies.

## Issues Encountered

None beyond the deviations documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `core/import_utils.py`'s `ImportReport` + CSV-reader helpers are ready for direct reuse by Plans 05 (Players), 06 (PlayerRoleScore), 07 (PlayerClubCompatibility), 08 (Transfer), and 09 (orchestration).
- `Club` rows are derivable and idempotently upsertable; Plan 05's Player import can rely on `Club.objects.values_list('name', 'id')` for its `club_id` FK resolution.
- The dev database's `Club` table was cleared after manual full-scale verification (to avoid stale data ahead of Plan 05's Player import), so the next plan starts from a clean slate and should re-run `import_clubs_playstyles` as its own prerequisite step if needed.
- No blockers identified for Plan 05.

---
*Phase: 01-data-foundation*
*Completed: 2026-07-20*

## Self-Check: PASSED

All created files verified present on disk; all 3 task/deviation commit hashes (6bb9c8e, e86cdce, 5fb6a19) verified present in git log.
