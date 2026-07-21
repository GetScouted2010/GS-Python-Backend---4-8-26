"""Normalize the 9 wide Compatibility Scores matrices into PlayerClubCompatibility.

Each `Compatability Scores/CS_*.csv` file is UniqueID, Position, plus ~212
club-name columns (one score per club). This is the highest-volume table in
Phase 1 (~8.1M values total across the 9 files) -- the wide shape cannot be
sorted/upserted by the ORM directly, so it is normalized at import time via
`pandas.melt` and upserted in chunks small enough to keep memory bounded.

Club column headers are resolved to a `Club` FK in two steps: (a) an exact
match against `Club.name`; (b) if that fails, a reverse-lookup through
`cs_field_mapping.json` (which maps a display name, e.g. "St. Louis City", to
the sanitized header actually used as a CSV column, e.g. "St_DOT_ Louis
City") to recover the display name and retry the `Club.name` match. Any
header that still doesn't resolve keeps `club=null` and preserves the
original header in `club_name_raw` -- it is NEVER dropped, and each distinct
unresolved header is logged exactly once (there are only ~212 distinct
headers per file, not one entry per row).

The unique key for the idempotent upsert is `(player, club_name_raw)`, NOT
`(player, club)` -- `club` is null for unresolved headers and Postgres
treats multiple NULLs as non-conflicting, which would break
`bulk_create(update_conflicts=True)` idempotency if `club` were part of the
conflict target (see 01-RESEARCH.md Open Question 2 and the
`uniq_player_clubname` constraint on `PlayerClubCompatibility`).

Depends on Plan 05 (`import_players`) and Plan 04 (`import_clubs_playstyles`)
having already populated `Player`/`Club` -- this command resolves both FKs
from in-memory maps and does not create either table's rows itself.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from clubs.models import Club
from core.import_utils import DEFAULT_REPORT_DIR, ImportReport, resolve_dataset_path
from players.models import Player, PlayerClubCompatibility

# The 9 real Compatability Scores filenames -> position_group. Filenames are
# deliberately inconsistent on disk (a stray "CS_DM_25 NEW.csv" with a space
# and a "NEW" suffix) -- these are the literal filenames, not something to
# normalize away.
FILE_TO_POSITION = {
    "CS_AM.csv": "AM",
    "CS_CB_25.csv": "CB",
    "CS_CM.csv": "CM",
    "CS_DM_25 NEW.csv": "DM",
    "CS_FWD.csv": "FWD",
    "CS_LB_25.csv": "LB",
    "CS_LW.csv": "LW",
    "CS_RB.csv": "RB",
    "CS_RW.csv": "RW",
}

# Below this measured rows/sec on the very first batch, warn that the
# psycopg copy()-into-staging-table fallback (per 01-RESEARCH.md's
# volume-driven import mechanics note) may be worth trying -- but this is a
# go/no-go *signal*, not a hard stop; the run always proceeds either way.
THROUGHPUT_WARN_THRESHOLD_ROWS_PER_SEC = 1000


def _clean(value):
    """Convert a pandas scalar to a plain Python value, mapping NA/NaN to None."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def load_header_to_display(cs_dir) -> dict:
    """Load cs_field_mapping.json and invert it to sanitized-header -> display-name.

    The file maps display name -> sanitized CSV header (e.g.
    `"St. Louis City": "St_DOT_ Louis City"`); most entries are unchanged
    (key == value). Inverting it gives the lookup this command actually
    needs: given a raw CSV column header, recover the real display name to
    retry against `Club.name`.
    """
    mapping_path = Path(cs_dir) / "cs_field_mapping.json"
    if not mapping_path.exists():
        return {}
    raw = json.loads(mapping_path.read_text(encoding="utf-8-sig"))
    return {sanitized: display for display, sanitized in raw.items()}


