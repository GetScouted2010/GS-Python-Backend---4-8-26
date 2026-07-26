"""Wave 0 RED scaffold: DRF APIClient integration tests for
GET /api/players/{id}/club-matches/ (PLAN-04, 12-01-PLAN.md).

Mirrors players/tests/test_scouting_report_view.py's auth_client pattern. The
route does not exist yet -- these tests are expected to fail/collect-error
today and turn green once a later plan wires the endpoint.

Runs under players/tests/conftest.py's autouse `_block_real_anthropic_calls`
guard -- harmless here since this endpoint makes no LLM call.
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from players.models import Player

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="club-matches-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_club_matches_endpoint_returns_ranked_list(auth_client):
    player = Player.objects.create(unique_id=999_998_001, player="Club Matches Subject", position="CB")

    response = auth_client.get(f"/api/players/{player.id}/club-matches/")

    assert response.status_code == 200
    assert "results" in response.data
    assert isinstance(response.data["results"], list)


def test_club_matches_route_not_swallowed_by_catchall(auth_client):
    player = Player.objects.create(unique_id=999_998_002, player="Route Order Subject", position="ST")

    response = auth_client.get(f"/api/players/{player.id}/club-matches/")

    assert response.status_code == 200
    assert "player" not in response.data
    assert "unique_id" not in response.data


def test_unknown_player_404(auth_client):
    response = auth_client.get(f"/api/players/{uuid.uuid4()}/club-matches/")

    assert response.status_code == 404


def test_club_matches_requires_auth():
    client = APIClient()
    player = Player.objects.create(unique_id=999_998_003, player="Anon Subject", position="GK")

    response = client.get(f"/api/players/{player.id}/club-matches/")

    assert response.status_code == 401
