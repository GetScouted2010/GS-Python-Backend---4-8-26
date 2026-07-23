"""Tests for scoring.services.transfer_probability (04-03-PLAN.md).

`get_transfer_probability(player_id, club_id)` is the request-facing wrapper
for SCORE-04 (TP via API) + its slice of SCORE-05: the real deterministic
Transfer Probability from `compute_cs_tp_for_pairs` (via `score_population`)
plus its 4 weighted terms (compatibility 0.30, performance 0.20,
financial 0.20, contract_fit 0.30), each with raw/weight/contribution.

`tp_breakdown_from_row` reads the already-computed columns off a cs_tp row
-- it never reimplements the tp math, only re-exposes the weighted terms for
explainability.

`real_data_available` lets the DB-backed test skip cleanly against an empty
dev DB (see scoring/tests/conftest.py).
"""

from __future__ import annotations

import uuid

import numpy as np
import pandas as pd
import pytest
from django.http import Http404

from scoring.characterization.role_fit import STYLE_COLUMNS
from scoring.services.transfer_probability import (
    WEIGHTS,
    get_transfer_probability,
    tp_breakdown_from_row,
)


def _cs_tp_row(**overrides):
    # compat=80, perf=70, fin=60, contract_fit=0.7 -> tp=71.0 (hand-computed,
    # matches test_deterministic_scores.test_transfer_probability_exact).
    base = {
        "compatibility_score": 80.0,
        "performance_score": 70.0,
        "financial_score": 60.0,
        "contract_fit": 0.7,
        "transfer_probability": 71.0,
    }
    base.update(overrides)
    return pd.Series(base)


def test_weights_are_the_locked_0_30_0_20_0_20_0_30_split():
    assert WEIGHTS == {"compatibility": 0.30, "performance": 0.20, "financial": 0.20, "contract_fit": 0.30}


def test_tp_breakdown_from_row_shape_and_contribution_math():
    row = _cs_tp_row()

    result = tp_breakdown_from_row(row)

    assert result["transfer_probability"] == pytest.approx(71.0, abs=1e-9)
    components = result["components"]
    assert set(components) == {"compatibility", "performance", "financial", "contract_fit"}

    for term, expected_raw, expected_weight in [
        ("compatibility", 80.0, 0.30),
        ("performance", 70.0, 0.20),
        ("financial", 60.0, 0.20),
        ("contract_fit", 70.0, 0.30),  # x100 for display parity with the 0-100 terms
    ]:
        assert components[term]["weight"] == expected_weight
        assert components[term]["raw"] == pytest.approx(expected_raw, abs=1e-6)
        assert components[term]["contribution"] == pytest.approx(
            round(expected_raw * expected_weight, 2), abs=1e-6
        )


def test_tp_breakdown_from_row_sum_of_contributions_reconstructs_transfer_probability():
    row = _cs_tp_row()

    result = tp_breakdown_from_row(row)

    total_contribution = sum(c["contribution"] for c in result["components"].values())
    assert total_contribution == pytest.approx(result["transfer_probability"], abs=0.5)


def test_tp_breakdown_from_row_nan_transfer_probability_returns_null_envelope():
    # NaN performance_score (e.g. from a NaN player_impact) propagates
    # through the deterministic tp formula to a NaN transfer_probability --
    # this is what tp_breakdown_from_row actually reads.
    row = _cs_tp_row(performance_score=np.nan, transfer_probability=np.nan)

    result = tp_breakdown_from_row(row)

    assert result["transfer_probability"] is None
    assert "reason" in result


@pytest.mark.django_db
def test_get_transfer_probability_returns_real_breakdown_for_real_player(real_data_available):
    from clubs.models import Club
    from scoring.services.population import reconstruct_population, score_population

    pop = reconstruct_population()

    usable_clubs = pop.team_styles_df[pop.team_styles_df[STYLE_COLUMNS].notna().any(axis=1)]
    assert not usable_clubs.empty, "expected at least one club with usable style data in real dev data"
    club_name = usable_clubs.iloc[0]["Team"]

    _, cs_tp = score_population(pop, club_name)
    valid = cs_tp[cs_tp["transfer_probability"].notna()]
    assert not valid.empty, f"expected at least one player with a resolvable TP against {club_name!r}"
    player_id = valid.index[0]

    club = Club.objects.get(name=club_name)

    result = get_transfer_probability(player_id, club.id)

    assert isinstance(result["transfer_probability"], float)
    for term, weight in [
        ("compatibility", 0.30),
        ("performance", 0.20),
        ("financial", 0.20),
        ("contract_fit", 0.30),
    ]:
        assert result["components"][term]["weight"] == weight


@pytest.mark.django_db
def test_get_transfer_probability_unknown_player_raises_http404(real_data_available):
    from clubs.models import Club

    club = Club.objects.first()

    with pytest.raises(Http404):
        get_transfer_probability(uuid.uuid4(), club.id)


@pytest.mark.django_db
def test_get_transfer_probability_unknown_club_raises_http404(real_data_available):
    from players.models import Player

    player = Player.objects.first()

    with pytest.raises(Http404):
        get_transfer_probability(player.id, uuid.uuid4())
