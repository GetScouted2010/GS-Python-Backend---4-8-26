"""Tests for scoring.services.summary (04-05-PLAN.md) -- the combined
Player Profile summary orchestrator: all four scores (RMM, Compatibility,
Financial Fit, Transfer Probability) + full breakdowns, in ONE response,
off a SINGLE `reconstruct_population()` + `score_population()` call.

The regression this plan exists to guard (the same bug class Plan 03's
`get_compatibility` fixes, replicated here verbatim): `cs_breakdown_from_row`
re-derives role_fit_score/bonus by reading the player's role-score columns
OFF `player_row` (`role in player_row.index`). `pop.players_df` alone
carries NO role-score columns -- a `player_row` sliced straight from it
would make the summary's compatibility breakdown's role_fit_score/bonus
silently disagree with the real `compatibility_score` `cs_tp` returns.
`get_summary` must merge `pop.players_df` with `pop.role_scores_wide`
(deterministic_scores.py:354's own internal merge pattern) BEFORE slicing
`player_row`, exactly like `get_compatibility` does.

And: the summary must reconstruct the population EXACTLY ONCE, never once
per sub-score -- `test_get_summary_reconstructs_population_exactly_once`
asserts `reconstruct_population`'s `call_count == 1`.

`real_data_available` lets the DB-backed tests skip cleanly against an
empty dev DB (see scoring/tests/conftest.py).

`reconstruct_population()`/`score_population()` over the whole real
41,708-player population is expensive (~1 min per distinct club, per
scoring/tests/test_services_financial_fit.py's own note) -- both are
memoized at module scope below (`_real_pop`/`_real_scored`, keyed by club
name) so this whole test module pays that cost AT MOST ONCE per distinct
club actually exercised, never once per test.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.http import Http404

from scoring.characterization.role_fit import STYLE_COLUMNS

# =========================================================================
# Synthetic (DB-independent) regression guard -- proves the two
# plan-checker-flagged properties even when the DB-backed tests below skip
# against an empty pytest-django test DB.
# =========================================================================
def test_get_summary_composes_four_helpers_from_single_reconstruction_synthetic():
    """Synthetic, DB-independent guard for the two things this plan exists
    to get right: (1) `get_summary` calls `reconstruct_population`/
    `score_population` exactly ONCE, never once per sub-score; (2) the
    `player_row` passed to `cs_breakdown_from_row` carries the role-score
    columns -- proving `pop.players_df` was merged with `pop.role_scores_wide`
    before slicing, not a bare `pop.players_df` row (this fails hard if the
    merge is ever dropped)."""
    import pandas as pd

    from scoring.services.population import Population

    players_df = pd.DataFrame(
        {
            "player_id": ["p1", "p2"],
            "Team": ["OwnClubP1", "OwnClubP2"],
            "Main_Position": ["CF", "CB"],
            "Position": ["CF", "CB"],
        }
    )
    role_scores_wide = pd.DataFrame({"player_id": ["p1", "p2"], "Poacher": [90.0, None]})
    pop = Population(
        players_df=players_df,
        role_scores_wide=role_scores_wide,
        team_styles_df=pd.DataFrame({"Team": ["OwnClubP1"]}),
        transfers_df=pd.DataFrame(),
    )

    scored = players_df[["player_id"]].copy()
    scored["Player Impact"] = [55.0, 42.0]

    cs_tp = pd.DataFrame(
        {
            "compatibility_score": [85.0, None],
            "financial_score": [60.0, None],
            "performance_score": [70.0, None],
            "contract_fit": [0.8, None],
            "role_pct": [80.0, None],
            "transfer_probability": [75.0, None],
        },
        index=pd.Index(["p1", "p2"], name="player_id"),
    )

    captured: dict = {}

    def _fake_cs_breakdown(cs_tp_row, player_row, club_name, team_styles_df):
        captured["player_row"] = player_row
        return {
            "compatibility_score": 85.0,
            "components": {"role_fit_score": 1.0, "similarity_pct": None, "bonus": 100.0},
        }

    with (
        patch("scoring.services.summary.group_for_player", return_value="legacy"),
        patch("scoring.services.summary.reconstruct_population", return_value=pop) as mock_reconstruct,
        patch("scoring.services.summary.score_population", return_value=(scored, cs_tp)) as mock_score,
        patch("scoring.services.summary.resolve_club_name", return_value="OwnClubP1"),
        # Plan 06-06 added an is_own_club(player_id, club_id) branch to get_summary,
        # which performs a real ORM lookup -- this test's player_id/club_id are
        # synthetic non-UUID strings ("p1"/"club-uuid"), so is_own_club must be
        # mocked (never hitting the DB). False routes through the arbitrary-club
        # path this test's other mocks (score_population/financial_fit_from_population)
        # already assume, matching the pre-06-06 test design exactly.
        patch("scoring.services.summary.is_own_club", return_value=False),
        patch("scoring.services.summary.cs_breakdown_from_row", side_effect=_fake_cs_breakdown),
        patch("scoring.services.summary.rmm_breakdown_from_scored", return_value={"rmm": 55.0}),
        patch(
            "scoring.services.summary.financial_fit_from_population",
            return_value={"predicted_fee": 1_000_000.0},
        ),
        patch(
            "scoring.services.summary.tp_breakdown_from_row",
            return_value={"transfer_probability": 75.0},
        ),
    ):
        from scoring.services.summary import get_summary

        result = get_summary("p1", "club-uuid")

    assert mock_reconstruct.call_count == 1
    assert mock_score.call_count == 1
    assert result == {
        "rmm": {"rmm": 55.0},
        "compatibility": {
            "compatibility_score": 85.0,
            "components": {"role_fit_score": 1.0, "similarity_pct": None, "bonus": 100.0},
        },
        "financial_fit": {"predicted_fee": 1_000_000.0},
        "transfer_probability": {"transfer_probability": 75.0},
    }

    # The regression guard: player_row passed to cs_breakdown_from_row must
    # carry the role-score column ("Poacher") -- proving the
    # players_df/role_scores_wide merge happened before slicing, not a bare
    # pop.players_df row.
    assert "Poacher" in captured["player_row"].index
    assert captured["player_row"]["Poacher"] == 90.0


# =========================================================================
# Real-data caches (module scope)
# =========================================================================
_REAL_POP_CACHE: dict = {}
_REAL_SCORE_CACHE: dict = {}


def _real_pop():
    if "pop" not in _REAL_POP_CACHE:
        from scoring.services.population import reconstruct_population

        _REAL_POP_CACHE["pop"] = reconstruct_population()
    return _REAL_POP_CACHE["pop"]


def _real_scored(club_name):
    if club_name not in _REAL_SCORE_CACHE:
        from scoring.services.population import score_population

        _REAL_SCORE_CACHE[club_name] = score_population(_real_pop(), club_name)
    return _REAL_SCORE_CACHE[club_name]


def _cached_summary(player_id, club):
    """Call the real `get_summary` for `(player_id, club)` with
    `reconstruct_population`/`score_population` patched to the module-level
    cache -- exercises the real composition/merge/breakdown logic without
    repaying the reconstruction or RMM/CS-TP scoring cost per test."""
    from scoring.services.summary import get_summary

    pop = _real_pop()
    scored, cs_tp = _real_scored(club.name)
    with (
        patch("scoring.services.summary.reconstruct_population", return_value=pop),
        patch("scoring.services.summary.score_population", return_value=(scored, cs_tp)),
    ):
        return get_summary(player_id, club.id)


# =========================================================================
# get_summary -- real DB data
# =========================================================================
@pytest.mark.django_db
def test_get_summary_returns_four_score_keys_and_rich_subscore_shapes(real_data_available):
    """Combined shape test: top-level keys are always exactly the 4 scores;
    each present sub-score carries its documented breakdown fields.
    Searches a small handful of player/club pairs (cached via
    `_cached_summary`) for one that produces a fully priced financial_fit --
    the money-scale regression guard (Plan 04's confirmed log-scale bug)
    only bites when a fee is actually present."""
    from clubs.models import Club
    from players.models import Player

    players = list(Player.objects.all()[:5])
    clubs = list(Club.objects.all()[:3])
    assert players and clubs, "expected real migrated Player/Club data"

    result = None
    for player in players:
        for club in clubs:
            candidate = _cached_summary(player.id, club)
            assert set(candidate.keys()) == {"rmm", "compatibility", "financial_fit", "transfer_probability"}
            for key in candidate:
                assert isinstance(candidate[key], dict)
            if result is None:
                result = candidate
            if candidate["financial_fit"].get("predicted_fee") is not None:
                result = candidate
                break
        if result is not None and result["financial_fit"].get("predicted_fee") is not None:
            break

    assert result is not None

    if result["rmm"].get("rmm") is not None:
        assert "components" in result["rmm"]
        assert isinstance(result["rmm"]["components"], dict)
    else:
        assert result["rmm"]["reason"]

    if result["compatibility"].get("compatibility_score") is not None:
        assert set(result["compatibility"]["components"]) == {"role_fit_score", "similarity_pct", "bonus"}
    else:
        assert result["compatibility"]["reason"]

    fee = result["financial_fit"].get("predicted_fee")
    if fee is not None:
        assert fee > 1000, f"predicted_fee={fee} looks log-scale, not money-scale"
        assert "value_verdict" in result["financial_fit"]
    else:
        assert result["financial_fit"]["reason"]

    if result["transfer_probability"].get("transfer_probability") is not None:
        assert set(result["transfer_probability"]["components"]) == {
            "compatibility",
            "performance",
            "financial",
            "contract_fit",
        }
    else:
        assert result["transfer_probability"]["reason"]


@pytest.mark.django_db
def test_get_summary_compatibility_consistency_reconstructs_score(real_data_available):
    """The regression this plan exists to guard (Plan 03's fix, replicated
    here): when the summary's `compatibility_score` is non-null, its
    `role_fit_score` is numeric (NOT None) and
    `round((clip(role_fit_score,0,100)+bonus)/2,2) == round(compatibility_score,2)`
    (+/-0.5) -- proving `get_summary` sliced a role-aware `player_row`
    (players_df merged with role_scores_wide), never a bare
    `pop.players_df` row."""
    from clubs.models import Club

    pop = _real_pop()
    usable_clubs = pop.team_styles_df[pop.team_styles_df[STYLE_COLUMNS].notna().any(axis=1)]
    assert not usable_clubs.empty, "expected at least one club with usable style data in real dev data"
    club_name = usable_clubs.iloc[0]["Team"]

    _, cs_tp = _real_scored(club_name)
    valid = cs_tp[cs_tp["compatibility_score"].notna()]
    assert not valid.empty, f"expected at least one player with a resolvable CS against {club_name!r}"
    player_id = valid.index[0]

    club = Club.objects.get(name=club_name)
    result = _cached_summary(player_id, club)

    compat = result["compatibility"]
    assert compat["compatibility_score"] is not None
    role_fit_score = compat["components"]["role_fit_score"]
    bonus = compat["components"]["bonus"]
    assert compat["components"]["similarity_pct"] is None
    assert role_fit_score is not None
    assert bonus in (70.0, 100.0)

    reconstructed = round((min(max(role_fit_score, 0.0), 100.0) + bonus) / 2, 2)
    assert reconstructed == pytest.approx(round(compat["compatibility_score"], 2), abs=0.5)


@pytest.mark.django_db
def test_get_summary_reconstructs_population_exactly_once(real_data_available):
    """`get_summary` must reconstruct the population and run
    `score_population` exactly ONCE per call -- never once per sub-score
    (RMM/CS/financial/TP), which would be 4x the reconstruction cost of the
    per-score endpoints combined."""
    from clubs.models import Club
    from players.models import Player
    from scoring.services.summary import get_summary

    player = Player.objects.first()
    club = Club.objects.first()

    pop = _real_pop()
    scored, cs_tp = _real_scored(club.name)

    with (
        patch("scoring.services.summary.reconstruct_population", return_value=pop) as mock_reconstruct,
        patch("scoring.services.summary.score_population", return_value=(scored, cs_tp)) as mock_score,
    ):
        get_summary(player.id, club.id)

    assert mock_reconstruct.call_count == 1
    assert mock_score.call_count == 1


@pytest.mark.django_db
def test_get_summary_missing_subscore_does_not_raise_others_still_present(real_data_available):
    """A styleless club (no usable playing-style data) nulls out
    `compatibility_score` -- but the whole summary must not raise, and RMM
    (club-independent) must still return a real value for a player with a
    real Player Impact."""
    from clubs.models import Club

    pop = _real_pop()
    styleless_clubs = pop.team_styles_df[pop.team_styles_df[STYLE_COLUMNS].isna().all(axis=1)]
    assert not styleless_clubs.empty, "expected at least one club with all-NaN style data in real dev data"
    club_name = styleless_clubs.iloc[0]["Team"]

    scored, _ = _real_scored(club_name)
    scored_with_impact = scored[scored["Player Impact"].notna()]
    assert not scored_with_impact.empty, "expected at least one player with a real Player Impact value"
    player_id = scored_with_impact.iloc[0]["player_id"]

    club = Club.objects.get(name=club_name)

    result = _cached_summary(player_id, club)

    assert result["compatibility"] == {"compatibility_score": None, "reason": "club_style_data_unavailable"}
    assert result["rmm"]["rmm"] is not None
    assert "components" in result["rmm"]


@pytest.mark.django_db
def test_get_summary_unknown_club_raises_http404(real_data_available):
    from players.models import Player
    from scoring.services.summary import get_summary

    player = Player.objects.first()
    with pytest.raises(Http404):
        get_summary(player.id, uuid.uuid4())


@pytest.mark.django_db
def test_get_summary_unknown_player_raises_http404(real_data_available):
    from clubs.models import Club
    from scoring.services.summary import get_summary

    club = Club.objects.first()
    with pytest.raises(Http404):
        get_summary(uuid.uuid4(), club.id)
