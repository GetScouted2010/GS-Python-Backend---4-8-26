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
from players.serializers import PlayerDetailSerializer, PlayerListSerializer

pytestmark = pytest.mark.django_db

_unique_id_seq = itertools.count(999_600_001)


# An OLD season: the A3 rule (league comes from the club, never the noisy raw
# column) applies to seasons NOT in players.season.ROW_LEAGUE_SEASONS.
OLD_SEASON = "2024-2025"


def _make_player(club, **kwargs):
    kwargs.setdefault("unique_id", next(_unique_id_seq))
    kwargs.setdefault("player", "League Test Player")
    kwargs.setdefault("season", OLD_SEASON)
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
        season=OLD_SEASON,
    )

    data = PlayerListSerializer(player).data

    assert data["league"] == "Some Raw League"


def test_filter_binds_to_club_league():
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    contaminated = _make_player(club, league="Premier League (England)")

    result = PlayerFilter(
        data={"league": "Premier League (England)", "season": OLD_SEASON},
        queryset=Player.objects.all(),
    ).qs

    # The player's raw column matches "Premier League (England)" but their
    # actual club does not -- must NOT be included.
    assert contaminated not in result


def test_filter_matches_players_by_actual_club_league():
    club = Club.objects.create(name="Brentford", league="Premier League (England)")
    genuine = _make_player(club, league="Premier League (England)")

    result = PlayerFilter(
        data={"league": "Premier League (England)", "season": OLD_SEASON},
        queryset=Player.objects.all(),
    ).qs

    assert genuine in result


def test_player_list_endpoint_serves_canonical_league(auth_client):
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    player = _make_player(club, league="Premier League (England)")

    response = auth_client.get("/api/v1/players/", {"season": OLD_SEASON})

    assert response.status_code == 200
    row = next(r for r in response.data["items"] if r["id"] == str(player.id))
    assert row["league"] == "EFL Championship"


# ---------------------------------------------------------------------------
# Seasons whose per-row league is clean (players.season.ROW_LEAGUE_SEASONS):
# 2025-2026 rows are shown/filtered by their OWN league, because Club.league
# is one value per club and is wrong or stale for many clubs (e.g. a club
# stored as "La Liga (Spain)" that actually plays in Greece).
# ---------------------------------------------------------------------------


def test_row_league_season_serializes_its_own_league_not_the_club_league():
    club = Club.objects.create(name="Panathinaikos", league="La Liga (Spain)")  # wrong legacy value
    player = _make_player(club, season="2025-2026", league="Super League (Greece)")

    assert PlayerListSerializer(player).data["league"] == "Super League (Greece)"
    assert PlayerDetailSerializer(player).data["league"] == "Super League (Greece)"


def test_old_season_still_uses_the_club_league_even_when_raw_differs():
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    player = _make_player(club, season="2024-2025", league="Premier League (England)")

    assert PlayerListSerializer(player).data["league"] == "EFL Championship"


def test_row_league_season_with_blank_raw_league_falls_back_to_club_league():
    club = Club.objects.create(name="Some FC", league="Serie A (Italy)")
    player = _make_player(club, season="2025-2026", league=None)

    assert PlayerListSerializer(player).data["league"] == "Serie A (Italy)"


def test_league_filter_matches_row_league_for_2025_2026():
    greek = Club.objects.create(name="Panathinaikos", league="La Liga (Spain)")  # wrong legacy value
    spanish = Club.objects.create(name="Real Madrid", league="La Liga (Spain)")
    p_greek = _make_player(greek, season="2025-2026", league="Super League (Greece)")
    p_spanish = _make_player(spanish, season="2025-2026", league="La Liga (Spain)")

    greece = PlayerFilter(
        data={"league": "Super League (Greece)", "season": "2025-2026"}, queryset=Player.objects.all()
    ).qs
    spain = PlayerFilter(
        data={"league": "La Liga (Spain)", "season": "2025-2026"}, queryset=Player.objects.all()
    ).qs

    assert list(greece) == [p_greek]
    assert list(spain) == [p_spanish]  # Panathinaikos must NOT leak into La Liga


def test_league_filter_still_uses_club_league_for_old_seasons():
    club = Club.objects.create(name="West Bromwich Albion", league="EFL Championship")
    player = _make_player(club, season="2024-2025", league="Premier League (England)")

    by_club_league = PlayerFilter(
        data={"league": "EFL Championship", "season": "2024-2025"}, queryset=Player.objects.all()
    ).qs
    by_raw_league = PlayerFilter(
        data={"league": "Premier League (England)", "season": "2024-2025"}, queryset=Player.objects.all()
    ).qs

    assert list(by_club_league) == [player]
    assert list(by_raw_league) == []  # the contaminated raw column must not match


def test_league_filter_keeps_null_season_rows_on_the_club_league_path():
    club = Club.objects.create(name="No Season FC", league="Serie A (Italy)")
    player = _make_player(club, season=None, league="Something Else")

    result = PlayerFilter(
        data={"league": "Serie A (Italy)", "ids": str(player.id)}, queryset=Player.objects.all()
    ).qs

    assert list(result) == [player]
