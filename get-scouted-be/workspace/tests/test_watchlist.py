"""DRF APIClient integration tests for workspace/views.py::WatchlistViewSet
(08-02-PLAN.md) -- covers CRUD-06 save/remove, duplicate-add handling via
DRF's auto UniqueTogetherValidator, list-scoping to the calling user, and
the cross-cutting authentication gate.

Uses the `authenticated_client` (accounts/tests/conftest.py, re-exported
via workspace/tests/conftest.py) and `player_factory` fixtures.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from workspace.models import Watchlist

pytestmark = pytest.mark.django_db

WATCHLIST_URL = "/api/v1/workspace/watchlist/"


def test_save_player_returns_201(authenticated_client, player_factory):
    client, user = authenticated_client()
    player = player_factory()

    response = client.post(WATCHLIST_URL, {"player": str(player.id)})

    assert response.status_code == 201
    assert Watchlist.objects.filter(user=user, player=player).exists()


def test_duplicate_save_returns_400_not_500(authenticated_client, player_factory):
    client, user = authenticated_client()
    player = player_factory()

    first = client.post(WATCHLIST_URL, {"player": str(player.id)})
    second = client.post(WATCHLIST_URL, {"player": str(player.id)})

    assert first.status_code == 201
    assert second.status_code == 400
    assert Watchlist.objects.filter(user=user, player=player).count() == 1


def test_remove_player_returns_204(authenticated_client, player_factory):
    client, user = authenticated_client()
    player = player_factory()
    row = Watchlist.objects.create(user=user, player=player)

    response = client.delete(f"{WATCHLIST_URL}{row.id}/")

    assert response.status_code == 204
    assert not Watchlist.objects.filter(id=row.id).exists()


def test_scoping_list_excludes_other_users(authenticated_client, player_factory):
    client_a, user_a = authenticated_client()
    client_b, user_b = authenticated_client()

    player_a = player_factory()
    player_b = player_factory()
    row_a = Watchlist.objects.create(user=user_a, player=player_a)
    row_b = Watchlist.objects.create(user=user_b, player=player_b)

    response = client_a.get(WATCHLIST_URL)

    assert response.status_code == 200
    result_ids = {row["id"] for row in response.data["items"]}
    assert result_ids == {str(row_a.id)}
    assert str(row_b.id) not in result_ids
    assert len(response.data["items"]) == Watchlist.objects.filter(user=user_a).count()


def test_ownership_delete_other_users_row_denied(authenticated_client, player_factory):
    client_a, _user_a = authenticated_client()
    _client_b, user_b = authenticated_client()
    player_b = player_factory()
    row_b = Watchlist.objects.create(user=user_b, player=player_b)

    response = client_a.delete(f"{WATCHLIST_URL}{row_b.id}/")

    assert response.status_code in (403, 404)
    assert Watchlist.objects.filter(id=row_b.id).exists()


def test_unauthenticated_denied():
    client = APIClient()

    response = client.get(WATCHLIST_URL)

    assert response.status_code == 401
