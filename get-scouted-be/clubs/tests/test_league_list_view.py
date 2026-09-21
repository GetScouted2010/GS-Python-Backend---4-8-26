"""GET /clubs/leagues/ -- feeds a league -> club cascading dropdown."""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from clubs.models import Club

pytestmark = pytest.mark.django_db


@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="league-list@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _rows(client):
    response = client.get("/api/v1/clubs/leagues/")
    assert response.status_code == 200
    return response.data


def test_lists_each_league_once_with_its_club_count_and_country(auth_client):
    Club.objects.create(name="Arsenal", league="Premier League (England)")
    Club.objects.create(name="Chelsea", league="Premier League (England)")
    Club.objects.create(name="Metz", league="Ligue 2 (France)")
    Club.objects.create(name="Dundee", league="SPL")

    assert _rows(auth_client) == [
        {"league": "Ligue 2 (France)", "country": "France", "club_count": 1},
        {"league": "Premier League (England)", "country": "England", "club_count": 2},
        {"league": "SPL", "country": "Scotland", "club_count": 1},
    ]


def test_clubs_without_a_league_are_not_listed_as_a_league(auth_client):
    Club.objects.create(name="No League FC", league=None)
    Club.objects.create(name="Blank League FC", league="")

    assert _rows(auth_client) == []


def test_a_listed_league_value_works_verbatim_as_the_clubs_filter(auth_client):
    # The point of the endpoint: what it returns is what the second step of
    # the cascade sends back.
    Club.objects.create(name="Arsenal", league="Premier League (England)")
    Club.objects.create(name="Metz", league="Ligue 2 (France)")

    league = _rows(auth_client)[1]["league"]
    response = auth_client.get("/api/v1/clubs/", {"league": league})

    assert response.status_code == 200
    assert [c["name"] for c in response.data["items"]] == ["Arsenal"]


def test_requires_authentication():
    assert APIClient().get("/api/v1/clubs/leagues/").status_code in (401, 403)
