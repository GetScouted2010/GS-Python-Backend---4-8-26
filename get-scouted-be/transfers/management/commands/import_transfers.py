"""Import transferdata final.csv into the Transfer table.

CRITICAL: transferdata's `UniqueID` column is a CLUB identifier (207 distinct
values, 1:1 with `Club`), NOT a player identifier, despite sharing an
identical column name with Players.csv's player-level `UniqueID` (see
transfers/models.py docstring and 01-RESEARCH.md "Transfer Model -- Critical
Pitfall"). This command resolves `Transfer.club` strictly via the `Club`
NAME column and stores the raw `UniqueID` only as `source_unique_id` for
cross-source confirmation -- it is never joined against `Player.unique_id`.

Other behavior:
- `Transfer.dealing_club` stays a plain string (no FK, no stub Club rows) --
  2,909 distinct counterparty values, a much larger/lower-league universe
  than the Club table.
- `Transfer.player` is a best-effort name match against `Player.player`.
  Non-unique (ambiguous) names are treated as unmatched rather than guessed;
  unmatched rows are still imported with `player=None` and logged, never
  dropped (01-CONTEXT.md data-quality policy).
- Idempotent upsert on the 6-column composite event key
  (player_name_raw, year, window, movement, club, dealing_club) -- there is
  no single natural unique column for a transfer event.
"""

from collections import Counter

import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from clubs.models import Club
from core.import_utils import (
    DEFAULT_REPORT_DIR,
    ImportReport,
    read_csv_chunks,
    resolve_dataset_path,
)
from players.models import Player
from transfers.models import Transfer

DTYPES = {
    "UniqueID": "int64",
    "Club": "string",
    "Player": "string",
    "Age": "Int64",
    "Nationality": "string",
    "Position": "string",
    "Short_Position": "string",
    "Market_Value": "Int64",
    "Dealing_Club": "string",
    "Dealing_Country": "string",
    # Fees are non-numeric strings in the wild ("Free", "loan", etc.) --
    # never let pandas infer a numeric dtype for this column.
    "Fee": "string",
    "Movement": "string",
    "Window": "string",
    "League_Name": "string",
    "Year": "int64",
    "is_loan": "string",
    "loan_status": "string",
}

# The 6-column composite key that identifies one real transfer event --
# mirrors transfers/models.py's uniq_transfer_event UniqueConstraint exactly.
KEY_FIELDS = ["player_name_raw", "year", "window", "movement", "club", "dealing_club"]

UPDATE_FIELDS = [f.name for f in Transfer._meta.fields if f.name not in ("id", *KEY_FIELDS)]


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


def _parse_is_loan(raw, report, sample_id):
    """transferdata's is_loan is the literal string "TRUE"/"FALSE" -- parse it
    explicitly rather than relying on any implicit truthiness coercion."""
    if raw is None:
        return None
    normalized = str(raw).strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    report.add_field_issue("is_loan", "unparseable", sample_id=sample_id)
    return None


def _build_transfer_kwargs(row: dict, club_id_map: dict, player_name_to_id: dict, report: ImportReport) -> dict:
    """Build one Transfer's constructor kwargs from a raw CSV row dict.

    Never raises/skips on an unresolved club or unmatched player -- both are
    logged via `report.add_field_issue` and the row is still constructed
    (01-CONTEXT.md data-quality policy: maximize completeness, never drop).
    """
    club_name = _clean(row.get("Club"))
    # UniqueID is a CLUB id, NOT a player id -- never join to Player.unique_id
    # (RESEARCH.md "Transfer Model -- Critical Pitfall", Pitfall 1). Club is
    # resolved strictly via this NAME lookup; source_unique_id below is kept
    # only for cross-source confirmation, never used to resolve a relation.
    source_unique_id = _clean(row.get("UniqueID"))

    club_id = None
    if club_name is not None:
        club_id = club_id_map.get(club_name)
        if club_id is None:
            report.add_field_issue("Club", "unresolved_club_name", sample_id=club_name)
    else:
        report.add_field_issue("Club", "missing_club_name", sample_id=source_unique_id)

    player_name_raw = _clean(row.get("Player")) or ""
    player_id = player_name_to_id.get(player_name_raw)
    if player_id is None:
        report.add_field_issue("Player", "unmatched_name", sample_id=player_name_raw)

    is_loan = _parse_is_loan(row.get("is_loan"), report, sample_id=player_name_raw)

    return {
        "club_id": club_id,
        "source_unique_id": source_unique_id,
        "player_id": player_id,
        "player_name_raw": player_name_raw,
        "age_at_transfer": _clean(row.get("Age")),
        "nationality": _clean(row.get("Nationality")),
        "position": _clean(row.get("Position")),
        "short_position": _clean(row.get("Short_Position")),
        "market_value_at_transfer": _clean(row.get("Market_Value")),
        "dealing_club": _clean(row.get("Dealing_Club")) or "",
        "dealing_country": _clean(row.get("Dealing_Country")),
        "fee": _clean(row.get("Fee")),
        "movement": _clean(row.get("Movement")) or "",
        "window": _clean(row.get("Window")) or "",
        "league_name": _clean(row.get("League_Name")),
        "year": int(_clean(row.get("Year"))),
        "is_loan": is_loan,
        "loan_status": _clean(row.get("loan_status")),
    }


