"""Tests for the UNSCORED_SEASONS mechanism (players/season.py).

Currently NO season is held out (2025-2026 is scored), but the mechanism stays
for the next season that is imported before it is scored: such a season's
players exist and are browsable, yet are held out of the scoring population.
Every scoring service raises Http404 for a player it can't find in that
population -- a misleading "player not found" for a player that plainly
exists, and only after a slow cold scoring pass. So the three per-player
endpoints must answer for these players WITHOUT ever reaching a scoring
service, and the scoring population itself must not include them (or every
existing player's percentile-ranked score would move).

The tests mark a stand-in season as held out for their duration.
"""

from __future__ import annotations

import itertools

import pytest
from rest_framework.test import APIClient

from clubs.models import Club
from players.models import Player
from players.season import DEFAULT_SEASON, UNSCORED_SEASONS
from scoring.characterization.reconstruct import build_players_df

pytestmark = pytest.mark.django_db

HELD_OUT = "2031-2032"  # a stand-in for "the next season, imported but not yet scored"

_unique_id_seq = itertools.count(1_500_000_001)


@pytest.fixture(autouse=True)
def _hold_out_the_stand_in_season(monkeypatch):
    held_out = frozenset({HELD_OUT})
    monkeypatch.setattr("players.views.UNSCORED_SEASONS", held_out)
    monkeypatch.setattr("players.season.UNSCORED_SEASONS", held_out)


@pytest.fixture
def auth_client():
    from accounts.models import User

    user = User.objects.create_user(email="unscored-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def unscored_player(db):
    club = Club.objects.create(name="Some FC", league="Premier League (England)")
    return Player.objects.create(
        unique_id=next(_unique_id_seq), player="New Season Player", season=HELD_OUT,
        club=club, position="CB", age=24, league="Premier League (England)",
    )


@pytest.fixture
def scoring_must_not_run(monkeypatch):
    """Fail loudly if any scoring service is reached."""

    def _boom(*args, **kwargs):
        raise AssertionError("a scoring service was called for an unscored-season player")

    monkeypatch.setattr("players.views.summary.get_summary", _boom)
    monkeypatch.setattr("players.views.rmm.get_rmm", _boom)
    monkeypatch.setattr("players.views.rank_clubs_for_player", _boom)
    monkeypatch.setattr("players.views.services.generate_scouting_report", _boom)


def test_no_season_is_held_out_in_production_config():
    # The fixture patches the module-level names; this asserts the REAL value.
    assert UNSCORED_SEASONS == frozenset()
    assert DEFAULT_SEASON not in UNSCORED_SEASONS


def test_detail_returns_profile_with_null_scores_and_a_reason(
    auth_client, unscored_player, scoring_must_not_run
):
    response = auth_client.get(f"/api/v1/players/{unscored_player.id}/")

    assert response.status_code == 200
    body = response.data
    assert body["player"] == "New Season Player"
    assert body["season"] == HELD_OUT
    assert body["scores"] == {
        "rmm": {"rmm": None, "reason": "season_not_scored"},
        "compatibility": {"compatibility_score": None, "reason": "season_not_scored"},
        "financial_fit": {"financial_fit": None, "reason": "season_not_scored"},
        "transfer_probability": {"transfer_probability": None, "reason": "season_not_scored"},
    }


def test_detail_scores_keep_the_same_keys_as_a_scored_player(auth_client, unscored_player):
    # The frontend reads these four keys for every player -- the unscored
    # shape must not drop or rename any.
    response = auth_client.get(f"/api/v1/players/{unscored_player.id}/")
    assert set(response.data["scores"]) == {
        "rmm", "compatibility", "financial_fit", "transfer_probability",
    }


def test_scouting_report_is_a_clear_400_not_a_404(auth_client, unscored_player, scoring_must_not_run):
    response = auth_client.post(
        f"/api/v1/players/{unscored_player.id}/scouting-report/", {}, format="json"
    )

    assert response.status_code == 400
    assert HELD_OUT in str(response.data)


def test_club_matches_returns_empty_results_with_a_reason(
    auth_client, unscored_player, scoring_must_not_run
):
    response = auth_client.get(f"/api/v1/players/{unscored_player.id}/club-matches/")

    assert response.status_code == 200
    assert response.data == {
        "player_id": str(unscored_player.id),
        "results": [],
        "reason": "season_not_scored",
    }


def test_unknown_player_is_still_a_404(auth_client):
    response = auth_client.get("/api/v1/players/00000000-0000-0000-0000-000000000000/")
    assert response.status_code == 404


def test_scoring_population_excludes_unscored_seasons_but_keeps_null_season_rows():
    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    scored = Player.objects.create(
        unique_id=next(_unique_id_seq), player="Scored", season="2024-2025", club=club
    )
    held_out = Player.objects.create(
        unique_id=next(_unique_id_seq), player="Held Out", season=HELD_OUT, club=club
    )
    # NULL-season rows must NOT be silently dropped by the exclusion.
    null_season = Player.objects.create(
        unique_id=next(_unique_id_seq), player="No Season", season=None, club=club
    )

    legacy_ids = set(build_players_df()["player_id"].astype(str))

    assert str(scored.id) in legacy_ids
    assert str(null_season.id) in legacy_ids
    assert str(held_out.id) not in legacy_ids
