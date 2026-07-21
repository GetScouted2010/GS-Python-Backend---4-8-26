---
phase: 01-data-foundation
plan: 07
subsystem: database
tags: [django, pandas, bulk_create, etl, import-report, players, clubs, melt, wide-to-long]

# Dependency graph
requires:
  - phase: 01-data-foundation (Plan 05)
    provides: Player rows (41,708) with unique_id populated
  - phase: 01-data-foundation (Plan 04)
    provides: Club rows (1,060) with name field populated for header resolution
provides:
  - players/management/commands/import_compatibility_scores.py (wide->long PlayerClubCompatibility import, idempotent upsert on player+club_name_raw)
  - players/tests/test_compatibility.py (test_compatibility_normalization, test_unresolved_club_header_kept, test_compatibility_idempotent)
  - Reviewed full-dataset import report (core/import_reports/Compatability Scores_20260721T015413Z.{json,md})
  - PlayerClubCompatibility table populated: 8,188,712 rows across 9 position-group CS_*.csv files, 1 distinct unresolved club header, 0 unmatched players
affects: [01-09]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Wide->long normalization at true production scale (8.1M+ rows): chunked pd.read_csv with a per-file dtype map (nullable Int64/Float64/string), read_chunksize sized to `batch_size // len(club_columns)` so each melted long-format chunk lands close to the target bulk_create batch size regardless of file row count"
    - "Per-distinct-header resolution cache (header_resolution dict) resolves each of ~212 club column headers to a club_id (or None) exactly once per run, no matter how many of the 8.1M rows reference it -- avoids O(rows) Club lookups and O(rows) unresolved-header logging"
    - "cs_field_mapping.json is a display-name -> sanitized-header map; the command inverts it once at startup (sanitized-header -> display-name) because the resolution direction it actually needs is raw CSV header -> Club.name, the reverse of how the file is authored"
    - "Nullable-club unique key: (player, club_name_raw) is the bulk_create unique_fields/conflict target, NOT (player, club) -- club is null for unresolved headers and Postgres treats multiple NULLs as non-conflicting, which would silently duplicate null-club rows on every re-run if club were part of the conflict target"
    - "Early throughput go/no-go check: times only the very first non-empty bulk_create batch, logs a warning (recommending the psycopg copy()-staging fallback) if measured rows/sec falls below a threshold, but always proceeds -- a signal, not a hard stop"

key-files:
  created:
    - get-scouted-be/players/management/commands/import_compatibility_scores.py
    - get-scouted-be/players/tests/test_compatibility.py
  modified: []
  reports:
    - get-scouted-be/core/import_reports/Compatability Scores_20260721T015413Z.json
    - get-scouted-be/core/import_reports/Compatability Scores_20260721T015413Z.md

key-decisions:
  - "The one unresolved club header found in the real dataset, \"St_DOT_ Louis City\", is NOT in cs_field_mapping.json (checked directly) -- it is kept with club=null + club_name_raw preserved rather than guessed at, exactly per the plan's must_haves (every score is retained, never dropped, for an unmapped header)."
  - "A prior session's background run had partially completed (2,149,892 rows: all of CS_AM.csv fully imported, CS_CB_25.csv partially) before this session resumed. Rather than truncate and restart, the command was simply re-run to completion -- its idempotent upsert on (player, club_name_raw) made this safe with no special-casing needed, which is itself a live confirmation of the idempotency the plan's must_haves require."
  - "Kept only the initial full-import report (8,188,712 created) committed, discarding the subsequent idempotent-rerun report (same 8,188,712 total, 0 net DB change verified directly via count query) after reviewing it -- same one-committed-report convention as Plans 04/05/06."

patterns-established:
  - "Continues Plans 04-06's manual full-scale verification pattern: run the command against the real dataset via local Postgres, confirm counts against the RESEARCH.md-implied ~8.1M total and per-file arithmetic (data_rows x 212 club columns), confirm idempotent re-run (row count unchanged), commit one reviewed report artifact."

requirements-completed: [DATA-03]

# Metrics
duration: ~35min
completed: 2026-07-21
---

# Phase 1 Plan 07: Compatibility Score Import Summary