class Command(BaseCommand):
    help = (
        "Import transferdata final.csv into the Transfer table (chunked, "
        "idempotent on the 6-column composite event key; club resolved by "
        "NAME -- never via transferdata's UniqueID, which is a Club id)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--transfers-csv",
            default=None,
            help='Path to transferdata final.csv (default: DATASET_DIR/"transferdata final.csv")',
        )
        parser.add_argument(
            "--report-dir",
            default=DEFAULT_REPORT_DIR,
            help="Directory to write the import report to.",
        )
        parser.add_argument(
            "--chunksize",
            type=int,
            default=5000,
            help="Number of rows to read/upsert per chunk (default: 5000).",
        )

    def handle(self, *args, **options):
        transfers_csv = options["transfers_csv"] or resolve_dataset_path(
            "transferdata final.csv"
        )
        report_dir = options["report_dir"]
        chunksize = options["chunksize"]

        club_id_map = dict(Club.objects.values_list("name", "id"))

        # Best-effort player name match: only names that are UNIQUE across the
        # Player table get a resolvable id -- a non-unique name is ambiguous
        # and must be treated as unmatched, never guessed (RESEARCH.md).
        name_counts = Counter(Player.objects.values_list("player", flat=True))
        player_name_to_id = {
            name: pid
            for name, pid in Player.objects.values_list("player", "id")
            if name_counts[name] == 1
        }

        report = ImportReport(source_file=str(transfers_csv))

        before_count = Transfer.objects.count()
        total_rows = 0
        unmatched_players = 0
        unresolved_clubs = 0
        unresolved_club_names = set()

        # Wrap report.add_field_issue so every issue logged inside
        # `_build_transfer_kwargs` also updates these run-level counters.
        _original_add_field_issue = report.add_field_issue

        def _add_field_issue(field, issue, sample_id=None):
            nonlocal unmatched_players, unresolved_clubs
            _original_add_field_issue(field, issue, sample_id=sample_id)
            if field == "Player" and issue == "unmatched_name":
                unmatched_players += 1
            if field == "Club" and issue == "unresolved_club_name":
                unresolved_clubs += 1
                if sample_id is not None:
                    unresolved_club_names.add(sample_id)

        report.add_field_issue = _add_field_issue

        for chunk in read_csv_chunks(transfers_csv, DTYPES, chunksize=chunksize):
            objs = []
            for row in chunk.to_dict(orient="records"):
                kwargs = _build_transfer_kwargs(row, club_id_map, player_name_to_id, report)
                objs.append(Transfer(**kwargs))
            total_rows += len(objs)
            with transaction.atomic():
                Transfer.objects.bulk_create(
                    objs,
                    batch_size=chunksize,
                    update_conflicts=True,
                    unique_fields=KEY_FIELDS,
                    update_fields=UPDATE_FIELDS,
                )

        after_count = Transfer.objects.count()
        created = max(after_count - before_count, 0)
        updated = max(total_rows - created, 0)

        report.source_row_count = total_rows
        report.set_counts(
            created=created,
            updated=updated,
            flagged=unmatched_players + unresolved_clubs,
        )
        if unresolved_club_names:
            report.add_section("unresolved_club_names", sorted(unresolved_club_names))
        report.add_section(
            "transfer_import",
            {
                "unmatched_players": unmatched_players,
                "unresolved_clubs": unresolved_clubs,
            },
        )

        json_path, md_path = report.write(report_dir)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {total_rows} transfer rows "
                f"({created} created, {updated} updated, "
                f"{unmatched_players} unmatched players, "
                f"{unresolved_clubs} unresolved clubs). "
                f"Report: {json_path}, {md_path}"
            )
        )
