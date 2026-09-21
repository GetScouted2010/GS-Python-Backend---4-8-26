"""Tests for the merge_duplicate_clubs management command (A3 fix).

Critical property under test: EVERY FK into the loser Club row must be
reassigned to the survivor before the loser is deleted -- especially
Shortlist.club/SquadPlan.club, both on_delete=CASCADE and both real
USER-CREATED data. A naive `loser.delete()` alone would silently destroy a
user's shortlist/squad plan if it referenced the duplicate spelling.
"""

from __future__ import annotations

import itertools

import pytest
from django.core.management import call_command

from clubs.management.commands.merge_duplicate_clubs import MERGES, _merge_transfers
from clubs.models import Club
from players.models import Player
from transfers.models import Transfer
from workspace.models import Shortlist, SquadPlan

pytestmark = pytest.mark.django_db

_unique_id_seq = itertools.count(999_700_001)


@pytest.fixture
def lask_pair(db):
    canonical = Club.objects.create(name="LASK")
    loser = Club.objects.create(name="LASK ")
    return canonical, loser


def test_reassigns_player_fk(lask_pair):
    canonical, loser = lask_pair
    player = Player.objects.create(unique_id=next(_unique_id_seq), player="Test", club=loser)

    call_command("merge_duplicate_clubs")

    player.refresh_from_db()
    assert player.club_id == canonical.id
    assert not Club.objects.filter(name="LASK ").exists()


def test_reassigns_user_shortlist_not_cascade_deleted(lask_pair):
    # The critical case: Shortlist.club is on_delete=CASCADE. If the merge
    # command ever regresses to a bare loser.delete() without reassigning
    # this first, this shortlist would be silently destroyed.
    from accounts.models import User

    canonical, loser = lask_pair
    user = User.objects.create_user(email="merge-test@example.com", password="testpass123")
    shortlist = Shortlist.objects.create(user=user, name="My List", club=loser)

    call_command("merge_duplicate_clubs")

    shortlist.refresh_from_db()  # would raise DoesNotExist if cascade-deleted
    assert shortlist.club_id == canonical.id


def test_reassigns_user_squad_plan_not_cascade_deleted(lask_pair):
    from accounts.models import User

    canonical, loser = lask_pair
    user = User.objects.create_user(email="merge-test-2@example.com", password="testpass123")
    plan = SquadPlan.objects.create(user=user, name="My Plan", club=loser)

    call_command("merge_duplicate_clubs")

    plan.refresh_from_db()
    assert plan.club_id == canonical.id


def test_dry_run_changes_nothing(lask_pair):
    canonical, loser = lask_pair
    player = Player.objects.create(unique_id=next(_unique_id_seq), player="Test", club=loser)

    call_command("merge_duplicate_clubs", dry_run=True)

    player.refresh_from_db()
    assert player.club_id == loser.id
    assert Club.objects.filter(name="LASK ").exists()


def test_idempotent_second_run_is_a_no_op(lask_pair):
    call_command("merge_duplicate_clubs")
    call_command("merge_duplicate_clubs")  # must not error on an already-merged pair
    assert Club.objects.filter(name="LASK").exists()
    assert not Club.objects.filter(name="LASK ").exists()


def _make_transfer(club, **kwargs):
    kwargs.setdefault("player_name_raw", "Test Player")
    kwargs.setdefault("movement", "departure")
    kwargs.setdefault("window", "Summer")
    kwargs.setdefault("year", 2020)
    kwargs.setdefault("dealing_club", "Some Club")
    return Transfer.objects.create(club=club, **kwargs)


def test_merge_transfers_reassigns_non_colliding_row(lask_pair):
    canonical, loser = lask_pair
    t = _make_transfer(loser)

    reassigned, deleted = _merge_transfers(loser, canonical)

    t.refresh_from_db()
    assert reassigned == 1
    assert deleted == 0
    assert t.club_id == canonical.id


