"""Import the 9 per-position role files (Positions/*.csv) into PlayerRoleScore.

Normalizes wide (one row per player, 4-7 role float columns) to long
PlayerRoleScore rows (one per player-role pair), resolving the player FK from
the `UniqueID` column against `Player.unique_id`. Verified in
01-RESEARCH.md's "PlayerRoleScore Model" section: each Positions/*.csv file's
`UniqueID`s are ~100% present in Players.csv -- unlike transferdata.csv's
`UniqueID` column (which is club-scoped), this one IS a genuine player id.

GK players legitimately get zero PlayerRoleScore rows -- there is no GK
Positions/*.csv file in the source dataset. The report states this explicitly
so it is never mistaken for a join failure.

Depends on Plan 05's `import_players` command having already populated the
Player table -- this command resolves PlayerRoleScore.player from an
in-memory `{Player.unique_id: Player.id}` map and does not create Player
rows itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from core.import_utils import (
    DEFAULT_REPORT_DIR,
    ImportReport,
    read_csv_full,
    resolve_dataset_path,
)
from players.models import Player, PlayerRoleScore

# The 9 real Positions/*.csv filenames -> their position_group. Filenames are
# deliberately inconsistent on disk (extra words, no shared naming scheme) --
# these are the literal filenames, not something to normalize away.
FILE_TO_POSITION = {
    "AM with league.csv": "AM",
    "CB with league.csv": "CB",
    "CM with league.csv": "CM",
    "DM with league.csv": "DM",
    "FWD with league Updated.csv": "FWD",
    "LB with league.csv": "LB",
    "LW with league2.csv": "LW",
    "RB with league.csv": "RB",
    "RW with league.csv": "RW",
}

_SANITIZE_RE = re.compile(r"[^0-9a-zA-Z]+")


def sanitize_role_name(raw: str) -> str:
    """Sanitize a raw role column header into a stable `role_name`.

    Strip parens, collapse any run of non-alphanumeric characters into a
    single underscore, trim leading/trailing underscores, lowercase. E.g.
    "Wide_Centre-Back_(LCB)" -> "wide_centre_back_lcb". A stray-space typo
    like "Advanced _Playmaker" (present verbatim in the AM file's header)
    collapses cleanly too -- the raw header is preserved separately in
    `role_name_raw` for traceability.
    """
    cleaned = raw.replace("(", "").replace(")", "")
    cleaned = _SANITIZE_RE.sub("_", cleaned)
    return cleaned.strip("_").lower()


class Command(BaseCommand):
    help = (
        "Normalize the 9 Positions/*.csv wide role files into long "
        "PlayerRoleScore rows, resolving the player FK by UniqueID "
        "(idempotent upsert on player+role_name)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--positions-dir",
            default=None,
            help=(
                "Directory containing the 9 Positions/*.csv files "
                "(default: DATASET_DIR/Positions)."
            ),
        )
        parser.add_argument(
            "--report-dir",
            default=DEFAULT_REPORT_DIR,
            help="Directory to write the import report to.",
        )

    def handle(self, *args, **options):
        positions_dir = (
            Path(options["positions_dir"])
            if options["positions_dir"]
            else resolve_dataset_path("Positions")
        )
        report_dir = options["report_dir"]

        player_id_map = dict(Player.objects.values_list("unique_id", "id"))
        if not player_id_map:
            self.stderr.write(
                self.style.ERROR(
                    "No Player rows found -- run `python manage.py import_players` "
                    "first."
                )
            )
            return

        report = ImportReport(source_file=str(positions_dir))

        total_rows = 0
        unmatched_uids: set[int] = set()
        per_position_row_counts: dict[str, int] = {}
        files_missing: list[str] = []
        objs: list[PlayerRoleScore] = []

        for filename, position_group in FILE_TO_POSITION.items():
            file_path = Path(positions_dir) / filename
            if not file_path.exists():
                # Tolerate a partial set of files (e.g. fixture-driven tests
                # that only ship one position's sample file) -- skip silently
                # rather than crash the whole run.
                files_missing.append(filename)
                continue

            header_df = pd.read_csv(file_path, nrows=0)
            role_columns = [c for c in header_df.columns if c != "UniqueID"]
            dtypes = {"UniqueID": "int64"}
            for col in role_columns:
                dtypes[col] = "Float64"

            df = read_csv_full(file_path, dtypes)
            long_df = df.melt(
                id_vars=["UniqueID"],
                value_vars=role_columns,
                var_name="role_name_raw",
                value_name="score",
            )

            file_row_count = 0
            for row in long_df.to_dict(orient="records"):
                uid = int(row["UniqueID"])
                player_id = player_id_map.get(uid)
                if player_id is None:
                    report.add_field_issue(
                        "UniqueID", "no_matching_player", sample_id=uid
                    )
                    unmatched_uids.add(uid)
                    continue

                role_name_raw = row["role_name_raw"]
                score = row["score"]
                if pd.isna(score):
                    score = None
                else:
                    score = float(score)

                objs.append(
                    PlayerRoleScore(
                        player_id=player_id,
                        position_group=position_group,
                        role_name=sanitize_role_name(role_name_raw),
                        role_name_raw=role_name_raw,
                        score=score,
                    )
                )
                file_row_count += 1

            per_position_row_counts[position_group] = file_row_count
            total_rows += file_row_count

        before_count = PlayerRoleScore.objects.count()
        PlayerRoleScore.objects.bulk_create(
            objs,
            batch_size=5000,
            update_conflicts=True,
            unique_fields=["player", "role_name"],
            update_fields=["score", "role_name_raw", "position_group"],
        )
        after_count = PlayerRoleScore.objects.count()
        created = max(after_count - before_count, 0)
        updated = max(total_rows - created, 0)

        report.source_row_count = total_rows
        report.set_counts(
            created=created, updated=updated, flagged=len(unmatched_uids)
        )
        report.add_section("per_position_row_counts", per_position_row_counts)
        if files_missing:
            report.add_section("files_missing", sorted(files_missing))
        report.add_section(
            "gk_coverage_note",
            "GK players have zero PlayerRoleScore rows by design -- there is "
            "no GK Positions/*.csv file in the source dataset. This is "
            "expected coverage, not a join failure.",
        )

        json_path, md_path = report.write(report_dir)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {total_rows} PlayerRoleScore rows "
                f"({created} created, {updated} updated, "
                f"{len(unmatched_uids)} unmatched UniqueIDs). "
                f"Report: {json_path}, {md_path}"
            )
        )
