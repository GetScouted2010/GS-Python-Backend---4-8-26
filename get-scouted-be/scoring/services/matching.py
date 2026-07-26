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

Implementation of the two ranking functions lands in later plans:
`rank_replacement_players` in 12-02-PLAN.md, `rank_clubs_for_player` in
12-03-PLAN.md. This module only establishes the shared contract + the fully
implemented shared enrichment primitive.
"""

from __future__ import annotations

import pandas as pd

from scoring.services.financial_fit import get_financial_fit
from scoring.services.population import reconstruct_population, resolve_club_name, score_population

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
    Implemented in 12-03-PLAN.md."""
    raise NotImplementedError


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
