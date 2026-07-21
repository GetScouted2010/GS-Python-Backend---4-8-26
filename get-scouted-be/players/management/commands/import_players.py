"""Import Players.csv into the Player table.

Chunked, idempotent (upsert on `unique_id`), club-FK-resolved (via
`Team_within_selected_timeframe`, NOT `Team` -- see FIELD_MAPPING.md section
1a), with the 14 movement/physical-tracking columns packed into
`Player.extended_stats` (keyed by the original CSV column name) and
`Total_Score` renamed to `Player.legacy_total_score`.

Data-quality policy (per 01-CONTEXT.md, locked): never skip a row for a
missing/dirty/outlier value -- flag it in the `ImportReport` and keep going.
See FIELD_MAPPING.md sections 1-2 and 01-RESEARCH.md "Player Model" for the
verified null/outlier rates this command's report should reproduce.

Depends on Plan 04's `import_clubs_playstyles` command having already
populated the `Club` table -- this command resolves `Player.club` from an
in-memory `{Club.name: Club.id}` map built up front and does not create Club
rows itself.
"""

from datetime import datetime

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

# The 14 movement/physical-tracking columns (Players.csv columns 122-135).
# Not valid Python identifiers, not referenced anywhere by impact_model_v4.1.py
# (verified, see FIELD_MAPPING.md section 2) -- packed verbatim, keyed by the
# original CSV column-name string, into Player.extended_stats.
MOVEMENT_COLUMNS = [
    "Total_Distance_per_90",
    "Running_Distance_per_90_(15-20_km/h)",
    "HSR_Distance_per_90_(20-25_km/h)",
    "Sprinting_Distance_per_90_(+25_km/h)",
    "HI_Distance_per_90_(+20_km/h)",
    "Meter/Min",
    "Max_Speed_(km/h)",
    "Count_Medium_Acceleration_per_90_(1_DOT_5_m/s²_to_3_m/s²)",
    "Count_High_Acceleration_per_90_(+3_m/s²)",
    "Count_Medium_Deceleration_per_90_(-1_DOT_5_m/s²_to_-3_m/s²)",
    "Count_High_Deceleration_per_90_(-3_m/s²)",
    "Count_HSR_per_90_(20-25_km/h)",
    "Count_Sprint_per_90_(+25_km/h)",
    "Count_HI_per_90_(+20_km/h)",
]

# Django Player fields that are NOT "mirror the CSV name verbatim" stat
# columns -- these get explicit, named handling in `_build_player_kwargs`.
# Everything else on the model is a ~99-column stat field whose Django name
# equals its CSV column name 1:1 (FIELD_MAPPING.md section 1b).
NON_STAT_FIELDS = {
    "id",
    "unique_id",
    "player",
    "season",
    "club",
    "legacy_total_score",
    "league",
    "positions",
    "main_position",
    "position",
    "age",
    "market_value",
    "contract_expires",
    "birth_country",
    "passport_country",
    "foot",
    "height",
    "weight",
    "on_loan",
    "extended_stats",
}

STAT_FIELD_NAMES = sorted(
    f.name
    for f in Player._meta.get_fields()
    if getattr(f, "concrete", False) and not f.is_relation and f.name not in NON_STAT_FIELDS
)

UPDATE_FIELDS = [f.name for f in Player._meta.fields if f.name not in ("id", "unique_id")]

IDENTIFIER_DTYPES = {
    "UniqueID": "int64",
    "Player": "string",
    "Season": "string",
    "Team_within_selected_timeframe": "string",
    "League": "string",
    "Positions": "string",
    "Main_Position": "string",
    "Position": "string",
    "Foot": "string",
    "Contract_expires": "string",
    "Birth_country": "string",
    "Passport_country": "string",
    "On_loan": "string",
    "Age": "Int64",
    "Market_value": "Int64",
    "Height": "Int64",
    "Weight": "Int64",
    "Total_Score": "Float64",
}


def _build_dtypes() -> dict:
    """Explicit dtype map for read_csv_chunks -- never let pandas infer.

    All ~99 stat columns + the 14 movement columns are nullable floats. The
    GK-block duplicate `Aerial_duels_per_90.1` (pandas auto-suffixes the
    second occurrence of a repeated header -- see FIELD_MAPPING.md section
    1b) gets its own explicit entry too.
    """
    dtypes = dict(IDENTIFIER_DTYPES)
    for name in STAT_FIELD_NAMES:
        dtypes[name] = "Float64"
    dtypes["Aerial_duels_per_90.1"] = "Float64"
    for col in MOVEMENT_COLUMNS:
        dtypes[col] = "Float64"
    return dtypes


DTYPES = _build_dtypes()


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


