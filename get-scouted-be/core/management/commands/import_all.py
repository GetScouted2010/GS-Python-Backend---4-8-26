"""Dependency-ordered orchestrator for the full Phase 1 data-import pipeline.

Runs, IN ORDER, the six import/cleanup commands built across Plans 04-08
plus the A1 fix (2026-09-09):
  1. import_clubs_playstyles      (Club)                    -- Players.csv + Playstyles.csv
  2. import_players                (Player)                  -- Players.csv, needs Club rows
  2.5. dedupe_players              (Player cleanup)          -- removes exact-duplicate rows (see dedupe_players.py)
  3. import_position_roles         (PlayerRoleScore)         -- Positions/*.csv, needs Player rows
  4. import_compatibility_scores   (PlayerClubCompatibility) -- Compatability Scores/*, needs Player+Club
  5. import_transfers              (Transfer)                -- transferdata final.csv, needs Player+Club

This is the dependency order because import_players/import_position_roles/
import_compatibility_scores/import_transfers all resolve their FKs from
in-memory `{name/unique_id: id}` maps built from an ALREADY-POPULATED
Club/Player table -- none of those four commands create Club or Player rows
themselves (see each command's module docstring). Running them out of order
silently produces zero rows (the commands print an error and no-op if the
table they depend on is empty) rather than a partial/incorrect import.

`dedupe_players` runs immediately after `import_players` and BEFORE
`import_position_roles`/`import_compatibility_scores` -- deliberately, so a
duplicate row's PlayerRoleScore/PlayerClubCompatibility children are never
created just to be cascade-deleted a step later (wasted work at ~8.1M-row
scale). It does not violate import_players' own locked "never skip a row"
policy: that policy governs the CSV->DB step itself; this is a separate,
explicit, re-runnable cleanup pass layered on top (same shape as
recompute_scores/train_tfm_model), and it never runs silently -- see its
own module docstring and JSON report.

After all five steps run, this command builds ONE combined report:
  - each sub-command's own report is located (by locating the newest report
    JSON written into `--report-dir` during that step) and embedded verbatim
    under its own key, so nothing from the five per-entity reports is lost;
  - a `reconciliation` section compares live table counts against the
    *actual* source-CSV row counts, read from disk at run time -- never
    hardcoded -- so a reviewer can see at a glance whether every row made it
    in without re-deriving expected counts by hand.

`--skip-compatibility` lets an operator do a fast end-to-end smoke run of the
other four steps without paying for the ~8.1M-row PlayerClubCompatibility
import (which alone takes several minutes against the real dataset).
"""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

from clubs.models import Club
from core.import_utils import DEFAULT_REPORT_DIR, ImportReport, resolve_dataset_path
from players.models import Player, PlayerClubCompatibility, PlayerRoleScore
from players.wyscout_season import DEFAULT_ID_OFFSET as WYSCOUT_ID_OFFSET
from transfers.models import Transfer

# Row-count reconciliation only makes a fixed-expectation comparison for
# tables whose source is a single CSV file with one row per DB row (Club,
# Player, Transfer). PlayerRoleScore/PlayerClubCompatibility are melted from
# 9 wide files each and depend on file-overlap + player-match rate -- there
# is no single fixed "expected" count to compare against (01-RESEARCH.md),
# so their reconciliation entries report the actual db count with
# source_rows/delta left as None rather than a misleading comparison.
NO_FIXED_EXPECTATION_TABLES = ("PlayerRoleScore", "PlayerClubCompatibility")


