"""Derive and upsert Club rows from Players.csv + Playstyles.csv.

No dedicated Clubs source file exists (see clubs/models.py docstring and
01-RESEARCH.md "Club Model & Derivation"). This command:

1. Builds the full club universe from Players.csv's
   `Team_within_selected_timeframe` column (authoritative -- zero nulls).
2. Derives `Club.league` as the MODE of `League` across each club's player
   rows, breaking ties alphabetically (~49.6% of real clubs have more than one
   distinct League value across their rows -- this path is common, not rare).
3. Joins in Playstyles.csv's 8 style floats + UniqueID for the ~22.6% of clubs
   it covers; the rest stay null (expected, not an error -- DATA-05).
4. Idempotently upserts on Club.name via bulk_create(update_conflicts=True).
5. Writes a structured ImportReport (JSON + Markdown) stating the ambiguous-
   league count and playing-style coverage rate explicitly, so a reviewer does
   not mistake the ~77% playing-style-null rate for a bug.
"""

from collections import Counter, defaultdict

import pandas as pd
from django.core.management.base import BaseCommand

from clubs.models import Club
from core.import_utils import (
    DEFAULT_REPORT_DIR,
    ImportReport,
    read_csv_full,
    resolve_dataset_path,
)

PLAYERS_DTYPES = {
    "Team_within_selected_timeframe": "string",
    "League": "string",
}

PLAYSTYLES_DTYPES = {
    "Team": "string",
    "UniqueID": "Int64",
    "Control_Possession": "float64",
    "Gegenpressing": "float64",
    "Direct_Play": "float64",
    "Defensive_Counter_Attack": "float64",
    "Tiki_Taka": "float64",
    "Counter_Attack": "float64",
    "Wing_Play": "float64",
    "Low_Block": "float64",
}

STYLE_COLUMN_MAP = {
    "control_possession": "Control_Possession",
    "gegenpressing": "Gegenpressing",
    "direct_play": "Direct_Play",
    "defensive_counter_attack": "Defensive_Counter_Attack",
    "tiki_taka": "Tiki_Taka",
    "counter_attack": "Counter_Attack",
    "wing_play": "Wing_Play",
    "low_block": "Low_Block",
}

UPDATE_FIELDS = [
    "league",
    "source_unique_id",
    "control_possession",
    "gegenpressing",
    "direct_play",
    "defensive_counter_attack",
    "tiki_taka",
    "counter_attack",
    "wing_play",
    "low_block",
]


def derive_club_league(players_df):
    """Most-common League per Team_within_selected_timeframe.

    Ties broken alphabetically via `sorted(...)`. Returns
    (league_map, tied_clubs, ambiguous_clubs):
    - tied_clubs: sorted list of {club, tied_leagues, winner} dicts, one per
      club whose TOP League count is shared by more than one League value
      (a genuine mode tie -- the alphabetical tie-break actually fires here).
    - ambiguous_clubs: sorted list of club names with MORE THAN ONE distinct
      League value at all (len(counter) > 1), matching the
      `clubs_with_ambiguous_league` metric definition from 01-RESEARCH.md
      (~49.6% of real clubs hit this -- most have a clear mode, not a tie,
      but still carry more than one League value across their player rows).
    """
    club_leagues = defaultdict(Counter)
    for team, league in zip(
        players_df["Team_within_selected_timeframe"], players_df["League"]
    ):
        if pd.isna(team):
            continue
        club_leagues[team][league] += 1

    league_map = {}
    tied_clubs = []
    ambiguous_clubs = []
    for club, counts in club_leagues.items():
        max_count = max(counts.values())
        winners = sorted(league for league, count in counts.items() if count == max_count)
        league_map[club] = winners[0]
        if len(winners) > 1:
            tied_clubs.append({"club": club, "tied_leagues": winners, "winner": winners[0]})
        if len(counts) > 1:
            ambiguous_clubs.append(club)

    return (
        league_map,
        sorted(tied_clubs, key=lambda entry: entry["club"]),
        sorted(ambiguous_clubs),
    )


