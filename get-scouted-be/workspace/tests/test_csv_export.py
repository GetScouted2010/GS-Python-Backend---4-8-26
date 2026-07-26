"""DRF APIClient integration tests for CSV export (08-06-PLAN.md, CRUD-10) --
covers Shortlist export (IsOwner-gated, columns matching PlayerListSerializer)
and Club report export (IsAuthenticated-only, profile + transfer aggregates).

Uses the `authenticated_client`, `club_factory`, and `player_factory` fixtures
(accounts/tests/conftest.py + workspace/tests/conftest.py).

Both endpoints return a StreamingHttpResponse; response.streaming_content is
an iterable of bytes chunks that must be joined + decoded before being fed
to csv.reader.
"""

from __future__ import annotations

import csv
import io

import pytest
from rest_framework.test import APIClient

from workspace.models import Shortlist, ShortlistEntry
from workspace.views import PLAYER_EXPORT_COLUMNS

pytestmark = pytest.mark.django_db


def _parse_csv(response):
    text = b"".join(response.streaming_content).decode("utf-8")
    return list(csv.reader(io.StringIO(text)))


def test_shortlist_export_returns_csv(authenticated_client, player_factory, club_factory):
    client, user = authenticated_client()
    club = club_factory()
    shortlist = Shortlist.objects.create(user=user, club=club, name="My Shortlist")
    player_a = player_factory()
    player_b = player_factory()
    ShortlistEntry.objects.create(shortlist=shortlist, player=player_a)
    ShortlistEntry.objects.create(shortlist=shortlist, player=player_b)

    response = client.get(f"/api/v1/workspace/shortlists/{shortlist.id}/export/")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    rows = _parse_csv(response)
    assert rows[0] == PLAYER_EXPORT_COLUMNS
    assert len(rows) - 1 == 2


def test_shortlist_export_ownership(authenticated_client, club_factory):
    client_a, user_a = authenticated_client()
    client_b, user_b = authenticated_client()
    club = club_factory()
    shortlist_b = Shortlist.objects.create(user=user_b, club=club, name="B's Shortlist")

    response = client_a.get(f"/api/v1/workspace/shortlists/{shortlist_b.id}/export/")

    assert response.status_code == 404


def test_club_export_returns_csv(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()

    response = client.get(f"/api/v1/clubs/{club.id}/export/")

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    rows = _parse_csv(response)
    assert "name" in rows[0]
    assert "total_transfers" in rows[0]
    assert len(rows) - 1 == 1


def test_club_export_content_disposition(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()

    response = client.get(f"/api/v1/clubs/{club.id}/export/")

    disposition = response["Content-Disposition"]
    assert "attachment" in disposition
    assert ".csv" in disposition


def test_unauthenticated_export_denied(club_factory):
    club = club_factory()
    shortlist_owner_client = APIClient()

    response = shortlist_owner_client.get("/api/v1/workspace/shortlists/00000000-0000-0000-0000-000000000000/export/")

    assert response.status_code == 401
