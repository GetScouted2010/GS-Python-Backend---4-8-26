"""The Compatibility Score (CS) service -- SCORE-02 (CS via API) and its
slice of SCORE-05 (full breakdown).

The final `compatibility_score` is ALWAYS sourced from
`compute_cs_tp_for_pairs` (via `population.score_population`) -- never from
calling `role_fit.compatibility_score` directly -- so the NaN-role-fit guard
(clubs with all-NaN playing-style data force `compatibility_score` to NaN,
never a bonus-only fallback) is preserved.

CRITICAL wiring note (the bug this plan exists to fix): `compute_cs_tp_for_pairs`
computes its role fit over a MERGED frame --
`players_df.merge(role_scores_wide, on="player_id", how="left", suffixes=("", "_role"))`
(deterministic_scores.py:354) -- because `calculate_subjective_role_fit_for_player_to_team`
and `get_player_own_best_role` both read the player's role-score columns
(e.g. "Poacher", "Regista", ...) directly off the row (`role in
player_row.index`). `pop.players_df` alone carries NO role-score columns.
`get_compatibility` REPLICATES that exact merge before slicing the single
`player_row` the breakdown re-derivation reads -- slicing straight from
`pop.players_df` instead would make `get_player_own_best_role` always return
`(None, np.nan)` (bonus stuck at 70.0) and `normalize_role_vector_from_row`
empty (role_fit_score always None), silently contradicting the real
`compatibility_score` the same request returns.

`cs_breakdown_from_row(cs_tp_row, player_row, club_name, team_styles_df)` is
the reusable low-level piece Plan 05's summary endpoint imports directly --
callers are responsible for passing a `player_row` that already carries the
role-score columns (see `get_compatibility` below for how to build one).
"""

from __future__ import annotations

import pandas as pd
from django.http import Http404

from scoring.characterization.role_fit import (
    calculate_subjective_role_fit_for_player_to_team,
    get_player_own_best_role,
    normalise_position,
)
from scoring.exceptions import null_with_reason
from scoring.services.population import reconstruct_population, resolve_club_name, score_population


def cs_breakdown_from_row(
    cs_tp_row: pd.Series, player_row: pd.Series, club_name: str, team_styles_df: pd.DataFrame
) -> dict:
    """Build the CS breakdown dict from an already-scored cs_tp row plus a
    role-aware player_row.

    `player_row` MUST already carry the role-score columns (the caller --
    `get_compatibility` -- is responsible for the players_df/role_scores_wide
    merge; this helper does not perform it). `compute_cs_tp_for_pairs` only
    exposes the FINAL `compatibility_score`, not its 3 pre-average terms, so
    this re-derives `role_fit_score`/`bonus` with a second (pure, cheap) call
    to the same role-fit logic used internally -- `similarity_pct` is always
    None (Phase 3 scope gap: no target-player comparison pool).

    Returns the shared null envelope (never a fabricated value) when
    `compatibility_score` is NaN -- i.e. the resolved club has no usable
    playing-style data.
    """
    if pd.isna(cs_tp_row["compatibility_score"]):
        return null_with_reason("compatibility_score", "club_style_data_unavailable")

    position = normalise_position(player_row.get("Main_Position", player_row.get("Position", "")))
    rf = calculate_subjective_role_fit_for_player_to_team(player_row, club_name, team_styles_df)
    own_best_role, _ = get_player_own_best_role(player_row, position)
    role_fit_score = rf.get("Role Fit Score")
    bonus = 100.0 if rf.get("Best Team Fit Role", "") == own_best_role and own_best_role not in (None, "") else 70.0

    return {
        "compatibility_score": float(cs_tp_row["compatibility_score"]),
        "components": {
            "role_fit_score": None if pd.isna(role_fit_score) else float(role_fit_score),
            "similarity_pct": None,  # ALWAYS None -- Phase 3 scope gap (needs a target-player comparison pool)
            "bonus": bonus,
        },
    }


def get_compatibility(player_id, club_id) -> dict:
    """Return the real Compatibility Score + breakdown for a single
    player/club pair.

    Raises `Http404` if `club_id`/`player_id` is unresolvable.
    """
    club_name = resolve_club_name(club_id)

    pop = reconstruct_population()
    _, cs_tp = score_population(pop, club_name)

    # Replicate compute_cs_tp_for_pairs' internal merge (deterministic_scores.py:354)
    # so player_row carries the role-score columns the breakdown re-derivation
    # needs -- pop.players_df alone has none.
    players_with_roles = pop.players_df.merge(
        pop.role_scores_wide, on="player_id", how="left", suffixes=("", "_role")
    )

    players_with_roles["_pid_str"] = players_with_roles["player_id"].astype(str)
    match = players_with_roles[players_with_roles["_pid_str"] == str(player_id)]
    if match.empty:
        raise Http404(f"Player {player_id} not found")
    player_row = match.iloc[0]

    cs_tp_indexed_str = cs_tp.set_axis(cs_tp.index.astype(str))
    if str(player_id) not in cs_tp_indexed_str.index:
        raise Http404(f"Player {player_id} not found")
    cs_tp_row = cs_tp_indexed_str.loc[str(player_id)]

    return cs_breakdown_from_row(cs_tp_row, player_row, club_name, pop.team_styles_df)
