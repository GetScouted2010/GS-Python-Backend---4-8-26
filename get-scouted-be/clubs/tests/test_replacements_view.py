"""Wave 0 RED scaffold: DRF APIClient integration tests for
GET /api/clubs/{id}/replacements/ (PLAN-02, 12-01-PLAN.md).

Mirrors clubs/tests/test_views_position_needs.py's auth_client + route-not-
swallowed + unknown-id-404 + requires-auth patterns. The route does not exist
yet -- these tests are expected to fail/collect-error today and turn green
once a later plan wires the endpoint.

Runs under clubs/tests/conftest.py's ported autouse `_block_real_anthropic_calls`
guard -- harmless here since this endpoint makes no LLM call.
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from clubs.models import Club
from players.models import Player

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="replacements-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_club_with_squad(name="Replacements United"):
    club = Club.objects.create(name=name, league="Test League")
    base = hash(name) % 1_000_000
    Player.objects.create(unique_id=base + 1, player="P1", club=club, position="CB", age=24)
    Player.objects.create(unique_id=base + 2, player="P2", club=club, position="ST", age=22)
    return club


def test_replacements_endpoint_returns_ranked_list(auth_client):
    club = _make_club_with_squad()

    response = auth_client.get(f"/api/clubs/{club.id}/replacements/?position=CB")

    assert response.status_code == 200
    assert "results" in response.data
    assert isinstance(response.data["results"], list)


def test_replacements_route_not_swallowed_by_catchall(auth_client):
    club = _make_club_with_squad("Route Order Replacements United")

    response = auth_client.get(f"/api/clubs/{club.id}/replacements/?position=CB")

    assert response.status_code == 200
    assert "id" not in response.data
    assert "name" not in response.data


def test_unknown_club_404(auth_client):
    response = auth_client.get(f"/api/clubs/{uuid.uuid4()}/replacements/?position=CB")

    assert response.status_code == 404


def test_replacements_requires_auth():
    client = APIClient()
    club = _make_club_with_squad("Anon Replacements United")

    response = client.get(f"/api/clubs/{club.id}/replacements/?position=CB")

    assert response.status_code == 401
