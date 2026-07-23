"""Tests for scoring.services.rmm (04-02-PLAN.md).

`get_rmm(player_id)` is the request-facing wrapper satisfying SCORE-01 (RMM
via API) and its slice of SCORE-05 (full breakdown): the score plus its
positive/negative totals, position-keyed components, and reliability --
sourced strictly from `add_player_impact`'s output columns (NEVER
`compute_rmm_column`, which discards the breakdown SCORE-05 needs).

`rmm_breakdown_from_scored(row)` is the reusable piece: given an
already-scored pandas row, build the same breakdown dict without
re-reconstructing the population -- Plan 05's summary endpoint reuses this
directly.

`real_data_available` lets the real-player test skip cleanly against an
empty dev DB (see scoring/tests/conftest.py).
"""

from __future__ import annotations

import uuid

import numpy as np
import pandas as pd
import pytest
from django.http import Http404

from scoring.services.rmm import get_rmm, rmm_breakdown_from_scored


@pytest.mark.django_db
def test_get_rmm_returns_real_breakdown_for_real_player(real_data_available):
    from scoring.characterization.impact import add_player_impact
    from scoring.characterization.reconstruct import build_players_df

    players_df = build_players_df()
    scored = add_player_impact(players_df.copy())

    # Pick a real player whose Player Impact actually computed (not NaN) so
    # the "happy path" breakdown shape is exercised end to end.
    scored_valid = scored[scored["Player Impact"].notna()]
    assert not scored_valid.empty, "expected at least one player with a computed RMM"
    player_id = scored_valid.iloc[0]["player_id"]

    result = get_rmm(player_id)

    assert isinstance(result["rmm"], float)
    assert 0 <= result["rmm"] <= 100
    assert "positive" in result
    assert "negative" in result
    assert isinstance(result["components"], dict)
    assert len(result["components"]) > 0
    assert "reliability" in result


@pytest.mark.django_db
def test_get_rmm_components_keys_unprefixed_and_numeric(real_data_available):
    from scoring.characterization.impact import add_player_impact
    from scoring.characterization.reconstruct import build_players_df

    players_df = build_players_df()
    scored = add_player_impact(players_df.copy())
    scored_valid = scored[scored["Player Impact"].notna()]
    assert not scored_valid.empty
    player_id = scored_valid.iloc[0]["player_id"]

    result = get_rmm(player_id)

    for key, value in result["components"].items():
        assert not key.startswith("Impact Comp - ")
        assert isinstance(value, (int, float))


@pytest.mark.django_db
def test_get_rmm_unknown_player_raises_http404(real_data_available):
    unknown_id = uuid.uuid4()

    with pytest.raises(Http404):
        get_rmm(unknown_id)


def test_rmm_breakdown_from_scored_nan_impact_returns_null_envelope():
    row = pd.Series(
        {
            "Player Impact": np.nan,
            "Player Impact Positive": np.nan,
            "Player Impact Negative": np.nan,
            "Impact Reliability": np.nan,
            "Impact Comp - defensive_actions": np.nan,
        }
    )

    result = rmm_breakdown_from_scored(row)

    assert result == {"rmm": None, "reason": "insufficient_player_data"}


def test_rmm_breakdown_from_scored_returns_breakdown_dict_shape():
    row = pd.Series(
        {
            "Player Impact": 72.5,
            "Player Impact Positive": 5.1,
            "Player Impact Negative": -1.2,
            # "Impact Reliability" is a categorical string
            # ("Very Low"/"Low"/"Medium"/"High"), never a number -- see
            # impact.py's `_reliability_flag`.
            "Impact Reliability": "High",
            "Impact Comp - defensive_actions": 3.4,
            "Impact Comp - duel_dominance": 2.2,
        }
    )

    result = rmm_breakdown_from_scored(row)

    assert result["rmm"] == 72.5
    assert result["positive"] == 5.1
    assert result["negative"] == -1.2
    assert result["reliability"] == "High"
    assert result["components"] == {
        "defensive_actions": 3.4,
        "duel_dominance": 2.2,
    }
