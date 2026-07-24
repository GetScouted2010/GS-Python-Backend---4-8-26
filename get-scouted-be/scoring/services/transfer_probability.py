"""The Transfer Probability (TP) service -- SCORE-04 (TP via API) and its
slice of SCORE-05 (full breakdown).

`get_transfer_probability` reads the already-computed deterministic
`transfer_probability` column off `compute_cs_tp_for_pairs`' output (via
`population.score_population`) and re-exposes its 4 weighted terms
(compatibility 0.30, performance 0.20, financial 0.20, contract_fit 0.30)
individually for explainability -- it never reimplements the tp math itself.

Unlike Compatibility Score, no role-column merge is needed here: the cs_tp
row already carries every column this service reads
(compatibility_score/performance_score/financial_score/contract_fit/
transfer_probability).

`tp_breakdown_from_row(cs_tp_row)` is the reusable low-level piece Plan 05's
summary endpoint imports directly.
"""

from __future__ import annotations

import pandas as pd
from django.http import Http404

from scoring.exceptions import null_with_reason
from scoring.services.population import (
    get_scored_population,
    is_own_club,
    reconstruct_population,
    resolve_club_name,
    score_population,
)

WEIGHTS = {"compatibility": 0.30, "performance": 0.20, "financial": 0.20, "contract_fit": 0.30}


def tp_breakdown_from_row(cs_tp_row: pd.Series) -> dict:
    """Build the TP breakdown dict from an already-scored cs_tp row.

    Returns the shared null envelope (never a fabricated value) when
    `transfer_probability` is NaN -- e.g. because one of its upstream terms
    (most commonly `performance_score`, from a NaN `player_impact`) was NaN
    and propagated through the deterministic formula.
    """
    tp = cs_tp_row.get("transfer_probability")
    if pd.isna(tp):
        return null_with_reason("transfer_probability", "insufficient_data")

    raw = {
        "compatibility": cs_tp_row["compatibility_score"],
        "performance": cs_tp_row["performance_score"],
        "financial": cs_tp_row["financial_score"],
        # x100 for display parity with the other 0-100 terms (contract_fit
        # itself is a 0-1 band value) -- documented here, not silently mixed
        # scales.
        "contract_fit": cs_tp_row["contract_fit"] * 100,
    }

    return {
        "transfer_probability": round(float(tp), 1),
        "components": {
            term: {
                "raw": None if pd.isna(raw[term]) else round(float(raw[term]), 2),
                "weight": WEIGHTS[term],
                "contribution": None if pd.isna(raw[term]) else round(float(raw[term]) * WEIGHTS[term], 2),
            }
            for term in WEIGHTS
        },
    }


def get_transfer_probability(player_id, club_id) -> dict:
    """Return the real deterministic Transfer Probability + its 4 weighted
    terms for a single player/club pair.

    Own-club fast path via the memoized `get_scored_population()` cs_tp;
    arbitrary-other-club fallback via a live `score_population(pop, club_name)`
    (same split as get_compatibility). O(1) on a warm process for the
    common own-club case.

    Raises `Http404` if `club_id`/`player_id` is unresolvable.
    """
    club_name = resolve_club_name(club_id)  # Http404 on unknown club

    pop = reconstruct_population()
    if is_own_club(player_id, club_id):
        _, cs_tp = get_scored_population()
    else:
        _, cs_tp = score_population(pop, club_name)

    cs_tp_indexed_str = cs_tp.set_axis(cs_tp.index.astype(str))
    if str(player_id) not in cs_tp_indexed_str.index:
        raise Http404(f"Player {player_id} not found")
    cs_tp_row = cs_tp_indexed_str.loc[str(player_id)]

    return tp_breakdown_from_row(cs_tp_row)
