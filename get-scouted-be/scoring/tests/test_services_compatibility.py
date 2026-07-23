"""Tests for scoring.services.compatibility (04-03-PLAN.md).

`get_compatibility(player_id, club_id)` is the request-facing wrapper for
SCORE-02 (CS via API) + its slice of SCORE-05 (full breakdown): the real
`compatibility_score` from `compute_cs_tp_for_pairs` (via `score_population`)
plus a role_fit_score/similarity_pct/bonus breakdown that RECONSTRUCTS it.

The regression this plan exists to guard: `compute_cs_tp_for_pairs`
internally merges `players_df` with `role_scores_wide`
(deterministic_scores.py:354) BEFORE computing role fit -- a `player_row`
sliced straight from `players_df` (no role-score columns) makes
`get_player_own_best_role` always return `(None, np.nan)` and
`normalize_role_vector_from_row` empty, so `role_fit_score`/`bonus` would
silently contradict the real `compatibility_score`. `get_compatibility` must
replicate that exact merge before slicing the row the breakdown reads.

`real_data_available` lets the DB-backed tests skip cleanly against an
empty dev DB (see scoring/tests/conftest.py).
"""

from __future__ import annotations

import uuid

import numpy as np
import pandas as pd
import pytest
from django.http import Http404

from scoring.characterization.role_fit import STYLE_COLUMNS
from scoring.services.compatibility import cs_breakdown_from_row, get_compatibility


def _cf_player_row(**role_scores):
    base = {
        "Main_Position": "CF",
        "Position": "CF",
    }
    base.update(role_scores)
    return pd.Series(base)


def _team_style_row(team_name, **styles):
    base = {
        "Team": team_name,
        "Control Possession": 0.0,
        "Gegenpressing": 0.0,
        "Direct Play": 0.0,
        "Defensive Counter Attack": 0.0,
        "Tiki Taka": 0.0,
        "Counter Attack": 0.0,
        "Wing Play": 0.0,
        "Low Block": 0.0,
    }
    base.update(styles)
    return pd.Series(base)


# =========================================================================
# cs_breakdown_from_row -- synthetic, no DB
# =========================================================================
def test_cs_breakdown_from_row_null_envelope_when_compatibility_score_nan():
    cs_tp_row = pd.Series({"compatibility_score": np.nan})
    player_row = _cf_player_row()
    team_styles_df = pd.DataFrame([_team_style_row("Any FC")])

    result = cs_breakdown_from_row(cs_tp_row, player_row, "Any FC", team_styles_df)

    assert result == {"compatibility_score": None, "reason": "club_style_data_unavailable"}


def test_cs_breakdown_from_row_reads_role_columns_off_merged_row():
    """The regression guard at the helper level: given a player_row that DOES
    carry role-score columns (the merge already happened upstream, as
    get_compatibility is responsible for), the breakdown's role_fit_score is
    numeric and bonus is a real 100.0/70.0 -- not the all-None/70.0
    degenerate output an un-merged row would produce."""
    player_row = _cf_player_row(**{"Poacher": 90.0})
    team_styles_df = pd.DataFrame(
        [_team_style_row("Test FC", **{"Direct Play": 80.0, "Counter Attack": 90.0, "Wing Play": 40.0})]
    )
    cs_tp_row = pd.Series({"compatibility_score": 85.0})

    result = cs_breakdown_from_row(cs_tp_row, player_row, "Test FC", team_styles_df)

    assert result["compatibility_score"] == 85.0
    assert result["components"]["role_fit_score"] is not None
    assert isinstance(result["components"]["role_fit_score"], float)
    assert result["components"]["similarity_pct"] is None
    assert result["components"]["bonus"] in (70.0, 100.0)


