"""The combined Player Profile summary orchestrator (04-05-PLAN.md) --
SCORE-01 through SCORE-05 in ONE response for the PRD Player Profile page.

`get_summary(player_id, club_id)` reuses every per-score helper Plans
02-04 already expose (`rmm_breakdown_from_scored`, `cs_breakdown_from_row`,
`tp_breakdown_from_row`, `financial_fit_from_population`) off a SINGLE
reconstruction + scoring pass -- the RMM-first sequencing Plan 01's
`population.py` documents runs exactly once here too, never once per
sub-score (that would be 4x the reconstruction cost of the per-score
endpoints combined).

CRITICAL wiring note (the same bug class Plan 03's `get_compatibility`
exists to fix, replicated here verbatim): `cs_breakdown_from_row`
re-derives `role_fit_score`/`bonus` by reading the player's role-score
columns OFF `player_row` (`role in player_row.index`). `pop.players_df`
alone carries NO role-score columns -- slicing `player_row` straight from
it would make the compatibility breakdown's `role_fit_score`/`bonus`
silently disagree with the real `compatibility_score` `cs_tp` returns.
`get_summary` merges `pop.players_df` with `pop.role_scores_wide`
(deterministic_scores.py:354's own internal merge pattern) BEFORE slicing
`player_row`, exactly like `get_compatibility` does.

`financial_fit` reuses the summary's own already-computed `scored`/`cs_tp`
(via `financial_fit_from_population`) rather than calling the high-level
`get_financial_fit`, which would reconstruct + re-score the whole
population again. This means the summary's 4 upstream TFM features
(player_impact/compatibility_score/performance_score/role_pct) are
computed in `club_name`'s context (the summary's single-club framing)
rather than the standalone Financial Fit endpoint's own-club context -- an
accepted within-scope efficiency reuse for this convenience aggregation.

Each of the 4 sub-score helpers already returns its own null+reason
envelope when its data is missing -- `get_summary` does NOT wrap them in a
broad try/except that would swallow genuine reconstruction `ValueError`s.
"""

from __future__ import annotations

from django.http import Http404

from scoring.services.compatibility import cs_breakdown_from_row
from scoring.services.financial_fit import _financial_fit_own_club, financial_fit_from_population
from scoring.services.population import (
    get_scored_population,
    group_for_player,
    is_own_club,
    reconstruct_population,
    resolve_club_name,
    score_population,
)
from scoring.services.rmm import rmm_breakdown_from_scored
from scoring.services.transfer_probability import tp_breakdown_from_row


def get_summary(player_id, club_id) -> dict:
    """Return all four scores (RMM, Compatibility, Financial Fit, Transfer
    Probability) + their full breakdowns for a single player/club pair, in
    one response -- the PRD Player Profile page's combined view.

    Reconstructs the population and runs the RMM-first `score_population`
    sequence exactly ONCE, then slices/reuses the results for every
    sub-score helper -- never re-reconstructing per score.

    Raises `Http404` if `club_id`/`player_id` is unresolvable.
    """
    club_name = resolve_club_name(club_id)  # Http404 on unknown club

    group = group_for_player(player_id)  # ranked in the player's season's population
    pop = reconstruct_population(group)
    own = is_own_club(player_id, club_id)
    if own:
        scored, cs_tp = get_scored_population(group)
    else:
        scored, cs_tp = score_population(pop, club_name)

    # Replicate compute_cs_tp_for_pairs' internal merge (deterministic_scores.py:354)
    # so player_row carries the role-score columns cs_breakdown_from_row's
    # role_fit_score/bonus re-derivation needs -- pop.players_df alone has none.
    players_with_roles = pop.players_df.merge(
        pop.role_scores_wide, on="player_id", how="left", suffixes=("", "_role")
    )
    players_with_roles["_pid_str"] = players_with_roles["player_id"].astype(str)
    player_match = players_with_roles[players_with_roles["_pid_str"] == str(player_id)]
    if player_match.empty:
        raise Http404(f"Player {player_id} not found")
    player_row = player_match.iloc[0]

    scored_indexed = scored.copy()
    scored_indexed["_pid_str"] = scored_indexed["player_id"].astype(str)
    scored_match = scored_indexed[scored_indexed["_pid_str"] == str(player_id)]
    if scored_match.empty:
        raise Http404(f"Player {player_id} not found")
    scored_row = scored_match.iloc[0]

    cs_tp_indexed_str = cs_tp.set_axis(cs_tp.index.astype(str))
    if str(player_id) not in cs_tp_indexed_str.index:
        raise Http404(f"Player {player_id} not found")
    cs_tp_row = cs_tp_indexed_str.loc[str(player_id)]

    # Financial Fit: own-club reads the denormalized O(1) field; arbitrary
    # club re-uses this summary's own scored/cs_tp (no extra reconstruction),
    # matching the prior within-scope efficiency reuse.
    if own:
        financial = _financial_fit_own_club(player_id, club_name)
    else:
        financial = financial_fit_from_population(player_id, club_name, pop, scored, cs_tp)

    return {
        "rmm": rmm_breakdown_from_scored(scored_row),
        "compatibility": cs_breakdown_from_row(cs_tp_row, player_row, club_name, pop.team_styles_df),
        "financial_fit": financial,
        "transfer_probability": tp_breakdown_from_row(cs_tp_row),
    }
