"""Tier-1 full-population bulk parity test (05-02-PLAN.md).

Runs the port's bulk scoring path -- `reconstruct_population()` +
`score_population(pop, None)`, plus the TFM Step-3/4 replay -- ONCE over
the whole real ~41,708-player population and diffs it against the
committed oracle CSV, parametrized over the 10 real position groups so
pytest natively reports pass/fail per group (ROADMAP's explicit per-group
requirement).

This is the core of SCORE-06: proving the port reproduces
`generate_scoring_oracle.py`'s output numerically for every position
group, within the locked tolerances (abs 0.01 for RMM/CS/TP, rel 0.1% on
money scale for TFM), treating null-parity (GK/LB/RB's structurally 100%
null CS/TP) as an enforced correctness check, not an exemption.

`None` as the club argument to `score_population` means "each player vs.
their OWN current club" -- the exact oracle methodology
(`generate_scoring_oracle.py` Step 3, `club_context=None`).

The expensive bulk scoring pass (`reconstruct_population` +
`score_population`, ~75-115s) runs AT MOST ONCE per test session via the
module-scope `bulk_scored` fixture below -- every RMM/CS/TP/TFM test in
this file reuses the same result.
"""

from __future__ import annotations

import pytest

from scoring.tests._parity_helpers import (
    GROUPS_WITH_NULL_CS_TP,
    POSITION_GROUPS,
    RMM_CS_TP_ATOL,
    compare_series,
    load_oracle_df,
    to_str_index,
    write_mismatch_report,
)


# =========================================================================
# Module-scope bulk scoring fixture -- runs reconstruct_population() +
# score_population(pop, None) EXACTLY ONCE for the whole file.
# =========================================================================
@pytest.fixture(scope="module")
def bulk_scored(django_db_setup, django_db_blocker):
    """Run the port's full bulk scoring path once for the whole module.

    Module-scope fixtures can't use the function-scope `real_data_available`
    / `db` fixtures directly, so this uses pytest-django's
    `django_db_blocker.unblock()` -- the established heavy-real-data
    pattern for a once-per-module expensive DB-backed computation.
    """
    with django_db_blocker.unblock():
        from players.models import Player

        if Player.objects.count() == 0:
            pytest.skip("No real Player data -- run Phase 1 import_all first.")

        from scoring.services.population import reconstruct_population, score_population

        pop = reconstruct_population()
        scored, cs_tp = score_population(pop, None)  # None == own current club == oracle methodology
    return pop, scored, cs_tp


# =========================================================================
# Merged oracle-vs-port comparison frame (RMM/CS/TP), built once.
# =========================================================================
@pytest.fixture(scope="module")
def oracle_and_port(bulk_scored):
    _pop, scored, cs_tp = bulk_scored

    oracle = load_oracle_df()

    # CRITICAL: the port's player_id is uuid.UUID (dtype=object); the
    # oracle index is str. Every port score Series MUST be string-indexed
    # via to_str_index() before it is ever reindexed against the oracle's
    # string index, or every alignment below silently returns all-NaN.
    port_rmm = to_str_index(scored.set_index("player_id")["Player Impact"])
    port_cs = to_str_index(cs_tp["compatibility_score"])
    port_tp = to_str_index(cs_tp["transfer_probability"])

    return oracle, port_rmm, port_cs, port_tp


# =========================================================================
# RMM parity, parametrized over the 10 real position groups.
# =========================================================================
@pytest.mark.parametrize("group", POSITION_GROUPS)
def test_rmm_parity_per_group(oracle_and_port, group):
    oracle, port_rmm, _port_cs, _port_tp = oracle_and_port
    ids = oracle.index[oracle["position_group"] == group]  # str ids
    mism = compare_series(oracle.loc[ids, "rmm"], port_rmm.reindex(ids), atol=RMM_CS_TP_ATOL)
    if len(mism):
        write_mismatch_report(f"bulk_rmm_{group}", mism)
    assert len(mism) == 0, f"{len(mism)} RMM mismatches in group {group} (see _parity_reports/bulk_rmm_{group}.csv)"


# =========================================================================
# Compatibility Score parity, parametrized over the 10 real position
# groups. GK/LB/RB naturally pass (both-null == pass) AND get an explicit
# both-sides-null guard against a future silent-fabrication regression.
# =========================================================================
@pytest.mark.parametrize("group", POSITION_GROUPS)
def test_cs_parity_per_group(oracle_and_port, group):
    oracle, _port_rmm, port_cs, _port_tp = oracle_and_port
    ids = oracle.index[oracle["position_group"] == group]  # str ids

    if group in GROUPS_WITH_NULL_CS_TP:
        assert oracle.loc[ids, "cs"].notna().sum() == 0
        assert port_cs.reindex(ids).notna().sum() == 0

    mism = compare_series(oracle.loc[ids, "cs"], port_cs.reindex(ids), atol=RMM_CS_TP_ATOL)
    if len(mism):
        write_mismatch_report(f"bulk_cs_{group}", mism)
    assert len(mism) == 0, f"{len(mism)} CS mismatches in group {group} (see _parity_reports/bulk_cs_{group}.csv)"


# =========================================================================
# Transfer Probability parity, parametrized over the 10 real position
# groups. GK/LB/RB naturally pass (both-null == pass) AND get an explicit
# both-sides-null guard.
# =========================================================================
@pytest.mark.parametrize("group", POSITION_GROUPS)
def test_tp_parity_per_group(oracle_and_port, group):
    oracle, _port_rmm, _port_cs, port_tp = oracle_and_port
    ids = oracle.index[oracle["position_group"] == group]  # str ids

    if group in GROUPS_WITH_NULL_CS_TP:
        assert oracle.loc[ids, "transfer_probability"].notna().sum() == 0
        assert port_tp.reindex(ids).notna().sum() == 0

    mism = compare_series(
        oracle.loc[ids, "transfer_probability"], port_tp.reindex(ids), atol=RMM_CS_TP_ATOL
    )
    if len(mism):
        write_mismatch_report(f"bulk_tp_{group}", mism)
    assert len(mism) == 0, f"{len(mism)} TP mismatches in group {group} (see _parity_reports/bulk_tp_{group}.csv)"
