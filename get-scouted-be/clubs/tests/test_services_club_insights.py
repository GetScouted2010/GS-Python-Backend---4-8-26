"""Tests for clubs/services.py (10-04-PLAN.md, AI-04).

Covers `position_needs_aggregate` (a bounded, single-club ORM group-by --
NEVER pandas / never a full-dataset op) and `generate_club_insights`
(combines it with reused transfer aggregates and generates via the
cross-app `players.ai.report_factory.get_report_generator()`).

Runs under clubs/tests/conftest.py's ported autouse
`_block_real_anthropic_calls` guard (10-04 Task 1) -- every test here
patches the CALLER's own binding `clubs.services.get_report_generator`,
matching test_scouting_report_view.py's established convention, so no test
ever needs a real client."""

from __future__ import annotations

import datetime
from unittest.mock import MagicMock

import pytest

from clubs import services
from clubs.models import Club
from players.ai.report_generator import GeneratedReport, ReportGeneratorError
from players.models import Player
from players.season import DEFAULT_SEASON

pytestmark = pytest.mark.django_db

FAKE_NARRATIVE = {
    "recruitment_gaps": "The squad is thin at centre-back with only 2 fit options.",
    "over_aged_positions": "The forward line averages 31.4 years, a succession risk.",
    "financial_constraints": "Historic spend has averaged 4.2M per window.",
}


def _fake_generator(return_value=None, side_effect=None):
    generator = MagicMock()
    if side_effect is not None:
        generator.generate.side_effect = side_effect
    else:
        generator.generate.return_value = return_value
    return MagicMock(return_value=generator)


def _make_club(name="Test United"):
    return Club.objects.create(name=name, league="Test League")


def _make_player(club, unique_id, position, age, contract_expires=None):
    return Player.objects.create(
        unique_id=unique_id,
        player=f"Player {unique_id}",
        club=club,
        position=position,
        age=age,
        contract_expires=contract_expires,
        season=DEFAULT_SEASON,
    )


# ---------------------------------------------------------------------------
# position_needs_aggregate -- aggregation shape
# ---------------------------------------------------------------------------
def test_position_needs_aggregate_shape():
    club = _make_club()
    today = datetime.date.today()
    soon = today + datetime.timedelta(days=100)  # within 12mo
    far = today + datetime.timedelta(days=800)  # NOT within 12mo

    _make_player(club, 1, "CB", 24, contract_expires=soon)
    _make_player(club, 2, "CB", 30, contract_expires=far)
    _make_player(club, 3, "CB", 26, contract_expires=None)
    _make_player(club, 4, "ST", 22, contract_expires=soon)
    _make_player(club, 5, "ST", 28, contract_expires=far)

    result = services.position_needs_aggregate(club)

    assert set(result.keys()) == {"CB", "ST"}

    cb = result["CB"]
    assert cb["squad_depth"] == 3
    assert cb["avg_age"] == round((24 + 30 + 26) / 3, 1)
    assert cb["contracts_expiring_within_12mo"] == 1

    st = result["ST"]
    assert st["squad_depth"] == 2
    assert st["avg_age"] == round((22 + 28) / 2, 1)
    assert st["contracts_expiring_within_12mo"] == 1


# ---------------------------------------------------------------------------
# position_needs_aggregate -- bounded / single-club scope
# ---------------------------------------------------------------------------
def test_position_needs_aggregate_scoped_to_single_club():
    club_a = _make_club("Club A")
    club_b = _make_club("Club B")

    _make_player(club_a, 10, "CB", 25)
    _make_player(club_b, 11, "CB", 27)  # different club -- must NOT be counted

    result = services.position_needs_aggregate(club_a)

    assert result["CB"]["squad_depth"] == 1
    assert result["CB"]["avg_age"] == 25.0


# ---------------------------------------------------------------------------
# position_needs_aggregate -- contract null-safety
# ---------------------------------------------------------------------------
def test_position_needs_aggregate_null_contract_not_counted_as_expiring():
    club = _make_club()
    _make_player(club, 20, "GK", 29, contract_expires=None)

    result = services.position_needs_aggregate(club)

    assert result["GK"]["squad_depth"] == 1
    assert result["GK"]["contracts_expiring_within_12mo"] == 0


def test_position_needs_aggregate_cutoff_boundary_inclusive():
    club = _make_club()
    cutoff = datetime.date.today() + datetime.timedelta(days=365)
    _make_player(club, 21, "LB", 24, contract_expires=cutoff)  # exactly at cutoff -> counted (<=)
    _make_player(club, 22, "LB", 26, contract_expires=cutoff + datetime.timedelta(days=1))  # past -> not counted

    result = services.position_needs_aggregate(club)

    assert result["LB"]["squad_depth"] == 2
    assert result["LB"]["contracts_expiring_within_12mo"] == 1


# ---------------------------------------------------------------------------
# generate_club_insights -- happy path
# ---------------------------------------------------------------------------
def test_generate_club_insights_happy_path(monkeypatch):
    club = _make_club()
    _make_player(club, 30, "CB", 25)

    fake_grounding = {"position_needs": {}, "transfer_aggregates": {}}
    fake_report = GeneratedReport(narrative=dict(FAKE_NARRATIVE), grounding=fake_grounding)
    monkeypatch.setattr("clubs.services.get_report_generator", _fake_generator(return_value=fake_report))

    result = services.generate_club_insights(club.id)

    assert set(result["narrative"].keys()) == {
        "recruitment_gaps",
        "over_aged_positions",
        "financial_constraints",
    }
    assert "position_needs" in result["grounding"]
    assert "transfer_aggregates" in result["grounding"]


# ---------------------------------------------------------------------------
# generate_club_insights -- generation failure propagates (never swallowed)
# ---------------------------------------------------------------------------
def test_generate_club_insights_propagates_generator_error(monkeypatch):
    club = _make_club()

    monkeypatch.setattr(
        "clubs.services.get_report_generator",
        _fake_generator(side_effect=ReportGeneratorError("provider failed")),
    )

    with pytest.raises(ReportGeneratorError):
        services.generate_club_insights(club.id)
