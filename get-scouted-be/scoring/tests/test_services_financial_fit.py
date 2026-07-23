"""Tests for scoring.services.financial_fit (04-04-PLAN.md) -- the
Financial Fit (TFM) request-facing service that prices a player against a
SPECIFIC requested club's spending profile.

This plan carries the phase's two highest-risk, explicitly-confirmed
concerns, each with a dedicated regression test:

    1. `pipeline.predict()` returns LOG-SCALE (`log1p(fee)`) output --
       `test_predicted_fee_is_money_scale_not_log_scale` fails loudly if
       `np.expm1()` is skipped (a raw log value like 15.2 would otherwise
       silently pass as a "fee").
    2. The requested `club_id` must genuinely change the prediction (buying
       -club context override BEFORE `build_oracle_player_features`, not a
       decorative label) -- `test_requested_club_overrides_team_before_build`
       and `test_requested_club_changes_prediction_real_data` guard this.

Synthetic (`unittest.mock.patch`-based) tests need no DB and exercise the
merge/override/null-envelope mechanics directly against
`financial_fit_from_population`. Real-data tests (`real_data_available`)
exercise `get_financial_fit` end-to-end against the real migrated
population + the real trained artifact.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from django.conf import settings

from scoring.exceptions import null_with_reason
from scoring.services.population import Population, get_tfm_pipeline


def _metrics_path() -> Path:
    return Path(settings.BASE_DIR) / "scoring" / "ml_artifacts" / "tfm_value_model_v1.metrics.json"


def _expected_feature_cols() -> list[str]:
    return json.loads(_metrics_path().read_text())["feature_cols"]


# =========================================================================
# Synthetic fixtures (no DB) -- for the merge/override/null-envelope
# mechanism tests.
# =========================================================================
def _synthetic_pop() -> Population:
    players_df = pd.DataFrame(
        {
            "player_id": ["p1", "p2"],
            "Team": ["OwnClubP1", "OwnClubP2"],
            "Market value": [5_000_000.0, 3_000_000.0],
            "Age": [24, 27],
            "Position": ["CM", "CB"],
        }
    )
    return Population(
        players_df=players_df,
        role_scores_wide=pd.DataFrame(),
        team_styles_df=pd.DataFrame(),
        transfers_df=pd.DataFrame(),
    )


def _synthetic_scored(players_df: pd.DataFrame) -> pd.DataFrame:
    scored = players_df[["player_id"]].copy()
    scored["Player Impact"] = [55.0, 42.0]
    return scored


def _synthetic_cs_tp() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "compatibility_score": [70.0, 40.0],
            "performance_score": [60.0, 50.0],
            "role_pct": [80.0, 55.0],
        },
        index=pd.Index(["p1", "p2"], name="player_id"),
    )


def _fake_priced_build_oracle_player_features(feature_cols, captured=None):
    """Build a `build_oracle_player_features` stand-in that returns a
    minimal-but-complete feature frame (every `feature_cols` name present,
    `_has_club_context` True) so `financial_fit_from_population` can run to
    completion, while optionally recording the `players_df` it was called
    with (for the merge/override assertions)."""

    def _fake(players_df, transfers_df, as_of_year=None):
        if captured is not None:
            captured["players_df"] = players_df.copy()
        idx = pd.Index(players_df["player_id"].astype(str), name="player_id")
        features = pd.DataFrame(index=idx)
        for c in feature_cols:
            features[c] = "CM" if c == "position" else 1.0
        features["_has_club_context"] = True
        return features

    return _fake


# =========================================================================
# feature_cols sidecar-fidelity test
# =========================================================================
def test_feature_cols_match_artifact_sidecar():
    """The columns actually selected for `pipeline.predict` must equal
    metrics.json's `feature_cols` exactly (23 entries, same order) -- not
    re-derived from tfm_model.py's nominal 33-name list, and not leaking
    any extra engineered column the feature frame happens to carry."""
    from scoring.services.financial_fit import financial_fit_from_population

    expected_feature_cols = _expected_feature_cols()
    assert len(expected_feature_cols) == 23

    pop = _synthetic_pop()
    scored = _synthetic_scored(pop.players_df)
    cs_tp = _synthetic_cs_tp()

    captured_predict_columns: dict[str, list[str]] = {}

    class _FakePipeline:
        def predict(self, X):
            captured_predict_columns["cols"] = list(X.columns)
            return np.array([10.0])

    fake_build = _fake_priced_build_oracle_player_features(expected_feature_cols)

    def _fake_build_with_bogus_extra(players_df, transfers_df, as_of_year=None):
        features = fake_build(players_df, transfers_df, as_of_year)
        features["extra_bogus_engineered_col"] = 999.0  # must never leak into X
        return features

    with (
        patch(
            "scoring.services.financial_fit.build_oracle_player_features",
            side_effect=_fake_build_with_bogus_extra,
        ),
        patch(
            "scoring.services.financial_fit.get_tfm_pipeline",
            return_value=(_FakePipeline(), expected_feature_cols),
        ),
    ):
        financial_fit_from_population("p1", "RequestedClub", pop, scored, cs_tp)

    assert captured_predict_columns["cols"] == expected_feature_cols


# =========================================================================
# Upstream RMM-first feature merge (fact 2)
# =========================================================================
def test_upstream_features_merged_before_build():
    """player_impact/compatibility_score/performance_score/role_pct must be
    populated on the players_df passed into `build_oracle_player_features`
    -- proving the RMM-first -> CS/TP merge happened BEFORE the TFM feature
    build (skipping it silently NaNs these 4 columns; tfm_model.py line
    ~799 reads them straight off players_df)."""
    from scoring.services.financial_fit import financial_fit_from_population

    pop = _synthetic_pop()
    scored = _synthetic_scored(pop.players_df)
    cs_tp = _synthetic_cs_tp()
    feature_cols = _expected_feature_cols()

    captured: dict[str, pd.DataFrame] = {}
    fake_build = _fake_priced_build_oracle_player_features(feature_cols, captured=captured)

    with patch("scoring.services.financial_fit.build_oracle_player_features", side_effect=fake_build):
        financial_fit_from_population("p1", "RequestedClub", pop, scored, cs_tp)

    merged = captured["players_df"]
    row = merged.loc[merged["player_id"] == "p1"].iloc[0]
    assert row["player_impact"] == 55.0
    assert row["compatibility_score"] == 70.0
    assert row["performance_score"] == 60.0
    assert row["role_pct"] == 80.0


# =========================================================================
# Buying-club-context override (locked CONTEXT.md decision)
# =========================================================================
def test_requested_club_overrides_team_before_build():
    """The requested club's name must replace the target player's `Team`
    on the players_df passed into `build_oracle_player_features` BEFORE
    that call -- club_id genuinely changes the club-aggregate features fed
    to the pipeline, not just a label attached to an unchanged
    player-own-club prediction."""
    from scoring.services.financial_fit import financial_fit_from_population

    pop = _synthetic_pop()
    scored = _synthetic_scored(pop.players_df)
    cs_tp = _synthetic_cs_tp()
    feature_cols = _expected_feature_cols()

    captured: dict[str, pd.DataFrame] = {}
    fake_build = _fake_priced_build_oracle_player_features(feature_cols, captured=captured)

    with patch("scoring.services.financial_fit.build_oracle_player_features", side_effect=fake_build):
        financial_fit_from_population("p1", "SomeOtherClub FC", pop, scored, cs_tp)

    merged = captured["players_df"]
    row = merged.loc[merged["player_id"] == "p1"].iloc[0]
    assert row["Team"] == "SomeOtherClub FC"

    # The OTHER player's row must be untouched by the override.
    other_row = merged.loc[merged["player_id"] == "p2"].iloc[0]
    assert other_row["Team"] == "OwnClubP2"


# =========================================================================
# Null envelope for no-club-context rows
# =========================================================================
def test_null_envelope_when_no_club_context():
    """A row build_oracle_player_features flags `_has_club_context=False`
    must return the shared null+reason envelope, never a fee manufactured
    from an all-imputed row."""
    from scoring.services.financial_fit import financial_fit_from_population

    pop = _synthetic_pop()
    scored = _synthetic_scored(pop.players_df)
    cs_tp = _synthetic_cs_tp()

    def _fake_no_context(players_df, transfers_df, as_of_year=None):
        idx = pd.Index(players_df["player_id"].astype(str), name="player_id")
        features = pd.DataFrame(index=idx)
        features["_has_club_context"] = False
        return features

    with patch("scoring.services.financial_fit.build_oracle_player_features", side_effect=_fake_no_context):
        result = financial_fit_from_population("p1", "RequestedClub", pop, scored, cs_tp)

    assert result == null_with_reason("predicted_fee", "no_club_context")


# =========================================================================
# Real-data tests -- money-scale regression, verdict shape, real
# end-to-end club-override effect.
#
# `score_population` (RMM + CS/TP over the whole real 41,708-player
# population) is expensive (~1 min) -- it is computed AT MOST ONCE for this
# whole test module via `_real_scored_population`'s process-level cache,
# then `reconstruct_population`/`score_population` are patched (still
# exercising the real `get_financial_fit` entry point end-to-end, including
# the real `resolve_club_name` DB lookup) so every test reuses it instead
# of re-paying that cost.
# =========================================================================
_REAL_POP_CACHE: dict = {}


def _real_scored_population():
    if "data" not in _REAL_POP_CACHE:
        from scoring.services.population import reconstruct_population, score_population

        pop = reconstruct_population()
        scored, cs_tp = score_population(pop, None)
        _REAL_POP_CACHE["data"] = (pop, scored, cs_tp)
    return _REAL_POP_CACHE["data"]


@pytest.fixture
def cached_real_population(real_data_available):
    """Real `get_financial_fit` calls, minus the per-test reconstruction
    cost -- `scoring.services.financial_fit.reconstruct_population`/
    `score_population` are patched to return the module-cached real
    population instead of recomputing it."""
    pop, scored, cs_tp = _real_scored_population()
    with (
        patch("scoring.services.financial_fit.reconstruct_population", return_value=pop),
        patch("scoring.services.financial_fit.score_population", return_value=(scored, cs_tp)),
    ):
        yield pop, scored, cs_tp


def _first_priced_result(clubs, player):
    from scoring.services.financial_fit import get_financial_fit

    for club in clubs:
        result = get_financial_fit(str(player.id), str(club.id))
        if result.get("predicted_fee") is not None:
            return club, result
    return None, None


@pytest.mark.django_db
def test_predicted_fee_is_money_scale_not_log_scale(cached_real_population):
    from clubs.models import Club
    from players.models import Player

    player = Player.objects.first()
    club, result = _first_priced_result(Club.objects.all()[:10], player)
    if club is None:
        pytest.skip("No real player/club combination produced a priced result to sample")

    fee = result["predicted_fee"]
    assert fee > 1000, f"predicted_fee={fee} looks log-scale (log1p output), not money-scale"
    assert not (0 <= fee <= 20), f"predicted_fee={fee} is in the log-scale bug's [0,20] range"


@pytest.mark.django_db
def test_value_verdict_and_market_value_present(cached_real_population):
    from clubs.models import Club
    from players.models import Player

    player = Player.objects.first()
    club, result = _first_priced_result(Club.objects.all()[:10], player)
    if club is None:
        pytest.skip("No real player/club combination produced a priced result to sample")

    assert "market_value" in result
    assert result["value_verdict"] in {"Bargain", "Fair Value", "Overpay", None}
    assert "value_comparison" in result
    assert result["buying_club"] == club.name


@pytest.mark.django_db
def test_requested_club_changes_prediction_real_data(cached_real_population):
    from clubs.models import Club
    from players.models import Player
    from scoring.services.financial_fit import get_financial_fit

    player = Player.objects.first()
    clubs = list(Club.objects.all()[:15])

    fees = []
    for club in clubs:
        result = get_financial_fit(str(player.id), str(club.id))
        fee = result.get("predicted_fee")
        if fee is not None:
            fees.append(fee)

    assert len(fees) >= 2, "Need at least 2 priced results to compare across clubs"
    assert len(set(fees)) > 1, (
        "predicted_fee did not vary across different requested clubs -- club_id must change "
        "the club-aggregate features fed into the TFM pipeline (locked buying-club-context "
        "override decision), not just label an unchanged prediction"
    )


@pytest.mark.django_db
def test_get_financial_fit_unknown_club_raises_http404(real_data_available):
    import uuid

    from django.http import Http404
    from players.models import Player
    from scoring.services.financial_fit import get_financial_fit

    player = Player.objects.first()
    with pytest.raises(Http404):
        get_financial_fit(str(player.id), str(uuid.uuid4()))
