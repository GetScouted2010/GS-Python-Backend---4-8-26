"""DRF APIClient integration tests for clubs/views.py::ClubInsightsView
(10-04-PLAN.md, AI-04) -- covers POST /api/v1/clubs/{id}/insights/'s success
shape, the clean-error-on-failure (503, locked decision #6) branch, and the
natural 404 for an unknown club.

Runs under clubs/tests/conftest.py's ported autouse
`_block_real_anthropic_calls` guard (10-04 Task 1). Every test here patches
the CALLER's own binding `clubs.services.get_report_generator`, matching
test_scouting_report_view.py's established convention, so no test ever
needs a real client."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from rest_framework.test import APIClient

from clubs.models import Club
from players.ai.report_generator import GeneratedReport, ReportGeneratorError
from players.models import Player
from transfers.models import Transfer

pytestmark = pytest.mark.django_db

FAKE_NARRATIVE = {
    "recruitment_gaps": "The squad is thin at centre-back with only 2 fit options.",
    "over_aged_positions": "The forward line averages 31.4 years, a succession risk.",
    "financial_constraints": "Historic spend has averaged 4.2M per window.",
}


# ---------------------------------------------------------------------------
# Auth fixture -- mirrors clubs/tests/test_views.py::auth_client verbatim.
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="club-insights-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _fake_generator(return_value=None, side_effect=None):
    generator = MagicMock()
    if side_effect is not None:
        generator.generate.side_effect = side_effect
    else:
        generator.generate.return_value = return_value
    return MagicMock(return_value=generator)


def _make_club_with_squad_and_transfers(name):
    club = Club.objects.create(name=name, league="Test League")
    p1 = Player.objects.create(unique_id=hash(name) % 1_000_000 + 1, player="P1", club=club, position="CB", age=25)
    Player.objects.create(unique_id=hash(name) % 1_000_000 + 2, player="P2", club=club, position="ST", age=29)
    Transfer.objects.create(
        club=club,
        player=p1,
        player_name_raw="P1",
        dealing_club="Some Other Club",
        movement="arrival",
        window="summer",
        year=2025,
        market_value_at_transfer=3_000_000,
    )
    return club


# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------
def test_club_insights_success(auth_client, monkeypatch):
    club = _make_club_with_squad_and_transfers("Insights United")

    fake_report = GeneratedReport(
        narrative=dict(FAKE_NARRATIVE),
        grounding={"position_needs": {}, "transfer_aggregates": {}},
    )
    monkeypatch.setattr("clubs.services.get_report_generator", _fake_generator(return_value=fake_report))

    response = auth_client.post(f"/api/v1/clubs/{club.id}/insights/")

    assert response.status_code == 200
    assert set(response.data["narrative"].keys()) == {
        "recruitment_gaps",
        "over_aged_positions",
        "financial_constraints",
    }
    grounding = response.data["grounding"]
    assert "position_needs" in grounding
    assert "transfer_aggregates" in grounding


# ---------------------------------------------------------------------------
# Failure -- clean 503, never a fabricated narrative (locked decision #6)
# ---------------------------------------------------------------------------
def test_club_insights_failure(auth_client, monkeypatch):
    club = _make_club_with_squad_and_transfers("Failure United")

    monkeypatch.setattr(
        "clubs.services.get_report_generator",
        _fake_generator(side_effect=ReportGeneratorError("provider failed")),
    )

    response = auth_client.post(f"/api/v1/clubs/{club.id}/insights/")

    assert response.status_code == 503
    assert "narrative" not in response.data
    body_str = str(response.data)
    for section_text in FAKE_NARRATIVE.values():
        assert section_text not in body_str


# ---------------------------------------------------------------------------
# Unknown club -- natural 404
# ---------------------------------------------------------------------------
def test_club_insights_unknown_club_404(auth_client, monkeypatch):
    mock_get_generator = MagicMock()
    monkeypatch.setattr("clubs.services.get_report_generator", mock_get_generator)

    response = auth_client.post(f"/api/v1/clubs/{uuid.uuid4()}/insights/")

    assert response.status_code == 404
    mock_get_generator.assert_not_called()


# ---------------------------------------------------------------------------
# Authentication gate
# ---------------------------------------------------------------------------
def test_club_insights_requires_authentication():
    client = APIClient()
    response = client.post(f"/api/v1/clubs/{uuid.uuid4()}/insights/")
    assert response.status_code in (401, 403)
