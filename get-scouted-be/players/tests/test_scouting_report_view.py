"""Tests for the player scouting-report slice (10-03-PLAN.md, AI-03).

Task 1 covers `players.services.generate_scouting_report` in isolation (a
fake generator + a mocked `get_summary`, no real DB / no real LLM call).
Task 2 adds `POST /api/v1/players/{id}/scouting-report/` endpoint integration
tests, including the clean-error-on-failure (503) and missing-club (400)
branches -- proving a `ReportGeneratorError` NEVER reaches the caller as a
fabricated/template report.

The autouse `_block_real_anthropic_calls` guard (players/tests/conftest.py)
blocks any real anthropic.Anthropic() construction; every test here patches
the CALLER's own import binding (`players.services.get_report_generator` /
`players.services.get_summary`), matching test_search_view.py's established
convention, so no test ever needs a real client or a real DB reconstruction.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest
from rest_framework.test import APIClient

from players import services
from players.ai.report_generator import GeneratedReport, ReportGeneratorError
from players.models import Player

pytestmark = pytest.mark.django_db

NARRATIVE_KEYS = {"strengths", "weaknesses", "tactical_fit", "financial_fit", "best_use_case"}

FAKE_NARRATIVE = {
    "strengths": "Strong in the air, wins 62% of aerial duels.",
    "weaknesses": "Limited left-foot passing range.",
    "tactical_fit": "Suits a possession-based back three.",
    "financial_fit": "Valued at 4.2M, within budget.",
    "best_use_case": "Best deployed as a ball-playing centre-back.",
}


def _fake_generator(return_value=None, side_effect=None):
    """Build a fake ReportGenerator instance whose .generate() either
    returns return_value or raises side_effect. get_report_generator() is
    patched to a callable returning this fake -- never a real provider."""
    generator = MagicMock()
    if side_effect is not None:
        generator.generate.side_effect = side_effect
    else:
        generator.generate.return_value = return_value
    return MagicMock(return_value=generator)


# ---------------------------------------------------------------------------
# Task 1: generate_scouting_report() service
# ---------------------------------------------------------------------------
def test_generate_scouting_report_happy_path(monkeypatch):
    grounding = {"rmm": {"score": 78.5}, "compatibility": {"score": 65.0}}
    fake_report = GeneratedReport(narrative=dict(FAKE_NARRATIVE), grounding=grounding)

    monkeypatch.setattr("players.services.get_summary", lambda pid, cid: grounding)
    monkeypatch.setattr("players.services.get_report_generator", _fake_generator(return_value=fake_report))

    result = services.generate_scouting_report("player-1", "club-1")

    assert set(result["narrative"].keys()) == NARRATIVE_KEYS
    assert result["grounding"] == grounding


def test_generate_scouting_report_propagates_generator_error(monkeypatch):
    grounding = {"rmm": {"score": 50.0}}

    monkeypatch.setattr("players.services.get_summary", lambda pid, cid: grounding)
    monkeypatch.setattr(
        "players.services.get_report_generator",
        _fake_generator(side_effect=ReportGeneratorError("provider failed")),
    )

    with pytest.raises(ReportGeneratorError):
        services.generate_scouting_report("player-1", "club-1")


def test_generate_scouting_report_passes_grounding_unchanged(monkeypatch):
    grounding = {"rmm": {"score": 91.2}, "financial_fit": {"score": 30.0}}
    captured = {}

    def fake_get_summary(pid, cid):
        assert pid == "player-1"
        assert cid == "club-1"
        return grounding

    def fake_generate(g, report_type):
        captured["grounding"] = g
        captured["report_type"] = report_type
        return GeneratedReport(narrative=dict(FAKE_NARRATIVE), grounding=g)

    generator = MagicMock()
    generator.generate.side_effect = fake_generate

    monkeypatch.setattr("players.services.get_summary", fake_get_summary)
    monkeypatch.setattr("players.services.get_report_generator", MagicMock(return_value=generator))

    services.generate_scouting_report("player-1", "club-1")

    assert captured["report_type"] == "player_scouting_report"
    assert captured["grounding"] is grounding


# ---------------------------------------------------------------------------
# Task 2: PlayerScoutingReportView endpoint
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="scouting-report-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_scouting_report_requires_authentication():
    client = APIClient()
    response = client.post(f"/api/v1/players/{uuid.uuid4()}/scouting-report/", {}, format="json")
    assert response.status_code in (401, 403)


def test_scouting_report_success(auth_client, monkeypatch):
    player = Player.objects.create(unique_id=999_999_101, player="Report Subject", position="CB")
    club_id = str(uuid.uuid4())
    grounding = {"rmm": {"score": 70.0}}
    fake_report = GeneratedReport(narrative=dict(FAKE_NARRATIVE), grounding=grounding)

    monkeypatch.setattr("players.services.get_summary", lambda pid, cid: grounding)
    monkeypatch.setattr("players.services.get_report_generator", _fake_generator(return_value=fake_report))

    response = auth_client.post(
        f"/api/v1/players/{player.id}/scouting-report/", {"club_id": club_id}, format="json"
    )

    assert response.status_code == 200
    assert set(response.data["narrative"].keys()) == NARRATIVE_KEYS
    assert response.data["grounding"] == grounding


def test_scouting_report_failure(auth_client, monkeypatch):
    player = Player.objects.create(unique_id=999_999_102, player="Report Failure Subject", position="CM")
    club_id = str(uuid.uuid4())

    monkeypatch.setattr("players.services.get_summary", lambda pid, cid: {"rmm": {"score": 50.0}})
    monkeypatch.setattr(
        "players.services.get_report_generator",
        _fake_generator(side_effect=ReportGeneratorError("provider failed")),
    )

    response = auth_client.post(
        f"/api/v1/players/{player.id}/scouting-report/", {"club_id": club_id}, format="json"
    )

    assert response.status_code == 503
    assert "narrative" not in response.data
    body_str = str(response.data)
    for section_text in FAKE_NARRATIVE.values():
        assert section_text not in body_str


def test_scouting_report_missing_club_returns_400(auth_client, monkeypatch):
    player = Player.objects.create(unique_id=999_999_103, player="No Club Subject", club=None, position="GK")

    mock_get_summary = MagicMock()
    mock_get_generator = MagicMock()
    monkeypatch.setattr("players.services.get_summary", mock_get_summary)
    monkeypatch.setattr("players.services.get_report_generator", mock_get_generator)

    response = auth_client.post(f"/api/v1/players/{player.id}/scouting-report/", {}, format="json")

    assert response.status_code == 400
    mock_get_summary.assert_not_called()
    mock_get_generator.assert_not_called()
