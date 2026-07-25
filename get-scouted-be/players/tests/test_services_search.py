"""Tests for players/services.py::search_players (09-03-PLAN.md Task 2).

`real_data_available` (players/tests/conftest.py) lets the real-data tests
skip cleanly against an empty pytest test DB (Phase 1's real migrated data
lives only in the dev DB).

Test 1 (`test_style_filter_field_name_transform`) is the regression test for
this plan's flagged trap: PlayerFilter silently ignores club__-prefixed keys
rather than erroring, so a bug here would silently return WRONG (unfiltered)
results instead of crashing. It asserts the style term actually NARROWS the
result set, not just that the request succeeds.
"""

from __future__ import annotations

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from players.filters import PlayerFilter
from players.models import Player
from players.services import search_players

pytestmark = pytest.mark.django_db


def _request():
    return Request(APIRequestFactory().post("/api/players/search/"))


# ---------------------------------------------------------------------------
# Test 1: style filter field-name transform (the flagged trap) -- regression
# ---------------------------------------------------------------------------
def test_style_filter_field_name_transform(real_data_available):
    baseline = search_players({}, _request())
    filtered = search_players({"club__control_possession_min": 15}, _request())

    # No FieldError raised (composition succeeded), AND the style term
    # actually narrowed the result set -- not just a request that succeeds
    # while silently ignoring the filter (the exact bug this test guards
    # against). ~77% of clubs have no Playstyles coverage (null style
    # fields), so a real gte filter is guaranteed to exclude some players.
    assert filtered["count"] < baseline["count"]


# ---------------------------------------------------------------------------
# Test 2: PlayerFilter path (position + age range)
# ---------------------------------------------------------------------------
def test_player_filter_path_position_and_age(real_data_available):
    response = search_players({"position": "CB", "age_max": 21}, _request())

    assert response["results"]
    assert all(row["position"] == "CB" for row in response["results"])
    assert all(row["age"] is None or row["age"] <= 21 for row in response["results"])


# ---------------------------------------------------------------------------
# Test 3: style keys are NOT smuggled through PlayerFilter's own data dict
# ---------------------------------------------------------------------------
def test_style_key_alone_not_applied_by_player_filter(real_data_available):
    """Documents WHY the manual step exists: PlayerFilter silently ignores
    an undeclared club__ key in its data dict, so passing it there alone
    does nothing. search_players must apply it via the separate step
    instead (proven by test_style_filter_field_name_transform above)."""
    qs = PlayerFilter(data={"club__control_possession_min": 15}, queryset=Player.objects.all()).qs

    assert qs.count() == Player.objects.count()


# ---------------------------------------------------------------------------
# Test 4: paginated envelope shape
# ---------------------------------------------------------------------------
def test_paginated_envelope_shape(real_data_available):
    response = search_players({}, _request())

    assert {"results", "count"}.issubset(response)
    assert response["results"]
    assert set(response["results"][0].keys()) >= {"id", "player", "position"}


# ---------------------------------------------------------------------------
# Test 5: empty filters returns the full paginated list
# ---------------------------------------------------------------------------
def test_empty_filters_returns_full_list(real_data_available):
    response = search_players({}, _request())

    assert response["count"] > 0
    assert response["count"] == Player.objects.count()
