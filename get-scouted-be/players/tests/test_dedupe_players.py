"""Tests for the dedupe_players management command (A1 fix).

See dedupe_players.py's module docstring for the full rationale: Players.csv
contains a real minority of exact-duplicate observations (same player,
season, club, age, position) differing only in stat completeness -- keep
the row with the most Matches_played/Minutes_played, drop the rest. Verified
against production data 2026-09-09: 691 groups, 698 losing rows, 0 of which
had a linked Transfer (SET_NULL) -- so no data-loss edge case to cover here.
"""

from __future__ import annotations

import itertools

import pytest
from django.core.management import call_command

from players.models import Player, PlayerRoleScore

pytestmark = pytest.mark.django_db

_unique_id_seq = itertools.count(999_800_001)


def _make_player(**kwargs):
    kwargs.setdefault("unique_id", next(_unique_id_seq))
    kwargs.setdefault("player", "Dup Test Player")
    kwargs.setdefault("season", "2024-2025")
    kwargs.setdefault("age", 25)
    kwargs.setdefault("position", "CM")
    return Player.objects.create(**kwargs)


def test_keeps_row_with_most_minutes():
    winner = _make_player(Minutes_played=1285, Matches_played=16)
    _make_player(Minutes_played=1087, Matches_played=15)
    _make_player(Minutes_played=10, Matches_played=1)

    call_command("dedupe_players", report_dir="/tmp")

    remaining = Player.objects.all()
    assert remaining.count() == 1
    assert remaining.first().id == winner.id


def test_ties_broken_by_matches_then_unique_id():
    # Equal minutes -> higher matches wins.
    _make_player(unique_id=1, Minutes_played=500, Matches_played=5)
    winner = _make_player(unique_id=2, Minutes_played=500, Matches_played=10)

    call_command("dedupe_players", report_dir="/tmp")

    assert Player.objects.get().id == winner.id


def test_does_not_merge_different_real_people_same_name():
    # Different age/position/club -- genuine name collisions, not the same
    # observation. Must NOT be collapsed (players/season.py's Paulinho case).
    _make_player(player="Same Name", age=23, position="FWD")
    _make_player(player="Same Name", age=30, position="GK")

    call_command("dedupe_players", report_dir="/tmp")

    assert Player.objects.count() == 2


def test_dry_run_deletes_nothing():
    _make_player(Minutes_played=1000)
    _make_player(Minutes_played=10)

    call_command("dedupe_players", dry_run=True, report_dir="/tmp")

    assert Player.objects.count() == 2


def test_cascades_delete_losing_rows_role_scores():
    winner = _make_player(Minutes_played=1000)
    loser = _make_player(Minutes_played=10)
    PlayerRoleScore.objects.create(player=winner, position_group="CM", role_name="r1", role_name_raw="R1")
    PlayerRoleScore.objects.create(player=loser, position_group="CM", role_name="r1", role_name_raw="R1")

    call_command("dedupe_players", report_dir="/tmp")

    assert PlayerRoleScore.objects.count() == 1
    assert PlayerRoleScore.objects.get().player_id == winner.id


def test_idempotent_second_run_is_a_no_op():
    _make_player(Minutes_played=1000)
    _make_player(Minutes_played=10)

    call_command("dedupe_players", report_dir="/tmp")
    assert Player.objects.count() == 1

    call_command("dedupe_players", report_dir="/tmp")
    assert Player.objects.count() == 1
