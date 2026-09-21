"""Correct `Club.league` values that are provably wrong, using a season file
as the evidence (run `--dry-run` first and read the list).

Why it's needed: `Club.league` is derived from the older data, which only
covers 25 leagues. Clubs outside them got whatever league their few stray
rows carried -- Panathinaikos is stored as "La Liga (Spain)", Olympiacos as
"Bundesliga 2", Toluca (Mexico) as "La Liga (Spain)". The 2025-2026 Wyscout
file covers 45 leagues, with a league on every row that is 99.24%
self-consistent per club, so it can say what these clubs' leagues really are.

What it will and will NOT change, per existing club:

  * stored league is a known alias spelling (e.g. "EFL League Two (England)")
      -> normalized to the canonical label.                         [alias]
  * stored league is empty                -> filled from the file.   [fill]
  * file league is in a DIFFERENT COUNTRY than the stored one
      -> corrected. A club does not move between countries' leagues, so
         this is a wrong stored value, not a real change.      [cross_country]
  * file league is in the SAME country (Metz Ligue 2 -> Ligue 1, Pisa Serie B
      -> Serie A: promotion/relegation) -> LEFT ALONE. `Club.league` is a
      single value, and older seasons' players still resolve through it, so
      overwriting it would make last season's league wrong.
  * different country BUT the club looks like it has real history in its stored
      league -> NOT applied, listed for review, because that pattern can mean
      two different clubs sharing one name. "Real history" = more than
      MAX_ROSTER_FOR_LEGACY_MISLABEL players in older seasons (a wrong-legacy
      club is one known only through a few stray transfer rows: every one of
      the 122 real corrections has an older squad of 7 or fewer), or >= 5 older
      players none of whom appear in the file's squad.
  * a country can't be determined for either league -> not applied.

Clubs absent from the file are untouched (except the alias rule). Same-name
clubs the season import split apart (e.g. "River Plate (Uruguay)") are their
own rows and are never matched to the original.

Idempotent: once applied, a second run proposes nothing. Every change is
listed as `old -> new` in the report, so it can be reverted by hand.

Usage:
    python manage.py correct_club_leagues --dry-run
    python manage.py correct_club_leagues
"""

from collections import Counter, defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from clubs.leagues import league_country, normalize_league_name
from clubs.models import Club
from core.import_utils import DEFAULT_REPORT_DIR, ImportReport, resolve_dataset_path
from players.models import Player
from players.season import SEASON_ORDER
from players.wyscout_season import adapt_wyscout_frame, read_wyscout_csv

DEFAULT_CSV = "missing_data/wyscout_with_TM_data.csv"
DEFAULT_SEASON = "2025-2026"

# A club with at least this many older-season players, none of whom are in
# the file's squad for the same name, is not assumed to be the same club.
MIN_ROSTER_FOR_COLLISION_CHECK = 5
# A club with MORE older-season players than this has real history in its
# stored league (a wrong-legacy club has only a few stray rows), so a
# different-country league in the file is a possible name clash, not proof
# the stored league is wrong -- even if some players happen to overlap.
MAX_ROSTER_FOR_LEGACY_MISLABEL = 8


