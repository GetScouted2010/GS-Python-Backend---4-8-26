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
    add_player_impact,
    compute_rmm_column,
)
from scoring.characterization.reconstruct import build_players_df

KNOWN_POSITION_GROUPS = {"GK", "CB", "LB", "RB", "CM", "DMF", "AMF", "LW", "RW", "CF"}


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


def test_add_player_impact_raises_on_missing_minutes_column():
    """The full add_player_impact wrapper propagates the same guard."""
    df = pd.DataFrame(
        {
            "Main_Position": ["CB", "CF"],
            "Position": ["CB", "CF"],
        }
    )

    with pytest.raises(ValueError):
        add_player_impact(df)


def test_add_player_impact_accepts_minutes_played_fallback():
    """A 'Minutes played' column (no bare 'Minutes') is still accepted."""
    df = pd.DataFrame(
        {
            "Main_Position": ["CB", "CB"],
            "Position": ["CB", "CB"],
            "Minutes played": [900, 450],
            "Successful defensive actions per 90": [4.0, 6.0],
            # add_player_impact's finishing_waste computation (verbatim from
            # source) reads these two columns unconditionally for every
            # position -- always present on the real reconstructed
            # players_df (FIELD_MAPPING.md _STAT_RENAME), included here so
            # this synthetic df matches that real contract.
            "xG per 90": [0.1, 0.2],
            "Non-penalty goals per 90": [0.05, 0.1],
        }
    )

    scored = add_player_impact(df)

    assert "Player Impact" in scored.columns
    assert scored["Minutes"].tolist() == [900, 450]


@pytest.mark.django_db
def test_rmm_full_population_coverage(real_data_available):
    """compute_rmm_column over the real reconstructed players_df.

    - non-empty
    - every value is in [0, 100] or NaN (never a spurious 0 for a player
      whose position/metrics were missing -- add_player_impact leaves
      unscored players as NaN, it never fabricates a 0)
    - most players (>50%) actually get scored
    - every main position group present in the real data has >=1 scored
      player (confirms population-relative, per-position percentiles are
      being computed across the whole df, not in isolation)

    NOTE (matches 03-01-SUMMARY.md's documented, expected precedent):
    pytest-django's `db`/`django_db` fixtures run against a fresh, empty
    test-database clone, entirely separate from the real dev DATABASE_URL
    database -- so this test skips cleanly under `pytest`. The real-data
    run (41,708 players, 41,707 scored -- 99.998% coverage, all 10 position
    groups covered, all values in [0.01, 100.0]) was additionally verified
    directly via `manage.py shell` against the real dev DB; see
    03-04-SUMMARY.md for the full output.
    """
    df = build_players_df()

    rmm = compute_rmm_column(df)

    assert not rmm.empty

    non_null = rmm.dropna()
    assert not non_null.empty
    assert ((non_null >= 0) & (non_null <= 100)).all()

    coverage_fraction = len(non_null) / len(rmm)
    assert coverage_fraction > 0.5, (
        f"Only {coverage_fraction:.1%} of players received an RMM value -- "
        "expected >50% coverage over the real population."
    )

    scored = add_player_impact(df)
    present_groups = set(scored["Main_Position"].dropna().unique()) & KNOWN_POSITION_GROUPS
    assert present_groups, "No recognised position groups found in real data"

    for pos in present_groups:
        group_scores = scored.loc[scored["Main_Position"] == pos, "Player Impact"]
        assert group_scores.notna().sum() >= 1, (
            f"Position group {pos!r} has zero scored players"
        )
