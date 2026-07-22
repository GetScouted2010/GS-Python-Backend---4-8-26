"""Tests for scoring.characterization.tfm_model -- the Financial Fit (TFM)
sklearn artifact port (03-06-PLAN.md).

Task 1 tests exercise `build_transfer_value_dataset` against a small
synthetic transfers+players DataFrame pair -- no DB required. The synthetic
`players_df` includes the 4 cross-plan feature columns (`player_impact`,
`performance_score`, `compatibility_score`, `role_pct`) under this
project's actual lowercase names (Plan 04/05's output shape), which is the
regression guard for 03-06-PLAN.md's central wiring concern: those 4
columns must survive `build_transfer_value_dataset`'s
`[c for c in feature_cols if c in model_df.columns]` filter, not be
silently dropped.

Task 2 tests (`test_artifact_loads_and_predicts`, `test_metrics_are_finite`)
exercise the full real-data path via `real_data_available` +
`@pytest.mark.django_db`.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scoring.characterization.tfm_model import (
    add_value_labels,
    build_transfer_value_dataset,
    contract_to_years_left,
    parse_money_to_numeric,
    safe_div,
    season_to_year,
    train_transfer_value_model,
)


# =========================================================================
# Synthetic fixtures
# =========================================================================
def _synthetic_transfers_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Player": ["Alice", "Bob", "Carol", "Dave"],
            "Year": [2023, 2023, 2024, 2023],
            "Position": ["CB", "CB", "CM", "CM"],
            "Age": [22, 30, 19, 25],
            # Alice/Bob: valid fees. Carol: unparseable/NaN fee (dropped).
            # Dave: zero fee (dropped).
            "Fee": ["€5m", "€2m", None, "€0"],
            "Dealing_Club": ["ClubA", "ClubB", "ClubC", "ClubD"],
            "League": [
                "Bundesliga (Germany)",
                "La Liga (Spain)",
                "Serie A (Italy)",
                "Ligue 1 (France)",
            ],
            "Club": ["ClubX", "ClubY", "ClubZ", "ClubW"],
            "is_loan": [False, False, True, False],
        }
    )


def _synthetic_players_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Player": ["Alice", "Bob", "Carol", "Dave"],
            "Season": ["2022-2023", "2022-2023", "2023-2024", "2022-2023"],
            "Age": [22, 30, 19, 25],
            "Position": ["CB", "CB", "CM", "CM"],
            "Market value": [4_000_000, 8_000_000, 1_000_000, 2_500_000],
            "Minutes played": [2000, 2500, 900, 1800],
            # The 4 cross-plan feature columns (Plan 04/05 outputs), under
            # this project's actual lowercase names -- the wiring guard.
            "player_impact": [55.0, 42.0, 61.0, 48.0],
            "performance_score": [60.0, 50.0, 65.0, 52.0],
            "compatibility_score": [70.0, 40.0, 80.0, 55.0],
            "role_pct": [80.0, 55.0, 90.0, 62.0],
        }
    )


# =========================================================================
# Small pure-helper tests
# =========================================================================
def test_parse_money_to_numeric_handles_currency_and_missing():
    assert parse_money_to_numeric("€5m") == 5_000_000
    assert parse_money_to_numeric("€1.2bn") == 1_200_000_000
    assert parse_money_to_numeric("£250k") == 250_000
    assert np.isnan(parse_money_to_numeric("free"))
    assert np.isnan(parse_money_to_numeric(None))
    assert parse_money_to_numeric(1_000_000) == 1_000_000.0


def test_safe_div_avoids_div_by_zero_and_nan():
    assert safe_div(10, 2) == 5.0
    assert np.isnan(safe_div(10, 0))
    assert np.isnan(safe_div(np.nan, 2))


def test_season_to_year_extracts_first_year():
    assert season_to_year("2022-2023") == 2022
    assert np.isnan(season_to_year(None))


def test_contract_to_years_left_extracts_last_year_minus_season_start():
    # "Contract expires" Timestamp-like string -> last 4-digit year found.
    assert contract_to_years_left("2025-06-30 00:00:00", "2022-2023") == 3
    assert np.isnan(contract_to_years_left(None, "2022-2023"))
    # Never negative -- clamped at 0 (verbatim source behavior).
    assert contract_to_years_left("2020-06-30 00:00:00", "2022-2023") == 0


# =========================================================================
# Task 1: build_transfer_value_dataset
# =========================================================================
def test_build_transfer_value_dataset_drops_nonpositive_and_nan_fees():
    transfers_df = _synthetic_transfers_df()
    players_df = _synthetic_players_df()

    model_df = build_transfer_value_dataset(transfers_df, players_df)

    # Carol (NaN fee) and Dave (zero fee) must be excluded.
    assert set(model_df["Player"]) == {"Alice", "Bob"}
    assert (model_df["actual_fee"] > 0).all()
    assert model_df["actual_fee"].notna().all()


def test_build_transfer_value_dataset_engineers_expected_flags():
    transfers_df = _synthetic_transfers_df()
    players_df = _synthetic_players_df()

    model_df = build_transfer_value_dataset(transfers_df, players_df)

    for col in ["age_squared", "u23_flag", "prime_age_flag", "older_flag", "mv_to_fee_ratio", "is_loan"]:
        assert col in model_df.columns

    alice = model_df[model_df["Player"] == "Alice"].iloc[0]
    assert alice["age_squared"] == 22**2
    assert alice["u23_flag"] == 1
    assert alice["older_flag"] == 0

    bob = model_df[model_df["Player"] == "Bob"].iloc[0]
    assert bob["older_flag"] == 1
    assert bob["u23_flag"] == 0

    # log_fee is derivable from the surviving actual_fee column (log_fee
    # itself is only materialized inside train_transfer_value_model, exactly
    # as in the source).
    assert np.all(np.isfinite(np.log1p(model_df["actual_fee"])))


def test_build_transfer_value_dataset_preserves_cross_plan_feature_columns():
    """Regression guard for 03-06-PLAN.md's central wiring concern: the 4
    cross-plan columns (player_impact/performance_score/compatibility_score
    /role_pct), present on the incoming players_df, must survive into
    model_df -- not be silently dropped by the feature_cols filter."""
    transfers_df = _synthetic_transfers_df()
    players_df = _synthetic_players_df()

    model_df = build_transfer_value_dataset(transfers_df, players_df)

    for col in ["player_impact", "performance_score", "compatibility_score", "role_pct"]:
        assert col in model_df.columns, f"cross-plan column {col!r} was dropped"

    alice = model_df[model_df["Player"] == "Alice"].iloc[0]
    assert alice["player_impact"] == 55.0
    assert alice["compatibility_score"] == 70.0
    assert alice["performance_score"] == 60.0
    assert alice["role_pct"] == 80.0


def test_build_transfer_value_dataset_without_cross_plan_columns_still_works():
    """When the 4 cross-plan columns are absent from players_df (caller
    didn't wire them in), build_transfer_value_dataset must not error --
    they're simply excluded from the eventual feature_cols, exactly like
    the source's own optional-column pattern."""
    transfers_df = _synthetic_transfers_df()
    players_df = _synthetic_players_df().drop(
        columns=["player_impact", "performance_score", "compatibility_score", "role_pct"]
    )

    model_df = build_transfer_value_dataset(transfers_df, players_df)

    for col in ["player_impact", "performance_score", "compatibility_score", "role_pct"]:
        assert col not in model_df.columns


# =========================================================================
# train_transfer_value_model + add_value_labels
# =========================================================================
def test_train_transfer_value_model_returns_fitted_pipeline_and_finite_metrics():
    # Build a slightly larger synthetic transfer set so train_test_split has
    # enough rows to work with.
    rng = np.random.default_rng(42)
    n = 40
    positions = ["CB", "CM", "CF", "LB"] * (n // 4)
    transfers_df = pd.DataFrame(
        {
            "Player": [f"Player{i}" for i in range(n)],
            "Year": [2023] * (n // 2) + [2024] * (n - n // 2),
            "Position": positions,
            "Age": rng.integers(18, 34, size=n),
            "Fee": [f"€{v}m" for v in rng.integers(1, 50, size=n)],
            "Dealing_Club": [f"SellClub{i % 5}" for i in range(n)],
            "League": ["Bundesliga (Germany)"] * n,
            "Club": [f"BuyClub{i % 5}" for i in range(n)],
            "is_loan": [False] * n,
        }
    )
    seasons = ["2022-2023" if y == 2023 else "2023-2024" for y in transfers_df["Year"]]
    players_df = pd.DataFrame(
        {
            "Player": transfers_df["Player"],
            "Season": seasons,
            "Age": transfers_df["Age"],
            "Position": positions,
            "Market value": rng.integers(500_000, 20_000_000, size=n),
            "Minutes played": rng.integers(300, 3000, size=n),
            "player_impact": rng.uniform(10, 90, size=n),
            "performance_score": rng.uniform(10, 90, size=n),
            "compatibility_score": rng.uniform(10, 90, size=n),
            "role_pct": rng.uniform(10, 90, size=n),
        }
    )

    model_df = build_transfer_value_dataset(transfers_df, players_df)
    pipeline, metrics = train_transfer_value_model(model_df)

    assert hasattr(pipeline, "predict")
    assert np.isfinite(metrics["mae_money"])
    assert np.isfinite(metrics["r2_log"])
    assert metrics["n_train"] > 0
    assert metrics["n_test"] > 0

    # Reload-and-predict smoke check via the same fitted pipeline object.
    feature_cols = metrics["feature_cols"]
    sample = model_df[feature_cols].iloc[[0]]
    pred = pipeline.predict(sample)
    assert np.isfinite(pred).all()


def test_add_value_labels_bands_fee_ratio():
    df = pd.DataFrame(
        {
            "actual_fee": [80.0, 100.0, 130.0, np.nan],
            "predicted_fee": [100.0, 100.0, 100.0, 100.0],
        }
    )
    out = add_value_labels(df)
    assert list(out["value_verdict"])[:3] == ["Bargain", "Fair Value", "Overpay"]
    assert pd.isna(out["value_verdict"].iloc[3])


# =========================================================================
# Task 2: real-data artifact tests
# =========================================================================
def _default_artifact_path() -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "scoring" / "ml_artifacts" / "tfm_value_model_v1.joblib"


def _default_metrics_path() -> Path:
    return _default_artifact_path().with_suffix("").with_suffix(".metrics.json")


@pytest.mark.django_db
def test_artifact_loads_and_predicts(real_data_available):
    import joblib

    artifact_path = _default_artifact_path()

    if artifact_path.exists():
        pipeline = joblib.load(artifact_path)
        assert hasattr(pipeline, "predict")

        from scoring.characterization.deterministic_scores import compute_cs_tp_for_pairs
        from scoring.characterization.impact import compute_rmm_column
        from scoring.characterization.reconstruct import (
            build_players_df,
            build_role_scores_wide,
            build_team_styles_df,
            build_transfers_df,
        )

        players_df = build_players_df().head(50).copy()
        rmm = compute_rmm_column(players_df)
        players_df["player_impact"] = players_df["player_id"].map(rmm)
        team_styles_df = build_team_styles_df()
        role_scores_wide = build_role_scores_wide()
        cs_tp = compute_cs_tp_for_pairs(
            players_df, team_styles_df, role_scores_wide, club_context=None, player_impact=rmm
        )
        merged = players_df.merge(
            cs_tp[["compatibility_score", "performance_score", "role_pct"]].reset_index(),
            on="player_id",
            how="left",
        )
        transfers_df = build_transfers_df()
        model_df = build_transfer_value_dataset(transfers_df, merged)
        if model_df.empty:
            pytest.skip("No real transfer rows matched this small player subset")

        feature_cols = [
            c
            for c in [
                "age", "age_squared", "u23_flag", "prime_age_flag", "older_flag",
                "minutes_played", "market_value", "contract_years_left",
                "performance_score", "compatibility_score", "player_impact", "role_pct",
                "from_league_weight", "mv_to_fee_ratio", "is_loan",
                "club_avg_in_fee", "club_max_in_fee", "club_median_in_fee",
                "club_count_in", "club_avg_in_age",
                "seller_hist_avg_out_fee", "seller_hist_max_out_fee",
                "seller_hist_median_out_fee", "seller_hist_count_out",
                "seller_hist_avg_out_age", "club_pos_avg_in_fee",
                "club_pos_avg_out_fee", "position",
            ]
            if c in model_df.columns
        ]
        sample = model_df[feature_cols].iloc[[0]]
        pred = pipeline.predict(sample)
        assert np.isfinite(pred).all()
        return

    pytest.skip(
        "No trained TFM artifact found at "
        f"{artifact_path} -- run `python manage.py train_tfm_model` first "
        "to produce one."
    )


def test_metrics_are_finite():
    metrics_path = _default_metrics_path()
    if not metrics_path.exists():
        pytest.skip(
            f"No metrics sidecar found at {metrics_path} -- run "
            "`python manage.py train_tfm_model` first to produce one."
        )

    with open(metrics_path) as f:
        metrics = json.load(f)

    assert np.isfinite(metrics["mae_money"])
    assert np.isfinite(metrics["r2_log"])
