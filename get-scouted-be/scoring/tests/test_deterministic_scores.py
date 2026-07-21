"""Tests for the CS / Transfer Probability characterization (03-05-PLAN.md).

Hand-computable synthetic fixtures only -- unlike test_reconstruct.py, these
functions are pure and don't need real migrated data, so no `real_data_available`
/ `django_db` marker is required (role_fit.py imports ROLE_COLUMNS_BY_POSITION
from reconstruct.py at module level, which imports Django models -- that's
fine without DB access since we never query them here).
"""

import inspect

import numpy as np
import pandas as pd
import pytest

from scoring.characterization import deterministic_scores
from scoring.characterization.deterministic_scores import (
    compute_cs_tp_for_pairs,
    contract_fit,
    financial_score,
    performance_score,
    transfer_probability,
)
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


# =========================================================================
# Task 2: deterministic Transfer Probability + Financial/Performance
# =========================================================================
def test_transfer_probability_exact():
    """Hand-computed against the line 3809-3814 formula:
    tp = (0.30*compat/100 + 0.20*perf/100 + 0.20*fin/100 + 0.30*contract_fit) * 100
    compat=80, perf=70, fin=60, contract_fit=0.7:
    tp = (0.30*0.80 + 0.20*0.70 + 0.20*0.60 + 0.30*0.7) * 100
       = (0.24 + 0.14 + 0.12 + 0.21) * 100 = 0.71 * 100 = 71.0
    """
    tp = transfer_probability(80.0, 70.0, 60.0, 0.7)
    assert tp == pytest.approx(71.0, abs=1e-9)

    # Full precision cross-check without hand-rounding intermediate terms.
    compat, perf, fin, cf = 33.24, 91.5, 46.0, 1.0
    expected = round(
        (0.30 * (compat / 100.0) + 0.20 * (perf / 100.0) + 0.20 * (fin / 100.0) + 0.30 * cf) * 100,
        1,
    )
    assert transfer_probability(compat, perf, fin, cf) == pytest.approx(expected, abs=1e-9)


def test_contract_fit_bands():
    assert contract_fit(-1) == 1.0  # already-expired quirk preserved verbatim
    assert contract_fit(0) == 1.0
    assert contract_fit(1) == 1.0
    assert contract_fit(2) == 0.7
    assert contract_fit(3) == 0.4
    assert contract_fit(4) == 0.1
    assert contract_fit(10) == 0.1
    assert contract_fit(np.nan) == 0.5


def test_no_sklearn_import():
    source = inspect.getsource(deterministic_scores)
    assert "import sklearn" not in source
    assert "from sklearn" not in source


def test_performance_needs_player_impact():
    # player_impact present -> a real (non-NaN) performance_score.
    assert performance_score(75.0) == pytest.approx(75.0, abs=1e-6)

    # player_impact NaN -> performance_score NaN (never 0), and
    # transfer_probability built from it is also NaN, not silently 0/low.
    assert np.isnan(performance_score(np.nan))
    tp = transfer_probability(80.0, performance_score(np.nan), 60.0, 0.7)
    assert np.isnan(tp)


def test_financial_score_avg_non_null():
    assert financial_score("Great Fit", "Poor Fit") == pytest.approx((100.0 + 20.0) / 2, abs=1e-6)
    assert financial_score("Unknown", "Poor Fit") == pytest.approx(20.0, abs=1e-6)
    assert np.isnan(financial_score("Unknown", "Unknown"))


def _synthetic_players_df():
    role_cols = ROLE_COLUMNS_BY_POSITION["CB"]
    row_a = {r: 0.0 for r in role_cols}
    row_a.update(
        {
            "player_id": "p1",
            "Team": "Test FC",
            "Main_Position": "CB",
            "Position": "CB",
            "Age": 24,
            "Market value": 5_000_000,
            "Contract expires": pd.Timestamp("2027-06-30"),
            "Ball Playing Defender": 100.0,
        }
    )
    row_b = {r: 0.0 for r in role_cols}
    row_b.update(
        {
            "player_id": "p2",
            "Team": None,
            "Main_Position": "CB",
            "Position": "CB",
            "Age": 30,
            "Market value": 2_000_000,
            "Contract expires": None,
            "Libero": 50.0,
        }
    )
    return pd.DataFrame([row_a, row_b])


def test_compute_cs_tp_for_pairs_emits_upstream_feature_columns():
    players_df = _synthetic_players_df()
    team_styles_df = pd.DataFrame(
        [
            {
                "Team": "Test FC",
                "Control Possession": 100.0,
                "Gegenpressing": 0.0,
                "Direct Play": 0.0,
                "Defensive Counter Attack": 0.0,
                "Tiki Taka": 0.0,
                "Counter Attack": 0.0,
                "Wing Play": 0.0,
                "Low Block": 0.0,
            }
        ]
    )
    role_scores_wide = pd.DataFrame({"player_id": ["p1", "p2"]})
    player_impact = pd.Series({"p1": 65.0}, name="Player Impact")  # p2 deliberately absent -> NaN

    result = compute_cs_tp_for_pairs(
        players_df, team_styles_df, role_scores_wide, None, player_impact, as_of_year=2025
    )

    for col in ["club_context", "compatibility_score", "financial_score", "performance_score", "contract_fit", "role_pct", "transfer_probability"]:
        assert col in result.columns

    # p1: has a resolvable club (own club "Test FC" with real styles) and a
    # real player_impact -> non-NaN CS/performance/TP.
    assert pd.notna(result.loc["p1", "compatibility_score"])
    assert result.loc["p1", "performance_score"] == pytest.approx(65.0, abs=1e-6)
    assert pd.notna(result.loc["p1", "transfer_probability"])

    # p2: no club (Team is None) AND NaN player_impact -> CS/performance/TP
    # all NaN, never zero-filled.
    assert pd.isna(result.loc["p2", "compatibility_score"])
    assert pd.isna(result.loc["p2", "performance_score"])
    assert pd.isna(result.loc["p2", "transfer_probability"])

    assert result.attrs["exclusion_counts"]["no_club"] == 1
    assert result.attrs["exclusion_counts"]["nan_player_impact"] == 1
