"""Score sorting puts players WITHOUT a score last, in either direction.

PostgreSQL sorts NULLs first on a descending sort, so the default
`-impact_score` list (and any `-compatibility_score` sort) used to open with
unscored players.
"""

from __future__ import annotations

import itertools

import pytest
from rest_framework.test import APIClient

from players.models import Player
from players.season import DEFAULT_SEASON

pytestmark = pytest.mark.django_db

_seq = itertools.count(1_900_000_001)


@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="ordering@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _player(name, **kw):
    return Player.objects.create(
        unique_id=next(_seq), player=name, season=DEFAULT_SEASON, **kw
    )


def _names(client, **params):
    response = client.get("/api/v1/players/", {"page_size": 50, **params})
    assert response.status_code == 200
    return [row["player"] for row in response.data["items"]]


def test_default_order_is_best_impact_first_with_unscored_players_last(auth_client):
    _player("none", impact_score=None)
    _player("low", impact_score=10.0)
    _player("high", impact_score=90.0)

    assert _names(auth_client) == ["high", "low", "none"]


def test_descending_sort_on_another_score_puts_missing_values_last(auth_client):
    _player("no-compat", compatibility_score=None)
    _player("mid", compatibility_score=70.0)
    _player("top", compatibility_score=95.0)

    assert _names(auth_client, ordering="-compatibility_score") == ["top", "mid", "no-compat"]


def test_ascending_sort_also_puts_missing_values_last(auth_client):
    # Not "lowest first" with the blanks up front: a blank is not the lowest.
    _player("no-compat", compatibility_score=None)
    _player("mid", compatibility_score=70.0)
    _player("top", compatibility_score=95.0)

    assert _names(auth_client, ordering="compatibility_score") == ["mid", "top", "no-compat"]


def test_ordering_by_an_unlisted_field_is_still_ignored(auth_client):
    # `ordering_fields` still governs what may be sorted on.
    _player("a", impact_score=1.0)
    _player("b", impact_score=2.0)

    assert _names(auth_client, ordering="player") == _names(auth_client)
