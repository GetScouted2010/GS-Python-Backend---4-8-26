"""The shared reconstruct -> RMM-first-score substrate every Phase 4 score
service (compatibility, financial, performance, transfer-probability,
summary) stands on.

Centralizes:

    - `reconstruct_population()`: the single ORM -> script-shaped-DataFrame
      reconstruction point (wraps `characterization.reconstruct`'s four
      `build_*` functions), called once per request instead of once per
      score.
    - `score_population(pop, club_name)`: the canonical RMM-first scoring
      sequence proven correct by Phase 3's `generate_scoring_oracle.py` --
      `add_player_impact` (RMM) runs FIRST and is explicitly merged onto
      `players_df` as `player_impact` BEFORE `compute_cs_tp_for_pairs` is
      called (that function raises `ValueError` if `player_impact` is
      missing -- this ordering is load-bearing, never reorder it).
    - `resolve_club_name(club_id)`: the one place a club UUID is turned into
      the `Club.name` string every characterization function actually reads
      -- no characterization code ever receives a UUID.
    - `get_tfm_pipeline()`: the memoized TFM joblib artifact loader, whose
      authoritative `feature_cols` always come from the `.metrics.json`
      sidecar, never a hardcoded list.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from scoring.characterization.deterministic_scores import compute_cs_tp_for_pairs
from scoring.characterization.impact import add_player_impact
from scoring.characterization.reconstruct import (
    build_players_df,
    build_role_scores_wide,
    build_team_styles_df,
    build_transfers_df,
)


class Population(NamedTuple):
    """The four script-shaped DataFrames every score service needs, built
    once from the ORM by `reconstruct_population()`."""

    players_df: pd.DataFrame
    role_scores_wide: pd.DataFrame
    team_styles_df: pd.DataFrame
    transfers_df: pd.DataFrame


def reconstruct_population() -> Population:
    """Build the four script-shaped DataFrames from the ORM, once.

    The single reconstruction point every downstream score service reuses
    instead of independently calling `characterization.reconstruct`'s
    `build_*` functions (which each re-query the DB).
    """
    return Population(
        players_df=build_players_df(),
        role_scores_wide=build_role_scores_wide(),
        team_styles_df=build_team_styles_df(),
        transfers_df=build_transfers_df(),
    )


def score_population(pop: Population, club_name: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the canonical RMM-first scoring sequence against `pop`.

    Replicates `generate_scoring_oracle.py`'s proven order EXACTLY:

        1. `add_player_impact` computes RMM (and its full breakdown --
           "Player Impact", "Player Impact Positive/Negative",
           "Impact Reliability", "Impact Comp - <name>" columns) over the
           WHOLE players_df, not just the thin `compute_rmm_column` value,
           since summary/RMM downstream services need the breakdown.
        2. The resulting "Player Impact" series is merged onto a copy of
           `pop.players_df` as `player_impact` BEFORE `compute_cs_tp_for_pairs`
           is called -- that function REQUIRES `player_impact` and raises
           `ValueError` if it's `None`. This ordering is load-bearing; never
           call `compute_cs_tp_for_pairs` before this merge.

    Args:
        pop: a `Population` from `reconstruct_population()`.
        club_name: the target club NAME (not a UUID -- see
            `resolve_club_name`) every player's CS/TP is computed against,
            or `None` to evaluate each player against their own current
            club.

    Returns:
        `(scored, cs_tp)` -- `scored` is `pop.players_df` + RMM's full
        breakdown columns (from `add_player_impact`); `cs_tp` is
        `compute_cs_tp_for_pairs`' per-player result (indexed by
        player_id; columns: club_context, compatibility_score,
        financial_score, performance_score, contract_fit, role_pct,
        transfer_probability).
    """
    scored = add_player_impact(pop.players_df.copy())
    rmm_series = scored.set_index("player_id")["Player Impact"]

    players_df = pop.players_df.copy()
    players_df["player_impact"] = players_df["player_id"].map(rmm_series)

    cs_tp = compute_cs_tp_for_pairs(
        players_df,
        pop.team_styles_df,
        pop.role_scores_wide,
        club_context=club_name,
        player_impact=rmm_series,
    )

    return scored, cs_tp


def resolve_club_name(club_id) -> str:
    """Resolve a Club UUID to its `name` string, raising `Http404` if
    unknown.

    The one place a club UUID is ever turned into the name string every
    characterization function actually reads -- no characterization code
    downstream of this call ever receives a UUID.
    """
    from django.shortcuts import get_object_or_404

    from clubs.models import Club

    return get_object_or_404(Club, id=club_id).name


def _tfm_artifact_path() -> Path:
    from django.conf import settings

    return Path(settings.BASE_DIR) / "scoring" / "ml_artifacts" / "tfm_value_model_v1.joblib"


def _tfm_metrics_path() -> Path:
    return _tfm_artifact_path().with_suffix("").with_suffix(".metrics.json")


@lru_cache(maxsize=1)
def get_tfm_pipeline() -> tuple[object, list[str]]:
    """Load the trained TFM joblib Pipeline at most once (memoized).

    `feature_cols` always come from the `.metrics.json` sidecar -- the
    authoritative source of the 23 feature names -- never a hardcoded list.
    """
    import joblib

    pipeline = joblib.load(_tfm_artifact_path())
    with open(_tfm_metrics_path()) as f:
        feature_cols = json.load(f)["feature_cols"]

    return pipeline, feature_cols