def test_merge_transfers_deletes_exact_duplicate_instead_of_reassigning(lask_pair):
    # The real bug this guards against: re-running merge_duplicate_clubs
    # after a fresh import re-derived the loser club (e.g. Playstyles.csv
    # still spells it the old way before clubs/name_normalization.py's
    # alias is applied everywhere) recreates a Transfer row identical to
    # one already reassigned in a prior run. A blanket .update(club=...)
    # would hit Transfer's uniq_transfer_event constraint.
    canonical, loser = lask_pair
    existing = _make_transfer(canonical, player_name_raw="Raffael", year=2020)
    duplicate = _make_transfer(
        loser, player_name_raw="Raffael", year=2020,
        window=existing.window, movement=existing.movement, dealing_club=existing.dealing_club,
    )

    reassigned, deleted = _merge_transfers(loser, canonical)

    assert reassigned == 0
    assert deleted == 1
    assert not Transfer.objects.filter(id=duplicate.id).exists()
    assert Transfer.objects.filter(id=existing.id, club=canonical).exists()


def test_merges_list_only_covers_confirmed_pairs():
    # Locks in the known-safe scope (players/season.py-style guard against
    # scope creep back into broad fuzzy matching, which risks false-positive
    # merges of genuinely different clubs).
    assert MERGES == [
        ("LASK", ["LASK "]),
        ("Borussia M'gladbach", ["Borussia M_gladbach"]),
        ("Esenler Erokspor", [" Esenler Erokspor"]),
        ("AEK Larnaca", ["AEK Larnaca "]),
        ("AVS", ["AVS "]),
        ("Rodez", ["Rodez "]),
        ("St. Louis City", ["St. Louis City "]),
    ]


# ---------------------------------------------------------------------------
# No clean-named row exists (production before the 2025-2026 import): the
# padded row is the ONLY, live row for the club and must be renamed in place.
# ---------------------------------------------------------------------------


def test_renames_padded_club_in_place_when_no_clean_row_exists(db):
    padded = Club.objects.create(name="AEK Larnaca ", league="Superliga (Denmark)")
    player = Player.objects.create(unique_id=next(_unique_id_seq), player="Live Player", club=padded)
    transfer = _make_transfer(padded)

    call_command("merge_duplicate_clubs")

    padded.refresh_from_db()
    assert padded.name == "AEK Larnaca"
    assert Club.objects.filter(name__startswith="AEK Larnaca").count() == 1
    # Everything stays attached to the SAME row (id unchanged).
    player.refresh_from_db()
    transfer.refresh_from_db()
    assert player.club_id == padded.id
    assert transfer.club_id == padded.id


def test_rename_preserves_user_shortlists_and_squad_plans(db):
    from accounts.models import User

    padded = Club.objects.create(name="Rodez ")
    user = User.objects.create_user(email="rename-test@example.com", password="testpass123")
    shortlist = Shortlist.objects.create(user=user, name="My List", club=padded)
    plan = SquadPlan.objects.create(user=user, name="My Plan", club=padded)

    call_command("merge_duplicate_clubs")

    shortlist.refresh_from_db()
    plan.refresh_from_db()
    assert shortlist.club.name == "Rodez"
    assert plan.club.name == "Rodez"


def test_rename_dry_run_changes_nothing(db):
    padded = Club.objects.create(name="AVS ")

    call_command("merge_duplicate_clubs", dry_run=True)

    padded.refresh_from_db()
    assert padded.name == "AVS "


def test_rename_then_second_run_is_a_no_op(db):
    Club.objects.create(name="St. Louis City ")
    call_command("merge_duplicate_clubs")
    call_command("merge_duplicate_clubs")
    assert list(Club.objects.filter(name__startswith="St. Louis").values_list("name", flat=True)) == ["St. Louis City"]


def test_variant_is_still_merged_when_the_clean_row_does_exist(lask_pair):
    # Regression guard: the original merge path is unchanged.
    canonical, loser = lask_pair
    call_command("merge_duplicate_clubs")
    assert Club.objects.filter(id=canonical.id, name="LASK").exists()
    assert not Club.objects.filter(id=loser.id).exists()
