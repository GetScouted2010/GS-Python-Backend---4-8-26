"""DRF APIClient integration tests for clubs/views.py (07-03-PLAN.md) --
covers ClubListView (CRUD-02 filter/paginate + CRUD-05 ?ids=) and
ClubDetailView (CRUD-04 full profile + squad overview + transfer-behaviour
aggregates), plus the cross-cutting authentication gate.

`real_data_available` (clubs/tests/conftest.py, from 07-01) lets the
real-data tests skip cleanly against an empty pytest test DB.
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from clubs.models import Club
from transfers.models import Transfer

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Auth fixture -- mirrors players/tests/test_views.py::auth_client /
# scoring/tests/test_views.py::auth_client verbatim.
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="clubs-view-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------
def test_list_requires_authentication():
    client = APIClient()
    response = client.get("/api/v1/clubs/")
    assert response.status_code in (401, 403)


def test_detail_requires_authentication():
    client = APIClient()
    response = client.get(f"/api/v1/clubs/{uuid.uuid4()}/")
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# List: filter / paginate
# ---------------------------------------------------------------------------
def test_list_filters_by_league(real_data_available, auth_client):
    league = Club.objects.exclude(league__isnull=True).values_list("league", flat=True).first()
    assert league, "expected at least one real Club.league value"

    response = auth_client.get(f"/api/v1/clubs/?league={league}&page_size=10")

    assert response.status_code == 200
    results = response.data["items"]
    assert results
    assert all(row["league"] == league for row in results)


def test_list_filters_by_country(real_data_available, auth_client):
    country = Club.objects.exclude(country__isnull=True).values_list("country", flat=True).first()
    assert country, "expected at least one real Club.country value"

    response = auth_client.get(f"/api/v1/clubs/?country={country}&page_size=10")

    assert response.status_code == 200
    results = response.data["items"]
    assert results
    assert all(row["country"] == country for row in results)


def test_list_pagination_shape(real_data_available, auth_client):
    response = auth_client.get("/api/v1/clubs/?page_size=5")

    assert response.status_code == 200
    assert {"items", "pagination"}.issubset(response.data)
    assert {"page", "page_size", "total_items", "has_next_page", "next_page"}.issubset(
        response.data["pagination"]
    )
    assert len(response.data["items"]) <= 5


# ---------------------------------------------------------------------------
# Detail: full profile + squad overview + transfer-behaviour aggregates
# ---------------------------------------------------------------------------
def test_detail_returns_profile_squad_and_transfer_aggregates(real_data_available, auth_client):
    club_id = Transfer.objects.values_list("club_id", flat=True).first()
    if club_id is None:
        club_id = Club.objects.values_list("id", flat=True).first()
    assert club_id is not None, "expected at least one real Club"

    response = auth_client.get(f"/api/v1/clubs/{club_id}/")

    assert response.status_code == 200
    assert isinstance(response.data["squad"], list)
    assert {
        "total_transfers", "arrivals", "departures",
        "avg_market_value_at_transfer", "total_market_value_at_transfer",
        "by_window",
    }.issubset(response.data["transfer_aggregates"])


def test_detail_aggregates_use_market_value_not_fee(real_data_available, auth_client):
    club_id = Transfer.objects.values_list("club_id", flat=True).first()
    if club_id is None:
        club_id = Club.objects.values_list("id", flat=True).first()
    assert club_id is not None, "expected at least one real Club"

    response = auth_client.get(f"/api/v1/clubs/{club_id}/")

    # A fee aggregation (Sum/Avg on the free-text CharField) would have
    # raised a DataError before reaching this point -- 200 + the key's
    # presence proves market_value_at_transfer (numeric) was used instead.
    assert response.status_code == 200
    assert "avg_market_value_at_transfer" in response.data["transfer_aggregates"]


# ---------------------------------------------------------------------------
# CRUD-05: ?ids= multi-fetch (club half)
# ---------------------------------------------------------------------------
def test_ids_multifetch_returns_unpaginated_exact_set(real_data_available, auth_client):
    ids = list(Club.objects.values_list("id", flat=True)[:3])
    assert len(ids) == 3

    response = auth_client.get(f"/api/v1/clubs/?ids={','.join(str(i) for i in ids)}")

    assert response.status_code == 200
    assert isinstance(response.data, list)
    assert {row["id"] for row in response.data} == {str(i) for i in ids}


def test_ids_over_cap_returns_400(auth_client):
    ids = ",".join(str(uuid.uuid4()) for _ in range(101))

    response = auth_client.get(f"/api/v1/clubs/?ids={ids}")

    assert response.status_code == 400
