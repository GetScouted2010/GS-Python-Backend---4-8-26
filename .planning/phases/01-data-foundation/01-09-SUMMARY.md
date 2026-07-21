---
phase: 01-data-foundation
plan: 09
subsystem: database
tags: [django, management-command, etl, postgres, bulk_create, data-import, orchestration]

# Dependency graph
requires:
  - phase: 01-data-foundation (Plans 04-08)
    provides: import_clubs_playstyles, import_players, import_position_roles, import_compatibility_scores, import_transfers (all individually verified against the real dataset)
provides:
  - "import_all: single dependency-ordered orchestrator for the whole Phase 1 migration"
  - "Combined import report (JSON+Markdown) with a source-CSV-vs-db reconciliation section"
  - "docs/IMPORT_RUNBOOK.md: operator instructions + full catalogue of expected coverage gaps"
  - "Fix: import_transfers now tolerates genuinely-duplicated source rows (Postgres CardinalityViolation) via chunk-local composite-key dedup"
affects: [phase-2-api, phase-3-curation, any-future-dataset-refresh]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestrator command locates each sub-command's freshly-written report by mtime (since=time.time() snapshot before call_command), not by parsing stdout or modifying the sub-commands"
    - "Reconciliation source-of-truth delegation: rather than recomputing an entity's expected row count independently, read it from that entity's own sub-report section (club_derivation.distinct_clubs, transfer_import.duplicate_event_keys_collapsed) so the two never drift apart"

key-files:
  created:
    - get-scouted-be/core/management/__init__.py
    - get-scouted-be/core/management/commands/__init__.py
    - get-scouted-be/core/management/commands/import_all.py
    - get-scouted-be/core/tests/test_import_all.py
    - get-scouted-be/docs/IMPORT_RUNBOOK.md
  modified:
    - get-scouted-be/transfers/management/commands/import_transfers.py

key-decisions:
  - "import_all's reconciliation delegates the 'expected' row count for Club and Transfer to each sub-command's OWN report section (club_derivation.distinct_clubs; transfer_import.duplicate_event_keys_collapsed) instead of recomputing independently, so the two calculations structurally cannot drift apart"
  - "import_transfers collapses same-composite-event-key rows within a chunk (last occurrence wins) before bulk_create, because Postgres's ON CONFLICT DO UPDATE cannot affect the same conflict target twice in one INSERT -- real transferdata final.csv has ~51 such genuinely-duplicated rows"
  - "PlayerRoleScore and PlayerClubCompatibility reconciliation entries report source_rows=null by design (no single fixed expected count exists for a 9-wide-file melt); only Club/Player/Transfer get a real delta check"

patterns-established:
  - "Full-pipeline orchestrator pattern: call_command in fixed dependency order + report-directory mtime-watch to aggregate independently-written sub-reports into one combined report, without modifying any of the five existing commands"

requirements-completed: [DATA-05]

# Metrics
duration: 100min
completed: 2026-07-21
---

# Phase 1 Plan 9: import_all Orchestrator + Reconciliation + Runbook Summary

**Single `import_all` command chains all five Phase 1 importers in dependency order, produces one combined report with a source-CSV-vs-db reconciliation, and (as a required blocking fix discovered during the real-data phase-gate run) makes `import_transfers` tolerate the ~51 genuinely-duplicated rows in the real transfer dataset.**

## Performance

- **Duration:** ~100 min (includes three full/partial real-dataset runs: one that crashed and surfaced the transfers bug, two that passed)
- **Tasks:** 2 completed
- **Files modified:** 6 (5 created, 1 modified) + 3 committed report artifacts

## Accomplishments

