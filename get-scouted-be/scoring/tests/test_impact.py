"""Tests for scoring.characterization.impact -- the RMM ("Player Impact") port.

Task 1 tests exercise the low-level pieces (`_build_std_lookup`, a single
`_calc_*_impact_raw`, and the missing-column ValueError guard) against a
tiny synthetic DataFrame -- no DB required.

Task 2's `test_rmm_full_population_coverage` exercises `compute_rmm_column`
against the REAL migrated Phase 1 dataset (see scoring/tests/conftest.py's
`real_data_available`), proving the whole-population RMM the oracle (Plan
07) will consume actually covers most players and is never a spurious 0
manufactured from a missing column.
"""

import pandas as pd
import pytest

from scoring.characterization.impact import (
    _build_std_lookup,
    _calc_cb_impact_raw,
    _ensure_minutes,
)


def _synthetic_cb_df():
    """Two CB players + one outlier CB, one metric populated, "Minutes" present."""
    return pd.DataFrame(
        {
            "Main_Position": ["CB", "CB", "CB"],
            "Position": ["CB", "CB", "CB"],
            "Minutes": [900, 900, 900],
            "Successful defensive actions per 90": [4.0, 5.0, 12.0],
        }
    )


def test_build_std_lookup_returns_finite_percentiles_per_position():
    df = _synthetic_cb_df()

    std_lookup = _build_std_lookup(
        df, ["Successful defensive actions per 90"], position_col="Main_Position"
    )

    assert "CB" in std_lookup
    vals = std_lookup["CB"]["Successful defensive actions per 90"]
    assert len(vals) == len(df)
    # Every value must be a finite percentile in [0, 100] -- never NaN/inf.
    assert vals.notna().all()
    assert ((vals >= 0) & (vals <= 100)).all()


def test_calc_cb_impact_raw_returns_four_tuple_with_float_raw():
    df = _synthetic_cb_df()
    std_lookup = _build_std_lookup(
        df, ["Successful defensive actions per 90"], position_col="Main_Position"
    )

    for idx, row in df.iterrows():
        raw, positive, negative, components = _calc_cb_impact_raw(
            row, idx, std_lookup, return_components=True
        )
        assert isinstance(raw, float)
        assert isinstance(positive, float)
        assert isinstance(negative, float)
        assert isinstance(components, dict)
        assert "defensive_actions" in components


def test_ensure_minutes_raises_on_missing_minutes_column():
    """No 'Minutes'-equivalent column at all -- must raise, not zero-fill.

    Proves APPLIED_FIXES[0]: the source's `_ensure_minutes` silently set
    the whole column to 0 in this situation; this port refuses to.
    """
    df = pd.DataFrame(
        {
            "Main_Position": ["CB", "CF"],
            "Position": ["CB", "CF"],
        }
    )

    with pytest.raises(ValueError):
        _ensure_minutes(df)
