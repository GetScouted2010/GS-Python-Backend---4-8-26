"""DRF APIClient integration tests for players/views.py::PlayerSearchView
(09-04-PLAN.md) -- covers POST /api/players/search/'s 3-tier degradation
(AI-01/AI-02), the RecentActivity "searched" logging contract completed
from Phase 8, and the auth gate.

`real_data_available` (players/tests/conftest.py) lets the real-data tests
skip cleanly against an empty pytest test DB. The autouse
`_block_real_anthropic_calls` guard (same conftest) blocks any real
anthropic.Anthropic() construction -- every test here patches the CALLER's
own binding `players.views.get_nl_query_parser` (09-RESEARCH.md Pitfall 2 /
STATE.md Phase 6-07 lesson: patch the caller's import binding, never the
definition module), so no test ever needs the real client at all.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from rest_framework.test import APIClient

from players.ai.base import NLQueryParserError, ParsedQuery
from players.models import Player
from workspace.models import RecentActivity

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Auth fixture -- mirrors players/tests/test_views.py::auth_client verbatim.
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="search-view-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _fake_parser(return_value=None, side_effect=None):
    """Build a fake NLQueryParser instance whose .parse() either returns
    return_value or raises side_effect. get_nl_query_parser() is patched to
    return a MagicMock() that returns this fake object -- never a real
    provider client."""
    parser = MagicMock()
    if side_effect is not None:
        parser.parse.side_effect = side_effect
    else:
        parser.parse.return_value = return_value
    return MagicMock(return_value=parser)


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------
def test_search_requires_authentication():
    client = APIClient()
    response = client.post("/api/players/search/", {"query": "x"})
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Tier 1: successful LLM parse
# ---------------------------------------------------------------------------
def test_search_success_returns_filters_and_results(real_data_available, auth_client, monkeypatch):
    monkeypatch.setattr(
        "players.views.get_nl_query_parser",
        _fake_parser(return_value=ParsedQuery(filters={"position": "CB"}, raw_query="central defenders")),
    )

    response = auth_client.post("/api/players/search/", {"query": "central defenders"}, format="json")

    assert response.status_code == 200
    assert response.data["fallback_used"] is False
    assert response.data["parsed_filters"] == {"position": "CB"}
    assert {"results", "count"}.issubset(response.data["results"])
    results = response.data["results"]["results"]
    assert results
    assert all(row["position"] == "CB" for row in results)


# ---------------------------------------------------------------------------
# Tier 2: LLM failure -> deterministic keyword fallback
# ---------------------------------------------------------------------------
def test_search_llm_failure_falls_back_to_keyword(real_data_available, auth_client, monkeypatch):
    monkeypatch.setattr(
        "players.views.get_nl_query_parser",
        _fake_parser(side_effect=NLQueryParserError("provider unavailable")),
    )

    response = auth_client.post("/api/players/search/", {"query": "strikers under €5M"}, format="json")

    assert response.status_code == 200
    assert response.data["fallback_used"] is True
    parsed_filters = response.data["parsed_filters"]
    assert parsed_filters.get("market_value_max") == 5_000_000 or parsed_filters.get("position") == "FWD"


# ---------------------------------------------------------------------------
# Tier 3: LLM failure AND keyword extractor yields nothing -> unfiltered list
# ---------------------------------------------------------------------------
def test_search_tier3_fallback_unfiltered_when_nothing_extractable(real_data_available, auth_client, monkeypatch):
    monkeypatch.setattr(
        "players.views.get_nl_query_parser",
        _fake_parser(side_effect=NLQueryParserError("provider unavailable")),
    )

    response = auth_client.post("/api/players/search/", {"query": "asdfghjkl"}, format="json")

    assert response.status_code == 200
    assert response.data["parsed_filters"] == {}
    assert response.data["fallback_used"] is True
    assert response.data["results"]["count"] == Player.objects.count()


# ---------------------------------------------------------------------------
# RecentActivity logging -- exactly one "searched" row per call
# ---------------------------------------------------------------------------
def test_search_logs_recent_activity(real_data_available, auth_client, monkeypatch):
    monkeypatch.setattr(
        "players.views.get_nl_query_parser",
        _fake_parser(return_value=ParsedQuery(filters={"position": "CB"}, raw_query="central defenders")),
    )

    response = auth_client.post("/api/players/search/", {"query": "central defenders"}, format="json")
    assert response.status_code == 200

    activities = RecentActivity.objects.filter(activity_type="searched")
    assert activities.count() == 1
    activity = activities.first()
    assert activity.query_text == "central defenders"
    assert activity.target_id is None


# ---------------------------------------------------------------------------
# Blank query never errors -- flows straight to tier 3
# ---------------------------------------------------------------------------
def test_search_never_errors_on_blank_query(real_data_available, auth_client, monkeypatch):
    monkeypatch.setattr(
        "players.views.get_nl_query_parser",
        _fake_parser(side_effect=NLQueryParserError("provider unavailable")),
    )

    response = auth_client.post("/api/players/search/", {}, format="json")

    assert response.status_code == 200
    assert response.data["parsed_filters"] == {}
