"""Tests for the A3 fix: player-facing `league` resolves through the club's
canonical league, never the raw per-row Player.league column.

See players/serializers.py's module docstring for the full rationale --
confirmed against production data 2026-09-09: the raw column is contaminated
for ~8.7% of rows (a player's row can carry a PRIOR club's league from a
transfer/loan spell), while Club.league (mode-derived) is correct for every
club checked.
"""

from __future__ import annotations

import itertools

import pytest
from rest_framework.test import APIClient

from clubs.models import Club
from players.filters import PlayerFilter
from players.models import Player
from players.season import DEFAULT_SEASON
from players.serializers import PlayerDetailSerializer, PlayerListSerializer

pytestmark = pytest.mark.django_db

_unique_id_seq = itertools.count(999_600_001)


def _make_player(club, **kwargs):
    kwargs.setdefault("unique_id", next(_unique_id_seq))
    kwargs.setdefault("player", "League Test Player")
    kwargs.setdefault("season", DEFAULT_SEASON)
    return Player.objects.create(club=club, **kwargs)


@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="league-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_list_serializer_uses_club_league_not_raw_column():
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    # Raw per-row value is a DIFFERENT, contaminated league -- exactly the
    # real West Brom / M. Holgate pattern found in production.
    player = _make_player(club, league="Premier League (England)")

    data = PlayerListSerializer(player).data

    assert data["league"] == "EFL Championship"
    assert player.league == "Premier League (England)"  # raw column untouched


def test_detail_serializer_uses_club_league_not_raw_column():
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    player = _make_player(club, league="Premier League (England)")

    data = PlayerDetailSerializer(player).data

    assert data["league"] == "EFL Championship"


def test_serializer_falls_back_to_raw_league_when_no_club():
    player = Player.objects.create(
        unique_id=next(_unique_id_seq),
        player="Clubless Player",
        club=None,
        league="Some Raw League",
        season=DEFAULT_SEASON,
    )

    data = PlayerListSerializer(player).data

    assert data["league"] == "Some Raw League"


def test_filter_binds_to_club_league():
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    contaminated = _make_player(club, league="Premier League (England)")

    result = PlayerFilter(
        data={"league": "Premier League (England)", "season": DEFAULT_SEASON},
        queryset=Player.objects.all(),
    ).qs

    # The player's raw column matches "Premier League (England)" but their
    # actual club does not -- must NOT be included.
    assert contaminated not in result


def test_filter_matches_players_by_actual_club_league():
    club = Club.objects.create(name="Brentford", league="Premier League (England)")
    genuine = _make_player(club, league="Premier League (England)")

    result = PlayerFilter(
        data={"league": "Premier League (England)", "season": DEFAULT_SEASON},
        queryset=Player.objects.all(),
    ).qs

    assert genuine in result


def test_player_list_endpoint_serves_canonical_league(auth_client):
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    player = _make_player(club, league="Premier League (England)")

    response = auth_client.get("/api/v1/players/")

    assert response.status_code == 200
    row = next(r for r in response.data["items"] if r["id"] == str(player.id))
    assert row["league"] == "EFL Championship"
