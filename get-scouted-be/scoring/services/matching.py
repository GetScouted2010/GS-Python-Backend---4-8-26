"""Phase 12's two bidirectional-matching ranking services (12-01-PLAN.md).

Both directions -- `rank_replacement_players` (PLAN-02, Pattern 1: given a
club's weak position, rank candidate replacement players) and
`rank_clubs_for_player` (PLAN-04, Pattern 2: given a player, rank clubs that
fit them) -- MUST reuse the SAME low-level scoring primitives already proven
by Phase 3-6 (`compatibility_score` from `role_fit`, `financial_score` /
`transfer_probability` from `deterministic_scores`, `add_player_impact` for
RMM). Neither direction may re-derive its own copy of the CS/TFM/TP formula.

Both directions also share the SAME `_attach_real_tfm` helper below: real TFM
(predicted_fee/value_verdict, the trained sklearn pipeline) is attached ONLY
to the bounded top-N ranked results, never to the full unranked candidate set
-- attaching real TFM to thousands of players (PLAN-02) or ~1,060 clubs
(PLAN-04) per request would be prohibitively expensive. Ranking itself uses
the cheap `financial_score` label-average column instead (see
`deterministic_scores.compute_cs_tp_for_pairs`), which is intentionally kept
separate from the real-TFM `financial_fit` object this helper attaches.

No LLM call anywhere in this module.

`rank_replacement_players` (Pattern 1) is implemented per 12-02-PLAN.md and
`rank_clubs_for_player` (Pattern 2) is implemented per 12-03-PLAN.md, both
against the shared contract + the fully implemented shared enrichment
primitive established here.
"""

from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
from django.http import Http404

from scoring.characterization.deterministic_scores import (
    _years_left_from_contract_expires,
    classify_age_fit,
    classify_fit,
    contract_fit,
    financial_score,
    performance_score,
    transfer_probability,
)
from scoring.characterization.role_fit import (
    calculate_subjective_role_fit_for_player_to_team,
    compatibility_score,
    get_player_own_best_role,
    normalise_position,
)
from scoring.services.financial_fit import get_financial_fit
from scoring.services.population import (
    get_scored_population,
    reconstruct_population,
    resolve_club_name,
    score_population,
)

DEFAULT_TOP_N = 10


def _none_if_nan(v):
    """Return `None` for a genuinely-unresolvable pandas/NaN value, otherwise
    a plain `float`. Keeps unknowns visible as null rather than fabricating a
    number or silently dropping the candidate row (12-RESEARCH.md)."""
    if pd.isna(v):
        return None
    return float(v)


def rank_replacement_players(club_id, position: str, top_n: int = DEFAULT_TOP_N) -> dict:
    """PLAN-02 (Pattern 1): rank replacement players for a club's weak position.

    Reuses `score_population(pop, club_name)` wholesale -- the arbitrary-
    other-club live scoring pass Phase 6 explicitly deferred to this phase
    (~44.6s on the real dev DB, accepted/uncached, see 12-CONTEXT.md). Filters
    the full-population result to the requested `position`, excludes players
    already on the target club, sorts by `transfer_probability` (primary),
    and bounds to `top_n`. The REAL TFM (predicted_fee/value_verdict) is
    attached only to that bounded top-N via the shared `_attach_real_tfm`
    helper -- never to the full candidate set.
    """
    club_name = resolve_club_name(club_id)  # Http404 on unknown club
    pop = reconstruct_population()
    scored, cs_tp = score_population(pop, club_name)  # ~44.6s live, accepted, single pass

    scored = scored.copy()
    scored["_pid_str"] = scored["player_id"].astype(str)
    candidates = scored[
        (scored["Position"] == position)  # requested (weak) position filter
        & (scored["Team"] != club_name)  # exclude "already there"
    ]
    if candidates.empty:
        return {"club": club_name, "club_id": str(club_id), "position": position, "results": []}

    cs_tp_str = cs_tp.reset_index()
    cs_tp_str["_pid_str"] = cs_tp_str["player_id"].astype(str)
    ranked = candidates.merge(
        cs_tp_str[["_pid_str", "compatibility_score", "financial_score", "transfer_probability"]],
        on="_pid_str", how="left",
    ).sort_values(
        ["transfer_probability", "Player Impact", "compatibility_score"],  # TP primary; RMM/CS visible tiebreak/breakdown
        ascending=False, na_position="last",
    ).head(top_n)

    results = []
    for _, r in ranked.iterrows():
        results.append({
            "player_id": str(r["_pid_str"]),
            "name": r.get("Player") if "Player" in ranked.columns else None,
            "current_club": r.get("Team"),
            "position": r.get("Position"),
            "transfer_probability": _none_if_nan(r.get("transfer_probability")),
            "player_impact": _none_if_nan(r.get("Player Impact")),  # RMM breakdown
            "compatibility_score": _none_if_nan(r.get("compatibility_score")),  # CS breakdown
            "financial_score": _none_if_nan(r.get("financial_score")),  # cheap CS-formula term (NOT real TFM)
        })

    pairs = [(entry["player_id"], club_id) for entry in results]  # each candidate priced vs the TARGET club
    _attach_real_tfm(results, pairs)  # adds entry["financial_fit"] = {predicted_fee, value_verdict}

    return {"club": club_name, "club_id": str(club_id), "position": position, "results": results}


