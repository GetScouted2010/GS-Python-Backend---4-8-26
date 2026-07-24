"""Financial Fit (TFM) request-facing service (04-04-PLAN.md).

Wraps the trained TFM sklearn `Pipeline` (`get_tfm_pipeline`) to price a
SPECIFIC player against a SPECIFIC requested club's spending profile,
returning a money-scale `predicted_fee`, the market-value comparison, and
the Bargain/Fair Value/Overpay verdict.

Two load-bearing, explicitly-confirmed facts this module gets right:

    1. RMM-first wiring (fact 2): `build_oracle_player_features` reads
       `player_impact`/`compatibility_score`/`performance_score`/`role_pct`
       straight off `players_df` columns (tfm_model.py line ~799). Those 4
       columns MUST be merged onto `players_df` (via `score_population`'s
       RMM-first -> CS/TP sequence) BEFORE `build_oracle_player_features`
       runs -- skipping this silently NaNs them and degrades the
       prediction. See `_merge_tfm_feature_columns`.
    2. Money-scale unwrap (the confirmed log-scale bug): the trained
       pipeline's raw `predict()` output is LOG-SCALE (`log1p(fee)`) --
       the oracle CSV's `tfm` column ranges 13.11-17.09 across 41,708 real
       players. `predicted_fee` MUST be `np.expm1(pipeline.predict(X))`,
       never the raw prediction.

Plus the locked CONTEXT.md buying-club-context override: the requested
`club_id` overrides the target player's `Team` on `players_df` BEFORE
`build_oracle_player_features` runs, so the club-aggregate features (and
thus the prediction) genuinely reflect the requested club -- not a
decorative label on an unchanged player-own-club prediction.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from django.http import Http404

from scoring.characterization.tfm_model import add_value_labels, build_oracle_player_features
from scoring.exceptions import null_with_reason
from scoring.services.population import (
    Population,
    get_scored_population,
    get_tfm_pipeline,
    is_own_club,
    reconstruct_population,
    resolve_club_name,
)


def _merge_tfm_feature_columns(
    base_players_df: pd.DataFrame, scored: pd.DataFrame, cs_tp: pd.DataFrame
) -> pd.DataFrame:
    """Merge the 4 upstream RMM/CS/TP columns onto a copy of
    `base_players_df` -- REQUIRED so `build_oracle_player_features` finds
    `player_impact`/`compatibility_score`/`performance_score`/`role_pct`
    (fact 2). Without this merge those columns are absent -> NaN -> imputed
    -> a degraded prediction, silently."""
    df = base_players_df.copy()
    df["player_impact"] = df["player_id"].map(scored.set_index("player_id")["Player Impact"])
    df = df.merge(
        cs_tp[["compatibility_score", "performance_score", "role_pct"]].reset_index(),
        on="player_id",
        how="left",
    )
    return df


def financial_fit_from_population(
    player_id,
    club_name: str,
    pop: Population,
    scored: pd.DataFrame,
    cs_tp: pd.DataFrame,
) -> dict:
    """The core Financial Fit computation, reusable by the summary
    endpoint (Plan 05) with no extra reconstruction.

    Args:
        player_id: the target player's id (UUID or str).
        club_name: the requested club's NAME (not a UUID -- see
            `resolve_club_name`) -- the buying-club context to price the
            player against.
        pop: a `Population` from `reconstruct_population()`.
        scored: `pop.players_df` + RMM's full breakdown columns (from
            `score_population`).
        cs_tp: `compute_cs_tp_for_pairs`' per-player result (from
            `score_population`).

    Returns:
        A dict with `predicted_fee` (money-scale), `market_value`,
        `value_comparison` (`fee_diff`/`ratio_market_to_predicted`),
        `value_verdict`, and `buying_club` -- or the shared
        `null_with_reason("predicted_fee", ...)` envelope if no fee can be
        honestly computed.
    """
    players_df = _merge_tfm_feature_columns(pop.players_df, scored, cs_tp)
    players_df["_pid_str"] = players_df["player_id"].astype(str)
    mask = players_df["_pid_str"] == str(player_id)
    if not mask.any():
        raise Http404(f"Player {player_id} not found")

    # LOCKED override: the requested club becomes the buying-club context
    # for the target player's row BEFORE the feature build -- this is what
    # makes club_id genuinely change the club-aggregate features (and thus
    # the prediction), not just label an unchanged player-own-club value.
    players_df.loc[mask, "Team"] = club_name
    players_df = players_df.drop(columns=["_pid_str"])

    pipeline, feature_cols = get_tfm_pipeline()  # feature_cols from the metrics.json sidecar
    features = build_oracle_player_features(players_df, pop.transfers_df)
    features.index = features.index.astype(str)

    if str(player_id) not in features.index:
        return null_with_reason("predicted_fee", "no_transfer_features")
    if not bool(features.loc[str(player_id), "_has_club_context"]):
        return null_with_reason("predicted_fee", "no_club_context")

    for c in [c for c in feature_cols if c not in features.columns]:
        features[c] = np.nan
    X = features.loc[[str(player_id)], feature_cols]
    predicted_fee = float(np.expm1(pipeline.predict(X))[0])  # REQUIRED unwrap -- predict() is log-scale

    market_value = players_df.loc[mask, "Market value"].iloc[0]
    labelled = add_value_labels(
        pd.DataFrame({"actual_fee": [market_value], "predicted_fee": [predicted_fee]})
    )
    verdict = labelled["value_verdict"].iloc[0]

    return {
        "predicted_fee": predicted_fee,
        "market_value": None if pd.isna(market_value) else float(market_value),
        "value_comparison": {
            "fee_diff": None
            if pd.isna(labelled["fee_diff"].iloc[0])
            else float(labelled["fee_diff"].iloc[0]),
            "ratio_market_to_predicted": None
            if pd.isna(labelled["fee_ratio_actual_to_pred"].iloc[0])
            else float(labelled["fee_ratio_actual_to_pred"].iloc[0]),
        },
        "value_verdict": None if pd.isna(verdict) else verdict,
        "buying_club": club_name,
    }


def _financial_fit_own_club(player_id, club_name: str) -> dict:
    """O(1) own-club Financial Fit: read the denormalized money-scale
    `Player.financial_fit_score` (written by `recompute_scores`, the same
    oracle orchestration Phase 5 proved) instead of running a full-population
    `build_oracle_player_features` pass per request.

    The own-club `predicted_fee` is exactly `Player.financial_fit_score`
    (already `np.expm1`-unwrapped to money scale at write time -- see
    recompute_scores.py:151). The value verdict/comparison are re-derived from
    that fee + the player's `market_value` via the SAME `add_value_labels`
    logic the live path uses, so the response shape is identical.

    Raises `Http404` if the player does not exist. Returns the shared
    null envelope if the player has no denormalized fee (structurally
    null -- should not occur for own-club players today, all 41,708 are
    non-null, but handled honestly rather than fabricated).
    """
    from players.models import Player

    row = (
        Player.objects.filter(id=player_id)
        .values("financial_fit_score", "market_value")
        .first()
    )
    if row is None:
        raise Http404(f"Player {player_id} not found")

    predicted_fee = row["financial_fit_score"]
    if predicted_fee is None:
        return null_with_reason("predicted_fee", "no_denormalized_fee")

    market_value = row["market_value"]
    labelled = add_value_labels(
        pd.DataFrame({"actual_fee": [market_value], "predicted_fee": [float(predicted_fee)]})
    )
    verdict = labelled["value_verdict"].iloc[0]

    return {
        "predicted_fee": float(predicted_fee),
        "market_value": None if pd.isna(market_value) else float(market_value),
        "value_comparison": {
            "fee_diff": None
            if pd.isna(labelled["fee_diff"].iloc[0])
            else float(labelled["fee_diff"].iloc[0]),
            "ratio_market_to_predicted": None
            if pd.isna(labelled["fee_ratio_actual_to_pred"].iloc[0])
            else float(labelled["fee_ratio_actual_to_pred"].iloc[0]),
        },
        "value_verdict": None if pd.isna(verdict) else verdict,
        "buying_club": club_name,
    }


def get_financial_fit(player_id, club_id) -> dict:
    """High-level entry point.

    Own-club fast path (the common case): read the denormalized money-scale
    `Player.financial_fit_score` -- a genuine O(1) indexed DB read, no
    full-population `build_oracle_player_features` pass, no TFM pipeline call.
    Arbitrary-other-club path (Phase 12's "rank clubs for a player"): the
    requested club overrides the player's buying context, so the fee genuinely
    differs and MUST be computed live -- but the ~74-115s upstream RMM/CS/TP
    pass is served from the memoized `get_scored_population()` (was a fresh
    `score_population(pop, None)`), so only the single-club TFM feature build
    runs live.

    Raises `Http404` if `club_id` is unknown or `player_id` doesn't resolve.
    """
    club_name = resolve_club_name(club_id)  # Http404 on unknown club

    if is_own_club(player_id, club_id):
        return _financial_fit_own_club(player_id, club_name)

    pop = reconstruct_population()
    scored, cs_tp = get_scored_population()
    return financial_fit_from_population(player_id, club_name, pop, scored, cs_tp)
