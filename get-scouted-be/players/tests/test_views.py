"""DRF APIClient integration tests for players/views.py (07-02-PLAN.md) --
covers PlayerListView (CRUD-01 filter/sort/paginate + CRUD-05 ?ids=) and
PlayerDetailView (CRUD-03 full profile + score breakdowns, including the
club=None defensive branch), plus the cross-cutting authentication gate.

`real_data_available` (players/tests/conftest.py, from 07-01) lets the
real-data tests skip cleanly against an empty pytest test DB.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from rest_framework.test import APIClient

from players.models import Player

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Auth fixture -- mirrors scoring/tests/test_views.py::auth_client verbatim.
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="players-view-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# Module-scope pre-warm of the memoized scored population -- mirrors
# scoring/tests/test_parity_bulk.py's bulk_scored fixture. The one real
# get_summary() call in test_detail_returns_profile_and_score_breakdowns
# needs the ~0.2s own-club warm path, not a cold ~74-115s reconstruction
# inside a single test function; module-scope fixtures can't use the
# function-scope db fixture, so this uses pytest-django's documented
# django_db_blocker.unblock() pattern.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def _warm_scored_population(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        if Player.objects.count() == 0:
            pytest.skip("No real Player data -- run Phase 1 import_all first.")

        from scoring.services.population import get_scored_population

        get_scored_population()


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------
def test_list_requires_authentication():
    client = APIClient()
    response = client.get("/api/v1/players/")
    assert response.status_code in (401, 403)


def test_detail_requires_authentication():
    client = APIClient()
    response = client.get(f"/api/v1/players/{uuid.uuid4()}/")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List: filter / sort / paginate
# ---------------------------------------------------------------------------
def test_list_filters_by_position(real_data_available, auth_client):
    position = Player.objects.exclude(position__isnull=True).values_list("position", flat=True).first()
    assert position, "expected at least one real Player.position value"

    response = auth_client.get(f"/api/v1/players/?position={position}&page_size=10")

    assert response.status_code == 200
    results = response.data["items"]
    assert results
    assert all(row["position"] == position for row in results)


def test_list_ordering_by_impact_score(real_data_available, auth_client):
    response = auth_client.get("/api/v1/players/?ordering=-impact_score&page_size=10")

    assert response.status_code == 200
    scores = [row["impact_score"] for row in response.data["items"] if row["impact_score"] is not None]
    assert scores == sorted(scores, reverse=True)


def test_list_pagination_shape(real_data_available, auth_client):
    response = auth_client.get("/api/v1/players/?page_size=5")

    assert response.status_code == 200
    assert {"items", "pagination"}.issubset(response.data)
    assert {"page", "page_size", "total_items", "has_next_page", "next_page"}.issubset(
        response.data["pagination"]
    )
    assert len(response.data["items"]) <= 5


def test_list_age_range_filter(real_data_available, auth_client):
    response = auth_client.get("/api/v1/players/?age_min=18&age_max=23&page_size=20")

    assert response.status_code == 200
    results = response.data["items"]
    assert results
    assert all(18 <= row["age"] <= 23 for row in results)


# ---------------------------------------------------------------------------
# Detail: full profile + score breakdowns
# ---------------------------------------------------------------------------
def test_detail_returns_profile_and_score_breakdowns(real_data_available, auth_client, _warm_scored_population):
    player = Player.objects.filter(club__isnull=False).first()
    assert player is not None, "expected at least one real player with a club"

    response = auth_client.get(f"/api/v1/players/{player.id}/")

    assert response.status_code == 200
    assert "season" in response.data
    assert set(response.data["scores"].keys()) == {
        "rmm", "compatibility", "financial_fit", "transfer_probability",
    }


def test_detail_club_none_returns_null_with_reason(auth_client, monkeypatch):
    player = Player.objects.create(
        unique_id=999_999_001,
        player="No Club",
        club=None,
        position="CM",
    )

    mock_get_summary = MagicMock()
    mock_get_rmm = MagicMock(return_value={"rmm": None, "reason": "stub"})
    monkeypatch.setattr("players.views.summary.get_summary", mock_get_summary)
    monkeypatch.setattr("players.views.rmm.get_rmm", mock_get_rmm)

    response = auth_client.get(f"/api/v1/players/{player.id}/")

    assert response.status_code == 200
    mock_get_summary.assert_not_called()
    mock_get_rmm.assert_called_once_with(player.id)

    scores = response.data["scores"]
    assert scores["compatibility"]["reason"] == "player_has_no_club"
    assert scores["financial_fit"]["reason"] == "player_has_no_club"
    assert scores["transfer_probability"]["reason"] == "player_has_no_club"


# ---------------------------------------------------------------------------
# CRUD-05: ?ids= multi-fetch
# ---------------------------------------------------------------------------
def test_ids_multifetch_returns_unpaginated_exact_set(real_data_available, auth_client):
    ids = list(Player.objects.values_list("id", flat=True)[:3])
    assert len(ids) == 3

    response = auth_client.get(f"/api/v1/players/?ids={','.join(str(i) for i in ids)}")

    assert response.status_code == 200
    assert isinstance(response.data, list)
    assert {row["id"] for row in response.data} == {str(i) for i in ids}


def test_ids_over_cap_returns_400(auth_client):
    ids = ",".join(str(uuid.uuid4()) for _ in range(101))

    response = auth_client.get(f"/api/v1/players/?ids={ids}")

    assert response.status_code == 400
