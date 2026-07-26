"""Unit tests for clubs/services.py::classify_position_needs (PLAN-01,
11-01-PLAN.md).

classify_position_needs layers a strong/weak/at-risk classification onto
position_needs_aggregate's existing numbers (Phase 10's AI-04 aggregation).
It must NEVER recompute the underlying aggregation -- these tests assert
against the classification thresholds locked by 11-CONTEXT.md:
  - weak: squad_depth < 2
  - at-risk: depth >= 2 AND (avg_age > 30 OR expiring >= depth / 2)
  - strong: otherwise

Mirrors clubs/tests/test_services_club_insights.py's Club.objects.create /
Player.objects.create factory style."""

from __future__ import annotations

import datetime

import pytest

from clubs import services
from clubs.models import Club
from players.models import Player

pytestmark = pytest.mark.django_db


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
    )


# ---------------------------------------------------------------------------
# weak: squad_depth < 2, regardless of age/contract
# ---------------------------------------------------------------------------
def test_classify_weak_when_depth_below_2():
    club = _make_club()
    _make_player(club, 1, "GK", 22)

    result = services.classify_position_needs(club)

    gk = result["GK"]
    assert gk["classification"] == "weak"
    assert gk["squad_depth"] == 1
    assert gk["avg_age"] == 22.0
    assert gk["contracts_expiring_within_12mo"] == 0


# ---------------------------------------------------------------------------
# at-risk: depth >= 2, avg_age > 30
# ---------------------------------------------------------------------------
def test_classify_at_risk_by_age():
    club = _make_club()
    _make_player(club, 1, "CB", 31)
    _make_player(club, 2, "CB", 33)

    result = services.classify_position_needs(club)

    cb = result["CB"]
    assert cb["classification"] == "at-risk"
    assert cb["squad_depth"] == 2
    assert cb["avg_age"] == 32.0
    assert cb["contracts_expiring_within_12mo"] == 0


# ---------------------------------------------------------------------------
# at-risk: depth >= 2, avg_age <= 30, but >= depth/2 expiring contracts
# ---------------------------------------------------------------------------
def test_classify_at_risk_by_contract_expiry():
    club = _make_club()
    today = datetime.date.today()
    soon = today + datetime.timedelta(days=100)  # within 12mo
    far = today + datetime.timedelta(days=800)  # NOT within 12mo

    _make_player(club, 1, "ST", 24, contract_expires=soon)
    _make_player(club, 2, "ST", 26, contract_expires=far)

    result = services.classify_position_needs(club)

    st = result["ST"]
    assert st["classification"] == "at-risk"
    assert st["squad_depth"] == 2
    assert st["avg_age"] == 25.0
    assert st["contracts_expiring_within_12mo"] == 1


# ---------------------------------------------------------------------------
# strong: adequate depth, not aging, no mass expiry
# ---------------------------------------------------------------------------
def test_classify_strong():
    club = _make_club()
    today = datetime.date.today()
    far = today + datetime.timedelta(days=800)  # NOT within 12mo

    _make_player(club, 1, "LB", 24, contract_expires=far)
    _make_player(club, 2, "LB", 26, contract_expires=far)
    _make_player(club, 3, "LB", 25, contract_expires=far)

    result = services.classify_position_needs(club)

    lb = result["LB"]
    assert lb["classification"] == "strong"
    assert lb["squad_depth"] == 3
    assert lb["avg_age"] == 25.0
    assert lb["contracts_expiring_within_12mo"] == 0
