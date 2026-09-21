"""GET /players/seasons/ -- feeds the frontend's season selector."""

from __future__ import annotations

import itertools

import pytest
from rest_framework.test import APIClient

from players.models import Player
from players.season import DEFAULT_SEASON, SEASON_ORDER

pytestmark = pytest.mark.django_db

_seq = itertools.count(1_600_000_001)


@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="season-list@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _rows(client):
    response = client.get("/api/v1/players/seasons/")
    assert response.status_code == 200
    return response.data


def test_lists_every_registered_season_in_order(auth_client):
    assert [r["season"] for r in _rows(auth_client)] == SEASON_ORDER


def test_exactly_one_season_is_the_default(auth_client):
    defaults = [r["season"] for r in _rows(auth_client) if r["is_default"]]
    assert defaults == [DEFAULT_SEASON]


def test_unscored_season_is_flagged_so_the_frontend_can_disable_score_controls(auth_client):
    by_season = {r["season"]: r for r in _rows(auth_client)}
    assert by_season["2025-2026"]["scored"] is False
    assert by_season[DEFAULT_SEASON]["scored"] is True


def test_player_counts_are_per_season(auth_client):
    for season, n in ((DEFAULT_SEASON, 2), ("2025-2026", 3)):
        for _ in range(n):
            Player.objects.create(unique_id=next(_seq), player="P", season=season)

    by_season = {r["season"]: r["player_count"] for r in _rows(auth_client)}

    assert by_season[DEFAULT_SEASON] == 2
    assert by_season["2025-2026"] == 3
    assert by_season["2023-2024"] == 0  # a listed season with no rows is 0, not missing


def test_requires_authentication():
    assert APIClient().get("/api/v1/players/seasons/").status_code in (401, 403)
