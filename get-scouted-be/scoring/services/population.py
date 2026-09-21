"""The shared reconstruct -> RMM-first-score substrate every Phase 4 score
service (compatibility, financial, performance, transfer-probability,
summary) stands on.

SCORING POPULATIONS. Impact is a percentile rank within position over a
population, so which players share one decides every number. Players are
therefore ranked in the population of THEIR season (players/season.py): the
legacy pool of the four older seasons (exactly as it always was), and
2025-2026 on its own -- how the data provider computes that season, and what
reproduces its exported impact almost exactly. Every entry point below takes a
`group`; services derive it from the player (`group_for_player`). Adding a
season as its own population never moves another population's scores.

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

from players.season import LEGACY_SCORING_GROUP, scoring_group, scoring_groups
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


@lru_cache(maxsize=None)
def _reconstruct_population(group: str) -> Population:
    return Population(
        players_df=build_players_df(group),
        role_scores_wide=build_role_scores_wide(group),
        team_styles_df=build_team_styles_df(),
        transfers_df=build_transfers_df(),
    )


def reconstruct_population(group: str = LEGACY_SCORING_GROUP) -> Population:
    """Build the four script-shaped DataFrames for one scoring population from
    the ORM, once per process per group (memoized -- see
    `clear_scoring_caches()`).

    `group` (players/season.py) is the population players are ranked in: the
    default is the legacy pool of older seasons; a season in
    OWN_POPULATION_SEASONS is ranked only against itself. Team styles and
    transfers are club-level and shared by every group.

    The single reconstruction point every downstream score service reuses
    instead of independently calling `characterization.reconstruct`'s
    `build_*` functions (which each re-query the DB). Subsequent calls in
    the same process return the cached result instead of re-querying
    Postgres; call `clear_scoring_caches()` after a data refresh to force a
    fresh rebuild.
    """
    return _reconstruct_population(group)


reconstruct_population.cache_clear = _reconstruct_population.cache_clear
reconstruct_population.cache_info = _reconstruct_population.cache_info


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


@lru_cache(maxsize=None)
def _get_scored_population(group: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    return score_population(_reconstruct_population(group), None)


def get_scored_population(group: str = LEGACY_SCORING_GROUP) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Memoized own-club (club_context=None) whole-population scoring of one
    scoring population.

    Runs score_population(reconstruct_population(group), None) at most once per
    process per group -- the ~74-115s legacy pass, or the shorter pass for a
    smaller season population -- and hands back the cached (scored, cs_tp)
    every subsequent call. This is the precomputed aggregate SCORE-07 Success
    Criterion 2 requires: the recompute_scores command (writes the denormalized
    Player fields) and any own-club live path both read this instead of
    re-scoring the whole population per request.

    Invalidated by clear_scoring_caches() after a data refresh. Callers
    MUST treat the returned DataFrames as read-only (copy/merge before
    mutating), exactly as reconstruct_population's callers already do.
    """
    return _get_scored_population(group)


get_scored_population.cache_clear = _get_scored_population.cache_clear
get_scored_population.cache_info = _get_scored_population.cache_info


def group_for_player(player_id) -> str:
    """The scoring population a player is ranked in, from their season.

    A cheap indexed single-row lookup. An unknown player resolves to the
    legacy group, where the service's own population lookup then raises the
    real Http404 -- same as before groups existed.
    """
    from players.models import Player

    season = Player.objects.filter(id=player_id).values_list("season", flat=True).first()
    return scoring_group(season)


def group_has_players(group: str) -> bool:
    """Whether a scoring population has any players at all. A group can be
    empty (a fresh environment before a season is imported); scoring one
    would raise, so callers that loop over every group skip it."""
    from players.models import Player
    from players.season import filter_to_scoring_group

    return filter_to_scoring_group(Player.objects.all(), group).exists()


def warm_scoring_caches() -> None:
    """Build and score every scoring population, then load the TFM pipeline.

    What each gunicorn worker does at boot (config/gunicorn.conf.py) so no
    request pays the cold cost. Legacy first: it is the largest. A group with no
    players yet is skipped rather than crashing the worker at boot.
    """
    for group in scoring_groups():
        if group_has_players(group):
            get_scored_population(group)
    get_tfm_pipeline()


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


def get_own_club_id(player_id):
    """Return the player's OWN current club_id (a Club UUID) or None.

    A cheap, indexed single-row PK lookup -- the O(1) primitive the live
    score services use to decide between the own-club fast path (read the
    memoized get_scored_population() aggregate / denormalized Player field)
    and the arbitrary-other-club live path (score_population(pop, name)).
    Returns None if the player has no club (SET_NULL FK) or does not exist;
    callers treat "no own club" as "not the requested club" and fall through
    to the live path, which then raises the real Http404.
    """
    from players.models import Player

    return Player.objects.filter(id=player_id).values_list("club_id", flat=True).first()


def is_own_club(player_id, club_id) -> bool:
    """True iff `club_id` is the player's OWN current club.

    The own-club case is the common one (Phase 4's default context, the one
    Phase 5's oracle proved) and the one served from the precomputed
    aggregate / denormalized fields. String-compare so a UUID object and its
    URL string form match.
    """
    own = get_own_club_id(player_id)
    return own is not None and str(own) == str(club_id)


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


def clear_scoring_caches() -> None:
    """Invalidate every in-process scoring aggregate cache so the next
    call rebuilds against fresh data. Call this after any data refresh
    (Phase 1's import_all) and at the end of the recompute_scores command.
    Does NOT clear get_tfm_pipeline -- the joblib artifact only changes via
    train_tfm_model, not a data refresh."""
    reconstruct_population.cache_clear()
    get_scored_population.cache_clear()