- `python manage.py import_all` runs `import_clubs_playstyles -> import_players -> import_position_roles -> import_compatibility_scores -> import_transfers` in one invocation, in the correct dependency order, with `--skip-compatibility` for fast smoke runs
- One combined report (JSON + Markdown) aggregates all five sub-reports plus a `reconciliation` section comparing live table counts to actual (never hardcoded) source-CSV row counts
- Whole-pipeline idempotency proven twice: once against the fixture set (`test_import_all_idempotent`) and once against the real full dataset (two consecutive real runs produced identical row counts, 0 created on the second)
- Full real-dataset phase-gate run completed and reconciled to **PASS**: Club 1060/1060, Player 41708/41708, Transfer 47201/47201 (reconciliation auto-adjusts for 51 collapsed duplicate rows), PlayerRoleScore 230139 and PlayerClubCompatibility 8188712 reported with no fixed expectation (by design)
- `docs/IMPORT_RUNBOOK.md` documents prerequisites, the single-command run, dependency order/why, how to read the combined report, and six documented "expected, not a bug" coverage gaps (including two newly-discovered ones from this plan's own full-scale verification)

## Task Commits

1. **Task 1: Build import_all orchestrator + row-count reconciliation + runbook** - `10a18fc` (feat)
   - Plus `4853c97` (fix) -- a Rule 1 blocking-bug fix in `import_transfers.py` discovered while executing this task's own required phase-gate verification (see Deviations below)
2. **Task 2: Whole-pipeline idempotency integration test** - `5b9c294` (test)

_No separate plan-metadata commit yet -- this SUMMARY/STATE/ROADMAP update commit follows this message._

## Files Created/Modified

- `get-scouted-be/core/management/__init__.py`, `get-scouted-be/core/management/commands/__init__.py` - management-command package scaffolding for the `core` app (didn't exist yet)
- `get-scouted-be/core/management/commands/import_all.py` - the orchestrator: runs the five commands in order, locates each one's freshly-written report by mtime, builds a combined `ImportReport` with `pipeline`, `table_counts`, `reconciliation`, and `sub_reports` sections
- `get-scouted-be/core/tests/test_import_all.py` - `test_import_all_idempotent`, `@pytest.mark.integration`, proves zero net row change across all five tables on a second run against the fixture set, plus asserts the reconciliation section shape
- `get-scouted-be/docs/IMPORT_RUNBOOK.md` - operator runbook: prerequisites, run command, options table, dependency order/why, how to read the combined report, six "expected coverage gap" items, re-run/troubleshooting guidance
- `get-scouted-be/transfers/management/commands/import_transfers.py` - added `_dedupe_transfer_objs` to collapse rows sharing an identical composite event key within one chunk before `bulk_create`, with per-row logging and corrected created/updated math
- `get-scouted-be/core/import_reports/import_all_20260721T024804Z.{json,md}` - reviewed combined report from the real-dataset phase-gate run (PASS)
- `get-scouted-be/core/import_reports/transferdata final_20260721T024803Z.{json,md}` - reviewed full-dataset `import_transfers` report from the same run (first-ever successful real full-scale run of this command)

## Decisions Made

- Reconciliation delegates the "expected" count for Club and Transfer to each sub-command's own report section rather than recomputing independently in `import_all`, so a future change to either sub-command's derivation logic can't silently desync the reconciliation math from reality.
- Chose chunk-local, last-occurrence-wins deduplication for the Transfer composite-key collision (rather than e.g. failing the whole import or globally pre-scanning the file) -- cheap, order-preserving, and every collapsed row is still individually logged in the report per the project's "never silently drop" policy.
- `PlayerRoleScore`/`PlayerClubCompatibility` reconciliation entries deliberately report `source_rows: null` -- there's no single correct "expected" row count for a value that depends on 9-file overlap plus player-match rate, and asserting a specific number would misrepresent the reconciliation's confidence.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] import_transfers crashed on real full-scale data with Postgres CardinalityViolation**
- **Found during:** Task 1's own required phase-gate verification (`python manage.py import_all` against the real dataset)
- **Issue:** `transferdata final.csv` contains 51 pairs of literal exact-duplicate rows sharing all 6 composite event-key columns. `bulk_create(update_conflicts=True)` cannot apply `ON CONFLICT DO UPDATE` to the same conflict-target row twice within one `INSERT` statement, so the transfers step (and the whole `import_all` run) crashed every time it hit one of these pairs within the same processing chunk. This bug pre-dated this plan (in `import_transfers.py`, built in Plan 08) but had never been exercised at real full scale before -- 01-08-SUMMARY.md explicitly flagged this manual full-scale run as still outstanding.
- **Fix:** Added `_dedupe_transfer_objs` to `import_transfers.py`: collapses same-key rows within a chunk (last occurrence wins, source order preserved) before `bulk_create`; logs each collapsed row as a `(transfer_event_key, duplicate_source_row)` field issue plus a `transfer_import.duplicate_event_keys_collapsed` count; fixed the `updated` count math to derive from the deduped upsert count instead of the raw per-row count.
- **Files modified:** `get-scouted-be/transfers/management/commands/import_transfers.py`
- **Verification:** All 4 existing `transfers/tests/test_transfer_import.py` tests still pass; real full-scale `import_transfers` run succeeded (47252 source rows -> 47201 imported, 51 collapsed, logged); `import_all`'s own reconciliation (which reads `duplicate_event_keys_collapsed` from this same report) shows `delta: 0` for Transfer.
- **Committed in:** `4853c97`

- **Total deviations:** 1 auto-fixed (1 bug)
- **Impact on plan:** Necessary for the plan's own explicit phase-gate verification requirement ("Phase gate ... `python manage.py import_all` against the real dataset") to actually succeed. No scope creep beyond what was required to make the orchestrator's own stated success criteria achievable; documented in the runbook as item 6 of the "expected coverage gaps" section so future reviewers don't mistake the resulting -51 offset for silent data loss.

## Issues Encountered

- The real full-scale `transferdata final.csv` run also surfaced (not fixed, not a bug -- see runbook item 5) a much higher `Transfer.player` unmatched rate than one might assume from the fixture tests alone: 46,391 of 47,252 rows (~98%) have no resolvable player match. This is the expected consequence of `Players.csv`'s one-row-per-player-per-season structure (most names are non-unique across the table) combined with Plan 08's deliberate "never guess an ambiguous name" policy -- not a join bug. Documented in `IMPORT_RUNBOOK.md` item 5 so this doesn't get "fixed" by loosening the name-matching policy without a deliberate design decision.
- Iterating on the reconciliation logic required re-running the full real-dataset pipeline three times (one crash, one success with a still-slightly-wrong reconciliation for the Club/Transfer expected counts, one final correct pass) -- used `--skip-compatibility` for the second and third runs since the ~8.1M-row compatibility step's idempotency was already independently proven in Plan 07 and didn't need re-verification each time.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- DATA-05's "reviewed import report for the whole migration" requirement is satisfied: one combined, committed, PASS-status report covering all five tables against the real dataset.
- Phase 1's full data-import pipeline is complete, re-runnable, and idempotent end-to-end. Ready for Phase 2 (API layer) to build against a populated, real-data-backed schema.
- Note for downstream consumers: `Transfer.player` is populated for only ~2% of rows today (documented, expected, not a blocker) -- any feature relying on Transfer-to-Player joins should be aware of this low match rate up front.

---
*Phase: 01-data-foundation*
*Completed: 2026-07-21*

## Self-Check: PASSED

All 11 claimed files verified present on disk (core/management package + import_all.py, test_import_all.py, IMPORT_RUNBOOK.md, modified import_transfers.py, the two committed real-dataset report artifacts, and this SUMMARY). All 3 claimed commit hashes (`10a18fc`, `4853c97`, `5b9c294`) verified present in git log.