def test_cs_breakdown_from_row_similarity_pct_always_none():
    player_row = _cf_player_row(**{"Poacher": 90.0})
    team_styles_df = pd.DataFrame([_team_style_row("Test FC", **{"Counter Attack": 90.0})])
    cs_tp_row = pd.Series({"compatibility_score": 70.0})

    result = cs_breakdown_from_row(cs_tp_row, player_row, "Test FC", team_styles_df)

    assert result["components"]["similarity_pct"] is None


# =========================================================================
# get_compatibility -- real DB data
# =========================================================================
@pytest.mark.django_db
def test_get_compatibility_returns_valid_envelope_or_breakdown_shape(real_data_available):
    from clubs.models import Club
    from players.models import Player

    player = Player.objects.first()
    club = Club.objects.first()

    result = get_compatibility(player.id, club.id)

    is_breakdown = (
        isinstance(result.get("compatibility_score"), (int, float))
        and "components" in result
        and set(result["components"]) == {"role_fit_score", "similarity_pct", "bonus"}
    )
    is_null_envelope = result == {"compatibility_score": None, "reason": "club_style_data_unavailable"}

    assert is_breakdown or is_null_envelope


@pytest.mark.django_db
def test_get_compatibility_consistency_reconstructs_score(real_data_available):
    """The regression this plan exists to guard: when get_compatibility
    returns a real compatibility_score, the breakdown's role_fit_score/bonus
    RECONSTRUCT it -- proving player_row carried the role-score columns
    (this fails hard if the merge were dropped: role_fit_score would be
    None / bonus stuck at 70.0 while compatibility_score stayed real)."""
    from clubs.models import Club
    from scoring.services.population import reconstruct_population, score_population

    pop = reconstruct_population()

    usable_clubs = pop.team_styles_df[pop.team_styles_df[STYLE_COLUMNS].notna().any(axis=1)]
    assert not usable_clubs.empty, "expected at least one club with usable style data in real dev data"
    club_name = usable_clubs.iloc[0]["Team"]

    _, cs_tp = score_population(pop, club_name)
    valid = cs_tp[cs_tp["compatibility_score"].notna()]
    assert not valid.empty, f"expected at least one player with a resolvable CS against {club_name!r}"
    player_id = valid.index[0]

    club = Club.objects.get(name=club_name)

    result = get_compatibility(player_id, club.id)

    assert result["compatibility_score"] is not None
    role_fit_score = result["components"]["role_fit_score"]
    bonus = result["components"]["bonus"]
    assert result["components"]["similarity_pct"] is None
    assert role_fit_score is not None
    assert bonus in (70.0, 100.0)

    reconstructed = round((min(max(role_fit_score, 0.0), 100.0) + bonus) / 2, 2)
    assert reconstructed == pytest.approx(round(result["compatibility_score"], 2), abs=0.5)


@pytest.mark.django_db
def test_get_compatibility_null_envelope_for_styleless_club(real_data_available):
    from clubs.models import Club
    from scoring.services.population import reconstruct_population, score_population

    pop = reconstruct_population()

    styleless_clubs = pop.team_styles_df[pop.team_styles_df[STYLE_COLUMNS].isna().all(axis=1)]
    assert not styleless_clubs.empty, "expected at least one club with all-NaN style data in real dev data"
    club_name = styleless_clubs.iloc[0]["Team"]

    _, cs_tp = score_population(pop, club_name)
    assert cs_tp["compatibility_score"].isna().all()
    player_id = cs_tp.index[0]

    club = Club.objects.get(name=club_name)

    result = get_compatibility(player_id, club.id)

    assert result == {"compatibility_score": None, "reason": "club_style_data_unavailable"}


@pytest.mark.django_db
def test_get_compatibility_unknown_club_raises_http404(real_data_available):
    from players.models import Player

    player = Player.objects.first()

    with pytest.raises(Http404):
        get_compatibility(player.id, uuid.uuid4())


@pytest.mark.django_db
def test_get_compatibility_unknown_player_raises_http404(real_data_available):
    from clubs.models import Club

    club = Club.objects.first()

    with pytest.raises(Http404):
        get_compatibility(uuid.uuid4(), club.id)
