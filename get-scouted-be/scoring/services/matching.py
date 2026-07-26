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

from scoring.services.financial_fit import get_financial_fit

DEFAULT_TOP_N = 10


def rank_replacement_players(club_id, position: str, top_n: int = DEFAULT_TOP_N) -> dict:
    """PLAN-02 (Pattern 1): rank replacement players for a club's weak position.
    Implemented in 12-02-PLAN.md."""
    raise NotImplementedError


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
