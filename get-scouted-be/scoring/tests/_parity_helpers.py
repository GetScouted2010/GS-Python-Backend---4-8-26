"""Shared substrate for Phase 5's oracle-vs-port parity test files.

`_parity_helpers.py` is a plain importable module (NOT a conftest). The
three parity test files (Plans 02-04: bulk, API-sample, edge-cases) import
from here rather than each re-implementing oracle discovery, oracle
loading, id-casting, tolerance comparison, or mismatch reporting. Keeping
these in exactly one place means the tolerance semantics, the UUID->str
id-alignment convention, and the "both-null is a pass, one-null is a hard
failure" invariant (05-CONTEXT.md locked decision) can never drift between
parity files.

Critical corrections this module encodes (verified live against the real
oracle CSV / dev DB during Phase 5 planning, 2026-07-24):

1. The oracle CSV's `tfm` column is LOG-SCALE (range 13.11-17.09), not
   money-scale -- `generate_scoring_oracle.py` writes the raw
   `pipeline.predict(X)` output with no `np.expm1`. `compare_tfm_series`
   (added in Task 2) converts the oracle side to money scale via
   `np.expm1` before comparing against the port's already-money-scale
   value.
2. There are 10 real `normalise_position()` groups (GK, CB, LB, RB, CM,
   DMF, AMF, LW, RW, CF), not 8. GK, LB, RB have structurally 100% null
   cs/transfer_probability across the whole population -- that is the
   correct current state, not a bug.
3. The port's `player_id` column holds `uuid.UUID` objects (dtype=object);
   the oracle CSV's `player_id`, loaded via `pd.read_csv`, is plain `str`.
   Every Phase 4 service already does `.astype(str)` on `player_id`/
   `cs_tp.index` before any lookup/merge against a string-keyed structure
   -- this is an established, load-bearing codebase convention. Every port
   score Series MUST be passed through `to_str_index()` before being
   reindexed against / compared to the oracle, or every alignment silently
   returns NaN.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from scoring.characterization.impact import normalise_position

ORACLE_DIR = Path(__file__).resolve().parents[1] / "oracle"

# The 10 real normalise_position() groups (verified live 2026-07-24).
POSITION_GROUPS = ["GK", "CB", "LB", "RB", "CM", "DMF", "AMF", "LW", "RW", "CF"]

# Structurally 100% null cs/transfer_probability across all 41,708 players
# -- correct current state, not a bug.
GROUPS_WITH_NULL_CS_TP = {"GK", "LB", "RB"}

ORACLE_COLUMNS = [
    "player_id",
    "player_name",
    "main_position",
    "rmm",
    "cs",
    "tfm",
    "transfer_probability",
]


def find_latest_oracle_csv() -> Path | None:
    """Version-agnostic discovery of the newest oracle CSV.

    Never hardcodes a filename -- globs `scoring_oracle_v1_*.csv` under
    scoring/oracle/ and returns the lexicographically-last match (the
    oracle filenames embed an ISO date, so sort order == recency order).
    Returns None if the oracle directory doesn't exist or has no CSVs yet.
    """
    if not ORACLE_DIR.exists():
        return None
    candidates = sorted(ORACLE_DIR.glob("scoring_oracle_v1_*.csv"))
    return candidates[-1] if candidates else None


def to_str_index(obj):
    """Return a Series/DataFrame whose index is cast to str, so a UUID-object-dtype
    port index aligns with the oracle's string player_id index. Mirrors the .astype(str)
    id-cast convention in rmm.py/compatibility.py/summary.py/financial_fit.py/
    transfer_probability.py -- Plans 02/03/04 pass every port score Series through this
    BEFORE reindexing/comparing against the string-keyed oracle."""
    return obj.set_axis(obj.index.astype(str))


def load_oracle_df() -> pd.DataFrame:
    """Load the latest oracle CSV into a DataFrame with a canonical
    `position_group` column (derived via the port's own
    `normalise_position()` -- single source of truth, no hand-rolled
    mapping dict) and a string `player_id` index.

    Skips the calling test (rather than failing/erroring) if no oracle CSV
    has been generated yet.
    """
    path = find_latest_oracle_csv()
    if path is None:
        pytest.skip(
            "No oracle CSV in scoring/oracle/ -- run "
            "`python manage.py generate_scoring_oracle` first."
        )
    df = pd.read_csv(path)
    df["position_group"] = df["main_position"].apply(normalise_position)
    df["player_id"] = df["player_id"].astype(str)
    return df.set_index("player_id", drop=False)