def rank_clubs_for_player(player_id, top_n: int = DEFAULT_TOP_N) -> dict:
    """PLAN-04 (Pattern 2): rank clubs that fit a given player.

    Reuses the low-level pure scoring functions directly -- `compatibility_score`
    (role_fit), `financial_score`/`transfer_probability` (deterministic_scores) --
    with `squad_stats` (avg age / avg market value per club) computed ONCE over
    the FULL population, then looked up O(1) per candidate club. This is the
    LOCKED correctness fix for a verified bug: slicing `players_df` to a single
    row before calling `compute_cs_tp_for_pairs` makes its internal
    `groupby("Team")` squad_stats contain ONLY the player's own club, silently
    NaN-ing `financial_score`/`transfer_probability` for every OTHER candidate
    (12-RESEARCH.md Pitfall 1). `compute_cs_tp_for_pairs` is never called here.

    Club-independent terms (player_impact/performance_score, own_best_role,
    contract_fit) are computed once; only role-fit/compatibility and the
    avg_age/avg_mv squad lookup vary per club. The player's own current club
    is excluded from the ranked results. Real TFM (predicted_fee/value_verdict)
    is attached only to the bounded top-N via the shared `_attach_real_tfm`
    helper.
    """
    pop = reconstruct_population()
    scored, _ = get_scored_population()  # memoized; "Player Impact" (RMM) is club-independent

    players_with_roles = pop.players_df.merge(
        pop.role_scores_wide, on="player_id", how="left", suffixes=("", "_role")
    )
    players_with_roles["_pid_str"] = players_with_roles["player_id"].astype(str)
    match = players_with_roles[players_with_roles["_pid_str"] == str(player_id)]
    if match.empty:
        raise Http404(f"Player {player_id} not found")
    player_row = match.iloc[0]
    own_club_name = player_row.get("Team")

    # --- club-INDEPENDENT terms: computed ONCE ---
    scored_str = scored.copy()
    scored_str["_pid_str"] = scored_str["player_id"].astype(str)
    impact_row = scored_str[scored_str["_pid_str"] == str(player_id)]
    player_impact_val = impact_row["Player Impact"].iloc[0] if not impact_row.empty else np.nan
    performance_val = performance_score(player_impact_val)

    position = normalise_position(player_row.get("Main_Position", player_row.get("Position", "")))
    own_best_role, own_best_score = get_player_own_best_role(player_row, position)

    years_left = _years_left_from_contract_expires(
        player_row.get("Contract expires"), datetime.date.today().year
    )
    contract_fit_val = contract_fit(years_left)

    # squad_stats computed ONCE over the FULL population -> correct avg for EVERY club
    squad_stats = (
        pop.players_df.groupby("Team")[["Age", "Market value"]].mean()
        .rename(columns={"Age": "_avg_age", "Market value": "_avg_mv"})
    )

    rows = []
    for _, team_row in pop.team_styles_df.iterrows():  # ~1,060 clubs -- cheap
        club_name = team_row["Team"]
        if club_name == own_club_name:
            continue  # exclude "already there"

        role_fit_info = calculate_subjective_role_fit_for_player_to_team(
            player_row, club_name, pop.team_styles_df
        )
        if pd.isna(role_fit_info.get("Role Fit Score", np.nan)):
            compat_val = np.nan  # unresolved role fit -> null, never a bonus-only 70
        else:
            bonus = 100.0 if (
                role_fit_info.get("Best Team Fit Role", "") == own_best_role
                and own_best_role not in (None, "")
            ) else 70.0
            compat_val = compatibility_score(role_fit_info["Role Fit Score"], np.nan, bonus)

        if club_name in squad_stats.index:
            avg_age = squad_stats.loc[club_name, "_avg_age"]
            avg_mv = squad_stats.loc[club_name, "_avg_mv"]
        else:
            avg_age, avg_mv = np.nan, np.nan

        age_fit_label = classify_age_fit(player_row.get("Age"), avg_age)
        mv_fit_label = (
            classify_fit(player_row.get("Market value"), avg_mv, avg_mv * 0.25, avg_mv * 0.5)
            if pd.notna(avg_mv) else "Unknown"
        )
        financial_val = financial_score(age_fit_label, mv_fit_label)
        tp_val = transfer_probability(compat_val, performance_val, financial_val, contract_fit_val)

        rows.append({
            "club": club_name,
            "transfer_probability": _none_if_nan(tp_val),
            "compatibility_score": _none_if_nan(compat_val),  # CS breakdown
            "financial_score": _none_if_nan(financial_val),  # cheap CS-formula term (NOT real TFM)
            "player_impact": _none_if_nan(player_impact_val),  # RMM breakdown (club-independent)
        })

    ranked = pd.DataFrame(rows).sort_values(
        ["transfer_probability", "compatibility_score"], ascending=False, na_position="last"
    ).head(top_n)
    return {"player_id": str(player_id), "results": ranked.to_dict("records")}


def _attach_real_tfm(entries, pairs, key: str = "financial_fit"):
    """Attach the REAL ML Financial Fit (TFM) to a bounded top-N only.

    `entries`: list of already-ranked result dicts (the top-N).
    `pairs`:   list of (player_id, club_id) aligned 1:1 with `entries`
               (player_id/club_id are the (player, buying-club) context each
               entry is priced under). MUST already be sliced to the top-N.

    For each entry, call get_financial_fit(player_id, club_id) once and attach
    entry[key] = {"predicted_fee": ..., "value_verdict": ...} read off its result
    (get_financial_fit returns a null_with_reason envelope when it cannot compute a
    fee -- .get() the keys so a missing predicted_fee surfaces as None, never raises).

    This helper is the ONLY place either direction calls the real TFM pipeline, so
    the number of TFM calls equals len(entries) == top_n by construction -- never the
    full candidate set (thousands for PLAN-02, ~1,060 for PLAN-04).
    """
    for entry, (player_id, club_id) in zip(entries, pairs):
        ff = get_financial_fit(player_id, club_id)
        entry[key] = {
            "predicted_fee": ff.get("predicted_fee"),
            "value_verdict": ff.get("value_verdict"),
        }
    return entries