def _build_player_kwargs(row: dict, club_id_map: dict, report: ImportReport) -> dict:
    """Build one Player's constructor kwargs from a raw CSV row dict.

    Never raises/skips on a missing or dirty value -- every issue is logged
    via `report.add_field_issue` (which the caller wraps to also track
    per-row flagged state) and the row is still constructed, per
    01-CONTEXT.md's data-quality policy.
    """
    uid = int(row["UniqueID"])

    def _flag(field: str, issue: str) -> None:
        report.add_field_issue(field, issue, sample_id=uid)

    club_name = _clean(row.get("Team_within_selected_timeframe"))
    club_id = None
    if club_name is not None:
        club_id = club_id_map.get(club_name)
        if club_id is None:
            _flag("club", "unresolved_club_name")
    else:
        _flag("club", "missing_team_name")

    main_position = _clean(row.get("Main_Position"))

    position = _clean(row.get("Position"))
    if position is None or position == "":
        _flag("Position", "missing")

    age = _clean(row.get("Age"))
    if age is not None and age > 60:
        _flag("Age", "outlier_gt_60")

    market_value = _clean(row.get("Market_value"))
    if market_value is None or market_value == 0:
        market_value = None
        _flag("Market_value", "missing_or_zero")
    elif market_value < 0:
        _flag("Market_value", "outlier_negative")

    raw_contract_expires = row.get("Contract_expires")
    contract_expires = None
    if pd.isna(raw_contract_expires):
        _flag("Contract_expires", "missing")
    else:
        try:
            contract_expires = datetime.strptime(
                str(raw_contract_expires).strip(), "%d/%m/%Y"
            ).date()
        except (TypeError, ValueError):
            _flag("Contract_expires", "unparseable")

    foot = _clean(row.get("Foot"))
    if foot in ("0", "unknown"):
        _flag("Foot", f"invalid_value:'{foot}'")

    raw_on_loan = _clean(row.get("On_loan"))
    if raw_on_loan == "yes":
        on_loan = True
    elif raw_on_loan == "no":
        on_loan = False
    else:
        on_loan = None

    extended_stats = {}
    for col in MOVEMENT_COLUMNS:
        val = _clean(row.get(col))
        if val is not None:
            extended_stats[col] = val

    # Aerial_duels_per_90 appears twice in the raw header (outfield block +
    # GK block); pandas auto-suffixes the second as "Aerial_duels_per_90.1".
    # GK rows use the GK-block occurrence, outfield rows use the first.
    if main_position == "GK":
        aerial_duels_per_90 = _clean(row.get("Aerial_duels_per_90.1"))
    else:
        aerial_duels_per_90 = _clean(row.get("Aerial_duels_per_90"))

    stat_kwargs = {}
    for field_name in STAT_FIELD_NAMES:
        if field_name == "Aerial_duels_per_90":
            stat_kwargs[field_name] = aerial_duels_per_90
            continue
        stat_kwargs[field_name] = _clean(row.get(field_name))

    kwargs = {
        "unique_id": uid,
        "player": _clean(row.get("Player")),
        "season": _clean(row.get("Season")),
        "club_id": club_id,
        "legacy_total_score": _clean(row.get("Total_Score")),
        "league": _clean(row.get("League")),
        "positions": _clean(row.get("Positions")),
        "main_position": main_position,
        "position": position,
        "age": age,
        "market_value": market_value,
        "contract_expires": contract_expires,
        "birth_country": _clean(row.get("Birth_country")),
        "passport_country": _clean(row.get("Passport_country")),
        "foot": foot,
        "height": _clean(row.get("Height")),
        "weight": _clean(row.get("Weight")),
        "on_loan": on_loan,
        "extended_stats": extended_stats,
    }
    kwargs.update(stat_kwargs)
    return kwargs


class Command(BaseCommand):
    help = (
        "Import Players.csv into the Player table (chunked, idempotent, "
        "club-FK-resolved, extended_stats-packed)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--players-csv",
            default=None,
            help="Path to Players.csv (default: DATASET_DIR/Players.csv)",
        )
        parser.add_argument(
            "--report-dir",
            default=DEFAULT_REPORT_DIR,
            help="Directory to write the import report to.",
        )
        parser.add_argument(
            "--chunksize",
            type=int,
            default=2000,
            help="Number of rows to read/upsert per chunk (default: 2000).",
        )

    def handle(self, *args, **options):
        players_csv = options["players_csv"] or resolve_dataset_path("Players.csv")
        report_dir = options["report_dir"]
        chunksize = options["chunksize"]

        club_id_map = dict(Club.objects.values_list("name", "id"))
        if not club_id_map:
            self.stderr.write(
                self.style.ERROR(
                    "No Club rows found -- run "
                    "`python manage.py import_clubs_playstyles` first."
                )
            )
            return

        report = ImportReport(source_file=str(players_csv))

        before_count = Player.objects.count()
        total_rows = 0
        flagged_uids = set()
        unresolved_club_names = set()

        # Wrap report.add_field_issue so every issue logged by
        # `_build_player_kwargs` (which only has access to `report`, not this
        # local `flagged_uids` set) also marks that row as flagged here.
        _original_add_field_issue = report.add_field_issue

        def _add_field_issue(field, issue, sample_id=None):
            _original_add_field_issue(field, issue, sample_id=sample_id)
            if sample_id is not None:
                flagged_uids.add(sample_id)

        report.add_field_issue = _add_field_issue

        for chunk in read_csv_chunks(players_csv, DTYPES, chunksize=chunksize):
            objs = []
            for row in chunk.to_dict(orient="records"):
                kwargs = _build_player_kwargs(row, club_id_map, report)
                club_name = _clean(row.get("Team_within_selected_timeframe"))
                if club_name is not None and kwargs["club_id"] is None:
                    unresolved_club_names.add(club_name)
                objs.append(Player(**kwargs))
            total_rows += len(objs)
            with transaction.atomic():
                Player.objects.bulk_create(
                    objs,
                    batch_size=chunksize,
                    update_conflicts=True,
                    unique_fields=['unique_id'],
                    update_fields=UPDATE_FIELDS,
                )

        after_count = Player.objects.count()
        created = max(after_count - before_count, 0)
        updated = max(total_rows - created, 0)

        report.source_row_count = total_rows
        report.set_counts(created=created, updated=updated, flagged=len(flagged_uids))
        if unresolved_club_names:
            report.add_section(
                "unresolved_club_names", sorted(unresolved_club_names)
            )

        json_path, md_path = report.write(report_dir)

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {total_rows} player rows "
                f"({created} created, {updated} updated, "
                f"{len(flagged_uids)} rows flagged, "
                f"{len(unresolved_club_names)} unresolved club names). "
                f"Report: {json_path}, {md_path}"
            )
        )