def _count_csv_data_rows(path) -> int | None:
    """Count data rows (excludes header) in a CSV file, or None if missing."""
    path = Path(path)
    if not path.exists():
        return None
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def _count_distinct_clubs(players_csv) -> int | None:
    """Distinct non-blank Team_within_selected_timeframe values in Players.csv.

    Mirrors import_clubs_playstyles's own club-universe derivation (there is
    no dedicated Clubs source file -- see clubs/models.py docstring).
    """
    players_csv = Path(players_csv)
    if not players_csv.exists():
        return None
    with open(players_csv, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        teams = {
            row["Team_within_selected_timeframe"]
            for row in reader
            if row.get("Team_within_selected_timeframe")
        }
    return len(teams)


def _newest_report_json(report_dir: Path, since: float) -> Path | None:
    """Find the most-recently-written *.json report in `report_dir` created
    at or after the `since` timestamp (a `time.time()` snapshot taken right
    before the step that should have produced it)."""
    candidates = [p for p in report_dir.glob("*.json") if p.stat().st_mtime >= since]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


class Command(BaseCommand):
    help = (
        "Run the full Phase 1 import pipeline (clubs -> players -> position "
        "roles -> compatibility -> transfers) in dependency order, then write "
        "one combined report with a source-vs-db row-count reconciliation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--report-dir",
            default=DEFAULT_REPORT_DIR,
            help="Directory every sub-command AND the combined report are written to.",
        )
        parser.add_argument("--players-csv", default=None, help="Path to Players.csv.")
        parser.add_argument(
            "--playstyles-csv", default=None, help="Path to Playstyles.csv."
        )
        parser.add_argument(
            "--transfers-csv", default=None, help='Path to "transferdata final.csv".'
        )
        parser.add_argument(
            "--positions-dir",
            default=None,
            help="Directory containing the 9 Positions/*.csv files.",
        )
        parser.add_argument(
            "--cs-dir",
            default=None,
            help='Directory containing the 9 "Compatability Scores" CSVs.',
        )
        parser.add_argument(
            "--skip-compatibility",
            action="store_true",
            help=(
                "Skip the ~8.1M-row PlayerClubCompatibility import (fast "
                "smoke run of the other four steps)."
            ),
        )

    def _banner(self, text: str) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING(f"\n=== {text} ==="))

    def _run_step(self, watch_dir: Path, label: str, command_name: str, **kwargs):
        self._banner(label)
        since = time.time()
        call_command(command_name, **kwargs)
        json_path = _newest_report_json(watch_dir, since)
        report_data = None
        if json_path is not None:
            try:
                report_data = json.loads(json_path.read_text())
            except (OSError, json.JSONDecodeError):
                report_data = None
        return json_path, report_data

    def handle(self, *args, **options):
        report_dir = Path(options["report_dir"])
        report_dir.mkdir(parents=True, exist_ok=True)

        players_csv = options["players_csv"] or resolve_dataset_path("Players.csv")
        playstyles_csv = options["playstyles_csv"] or resolve_dataset_path(
            "Playstyles.csv"
        )
        transfers_csv = options["transfers_csv"] or resolve_dataset_path(
            "transferdata final.csv"
        )

        step_reports: dict[str, dict] = {}
        step_report_paths: dict[str, str] = {}

        json_path, data = self._run_step(
            report_dir,
            "1/6 import_clubs_playstyles (Club)",
            "import_clubs_playstyles",
            players_csv=str(players_csv),
            playstyles_csv=str(playstyles_csv),
            report_dir=str(report_dir),
        )
        step_reports["clubs"] = data
        step_report_paths["clubs"] = str(json_path) if json_path else None

        json_path, data = self._run_step(
            report_dir,
            "2/6 import_players (Player)",
            "import_players",
            players_csv=str(players_csv),
            report_dir=str(report_dir),
        )
        step_reports["players"] = data
        step_report_paths["players"] = str(json_path) if json_path else None

        # A1 fix: cleanup pass, not a source import -- see dedupe_players.py
        # module docstring for why this runs HERE (right after import_players,
        # before position-roles/compatibility) rather than as a change to
        # import_players itself.
        json_path, data = self._run_step(
            report_dir,
            "2.5/6 dedupe_players (Player cleanup)",
            "dedupe_players",
            report_dir=str(report_dir),
        )
        step_reports["dedupe_players"] = data
        step_report_paths["dedupe_players"] = str(json_path) if json_path else None

        position_kwargs = {"report_dir": str(report_dir)}
        if options["positions_dir"]:
            position_kwargs["positions_dir"] = options["positions_dir"]
        json_path, data = self._run_step(
            report_dir,
            "3/6 import_position_roles (PlayerRoleScore)",
            "import_position_roles",
            **position_kwargs,
        )
        step_reports["position_roles"] = data
        step_report_paths["position_roles"] = str(json_path) if json_path else None

        if options["skip_compatibility"]:
            self._banner(
                "4/6 import_compatibility_scores -- SKIPPED (--skip-compatibility)"
            )
            step_reports["compatibility"] = {"skipped": True}
            step_report_paths["compatibility"] = None
        else:
            cs_kwargs = {"report_dir": str(report_dir)}
            if options["cs_dir"]:
                cs_kwargs["cs_dir"] = options["cs_dir"]
            json_path, data = self._run_step(
                report_dir,
                "4/6 import_compatibility_scores (PlayerClubCompatibility)",
                "import_compatibility_scores",
                **cs_kwargs,
            )
            step_reports["compatibility"] = data
            step_report_paths["compatibility"] = str(json_path) if json_path else None

        json_path, data = self._run_step(
            report_dir,
            "5/6 import_transfers (Transfer)",
            "import_transfers",
            transfers_csv=str(transfers_csv),
            report_dir=str(report_dir),
        )
        step_reports["transfers"] = data
        step_report_paths["transfers"] = str(json_path) if json_path else None

        self._banner("Reconciliation")

        # import_clubs_playstyles derives the Club universe as the UNION of
        # Players.csv's Team_within_selected_timeframe values AND any
        # Playstyles-only club name (its own docstring: "at most one such
        # name, e.g. Borussia M_gladbach, but never assume -- union
        # defensively"). Delegate to that command's own authoritative
        # `club_derivation.distinct_clubs` count rather than recomputing
        # just the Players.csv side here and falsely flagging the (expected)
        # +1-or-so delta from any Playstyles-only club names.
        clubs_report = step_reports.get("clubs") or {}
        distinct_clubs = (clubs_report.get("club_derivation") or {}).get(
            "distinct_clubs"
        )
        if distinct_clubs is None:
            distinct_clubs = _count_distinct_clubs(players_csv)

        players_source_rows = _count_csv_data_rows(players_csv)
        transfers_source_rows = _count_csv_data_rows(transfers_csv)

        # dedupe_players (step 2.5) removes exact-duplicate rows RIGHT after
        # import_players loads the raw CSV 1:1 -- so a healthy Player count
        # is `players_source_rows - rows_removed`, not the raw source row
        # count. Same pattern as the Transfer duplicate-collapse adjustment
        # below.
        dedupe_report = step_reports.get("dedupe_players") or {}
        players_rows_removed = dedupe_report.get("rows_removed")
        players_expected_rows = players_source_rows
        if players_source_rows is not None and players_rows_removed:
            players_expected_rows = players_source_rows - players_rows_removed

        # import_transfers collapses any source rows sharing the exact same
        # composite event key within one chunk (Postgres cannot apply
        # ON CONFLICT DO UPDATE to the same conflict target twice within one
        # INSERT -- see import_transfers.py's `_dedupe_transfer_objs`). The
        # real dataset has ~51 such genuinely-duplicated rows, so a healthy
        # Transfer count is `transfers_source_rows - duplicates_collapsed`,
        # not the raw source row count -- adjust the expectation using the
        # transfers sub-report's own count rather than hardcoding "51".
        transfers_report = step_reports.get("transfers") or {}
        duplicates_collapsed = (
            transfers_report.get("transfer_import", {}).get(
                "duplicate_event_keys_collapsed"
            )
            if isinstance(transfers_report.get("transfer_import"), dict)
            else None
        )
        transfers_expected_rows = transfers_source_rows
        if transfers_source_rows is not None and duplicates_collapsed:
            transfers_expected_rows = transfers_source_rows - duplicates_collapsed

        # `import_wyscout_season` (a separate, deliberately-run command) adds
        # Player rows under unique_ids >= WYSCOUT_ID_OFFSET plus Clubs that
        # exist only for those rows. This pipeline's source files know
        # nothing about either, so reconcile only what it owns -- otherwise
        # every run after a Wyscout-season import would report a permanent,
        # meaningless REVIEW that teaches operators to ignore the check.
        wyscout_player_rows = Player.objects.filter(unique_id__gte=WYSCOUT_ID_OFFSET).count()
        # A Wyscout-only club: no Playstyles source row, no base-pipeline
        # players, at least one Wyscout player. (Every club derived from
        # Players.csv has a base player; a Playstyles-only club has a
        # source_unique_id -- so neither is miscounted here.)
        wyscout_only_clubs = (
            Club.objects.filter(
                source_unique_id__isnull=True, players__unique_id__gte=WYSCOUT_ID_OFFSET
            )
            .exclude(players__unique_id__lt=WYSCOUT_ID_OFFSET)
            .distinct()
            .count()
        )

        db_counts = {
            "Club": Club.objects.count() - wyscout_only_clubs,
            "Player": Player.objects.filter(unique_id__lt=WYSCOUT_ID_OFFSET).count(),
            "PlayerRoleScore": PlayerRoleScore.objects.count(),
            "PlayerClubCompatibility": PlayerClubCompatibility.objects.count(),
            "Transfer": Transfer.objects.count(),
        }
        source_counts = {
            "Club": distinct_clubs,
            "Player": players_expected_rows,
            "PlayerRoleScore": None,
            "PlayerClubCompatibility": None,
            "Transfer": transfers_expected_rows,
        }

        reconciliation_rows = []
        review_needed = False
        for table, db_rows in db_counts.items():
            source_rows = source_counts[table]
            if source_rows is None:
                delta = None
            else:
                delta = db_rows - source_rows
                if delta != 0:
                    review_needed = True
            note = None
            if table in NO_FIXED_EXPECTATION_TABLES:
                note = (
                    "No fixed source-row expectation (melted from 9 wide "
                    "files, depends on file overlap + player-match rate) -- "
                    "reporting actual db count only."
                )
            if table == "PlayerClubCompatibility" and options["skip_compatibility"]:
                note = (
                    (note + " " if note else "")
                    + "--skip-compatibility was set: this run did NOT touch "
                    "this table; db_rows reflects whatever was already there."
                )
            if table == "Transfer" and duplicates_collapsed:
                note = (
                    (note + " " if note else "")
                    + f"source_rows adjusted down by {duplicates_collapsed} "
                    "duplicate-composite-event-key source row(s) collapsed "
                    "by import_transfers (raw CSV row count was "
                    f"{transfers_source_rows}) -- see "
                    "sub_reports.transfers.transfer_import."
                )
            if table == "Club" and wyscout_only_clubs:
                note = (
                    (note + " " if note else "")
                    + f"excludes {wyscout_only_clubs} club(s) that exist only for "
                    "Wyscout-season players (import_wyscout_season)."
                )
            if table == "Player" and wyscout_player_rows:
                note = (
                    (note + " " if note else "")
                    + f"excludes {wyscout_player_rows} Wyscout-season row(s) "
                    f"(unique_id >= {WYSCOUT_ID_OFFSET:,}, import_wyscout_season)."
                )
            if table == "Player" and players_rows_removed:
                note = (
                    (note + " " if note else "")
                    + f"source_rows adjusted down by {players_rows_removed} "
                    "exact-duplicate row(s) removed by dedupe_players (raw "
                    f"CSV row count was {players_source_rows}) -- see "
                    "sub_reports.dedupe_players."
                )
            reconciliation_rows.append(
                {
                    "table": table,
                    "source_rows": source_rows,
                    "db_rows": db_rows,
                    "delta": delta,
                    "note": note,
                }
            )

        combined = ImportReport(source_file="import_all", source_row_count=0)
        combined.set_counts(
            created=0,
            updated=0,
            flagged=sum(
                1 for r in reconciliation_rows if r["delta"] not in (0, None)
            ),
        )
        combined.add_section(
            "pipeline",
            {
                "order": [
                    "import_clubs_playstyles",
                    "import_players",
                    "dedupe_players",
                    "import_position_roles",
                    "import_compatibility_scores"
                    + (" (SKIPPED)" if options["skip_compatibility"] else ""),
                    "import_transfers",
                ],
                "report_dir": str(report_dir),
                "sub_report_paths": step_report_paths,
            },
        )
        combined.add_section("table_counts", db_counts)
        combined.add_section("reconciliation", reconciliation_rows)
        combined.add_section("sub_reports", step_reports)

        json_path, md_path = combined.write(str(report_dir))

        status = "REVIEW" if review_needed else "PASS"
        self.stdout.write(
            self.style.SUCCESS(
                f"import_all complete. {status}: reconciliation "
                f"{'has unexpected deltas -- see report' if review_needed else 'matches source counts'}. "
                f"Combined report: {json_path}, {md_path}"
            )
        )
