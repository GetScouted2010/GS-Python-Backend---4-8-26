"""DB-backed tests for the A2 fix: score _max and minutes _min/_max range
filters actually narrow the queryset, not just that the fields exist
(players/tests/test_filters.py covers the field bindings)."""

from __future__ import annotations

import itertools

import pytest

from players.filters import PlayerFilter
from players.models import Player
from players.season import DEFAULT_SEASON

pytestmark = pytest.mark.django_db

_unique_id_seq = itertools.count(999_500_001)


def _make_player(**kwargs):
    kwargs.setdefault("unique_id", next(_unique_id_seq))
    kwargs.setdefault("player", "Range Test Player")
    kwargs.setdefault("season", DEFAULT_SEASON)
    return Player.objects.create(**kwargs)


def test_impact_score_max_excludes_players_above_threshold():
    low = _make_player(impact_score=50.0)
    high = _make_player(impact_score=90.0)

    result = PlayerFilter(
        data={"impact_score_max": "60", "season": DEFAULT_SEASON}, queryset=Player.objects.all()
    ).qs

    assert low in result
    assert high not in result


def test_minutes_range_filters_both_ends():
    too_low = _make_player(Minutes_played=100)
    in_range = _make_player(Minutes_played=1500)
    too_high = _make_player(Minutes_played=3500)

    result = PlayerFilter(
        data={"minutes_min": "500", "minutes_max": "2000", "season": DEFAULT_SEASON},
        queryset=Player.objects.all(),
    ).qs

    assert in_range in result
    assert too_low not in result
    assert too_high not in result
