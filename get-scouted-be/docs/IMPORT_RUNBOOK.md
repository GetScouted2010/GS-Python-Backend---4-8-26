# Import Runbook: Running the Full Phase 1 Data Migration

**Purpose:** Operator instructions for running the whole Phase 1 CSV-to-Postgres migration with
`python manage.py import_all`, and for reviewing its combined report -- the "reviewed import
report for the whole migration" DATA-05 requires, not five disconnected per-table reports.

`import_all` (`core/management/commands/import_all.py`) wires together the five import commands
built in Plans 04-08 into one dependency-ordered, re-runnable command.

---

## 1. Prerequisites

1. Postgres is up and reachable.
2. `DATABASE_URL` (and any other required env vars -- see `config/settings/base.py`) is set in
   your shell or `.env`.
3. Install dependencies:
   ```bash
   cd get-scouted-be
   pip install -r requirements/dev.txt
   ```
4. Apply migrations:
   ```bash
   python manage.py migrate
   ```
5. The real dataset CSVs are present under `DATASET_DIR` (default:
   `API-Updated-/dataset/`, i.e. the repo-root sibling of `get-scouted-be/` -- see
   `config/settings/base.py`). `import_all` (and every sub-command) resolves each CSV's default
   path against `DATASET_DIR` automatically; you only need `--*-csv`/`--*-dir` overrides if your
   files live somewhere else.

## 2. Running the migration

The whole migration is one command:

```bash
cd get-scouted-be
python manage.py import_all
```

That's it. `import_all` runs all five imports, in dependency order, and writes one combined report.

**Useful options:**

| Option | Purpose |
|---|---|
| `--report-dir DIR` | Where every sub-command's report AND the combined report land (default: `core/import_reports/`). |
| `--players-csv`, `--playstyles-csv`, `--transfers-csv`, `--positions-dir`, `--cs-dir` | Override any input path/dir (all default to the real dataset under `DATASET_DIR`). |
| `--skip-compatibility` | Skip the `PlayerClubCompatibility` step (~8.1M rows, the slowest step by far -- took ~3-4 minutes on the reference dev machine). Use this for a fast smoke run of the other four steps; re-run without the flag afterward to fill in compatibility data. |

**It is safe to re-run.** Every one of the five underlying commands does an idempotent upsert
(`bulk_create(update_conflicts=True)` on each table's natural/composite key) -- running
`import_all` twice in a row produces zero net row change across all five tables. This is proven by
`core/tests/test_import_all.py::test_import_all_idempotent` and was also manually verified against
the full real dataset for `import_compatibility_scores` specifically (Plan 07's SUMMARY: re-run
left row count unchanged at 8,188,712).

## 3. Dependency order (and why)

```
1. import_clubs_playstyles   -> Club                     (no dependency)
2. import_players             -> Player                   (needs Club, for Player.club FK)
3. import_position_roles      -> PlayerRoleScore           (needs Player, for the player FK)
4. import_compatibility_scores -> PlayerClubCompatibility  (needs Player AND Club, for both FKs)
5. import_transfers            -> Transfer                 (needs Player AND Club, for both FKs)
```

Steps 2-5 each resolve their foreign keys from an in-memory `{name/unique_id: id}` map built from
an *already-populated* Club/Player table -- none of them create Club or Player rows themselves.
Running them out of order does not error loudly: `import_players`, `import_position_roles`, and
`import_compatibility_scores` each print an error and no-op if their upstream table is empty,
which is why `import_all` always runs the five steps in this fixed order rather than leaving
ordering to the operator.

## 4. Reading the combined report

`import_all` writes ONE combined report (JSON + Markdown, same `ImportReport` format every
sub-command uses) into `--report-dir`, named `import_all_<timestamp>.{json,md}`. It contains:

- **`pipeline`** -- the step order that ran, whether `--skip-compatibility` was set, and the file
  path of each individual sub-command's own report (so you can drill into e.g. just the Player
  import's field issues).
- **`table_counts`** -- the live row count of all five tables after the run.
- **`reconciliation`** -- one row per table: `{table, source_rows, db_rows, delta, note}`.
  `source_rows` is read directly from the actual CSV file(s) on disk at run time (never
  hardcoded), so this reflects whatever dataset you actually pointed the command at. A non-zero
  `delta` on `Club`, `Player`, or `Transfer` means the reconciliation FAILED and needs
  investigation. `Transfer`'s `source_rows` is the raw CSV row count MINUS however many rows
  `import_transfers` itself collapsed for sharing an exact duplicate composite event key (see
  "Expected coverage gaps" item 6 below) -- read from that sub-command's own report, not
  hardcoded -- so a healthy `Transfer` run still reconciles to `delta == 0`; the `note` field
  states the raw (pre-adjustment) CSV row count for transparency. `PlayerRoleScore` and
  `PlayerClubCompatibility` report `source_rows: null` by design (see item 2 below) -- there is
  no single fixed expected count for either, so only their actual `db_rows` is meaningful.
- **`sub_reports`** -- the full embedded JSON of each of the five individual command reports,
  including their own `field_issues` (grouped by field+issue, not one entry per row) and any
  named sections (`club_derivation`, `unresolved_club_names`, `per_position_row_counts`, etc).

The command's final stdout line prints **PASS** (reconciliation matches source counts, or the
only deltas are on the two no-fixed-expectation tables) or **REVIEW** (an unexpected delta was
found on `Club`, `Player`, or `Transfer` -- open the report and investigate before trusting the
data).

