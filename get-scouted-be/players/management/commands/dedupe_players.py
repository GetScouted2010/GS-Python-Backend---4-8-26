"""One-time (and re-runnable) cleanup of exact-duplicate Player rows (A1 fix).

Players.csv itself contains, for a real minority of rows, multiple UniqueID
rows that describe the SAME real observation -- identical player name,
season, resolved club, age, and position -- differing only in stat
completeness (e.g. one row has 15 matches/1087 minutes with a correct
league label, its "duplicate" has 1 match/10 minutes, near-zero stats, and
a wrong league label). Confirmed against production data 2026-09-09: 691
such groups, 698 losing rows, zero of which have any linked Transfer record.

This does NOT touch genuine name collisions (different real people who
share a name, e.g. 7 distinct real "Paulinho"s in the 2022-2023 season
alone) -- those differ in club/age/position and are correctly left alone.
Grouping key is (player, season, club_id, age, position): an EXACT match on
all five is what makes two rows "the same observation", never name alone.

Import-time policy (import_players.py, locked) is to NEVER skip a row from
the source CSV -- so this is deliberately a SEPARATE, explicit, re-runnable
command (matching the recompute_scores/train_tfm_model convention), not a
change to the importer. Run it after every `import_players` (wired into
`import_all` immediately after step 2, before position-roles/compatibility
import, so no per-duplicate PlayerRoleScore/PlayerClubCompatibility rows are
even created just to be cascade-deleted).

Winner per group = highest Minutes_played, tie-broken by Matches_played,
then lowest unique_id (deterministic). Losers are hard-deleted -- their own
PlayerRoleScore/PlayerClubCompatibility rows cascade-delete with them
(on_delete=CASCADE, players/models.py); Transfer.player is on_delete=SET_NULL
but this never fires in practice (verified: 0 of 698 losing rows have a
linked Transfer).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from core.import_utils import DEFAULT_REPORT_DIR
from players.models import Player

GROUP_FIELDS = ["player", "season", "club_id", "age", "position"]


class Command(BaseCommand):
    help = (
        "Delete exact-duplicate Player rows (same player/season/club/age/"
        "position), keeping the row with the most Matches_played/"
        "Minutes_played per group. Re-runnable/idempotent -- a clean table "
        "is a no-op."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be deleted without deleting anything.",
        )
        parser.add_argument(
            "--report-dir",
            default=DEFAULT_REPORT_DIR,
            help="Directory the JSON summary is written into.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        report_dir = Path(options["report_dir"])
        report_dir.mkdir(parents=True, exist_ok=True)

        dup_groups = (
            Player.objects.values(*GROUP_FIELDS)
            .annotate(n=Count("id"))
            .filter(n__gt=1)
        )
        group_count = 0
        loser_ids: list[str] = []
        loser_summary: list[dict] = []

        for group in dup_groups:
            group_count += 1
            key = {f: group[f] for f in GROUP_FIELDS}
            rows = list(
                Player.objects.filter(**key)
                .order_by("-Minutes_played", "-Matches_played", "unique_id")
                .values("id", "unique_id", "Minutes_played", "Matches_played", "league")
            )
            winner, losers = rows[0], rows[1:]
            for loser in losers:
                loser_ids.append(str(loser["id"]))
            loser_summary.append(
                {
                    "player": key["player"],
                    "season": key["season"],
                    "age": key["age"],
                    "position": key["position"],
                    "kept_unique_id": winner["unique_id"],
                    "kept_minutes": winner["Minutes_played"],
                    "removed_unique_ids": [r["unique_id"] for r in losers],
                    "removed_minutes": [r["Minutes_played"] for r in losers],
                }
            )

        self.stdout.write(
            f"Found {group_count} exact-duplicate group(s), "
            f"{len(loser_ids)} row(s) to remove."
        )

        if not dry_run and loser_ids:
            with transaction.atomic():
                deleted, _ = Player.objects.filter(id__in=loser_ids).delete()
            self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} row(s) (incl. cascades)."))
        elif dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: nothing deleted."))

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "dry_run": dry_run,
            "duplicate_groups": group_count,
            "rows_removed": 0 if dry_run else len(loser_ids),
            "groups": loser_summary,
        }
        out_path = report_dir / f"dedupe_players_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
        out_path.write_text(json.dumps(report, indent=2, default=str))
        self.stdout.write(f"Report written to {out_path}")