**import_compatibility_scores Django management command that melts all 9 wide Compatability Scores/*.csv matrices into 8,188,712 long PlayerClubCompatibility rows, resolves ~212 club-name column headers per file via exact match then cs_field_mapping.json with a per-header cache, and keeps the one genuinely unresolvable header (club=null) rather than dropping its 38,626 scores.**

## Performance

- **Duration:** ~35 min (includes resuming/completing a background full-scale run started in a prior session)
- **Started:** 2026-07-21T02:38:00Z (approx., Task 1 commit)
- **Completed:** 2026-07-21T02:12:00Z (full-scale verification report reviewed)
- **Tasks:** 2 completed
- **Files modified:** 4 (1 command created, 1 test file created, 1 reviewed report artifact pair)

## Accomplishments

- `import_compatibility_scores` management command: for each of the 9 real `Compatability Scores/CS_*.csv` filenames (mapped via a hardcoded `FILE_TO_POSITION` dict, including the irregularly-named `"CS_DM_25 NEW.csv"`), reads the header dynamically to discover that file's ~212 club columns, builds an explicit nullable dtype map, and chunk-reads + `melt()`s the wide shape into long `(UniqueID, Position, club_name_raw, score)` rows sized so memory stays bounded across the ~8.1M-row total.
- Club column headers resolved via a per-distinct-header cache (`header_resolution`): exact `Club.name` match first, then a reverse-lookup through `cs_field_mapping.json` (inverted at startup from display-name->sanitized-header to sanitized-header->display-name) to recover the real display name and retry.
- Unresolved headers are never dropped: they keep `club=null`, preserve the original header in `club_name_raw`, and are logged exactly once per distinct header (not once per row) in the report's `unresolved_club_names` section.
- Idempotent upsert via `PlayerClubCompatibility.objects.bulk_create(batch_size=8000, update_conflicts=True, unique_fields=['player','club_name_raw'], update_fields=['club','score','position_group'])` -- `club_name_raw` (not `club`) is the conflict target specifically so null-club rows don't duplicate on re-run.
- Early throughput check on the first non-empty batch: measured ~5,134 rows/sec, above the warn threshold, logged as OK (no fallback needed).
- `players/tests/test_compatibility.py` (its own file, additive alongside Plan 06's `test_import.py`): `test_compatibility_normalization` (wide CB fixture normalizes to one row per player-club pair with correct FK/score round-trip), `test_unresolved_club_header_kept` (the fixture's deliberately-unresolvable header keeps `club=None` + `club_name_raw`, logged once in the report), `test_compatibility_idempotent` (re-run produces zero net row change, including null-club rows). All 3 tests green; full `players/` suite (7 tests) green.
- **Verified against the real, full-scale dataset**: 8,188,712 PlayerClubCompatibility rows created (0 unmatched player UniqueIDs, 0 flagged rows), matching the exact arithmetic of each file's row count x 212 club columns summed across all 9 files. Only 1 distinct club header failed to resolve (`"St_DOT_ Louis City"`), contributing 38,626 null-club rows (one distinct raw score per qualifying player per file it appears in) -- correctly preserved rather than dropped. Re-running the full import against the real dataset produced an unchanged total row count (8,188,712 before and after), confirming idempotency at production scale, including for the null-club rows.

## Task Commits

1. **Task 1: Build import_compatibility_scores command (wide->long, club resolution, chunked upsert)** - `87a7fa1` (feat)
2. **Task 2: Compatibility normalization + unresolved-header tests** - `2ba82cd` (test)
3. **Full-dataset report artifact** - `57b1c68` (chore)

**Plan metadata:** (this commit, next)

## Files Created/Modified

- `get-scouted-be/players/management/commands/import_compatibility_scores.py` - The import command (per-file dynamic dtype/column discovery, chunked melt-based wide->long normalization, per-header club resolution cache, early throughput check, idempotent bulk_create upsert)
- `get-scouted-be/players/tests/test_compatibility.py` - `test_compatibility_normalization`, `test_unresolved_club_header_kept`, `test_compatibility_idempotent`, plus a `cs_field_mapping_sample.json` fixture
- `get-scouted-be/core/import_reports/Compatability Scores_20260721T015413Z.{json,md}` - Reviewed full-dataset import report artifact

## Decisions Made

- Resumed rather than restarted a prior session's partially-completed background full-scale run, relying on the command's idempotent upsert to make the resume safe -- see key-decisions in frontmatter for full detail.
- Confirmed the sole unresolved header (`"St_DOT_ Louis City"`) is genuinely absent from `cs_field_mapping.json` rather than a resolution bug, and left it as `club=null` per the plan's explicit must_haves.
- Kept only the initial full-import report committed, discarding the idempotent-rerun report after confirming zero net row-count change directly via a DB count query -- same convention as Plans 04/05/06.

## Deviations from Plan

None - plan executed exactly as written. The command, tests, and full-scale verification all matched the plan's must_haves and acceptance criteria without requiring any code changes beyond what Task 1/2 already specified.

## Issues Encountered

- A background full-scale import from a prior session had left the `PlayerClubCompatibility` table partially populated (2,149,892 rows: `CS_AM.csv` fully done, `CS_CB_25.csv` partially done) when this session resumed. Briefly ran a duplicate second full-scale process by mistake before noticing the original was still alive; killed the duplicate immediately (harmless -- no rows had been written by the duplicate yet) and let the original run to completion. No data corruption resulted; the idempotent upsert design meant even a genuine double-run would have been safe.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `PlayerClubCompatibility` is fully populated (8,188,712 rows, both directions queryable: by player or by club) and ready for Plan 09's `import_all` orchestrator + reconciliation + combined report.
- The one unresolved club header (`"St_DOT_ Louis City"`) should be visible in Plan 09's combined report; no action needed unless a future data-quality pass wants to add it to `cs_field_mapping.json`.

---
*Phase: 01-data-foundation*
*Completed: 2026-07-21*