class Command(BaseCommand):
    help = (
        "Normalize the 9 wide Compatability Scores matrices into long "
        "PlayerClubCompatibility rows, resolving club-name column headers "
        "via exact match then cs_field_mapping.json (idempotent upsert on "
        "player+club_name_raw)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--cs-dir",
            default=None,
            help=(
                "Directory containing the 9 CS_*.csv files and "
                "cs_field_mapping.json (default: "
                "DATASET_DIR/'Compatability Scores')."
            ),
        )
        parser.add_argument(
            "--report-dir",
            default=DEFAULT_REPORT_DIR,
            help="Directory to write the import report to.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=8000,
            help="bulk_create batch size / target rows per upsert chunk (default: 8000).",
        )

    def handle(self, *args, **options):
        cs_dir = (
            Path(options["cs_dir"])
            if options["cs_dir"]
            else resolve_dataset_path("Compatability Scores")
        )
        report_dir = options["report_dir"]
        batch_size = options["batch_size"]

        player_id_map = dict(Player.objects.values_list("unique_id", "id"))
        if not player_id_map:
            self.stderr.write(
                self.style.ERROR(
                    "No Player rows found -- run `python manage.py import_players` "
                    "first."
                )
            )
            return

        club_id_map = dict(Club.objects.values_list("name", "id"))
        header_to_display = load_header_to_display(cs_dir)

        # Per-run cache: resolve each distinct raw header to a club_id (or
        # None) exactly once, no matter how many rows/files reference it.
        header_resolution: dict[str, int | None] = {}
        unresolved_club_names: set[str] = set()

        def resolve_header(header: str):
            if header in header_resolution:
                return header_resolution[header]
            club_id = club_id_map.get(header)
            if club_id is None:
                display_name = header_to_display.get(header)
                if display_name is not None:
                    club_id = club_id_map.get(display_name)
            header_resolution[header] = club_id
            if club_id is None:
                unresolved_club_names.add(header)
            return club_id

        report = ImportReport(source_file=str(cs_dir))

        total_rows = 0
        unmatched_player_uids: set[int] = set()
        per_file_row_counts: dict[str, int] = {}
        files_missing: list[str] = []
        throughput_checked = False

        for filename, default_position in FILE_TO_POSITION.items():
            file_path = cs_dir / filename
            if not file_path.exists():
                # Tolerate a partial set of files (e.g. fixture-driven tests
                # that only ship one position's sample file) instead of
                # crashing the whole run.
                files_missing.append(filename)
                continue

            header_cols = pd.read_csv(
                file_path, nrows=0, encoding="utf-8-sig"
            ).columns.tolist()
            club_columns = [c for c in header_cols if c not in ("UniqueID", "Position")]
            dtypes = {"UniqueID": "Int64", "Position": "string"}
            for col in club_columns:
                dtypes[col] = "Float64"

            # Size the raw-CSV read chunk so that each melted long-format
            # chunk lands close to `batch_size` rows -- this is what keeps
            # the long frame's memory bounded regardless of how many rows
            # the source file has (RESEARCH.md: 8.1M rows total, one file
            # alone melts to >1.6M long rows if read whole).
            read_chunksize = max(1, batch_size // max(len(club_columns), 1))

            file_row_count = 0
            for chunk in pd.read_csv(
                file_path,
                dtype=dtypes,
                na_values=["", "N/A", "NA"],
                keep_default_na=True,
                chunksize=read_chunksize,
                encoding="utf-8-sig",
            ):
                long_df = chunk.melt(
                    id_vars=["UniqueID", "Position"],
                    value_vars=club_columns,
                    var_name="club_name_raw",
                    value_name="score",
                )

                objs = []
                for row in long_df.itertuples(index=False):
                    uid = _clean(row.UniqueID)
                    if uid is None:
                        continue
                    uid = int(uid)
                    player_id = player_id_map.get(uid)
                    if player_id is None:
                        unmatched_player_uids.add(uid)
                        continue

                    club_name_raw = row.club_name_raw
                    club_id = resolve_header(club_name_raw)
                    position_group = _clean(row.Position) or default_position

                    objs.append(
                        PlayerClubCompatibility(
                            player_id=player_id,
                            club_id=club_id,
                            club_name_raw=club_name_raw,
                            position_group=position_group,
                            score=_clean(row.score),
                        )
                    )

                if objs:
                    start = time.monotonic() if not throughput_checked else None
                    with transaction.atomic():
                        PlayerClubCompatibility.objects.bulk_create(
                            objs,
                            batch_size=batch_size,
                            update_conflicts=True,
                            unique_fields=["player", "club_name_raw"],
                            update_fields=["club", "score", "position_group"],
                        )
                    if start is not None:
                        elapsed = time.monotonic() - start
                        rate = len(objs) / elapsed if elapsed > 0 else float("inf")
                        throughput_checked = True
                        if rate < THROUGHPUT_WARN_THRESHOLD_ROWS_PER_SEC:
                            self.stdout.write(
                                self.style.WARNING(
                                    "Early throughput check: first bulk_create "
                                    f"batch measured ~{rate:.0f} rows/sec "
                                    f"({len(objs)} rows in {elapsed:.2f}s). At "
                                    "this rate the full ~8.1M-row import will "
                                    "be slow -- consider the psycopg copy() "
                                    "staging-table fallback (01-RESEARCH.md's "
                                    "volume-driven import mechanics note). "
                                    "Proceeding anyway."
                                )
                            )
                        else:
                            self.stdout.write(
                                "Early throughput check: first bulk_create "
                                f"batch measured ~{rate:.0f} rows/sec "
                                f"({len(objs)} rows in {elapsed:.2f}s). OK."
                            )

                file_row_count += len(objs)
                total_rows += len(objs)

            per_file_row_counts[filename] = file_row_count

        report.source_row_count = total_rows
        report.set_counts(
            created=total_rows, updated=0, flagged=len(unmatched_player_uids)
        )
        report.add_section("per_file_row_counts", per_file_row_counts)
        # Logged once per distinct header (not per row) -- there are only
        # ~212 distinct club-name headers per file, so this stays readable
        # even though the run itself touches ~8.1M score values.
        report.add_section(
            "unresolved_club_names", sorted(unresolved_club_names)
        )
        if unmatched_player_uids:
            report.add_section(
                "unmatched_player_unique_ids",
                sorted(unmatched_player_uids)[:50],
            )
        if files_missing:
            report.add_section("files_missing", sorted(files_missing))

        json_path, md_path = report.write(report_dir)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {total_rows} PlayerClubCompatibility rows across "
                f"{len(per_file_row_counts)} files "
                f"({len(unresolved_club_names)} unresolved club headers, "
                f"{len(unmatched_player_uids)} unmatched player UniqueIDs). "
                f"Report: {json_path}, {md_path}"
            )
        )
