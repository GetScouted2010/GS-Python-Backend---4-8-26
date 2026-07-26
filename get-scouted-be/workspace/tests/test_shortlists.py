"""DRF APIClient integration tests for workspace/views.py::ShortlistViewSet
(08-03-PLAN.md) -- covers CRUD-07 create/name/club, nested entries
list/create/delete via @action routes, list-scoping to the calling user,
ownership propagation from the parent Shortlist to entry sub-routes, and
the cross-cutting authentication gate.

Uses the `authenticated_client`, `club_factory`, and `player_factory`
fixtures (accounts/tests/conftest.py + workspace/tests/conftest.py).
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from workspace.models import Shortlist, ShortlistEntry

pytestmark = pytest.mark.django_db

SHORTLISTS_URL = "/api/v1/workspace/shortlists/"


def test_create_named_shortlist_tied_to_club(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()

    response = client.post(SHORTLISTS_URL, {"name": "Targets", "club": str(club.id)})

    assert response.status_code == 201
    row = Shortlist.objects.get(id=response.data["id"])
    assert row.user == user
    assert row.name == "Targets"
    assert row.club == club


def test_add_entry_with_note(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player = player_factory()
    shortlist = Shortlist.objects.create(user=user, name="Targets", club=club)

    response = client.post(
        f"{SHORTLISTS_URL}{shortlist.id}/entries/",
        {"player": str(player.id), "note": "quick"},
    )

    assert response.status_code == 201
    entry = ShortlistEntry.objects.get(shortlist=shortlist, player=player)
    assert entry.note == "quick"


def test_list_entries(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    shortlist = Shortlist.objects.create(user=user, name="Targets", club=club)
    player_a = player_factory()
    player_b = player_factory()
    ShortlistEntry.objects.create(shortlist=shortlist, player=player_a, note="a")
    ShortlistEntry.objects.create(shortlist=shortlist, player=player_b, note="b")

    response = client.get(f"{SHORTLISTS_URL}{shortlist.id}/entries/")

    assert response.status_code == 200
    assert len(response.data) == 2


def test_delete_entry(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player = player_factory()
    shortlist = Shortlist.objects.create(user=user, name="Targets", club=club)
    entry = ShortlistEntry.objects.create(shortlist=shortlist, player=player, note="")

    response = client.delete(f"{SHORTLISTS_URL}{shortlist.id}/entries/{entry.id}/")

    assert response.status_code == 204
    assert not ShortlistEntry.objects.filter(id=entry.id).exists()


def test_scoping_list_excludes_other_users(authenticated_client, club_factory):
    client_a, user_a = authenticated_client()
    _client_b, user_b = authenticated_client()
    club = club_factory()

    shortlist_a = Shortlist.objects.create(user=user_a, name="A's list", club=club)
    shortlist_b = Shortlist.objects.create(user=user_b, name="B's list", club=club)

    response = client_a.get(SHORTLISTS_URL)

    assert response.status_code == 200
    result_ids = {row["id"] for row in response.data}
    assert result_ids == {str(shortlist_a.id)}
    assert str(shortlist_b.id) not in result_ids


def test_ownership_cannot_access_other_users_entries(authenticated_client, club_factory, player_factory):
    client_a, _user_a = authenticated_client()
    _client_b, user_b = authenticated_client()
    club = club_factory()
    player = player_factory()
    shortlist_b = Shortlist.objects.create(user=user_b, name="B's list", club=club)

    response = client_a.post(
        f"{SHORTLISTS_URL}{shortlist_b.id}/entries/",
        {"player": str(player.id), "note": "sneaky"},
    )

    assert response.status_code == 404
    assert not ShortlistEntry.objects.filter(shortlist=shortlist_b).exists()


def test_unauthenticated_denied():
    client = APIClient()

    response = client.get(SHORTLISTS_URL)

    assert response.status_code == 401
