"""One-time cleanup: merge Club rows that are the same real club under a
whitespace-variant name (A3 fix).

Round 1 (confirmed 2026-09-09, normalizing name -> lower(trim(name)) and
separately -> lower(alnum-only(name)) against the pre-fix 1060-club table):
  - "LASK" / "LASK " (trailing whitespace)
  - "Borussia M'gladbach" / "Borussia M_gladbach" (apostrophe-vs-underscore
    encoding variant between Players.csv and Playstyles.csv)

Round 2 (confirmed 2026-09-09, AFTER import_clubs_playstyles.py's new
`.strip()` shipped and import_all was re-run): 5 more names turned up as
orphans -- these never had a clean-spelling row to collide with UNTIL the
strip fix started deriving the correct stripped name for the first time, at
which point bulk_create's upsert created the clean row and left the old
padded-name row behind (upsert never deletes what drops out of the source):
  - " Esenler Erokspor" (leading space) -> "Esenler Erokspor"
  - "AEK Larnaca " / "AVS " / "Rodez " / "St. Louis City " (trailing space)
    -> stripped equivalents
All 5 orphans confirmed to have ZERO Player/PlayerClubCompatibility/
Transfer/Shortlist/SquadPlan references left (the strip fix routes
everything to the clean name going forward) -- pure dead rows, safe to
remove via this same reassign-then-delete mechanism (reassignment is a
no-op for these, but running them through the identical path costs nothing
and stays consistent/auditable rather than a bespoke bare delete).

Broad fuzzy name-matching is deliberately NOT used beyond exact whitespace/
encoding variants -- the risk of false-positive merges (e.g. a reserve/B
team wrongly merged into its first team) outweighs catching more variants,
and a full re-derivation diff (`derived_names - db_names` /
`db_names - derived_names`) after the strip fix found nothing further.
Where a pair's clean-named row does NOT exist at all (production, before the
2025-2026 import: import_all had never been re-run after the strip fix, so
"AEK Larnaca " / "AVS " / "Rodez " / "St. Louis City " were still the only,
LIVE rows), the padded row is renamed in place rather than skipped.

This command is safe to re-run any time (no-op once clean) and costs
nothing to run again after a future data pull, as a cheap audit.

Reassigns EVERY FK into Club before deleting the loser -- critically
including Shortlist.club and SquadPlan.club, both on_delete=CASCADE and
BOTH USER-CREATED DATA. Simply deleting the loser Club row would silently
destroy a real user's shortlist/squad plan if it happened to reference the
duplicate spelling; never rely on cascade for a merge like this.

Transfer needs its OWN per-row handling, not a blanket `.update(club=...)`:
Transfer has a `uniq_transfer_event` UniqueConstraint on (player_name_raw,
year, window, movement, club, dealing_club). If a loser's Transfer row is
an EXACT duplicate of one that already exists under the canonical club
(confirmed case: a re-run of import_all after this command re-derives the
loser name -- clubs/name_normalization.py's alias now prevents that
specific case going forward, but the general shape can recur any time an
import runs between two invocations of this command) -- reassigning it
would violate that constraint. Delete the loser's row in that case; only
reassign the ones that are genuinely new.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from clubs.models import Club
from players.models import Player, PlayerClubCompatibility
from transfers.models import Transfer
from workspace.models import Shortlist, SquadPlan


def _merge_transfers(loser: Club, canonical: Club) -> tuple[int, int]:
    """Reassign loser's Transfer rows to canonical; delete any that would
    collide with an already-existing (player_name_raw, year, window,
    movement, dealing_club) event under canonical. Returns (reassigned,
    deleted_as_duplicate)."""
    reassigned = deleted = 0
    for t in Transfer.objects.filter(club=loser):
        collides = Transfer.objects.filter(
            club=canonical,
            player_name_raw=t.player_name_raw,
            year=t.year,
            window=t.window,
            movement=t.movement,
            dealing_club=t.dealing_club,
        ).exists()
        if collides:
            t.delete()
            deleted += 1
        else:
            t.club = canonical
            t.save(update_fields=["club"])
            reassigned += 1
    return reassigned, deleted

# (name kept as canonical, name(s) merged into it)
MERGES: list[tuple[str, list[str]]] = [
    ("LASK", ["LASK "]),
    ("Borussia M'gladbach", ["Borussia M_gladbach"]),
    ("Esenler Erokspor", [" Esenler Erokspor"]),
    ("AEK Larnaca", ["AEK Larnaca "]),
    ("AVS", ["AVS "]),
    ("Rodez", ["Rodez "]),
    ("St. Louis City", ["St. Louis City "]),
]


class Command(BaseCommand):
    help = "Merge known duplicate Club rows (whitespace/encoding name variants) into one canonical row."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        for canonical_name, loser_names in MERGES:
            canonical = Club.objects.filter(name=canonical_name).first()
            if canonical is None:
                # No clean-named row exists (e.g. an environment where
                # import_all hasn't re-run since the strip fix, so the padded
                # row is still the ONLY, live row for this club). Skipping
                # would leave it padded, and the next import would then
                # create a second clean row beside it -- the exact duplicate
                # this command exists to prevent. The padded row IS the club:
                # promote it by renaming in place (keeps every player,
                # transfer, shortlist and squad plan attached), then merge
                # any further variants into it below.
                promoted = next(
                    (c for n in loser_names if (c := Club.objects.filter(name=n).first())), None
                )
                if promoted is None:
                    self.stdout.write(
                        self.style.WARNING(f"Skip: neither {canonical_name!r} nor its variants found.")
                    )
                    continue
                self.stdout.write(f"Renaming {promoted.name!r} -> {canonical_name!r} (no clean row exists).")
                loser_names = [n for n in loser_names if n != promoted.name]
                if not dry_run:
                    promoted.name = canonical_name
                    promoted.save(update_fields=["name"])
                canonical = promoted

            for loser_name in loser_names:
                loser = Club.objects.filter(name=loser_name).first()
                if loser is None:
                    self.stdout.write(f"Skip: {loser_name!r} not found (already merged?).")
                    continue

                counts = {
                    "Player": Player.objects.filter(club=loser).count(),
                    "PlayerClubCompatibility": PlayerClubCompatibility.objects.filter(club=loser).count(),
                    "Transfer": Transfer.objects.filter(club=loser).count(),
                    "Shortlist": Shortlist.objects.filter(club=loser).count(),
                    "SquadPlan": SquadPlan.objects.filter(club=loser).count(),
                }
                self.stdout.write(
                    f"Merging {loser_name!r} -> {canonical_name!r}: {counts}"
                )

                if dry_run:
                    continue

                with transaction.atomic():
                    Player.objects.filter(club=loser).update(club=canonical)
                    PlayerClubCompatibility.objects.filter(club=loser).update(club=canonical)
                    reassigned, dup_deleted = _merge_transfers(loser, canonical)
                    Shortlist.objects.filter(club=loser).update(club=canonical)
                    SquadPlan.objects.filter(club=loser).update(club=canonical)
                    loser.delete()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"Merged and deleted {loser_name!r} "
                        f"(Transfer: {reassigned} reassigned, {dup_deleted} exact-duplicate deleted)."
                    )
                )

        if dry_run:
            self.stdout.write(self.style.WARNING("--dry-run: nothing changed."))
