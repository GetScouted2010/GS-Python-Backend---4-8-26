"""The RMM (Player Impact) service -- SCORE-01 (RMM via API) and its slice
of SCORE-05 (full breakdown).

The only Phase 4 score needing no club context: a plain player-scoped
calculation. Reads the breakdown directly off `add_player_impact`'s output
columns -- the oracle's thin RMM-only convenience wrapper is deliberately
never used here, since it discards the components SCORE-05 requires.

`rmm_breakdown_from_scored(row)` is the reusable piece Plan 05's summary
endpoint imports directly (an already-scored pandas row -> the same
breakdown dict) without re-reconstructing the population.
"""

from __future__ import annotations

import pandas as pd
from django.http import Http404

from scoring.exceptions import null_with_reason
from scoring.services.population import get_scored_population


def rmm_breakdown_from_scored(row: pd.Series) -> dict:
    """Build the RMM breakdown dict from an already-scored pandas row.

    `row` is a row from `add_player_impact`'s output (i.e. carries "Player
    Impact", "Player Impact Positive/Negative", "Impact Reliability", and
    the position-keyed "Impact Comp - <name>" columns). Returns the shared
    null envelope (never a fabricated 0) when "Player Impact" is NaN.
    """
    impact = row["Player Impact"]
    if pd.isna(impact):
        return null_with_reason("rmm", "insufficient_player_data")

    comp_cols = [c for c in row.index if c.startswith("Impact Comp - ")]

    return {
        "rmm": float(impact),
        "positive": None if pd.isna(row.get("Player Impact Positive")) else float(row["Player Impact Positive"]),
        "negative": None if pd.isna(row.get("Player Impact Negative")) else float(row["Player Impact Negative"]),
        "components": {c.removeprefix("Impact Comp - "): float(row[c]) for c in comp_cols if pd.notna(row[c])},
        # "Impact Reliability" is a categorical string ("Very Low"/"Low"/
        # "Medium"/"High" -- see impact.py's `_reliability_flag`), never a
        # number -- do NOT float() it.
        "reliability": None if pd.isna(row.get("Impact Reliability")) else row["Impact Reliability"],
    }


def get_rmm(player_id) -> dict:
    """Return the real computed RMM (Player Impact) + full breakdown for a
    single player.

    O(1) on a warm process: reads the memoized `get_scored_population()`
    `scored` frame (which is `add_player_impact(...)` over the whole
    population, computed at most once per process) and slices the single
    player's row -- it does NOT run a fresh full-population `add_player_impact`
    pass per request (the pre-Phase-6 behavior the verifier measured at 9.15s).
    RMM is position-relative and context-free, so there is no own-club/other-club
    branch here. The breakdown is still complete: `scored` carries every
    "Impact Comp - <name>" / "Player Impact *" column `rmm_breakdown_from_scored`
    reads.

    Raises `Http404` if `player_id` is absent from the population.
    """
    scored, _cs_tp = get_scored_population()

    # players_df's "player_id" holds Player UUID objects; the URL id arrives
    # as a string -- coerce both to str before matching.
    scored = scored.copy()
    scored["_pid_str"] = scored["player_id"].astype(str)
    match = scored[scored["_pid_str"] == str(player_id)]

    if match.empty:
        raise Http404(f"Player {player_id} not found")

    return rmm_breakdown_from_scored(match.iloc[0])