def _clean(value):
    """Convert a pandas scalar to a plain Python value, mapping NA/NaN to None."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def load_playstyles(playstyles_df):
    """Build team -> {source_unique_id, 8 style floats} from Playstyles.csv."""
    styles = {}
    for row in playstyles_df.itertuples(index=False):
        team = getattr(row, "Team")
        if pd.isna(team):
            continue
        entry = {"source_unique_id": _clean(getattr(row, "UniqueID"))}
        for model_field, csv_column in STYLE_COLUMN_MAP.items():
            entry[model_field] = _clean(getattr(row, csv_column))
        styles[team] = entry
    return styles


class Command(BaseCommand):
    help = "Derive and upsert Club rows from Players.csv + Playstyles.csv."

    def add_arguments(self, parser):
        parser.add_argument(
            "--players-csv",
            default=None,
            help="Path to Players.csv (default: DATASET_DIR/Players.csv)",
        )
        parser.add_argument(
            "--playstyles-csv",
            default=None,
            help="Path to Playstyles.csv (default: DATASET_DIR/Playstyles.csv)",
        )
        parser.add_argument(
            "--report-dir",
            default=DEFAULT_REPORT_DIR,
            help="Directory to write the import report to.",
        )

    def handle(self, *args, **options):
        players_csv = options["players_csv"] or resolve_dataset_path("Players.csv")
        playstyles_csv = options["playstyles_csv"] or resolve_dataset_path(
            "Playstyles.csv"
        )
        report_dir = options["report_dir"]

        players_df = read_csv_full(players_csv, PLAYERS_DTYPES)
        playstyles_df = read_csv_full(playstyles_csv, PLAYSTYLES_DTYPES)

        report = ImportReport(source_file=str(players_csv), source_row_count=len(players_df))

        league_map, tied_clubs, ambiguous_clubs = derive_club_league(players_df)
        styles_map = load_playstyles(playstyles_df)

        # Union: every Players.csv club, plus any Playstyles-only club name
        # (verified in research: at most one such name, e.g. Borussia M_gladbach,
        # but never assume -- union defensively).
        all_club_names = set(league_map) | set(styles_map)

        club_objs = []
        clubs_with_style = 0
        for name in sorted(all_club_names):
            style = styles_map.get(name)
            kwargs = {
                "name": name,
                "league": league_map.get(name),
                "source_unique_id": style["source_unique_id"] if style else None,
            }
            for model_field in STYLE_COLUMN_MAP:
                kwargs[model_field] = style[model_field] if style else None
            if style is not None:
                clubs_with_style += 1
            club_objs.append(Club(**kwargs))

        before_count = Club.objects.count()
        Club.objects.bulk_create(
            club_objs,
            batch_size=1000,
            update_conflicts=True,
            unique_fields=['name'],
            update_fields=UPDATE_FIELDS,
        )
        after_count = Club.objects.count()

        created = max(after_count - before_count, 0)
        updated = len(club_objs) - created

        # Log every genuine tie-break event (mode shared by >1 League value) --
        # verified rarer than "ambiguous" (a club having >1 distinct League
        # value at all), but this is the specific case where the alphabetical
        # tie-break decision actually changes the outcome.
        for entry in tied_clubs:
            report.add_field_issue("League", "ambiguous_league_tie", sample_id=entry["club"])

        report.set_counts(created=created, updated=updated, flagged=len(ambiguous_clubs))

        distinct_clubs = len(all_club_names)
        coverage_rate = (
            round(clubs_with_style / distinct_clubs, 4) if distinct_clubs else 0.0
        )
        report.add_section(
            "club_derivation",
            {
                "distinct_clubs": distinct_clubs,
                # Per 01-RESEARCH.md: any club with MORE THAN ONE distinct
                # League value across its player rows counts as ambiguous
                # (~49.6% of real clubs) -- a strict superset of tied_clubs,
                # which is only the subset where the mode itself is tied.
                "clubs_with_ambiguous_league": len(ambiguous_clubs),
                "clubs_with_playing_style_coverage": clubs_with_style,
                "playing_style_coverage_rate": coverage_rate,
                "ambiguous_clubs": ambiguous_clubs,
                "tied_clubs": tied_clubs,
            },
        )

        json_path, md_path = report.write(report_dir)

        self.stdout.write(
            self.style.SUCCESS(
                f"Upserted {len(club_objs)} clubs "
                f"({len(ambiguous_clubs)} ambiguous-league clubs, "
                f"{len(tied_clubs)} genuine mode ties, "
                f"playing-style coverage {coverage_rate:.1%}). "
                f"Report: {json_path}, {md_path}"
            )
        )
