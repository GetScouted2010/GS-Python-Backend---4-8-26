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

import numpy as np
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


# =========================================================================
# Tolerance comparator (both-null-aware) + mismatch-report writer
# =========================================================================

RMM_CS_TP_ATOL = 0.01
TFM_RTOL = 0.001


def compare_scalar(oracle_val, port_val, *, atol=None, rtol=None) -> bool:
    """Both-null-aware scalar tolerance comparison (05-CONTEXT.md locked
    policy):

    - both null -> pass (both sides correctly abstained)
    - exactly one null -> HARD failure (a fabricated-or-dropped value)
    - otherwise -> compare within atol (absolute) or rtol (relative)
    """
    o_null = oracle_val is None or (isinstance(oracle_val, float) and np.isnan(oracle_val)) or pd.isna(oracle_val)
    p_null = port_val is None or (isinstance(port_val, float) and np.isnan(port_val)) or pd.isna(port_val)
    if o_null and p_null:
        return True  # both abstained -> pass
    if o_null != p_null:
        return False  # one null, one not -> HARD failure (fabricated-or-dropped value)
    o, p = float(oracle_val), float(port_val)
    if atol is not None:
        return abs(o - p) <= atol
    if rtol is not None:
        return abs(o - p) <= rtol * abs(o)
    raise ValueError("compare_scalar requires exactly one of atol/rtol")


def compare_series(oracle: pd.Series, port: pd.Series, *, atol=None, rtol=None) -> pd.DataFrame:
    """Align `oracle` and `port` on their shared (string) index and compare
    row-by-row via `compare_scalar`. Callers must have already passed the
    port side through `to_str_index()` -- id-normalization responsibility
    stays in exactly one place, this function does not re-cast.

    Returns a DataFrame of ONLY the mismatched rows with columns
    ["player_id", "oracle", "port", "diff"] (diff = port - oracle where
    both non-null, else the string "null_mismatch"). An empty DataFrame
    means every row matched. Never raises -- the caller asserts on
    `len(result) == 0`.
    """
    shared_index = oracle.index.intersection(port.index)
    rows = []
    for pid in shared_index:
        o_val = oracle.loc[pid]
        p_val = port.loc[pid]
        if not compare_scalar(o_val, p_val, atol=atol, rtol=rtol):
            o_null = o_val is None or (isinstance(o_val, float) and np.isnan(o_val)) or pd.isna(o_val)
            p_null = p_val is None or (isinstance(p_val, float) and np.isnan(p_val)) or pd.isna(p_val)
            diff = "null_mismatch" if (o_null or p_null) else (float(p_val) - float(o_val))
            rows.append({"player_id": pid, "oracle": o_val, "port": p_val, "diff": diff})
    return pd.DataFrame(rows, columns=["player_id", "oracle", "port", "diff"])


def compare_tfm_series(oracle_log: pd.Series, port_money: pd.Series) -> pd.DataFrame:
    """TFM-specific convenience: the oracle `tfm` column is LOG-scale
    (13-17), while the per-request service's `predicted_fee` is already
    money-scale. This is the single place that reconciles the two scales
    (via `np.expm1` on the oracle side) -- no test file re-derives the
    conversion. Compares with rtol=TFM_RTOL (0.1%, money scale).
    """
    oracle_money = np.expm1(oracle_log)
    return compare_series(oracle_money, port_money, rtol=TFM_RTOL)


def write_mismatch_report(name: str, mismatches: pd.DataFrame) -> Path:
    """Write a per-group mismatch-detail report so a failing parity
    assertion gives a developer a debuggable CSV (player_id, score,
    oracle, port, diff) instead of a bare assert. Called by the caller's
    failing assertion; if `mismatches` is empty, still returns the path
    but does not write meaningful rows.
    """
    reports_dir = Path(__file__).resolve().parent / "_parity_reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{name}.csv"
    mismatches.to_csv(path, index=False)
    return path
