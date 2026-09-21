"""DRF APIClient integration tests for clubs/views.py::PositionNeedsView
(PLAN-01, 11-01-PLAN.md) -- covers GET /api/v1/clubs/{id}/position-needs/'s
classified-payload success shape, route-ordering correctness (must not be
swallowed by the <uuid:pk>/ catch-all), the natural 404 for an unknown
club, and the 401 authentication gate.

Runs under clubs/tests/conftest.py's ported autouse
`_block_real_anthropic_calls` guard -- harmless here since this endpoint
makes no LLM call."""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from clubs.models import Club
from players.models import Player
from players.season import DEFAULT_SEASON

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Auth fixture -- mirrors clubs/tests/test_ai_club_insights.py::auth_client.
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="position-needs-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _make_club_with_squad(name="Position Needs United"):
    club = Club.objects.create(name=name, league="Test League")
    base = hash(name) % 1_000_000
    Player.objects.create(unique_id=base + 1, player="P1", club=club, position="CB", age=24, season=DEFAULT_SEASON)
    Player.objects.create(unique_id=base + 2, player="P2", club=club, position="CB", age=26, season=DEFAULT_SEASON)
    Player.objects.create(unique_id=base + 3, player="P3", club=club, position="ST", age=22, season=DEFAULT_SEASON)
    return club


# ---------------------------------------------------------------------------
# Success -- classified payload
# ---------------------------------------------------------------------------
def test_position_needs_endpoint_returns_classified_payload(auth_client):
    club = _make_club_with_squad()

    response = auth_client.get(f"/api/v1/clubs/{club.id}/position-needs/")

    assert response.status_code == 200
    assert len(response.data) > 0
    for position, stats in response.data.items():
        assert stats["classification"] in {"weak", "at-risk", "strong"}
        assert "squad_depth" in stats
        assert "avg_age" in stats
        assert "contracts_expiring_within_12mo" in stats


# ---------------------------------------------------------------------------
# Route ordering -- must not be swallowed by the <uuid:pk>/ catch-all
# ---------------------------------------------------------------------------
def test_position_needs_route_not_swallowed_by_catchall(auth_client):
    club = _make_club_with_squad("Route Order United")

    response = auth_client.get(f"/api/v1/clubs/{club.id}/position-needs/")

    assert response.status_code == 200
    assert "id" not in response.data
    assert "name" not in response.data


# ---------------------------------------------------------------------------
# Unknown club -- natural 404
# ---------------------------------------------------------------------------
def test_position_needs_unknown_club_404(auth_client):
    response = auth_client.get(f"/api/v1/clubs/{uuid.uuid4()}/position-needs/")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------
def test_position_needs_requires_auth():
    client = APIClient()
    club = _make_club_with_squad("Anon United")

    response = client.get(f"/api/v1/clubs/{club.id}/position-needs/")

    assert response.status_code == 401
