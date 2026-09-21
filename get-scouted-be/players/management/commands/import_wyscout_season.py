"""Import a Wyscout(+Transfermarkt) season export (e.g. 2025-2026) as Player rows.

Additive by design -- it only ever creates/updates rows of the season it is
given, under offset `unique_id`s that cannot collide with Players.csv rows
(see players/wyscout_season.py for why that matters: 7,255 of the raw IDs
collide with DIFFERENT real players). Nothing about existing seasons, and
nothing about existing Club rows, is modified.

What it does, in one transaction:
  1. Reshape the file into the Players.csv schema (`adapt_wyscout_frame`).
  2. Refuse to run if any resulting `unique_id` already belongs to a Player
     of a different season (belt-and-braces against a mistyped --id-offset).
  3. Create Club rows for team names not already in the Club table (league =
     mode of the new rows' league labels, exactly like the original club
     derivation). Existing Club rows are never touched.
  4. Upsert the players through `import_players._build_player_kwargs` -- the
     same row builder, validation and flag-don't-skip policy as every other
     season.

Deliberately NOT part of `import_all`: its source lives in
`dataset/missing_data/` and it is meant to be run on purpose.

The four denormalized scores are left NULL: the season is listed in
`players.season.UNSCORED_SEASONS`, so `recompute_scores` neither scores these
rows nor lets them shift existing players' percentile ranks.

Usage:
    python manage.py import_wyscout_season --dry-run
    python manage.py import_wyscout_season
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clubs.leagues import REAL_LEAGUES
from clubs.management.commands.import_clubs_playstyles import derive_club_league
from clubs.models import Club
from core.import_utils import DEFAULT_REPORT_DIR, ImportReport, resolve_dataset_path
from players.management.commands.import_players import (
    UPDATE_FIELDS,
    _build_player_kwargs,
    _clean,
)
from players.models import Player
from players.season import SEASON_ORDER
from players.wyscout_season import (
    DEFAULT_ID_OFFSET,
    adapt_wyscout_frame,
    read_wyscout_csv,
)

DEFAULT_CSV = "missing_data/wyscout_with_TM_data.csv"
DEFAULT_SEASON = "2025-2026"


class Command(BaseCommand):
    help = (
        "Import a Wyscout(+TM) season export as new Player rows under offset "
        "unique_ids (additive; existing seasons and clubs are untouched)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            default=None,
            help=f"Path to the export (default: DATASET_DIR/{DEFAULT_CSV})",
        )
        parser.add_argument("--season", default=DEFAULT_SEASON)
        parser.add_argument(
            "--id-offset",
            type=int,
            default=DEFAULT_ID_OFFSET,
            help=(
                f"Added to every source UniqueID (default {DEFAULT_ID_OFFSET:,}). "
                "Must be identical on every re-import of the same season."
            ),
        )
        parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
        parser.add_argument("--chunksize", type=int, default=2000)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Adapt and validate the file and print what would change; write nothing.",
        )

    def handle(self, *args, **options):
        season = options["season"]
        if season not in SEASON_ORDER:
            raise CommandError(
                f"{season!r} is not a registered season. Add it to "
                f"players/season.py's SEASON_ORDER first (have: {SEASON_ORDER})."
            )

        csv_path = options["csv"] or resolve_dataset_path(DEFAULT_CSV)
        id_offset = options["id_offset"]
        dry_run = options["dry_run"]
        chunksize = options["chunksize"]

        club_id_map = dict(Club.objects.values_list("name", "id"))
        if not club_id_map:
            raise CommandError(
                "No Club rows found -- run `python manage.py import_clubs_playstyles` first."
            )
        club_league_db = dict(Club.objects.values_list("name", "league"))

        self.stdout.write(f"Reading {csv_path} ...")
        try:
            frame, adapt_stats = adapt_wyscout_frame(
                read_wyscout_csv(csv_path),
                season=season,
                id_offset=id_offset,
                existing_club_league=club_league_db,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        # (2) ID-collision guard.
        colliding = (
            Player.objects.filter(unique_id__in=frame["UniqueID"].tolist())
            .exclude(season=season)
            .count()
        )
        if colliding:
            raise CommandError(
                f"{colliding} unique_id(s) in this file already belong to Player rows of a "
                f"DIFFERENT season -- importing would overwrite them. Check --id-offset "
                f"(currently {id_offset:,})."
            )

        # (3) Clubs that don't exist yet.
        clubbed = frame[
            frame["Team_within_selected_timeframe"].notna() & frame["League"].notna()
        ]
        league_map, _tied, _ambiguous = derive_club_league(clubbed)
        team_names = set(frame["Team_within_selected_timeframe"].dropna().unique())
        new_club_names = sorted(n for n in team_names if n not in club_id_map)
        new_leagues = sorted(
            {league_map[n] for n in new_club_names if league_map.get(n)} - REAL_LEAGUES
        )

        # Existing clubs whose stored league disagrees with what this season's
        # rows say (pre-existing bad club leagues, e.g. a Polish club tagged
        # with a Swedish league). Reported, never "fixed" here.
        disagreements = Counter()
        for team, league in zip(
            clubbed["Team_within_selected_timeframe"], clubbed["League"]
        ):
            if team in club_league_db and club_league_db[team] not in (None, league):
                disagreements[(team, club_league_db[team], league)] += 1

        before_season_rows = Player.objects.filter(season=season).count()
        summary = (
            f"{len(frame)} rows | {len(new_club_names)} new clubs "
            f"({len(new_leagues)} new leagues) | "
            f"{before_season_rows} {season} rows already in DB"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN -- nothing written. {summary}"))
            self.stdout.write(
                "Adapter stats: "
                f"{ {k: v for k, v in adapt_stats.items() if k != 'club_identity_decisions'} }"
            )
            for d in adapt_stats["club_identity_decisions"]:
                self.stdout.write(
                    f"  same-name split: {d['source_name']!r} [{d['league']}] "
                    f"{d['rows']} rows -> {d['assigned_club']!r}"
                )
            return

        # (4) Write everything atomically: either the whole season lands or nothing does.
        report = ImportReport(source_file=str(csv_path))
        flagged_uids: set[int] = set()
        _add_issue = report.add_field_issue

        def _tracking_add_issue(field, issue, sample_id=None):
            _add_issue(field, issue, sample_id=sample_id)
            if sample_id is not None:
                flagged_uids.add(sample_id)

        report.add_field_issue = _tracking_add_issue

        unresolved_club_names: set[str] = set()
        total_rows = 0
        with transaction.atomic():
            Club.objects.bulk_create(
                [Club(name=n, league=league_map.get(n)) for n in new_club_names],
                batch_size=1000,
                ignore_conflicts=True,
            )
            club_id_map = dict(Club.objects.values_list("name", "id"))

            for start in range(0, len(frame), chunksize):
                chunk = frame.iloc[start : start + chunksize]
                objs = []
                for row in chunk.to_dict(orient="records"):
                    kwargs = _build_player_kwargs(row, club_id_map, report)
                    club_name = _clean(row.get("Team_within_selected_timeframe"))
                    if club_name is not None and kwargs["club_id"] is None:
                        unresolved_club_names.add(club_name)
                    objs.append(Player(**kwargs))
                total_rows += len(objs)
                Player.objects.bulk_create(
                    objs,
                    batch_size=chunksize,
                    update_conflicts=True,
                    unique_fields=["unique_id"],
                    update_fields=UPDATE_FIELDS,
                )

        after_season_rows = Player.objects.filter(season=season).count()
        created = max(after_season_rows - before_season_rows, 0)
        report.source_row_count = total_rows
        report.set_counts(
            created=created, updated=max(total_rows - created, 0), flagged=len(flagged_uids)
        )
        report.add_section(
            "wyscout_season_import",
            {
                "season": season,
                "id_offset": id_offset,
                "adapter": adapt_stats,
                "clubs_created": len(new_club_names),
                "new_club_names_sample": new_club_names[:50],
                "new_leagues_not_in_REAL_LEAGUES": new_leagues,
                "unresolved_club_names": sorted(unresolved_club_names),
                "existing_club_league_disagrees_with_season_rows": {
                    "distinct_clubs": len({k[0] for k in disagreements}),
                    "rows": sum(disagreements.values()),
                    "top_25": [
                        {"club": c, "club_table_league": cl, "season_row_league": rl, "rows": n}
                        for (c, cl, rl), n in disagreements.most_common(25)
                    ],
                },
            },
        )
        json_path, md_path = report.write(options["report_dir"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {season}: {total_rows} rows ({created} created, "
                f"{max(total_rows - created, 0)} updated, {len(flagged_uids)} flagged), "
                f"{len(new_club_names)} clubs created. Report: {json_path}, {md_path}"
            )
        )
        if unresolved_club_names:
            self.stdout.write(
                self.style.WARNING(f"{len(unresolved_club_names)} club names unresolved (see report).")
            )
