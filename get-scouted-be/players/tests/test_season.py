"""Tests for the A1 season-dimension fix (players/season.py + PlayerFilter).

Player rows are player-SEASON records -- see players/season.py's module
docstring for the full rationale (verified against production data
2026-09-09: unfiltered listings return up to 4 rows per real person, plus
genuine cross-season name collisions like 7 distinct real "Paulinho"s in
one season alone).
"""

from __future__ import annotations

import itertools

import pytest
from rest_framework.test import APIClient

from players.models import Player
from players.season import DEFAULT_SEASON, SEASON_ORDER, resolve_season, scope_to_season

pytestmark = pytest.mark.django_db

_unique_id_seq = itertools.count(999_900_001)


def _make_player(**kwargs):
    kwargs.setdefault("unique_id", next(_unique_id_seq))
    kwargs.setdefault("player", "Season Test Player")
    return Player.objects.create(**kwargs)


# ---------------------------------------------------------------------------
# Auth fixture -- mirrors players/tests/test_views.py::auth_client verbatim.
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="season-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --- Pure-Python: resolve_season (no DB needed, but module is marked django_db) ---


def test_resolve_season_returns_default_when_none():
    assert resolve_season(None) == DEFAULT_SEASON


def test_resolve_season_returns_default_when_blank():
    assert resolve_season("") == DEFAULT_SEASON


def test_resolve_season_returns_default_when_unrecognized():
    assert resolve_season("not-a-real-season") == DEFAULT_SEASON


def test_resolve_season_passes_through_known_value():
    assert resolve_season("2023-2024") == "2023-2024"


def test_default_season_is_the_first_in_season_order():
    # Product decision (2026-09-21): the newest scored season, 2025-2026, is
    # what an omitted ?season= resolves to. (Previously "Last Calendar Year",
    # the freshest data available until 2025-2026 was imported and scored.)
    assert DEFAULT_SEASON == "2025-2026"
    assert SEASON_ORDER[0] == DEFAULT_SEASON


# --- DB-backed: scope_to_season / PlayerListView default behavior ---


def test_scope_to_season_filters_to_one_season():
    _make_player(season="2023-2024")
    latest = _make_player(season=DEFAULT_SEASON)

    result = scope_to_season(Player.objects.all())
    assert result.count() == 1
    assert result.first().id == latest.id


def test_player_list_defaults_to_latest_season(auth_client):
    same_name_latest = _make_player(player="Same Name", season=DEFAULT_SEASON)
    _make_player(player="Same Name", season="2022-2023")

    response = auth_client.get("/api/v1/players/")

    assert response.status_code == 200
    ids = {row["id"] for row in response.data["items"]}
    assert ids == {str(same_name_latest.id)}


def test_player_list_honors_explicit_season_override(auth_client):
    _make_player(player="Same Name", season=DEFAULT_SEASON)
    older = _make_player(player="Same Name", season="2022-2023")

    response = auth_client.get("/api/v1/players/?season=2022-2023")

    assert response.status_code == 200
    ids = {row["id"] for row in response.data["items"]}
    assert ids == {str(older.id)}


def test_ids_multi_fetch_bypasses_season_default(auth_client):
    # ?ids= is documented as fetching an EXACT set of rows by primary key --
    # forcing the season default on top would silently drop a requested id
    # that isn't in the default season (players/filters.py).
    older = _make_player(player="Old Season Player", season="2022-2023")

    response = auth_client.get(f"/api/v1/players/?ids={older.id}")

    assert response.status_code == 200
    ids = {row["id"] for row in response.data}
    assert ids == {str(older.id)}


# ---------------------------------------------------------------------------
# 2025-2026: selectable, but NOT the default, NOT scored, per-row league.
# ---------------------------------------------------------------------------


def test_2025_2026_is_the_default_season():
    assert DEFAULT_SEASON == "2025-2026"
    assert resolve_season(None) == "2025-2026"
    assert resolve_season("") == "2025-2026"
    assert resolve_season("not-a-season") == "2025-2026"


def test_2025_2026_is_listed_first_and_last_calendar_year_stays_selectable():
    assert SEASON_ORDER[:2] == ["2025-2026", "Last Calendar Year"]
    assert resolve_season("Last Calendar Year") == "Last Calendar Year"


def test_list_defaults_to_2025_2026_and_an_older_season_can_be_requested(auth_client):
    default_row = _make_player(season=DEFAULT_SEASON)
    older_row = _make_player(season="Last Calendar Year")

    default_ids = {r["id"] for r in auth_client.get("/api/v1/players/?page_size=100").data["items"]}
    older_ids = {
        r["id"]
        for r in auth_client.get("/api/v1/players/?season=Last Calendar Year&page_size=100").data["items"]
    }

    assert str(default_row.id) in default_ids and str(older_row.id) not in default_ids
    assert str(older_row.id) in older_ids and str(default_row.id) not in older_ids
