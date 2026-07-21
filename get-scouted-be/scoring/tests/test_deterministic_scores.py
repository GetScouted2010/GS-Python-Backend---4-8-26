"""Tests for the CS / Transfer Probability characterization (03-05-PLAN.md).

Hand-computable synthetic fixtures only -- unlike test_reconstruct.py, these
functions are pure and don't need real migrated data, so no `real_data_available`
/ `django_db` marker is required (role_fit.py imports ROLE_COLUMNS_BY_POSITION
from reconstruct.py at module level, which imports Django models -- that's
fine without DB access since we never query them here).
"""

import numpy as np
import pandas as pd
import pytest

from scoring.characterization.role_fit import (
    ROLE_COLUMNS_BY_POSITION,
    calculate_subjective_role_fit_for_player_to_team,
    compatibility_score,
    get_player_own_best_role,
)


def _cb_player_row(**role_scores):
    role_cols = ROLE_COLUMNS_BY_POSITION["CB"]
    base = {r: 0.0 for r in role_cols}
    base.update(role_scores)
    base["Main_Position"] = "CB"
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
# Task 1: role-fit port
# =========================================================================
def test_calculate_subjective_role_fit_hand_computable():
    """A CB player with a single scored role, against a club whose playing
    style is a pure one-hot vector, has a hand-computable Role Fit Score.

    Player role vector after normalization: Ball Playing Defender=1.0, rest 0.
    Team style vector after normalization: Control Possession=1.0, rest 0.
    Team role demand (CB) driven purely by the Control Possession weight for
    each CB role: LCB=0.70, NNCB=0.15, BPD=0.95, RCB=0.70, Libero=0.90 (sum
    3.40) -> normalized -> sharpened (power=2) -> BPD's sharpened share is
    0.078071/0.234866 = 0.332412..., and min(player_p, team_t) collapses to
    just that BPD term since the player vector is 1.0 on BPD and 0 elsewhere.
    role_fit_score = 0.332412... * 100 = 33.2412 -> round(2) = 33.24.
    """
    player_row = _cb_player_row(**{"Ball Playing Defender": 100.0})
    team_styles_df = pd.DataFrame([_team_style_row("Test FC", **{"Control Possession": 100.0})])

    result = calculate_subjective_role_fit_for_player_to_team(player_row, "Test FC", team_styles_df)

    assert result["Role Fit Score"] == pytest.approx(33.24, abs=1e-6)
    assert result["Best Team Fit Role"] == "Ball Playing Defender"


def test_calculate_subjective_role_fit_all_nan_club_styles_yields_nan_not_zero():
    """A club with an entirely NaN playing-style vector (the ~77%-null case)
    must yield NaN role-fit, not a confidently-wrong zero (APPLIED_FIXES)."""
    player_row = _cb_player_row(**{"Ball Playing Defender": 100.0})
    nan_styles = {
        "Control Possession": np.nan,
        "Gegenpressing": np.nan,
        "Direct Play": np.nan,
        "Defensive Counter Attack": np.nan,
        "Tiki Taka": np.nan,
        "Counter Attack": np.nan,
        "Wing Play": np.nan,
        "Low Block": np.nan,
    }
    team_styles_df = pd.DataFrame([_team_style_row("Unknown FC", **nan_styles)])

    result = calculate_subjective_role_fit_for_player_to_team(player_row, "Unknown FC", team_styles_df)

    assert result["Role Fit Score"] is np.nan or (
        isinstance(result["Role Fit Score"], float) and np.isnan(result["Role Fit Score"])
    )
    assert result["Role Fit Score"] != 0.0


def test_calculate_subjective_role_fit_unknown_team_yields_nan():
    player_row = _cb_player_row(**{"Ball Playing Defender": 100.0})
    team_styles_df = pd.DataFrame([_team_style_row("Test FC", **{"Control Possession": 100.0})])

    result = calculate_subjective_role_fit_for_player_to_team(player_row, "Nonexistent FC", team_styles_df)

    assert np.isnan(result["Role Fit Score"])


def test_compatibility_score_avg_non_null_assembly():
    # All three terms present -> simple mean, rounded to 2dp.
    assert compatibility_score(60.0, 80.0, 100.0) == pytest.approx((60 + 80 + 100) / 3, abs=1e-6)
    # NaN role_fit_score/similarity excluded, not zero-filled -- averages
    # only the bonus term.
    assert compatibility_score(np.nan, np.nan, 70.0) == pytest.approx(70.0, abs=1e-6)
    # All-NaN inputs (bonus is never NaN in practice, but the assembly
    # itself must not fabricate a 0.0 when every term is unknown).
    assert np.isnan(compatibility_score(np.nan, np.nan, np.nan))


def test_get_player_own_best_role_excludes_nan_not_zero_fill():
    player_row = _cb_player_row(**{"Ball Playing Defender": 100.0, "Libero": 40.0})
    best_role, best_score = get_player_own_best_role(player_row, "CB")
    assert best_role == "Ball Playing Defender"
    assert best_score == pytest.approx(100.0)

    # All roles NaN -> excluded entirely -> (None, NaN), not (None, 0.0).
    role_cols = ROLE_COLUMNS_BY_POSITION["CB"]
    nan_row = pd.Series({**{r: np.nan for r in role_cols}, "Main_Position": "CB"})
    best_role_nan, best_score_nan = get_player_own_best_role(nan_row, "CB")
    assert best_role_nan is None
    assert np.isnan(best_score_nan)