## 5. Expected coverage gaps -- NOT bugs

A reviewer opening the combined (or per-command) report will see several rates/counts that look
like missing data at first glance. Every one of these is a verified, expected property of the
source dataset itself, not an import bug. Do not "fix" these by changing import logic.

1. **~77% of clubs have `Club.playing_style` fields all null.** Only ~239 of the ~1,059 clubs
   derived from `Players.csv` appear in `Playstyles.csv` at all -- there is no playing-style data
   for the rest anywhere in the source dataset. See the `import_clubs_playstyles` report's
   `club_derivation.playing_style_coverage_rate` section.

2. **~3,081 GK players have zero `PlayerRoleScore` rows.** There is no GK `Positions/*.csv` file
   in the source dataset at all (the 9 real files cover AM/CB/CM/DM/FWD/LB/LW/RB/RW only) -- GK
   role scores simply don't exist upstream. See the `import_position_roles` report's
   `gk_coverage_note` section.

3. **~18% of players are missing `Contract_expires`; ~14% are missing `Market_value`.** These are
   blank cells in the real `Players.csv` -- kept as `null` on the `Player` row and flagged in the
   report's `field_issues` (never skipped; every source row still becomes exactly one `Player`
   row, per the project's "never drop a row" data-quality policy).

4. **INTENTIONAL BOUNDED EXCEPTION to the "never skip a row" policy:** `import_position_roles`
   and `import_compatibility_scores` **SKIP** (do not insert) any score row whose `UniqueID`
   does not match an existing `Player`, because `PlayerRoleScore.player` and
   `PlayerClubCompatibility.player` are **NON-NULLABLE** foreign keys -- a null-FK row for either
   is structurally impossible to insert, unlike `Transfer.player` (which IS nullable, and where
   an unmatched player is correctly imported with `player=None` rather than skipped). Every
   skipped row is still logged, individually, per `UniqueID`, as a `(UniqueID,
   no_matching_player)` field issue in that command's own report -- nothing is silently dropped
   from the report even though the row itself is not inserted.

   In practice this count should be **~0**: 01-RESEARCH.md verified ~100% `UniqueID` overlap
   between `Players.csv` and the role/compatibility source files, and the full-scale
   `import_compatibility_scores` run (Plan 07) confirmed exactly **0** unmatched players across
   all 8,188,712 rows. If you see a non-trivial `no_matching_player` count in a real run, that
   means the upstream `import_players` step did not actually complete (or ran against a different
   `Players.csv` than the role/compatibility files expect) -- it is a signal to re-check the
   Player import, not evidence of silent data loss in this step.

5. **~98% of Transfer rows have `Transfer.player` = null** (verified against the real dataset:
   46,391 of 47,252 unmatched). This is NOT a join bug -- it is the direct, expected consequence
   of two compounding, already-documented design decisions: (a) `Players.csv` has one row per
   player-PER-SEASON (41,708 rows for far fewer distinct real people), so the same person's name
   recurs across many rows, and (b) `import_transfers`' player-name matching (Plan 08, "never
   guess" policy) only resolves a name that is UNIQUE across the whole `Player` table --
   ambiguous (non-unique) names are treated exactly like genuinely-absent names: unmatched,
   logged, `player=None`, row still imported. Combined, almost every real player name collides
   with itself across seasons and is therefore excluded from the resolvable map. This was flagged
   in 01-08-SUMMARY.md as needing a full-scale observation, which this plan's phase-gate run
   provided. It is expected given the current Player/Transfer name-matching design, not evidence
   of a broken join -- but it does mean `Transfer.player` is populated for only a small minority
   of rows today; note this if Transfer-to-Player joins matter for downstream consumers.

6. **Real "transferdata final.csv" contains ~51 pairs of genuinely duplicated rows** -- literal
   duplicate data-entry rows that share every one of the 6 composite event-key columns
   (`player_name_raw`, `year`, `window`, `movement`, `club`, `dealing_club`). Postgres cannot
   apply `ON CONFLICT DO UPDATE` to the same conflict-target row twice within a single `INSERT`
   statement (`CardinalityViolation`), so `import_transfers` collapses any such rows found within
   one processing chunk, keeping the last occurrence, and logs every collapsed row individually
   as a `(transfer_event_key, duplicate_source_row)` field issue plus a
   `transfer_import.duplicate_event_keys_collapsed` count in its own report. `import_all`'s
   reconciliation already adjusts `Transfer`'s expected row count down by this same number (read
   from that report, never hardcoded), so a healthy run still reconciles to `delta == 0`. If this
   count changes on a future dataset refresh, that's expected too (it reflects however many exact
   duplicates that refresh's source file happens to contain) -- it is not, by itself, a sign of an
   import bug.

## 6. Re-running / troubleshooting

- **Safe to re-run in full**, any time, including after a partial/failed run -- every step
  upserts idempotently (see "It is safe to re-run" above).
- If `import_all` reports **REVIEW**, open the Markdown report (`import_all_<timestamp>.md`),
  check which table's `reconciliation` row has a non-zero `delta`, then open that table's own
  sub-report (path is in the `pipeline.sub_report_paths` section) for the specific
  `field_issues`/`unresolved_*` sections explaining why.
- `--skip-compatibility` is the fastest way to sanity-check the other four steps end-to-end
  before committing to the multi-minute compatibility import.