class Command(BaseCommand):
    help = "Correct provably-wrong Club.league values using a season file as evidence."

    def add_arguments(self, parser):
        parser.add_argument("--csv", default=None, help=f"Season file (default: DATASET_DIR/{DEFAULT_CSV})")
        parser.add_argument("--season", default=DEFAULT_SEASON)
        parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR)
        parser.add_argument(
            "--dry-run", action="store_true", help="List every proposed change; write nothing."
        )

    def handle(self, *args, **options):
        season = options["season"]
        if season not in SEASON_ORDER:
            raise CommandError(f"{season!r} is not a registered season (have: {SEASON_ORDER}).")
        csv_path = options["csv"] or resolve_dataset_path(DEFAULT_CSV)

        clubs = list(Club.objects.values("id", "name", "league"))
        if not clubs:
            raise CommandError("No Club rows found.")
        stored_by_name = {c["name"]: c["league"] for c in clubs}

        try:
            frame, _stats = adapt_wyscout_frame(
                read_wyscout_csv(csv_path), season=season, existing_club_league=stored_by_name
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        evidence = self._evidence_by_club(frame)
        old_rosters = self._old_rosters(season)

        proposals, review, counts = [], [], Counter()
        for club in clubs:
            stored = club["league"]
            target = normalize_league_name(stored) if stored else None
            reason = "alias" if stored and target != stored else None

            ev = evidence.get(club["name"])
            if ev is not None:
                file_league = min(ev["leagues"], key=lambda lg: (-ev["leagues"][lg], lg))
                if target is None:
                    target, reason = file_league, "fill"
                elif file_league == target:
                    counts["agrees_with_file"] += 1
                else:
                    stored_country, file_country = league_country(target), league_country(file_league)
                    if stored_country is None or file_country is None:
                        counts["skipped_country_unknown"] += 1
                    elif stored_country == file_country:
                        counts["skipped_same_country"] += 1
                    else:
                        roster = old_rosters.get(club["id"], set())
                        overlap = len(roster & ev["players"])
                        info = {
                            "club": club["name"], "stored_league": stored, "file_league": file_league,
                            "file_rows": ev["leagues"][file_league],
                            "older_roster_size": len(roster), "roster_overlap": overlap,
                        }
                        if len(roster) > MAX_ROSTER_FOR_LEGACY_MISLABEL or (
                            len(roster) >= MIN_ROSTER_FOR_COLLISION_CHECK and overlap == 0
                        ):
                            review.append(info)
                            counts["needs_review_possible_name_collision"] += 1
                        else:
                            target, reason = file_league, "cross_country"
                            proposals.append({**info, "new_league": target, "reason": reason})
                            continue
            else:
                counts["not_in_file"] += 1

            if reason == "alias" or (reason == "fill" and target):
                proposals.append(
                    {"club": club["name"], "stored_league": stored, "new_league": target,
                     "reason": reason, "file_rows": None, "older_roster_size": None, "roster_overlap": None}
                )

        by_reason = Counter(p["reason"] for p in proposals)
        self._print(proposals, review, counts, by_reason)

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("--dry-run: nothing changed."))
            return

        ids = {c["name"]: c["id"] for c in clubs}
        with transaction.atomic():
            for p in proposals:
                Club.objects.filter(id=ids[p["club"]]).update(league=p["new_league"])

        report = ImportReport(source_file=str(csv_path), source_row_count=len(clubs))
        report.set_counts(created=0, updated=len(proposals), flagged=len(review))
        report.add_section(
            "club_league_correction",
            {"season_evidence": season, "changes": proposals, "needs_review": review,
             "not_applied_counts": dict(counts), "changes_by_reason": dict(by_reason)},
        )
        json_path, md_path = report.write(options["report_dir"])
        self.stdout.write(
            self.style.SUCCESS(
                f"Corrected {len(proposals)} club league(s); {len(review)} left for review. "
                f"Report: {json_path}, {md_path}"
            )
        )

    @staticmethod
    def _evidence_by_club(frame):
        evidence = defaultdict(lambda: {"leagues": Counter(), "players": set()})
        valid = frame[
            frame["Team_within_selected_timeframe"].notna() & frame["League"].notna()
        ]
        for team, league, player in zip(
            valid["Team_within_selected_timeframe"], valid["League"], valid["Player"]
        ):
            evidence[team]["leagues"][league] += 1
            evidence[team]["players"].add(str(player).strip().lower())
        return evidence

    @staticmethod
    def _old_rosters(season):
        rosters = defaultdict(set)
        rows = (
            Player.objects.exclude(season=season)
            .exclude(club__isnull=True)
            .values_list("club_id", "player")
        )
        for club_id, name in rows:
            if name:
                rosters[club_id].add(name.strip().lower())
        return rosters

    def _print(self, proposals, review, counts, by_reason):
        self.stdout.write(f"{len(proposals)} proposed change(s): {dict(by_reason)}")
        for p in sorted(proposals, key=lambda x: (x["reason"], x["club"])):
            evidence = (
                f"  [file rows {p['file_rows']}, older squad {p['older_roster_size']}, "
                f"shared players {p['roster_overlap']}]"
                if p["file_rows"] is not None
                else ""
            )
            self.stdout.write(f"  {p['reason']:>13}: {p['club']!r}: {p['stored_league']!r} -> {p['new_league']!r}{evidence}")
        if review:
            self.stdout.write(f"{len(review)} NOT applied -- needs a human look (possible name collision):")
            for r in review:
                self.stdout.write(
                    f"  {r['club']!r}: stored {r['stored_league']!r} vs file {r['file_league']!r} "
                    f"(older squad {r['older_roster_size']}, shared players {r['roster_overlap']})"
                )
        self.stdout.write(f"Left alone: {dict(counts)}")
