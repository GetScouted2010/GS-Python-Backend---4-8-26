"""DRF APIClient integration tests for RecentActivity (08-05-PLAN.md, CRUD-09) --
covers auto-logging of viewed_player/viewed_club on the Phase 7 detail views,
newest-first retrieval, owner scoping, and confirms the RecentActivity write
did not alter Phase 7's player detail response contract.

Uses the `authenticated_client`, `club_factory`, and `player_factory` fixtures
(accounts/tests/conftest.py + workspace/tests/conftest.py).

A bare PlayerFactory() row has no club, so PlayerDetailView branches to the
club=None path and calls rmm.get_rmm() directly. Against an empty pytest test
DB that path would try a real scoring-engine population reconstruction (no
migrated Team/Club playing-style data exists), so -- mirroring
players/tests/test_views.py::test_detail_club_none_returns_null_with_reason --
players.views.rmm.get_rmm is monkeypatched to a stub in every test that hits
the player detail endpoint. This exercises the RecentActivity write path
without depending on real scoring data.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from workspace.models import RecentActivity

pytestmark = pytest.mark.django_db

ACTIVITY_URL = "/api/workspace/activity/"


@pytest.fixture(autouse=True)
def _stub_rmm(monkeypatch):
    monkeypatch.setattr(
        "players.views.rmm.get_rmm", lambda pk: {"rmm": None, "reason": "stub"}
    )


def test_viewing_player_logs_activity(authenticated_client, player_factory):
    client, user = authenticated_client()
    player = player_factory()

    response = client.get(f"/api/players/{player.id}/")

    assert response.status_code == 200
    assert RecentActivity.objects.filter(
        user=user, activity_type="viewed_player", target_id=player.id
    ).exists()


def test_viewing_club_logs_activity(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()

    response = client.get(f"/api/clubs/{club.id}/")

    assert response.status_code == 200
    assert RecentActivity.objects.filter(
        user=user, activity_type="viewed_club", target_id=club.id
    ).exists()


def test_activity_list_newest_first(authenticated_client, player_factory):
    client, user = authenticated_client()
    player_a = player_factory()
    player_b = player_factory()

    client.get(f"/api/players/{player_a.id}/")
    client.get(f"/api/players/{player_b.id}/")

    response = client.get(ACTIVITY_URL)

    assert response.status_code == 200
    target_ids = [row["target_id"] for row in response.data]
    assert target_ids == [str(player_b.id), str(player_a.id)]


def test_scoping_activity_excludes_other_users(authenticated_client, player_factory):
    client_a, user_a = authenticated_client()
    client_b, user_b = authenticated_client()
    player = player_factory()

    client_b.get(f"/api/players/{player.id}/")

    response = client_a.get(ACTIVITY_URL)

    assert response.status_code == 200
    assert response.data == []


def test_player_detail_response_shape_unchanged(authenticated_client, player_factory):
    client, user = authenticated_client()
    player = player_factory()

    response = client.get(f"/api/players/{player.id}/")

    assert response.status_code == 200
    assert "scores" in response.data
    assert "player" in response.data


def test_unauthenticated_activity_denied():
    client = APIClient()
    response = client.get(ACTIVITY_URL)

    assert response.status_code == 401
