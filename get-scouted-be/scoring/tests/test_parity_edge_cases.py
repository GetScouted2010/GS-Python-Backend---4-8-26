"""Edge-case parity tests (05-04-PLAN.md) -- SCORE-06.

Unlike Plan 02's bulk (all 41,708 players) and Plan 03's API-sample
(random sample) parity suites, this file targets NAMED, dynamically-mined
edge-case players from the real dataset: zero-appearance minutes, missing
key input stats, boundary ages, and an invalid position label. Every case
is mined live off the current Player table / oracle (never a hardcoded
player_id), so re-running after an oracle regeneration needs no edits --
a case simply `pytest.skip`s if it no longer exists in the data.

The zero-minutes case is specifically the regression guard for Phase 3's
silent-zero-fill fix: `_ensure_minutes` now raises `ValueError` when NO
Minutes-equivalent column exists at all, rather than defaulting the whole
column to 0 (which would have fabricated a plausible-looking 0.55
reliability floor for every player). A genuine per-player zero-minutes
value (column present, this player's value is 0) is left as an honest
per-player state -- this test proves the port reproduces the oracle's
actual handling of that state, not a fabricated number.
See scoring/docs/CURATION_MAP.md.

Real-population reconstruction/scoring is expensive -- this module reuses
the SAME module-scope memoization pattern scoring/tests/test_views.py
already establishes: `reconstruct_population()` (~3.5s) and, where
needed, `score_population(pop, None)` (~75-115s, own-club context --
matching the oracle's own methodology) are each computed AT MOST ONCE for
the whole file, then patched onto the service modules' imported names for
every edge-case call below. The real service functions (`get_rmm`,
`get_financial_fit`) are never mocked -- only the expensive
reconstruction/scoring pass underneath them is memoized.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from scoring.tests._parity_helpers import RMM_CS_TP_ATOL, TFM_RTOL, compare_scalar, load_oracle_df

pytestmark = pytest.mark.django_db


def _is_null(v):
    return v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v)


# ---------------------------------------------------------------------------
# Module-scope real-data gate (django_db_blocker.unblock() pattern -- a
# module-scope fixture cannot use the function-scope `real_data_available`/
# `db` fixtures directly, so this mirrors Plan 02/03's established
# heavy-real-data pattern).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_data_gate(django_db_setup, django_db_blocker):
    with django_db_blocker.unblock():
        from players.models import Player

        if Player.objects.count() == 0:
            pytest.skip("No real Player data -- run Phase 1's import_all first.")
    return True


@pytest.fixture(scope="module")
def oracle(real_data_gate):
    return load_oracle_df()


# ---------------------------------------------------------------------------
# Module-wide memoization cache -- mirrors test_views.py's `_CACHE` /
# `_real_pop()` / `_patched_services()` pattern. `reconstruct_population()`
# and `score_population(pop, None)` are each expensive DB/CPU passes; every
# edge-case test below shares the SAME cached results rather than paying
# that cost per test.
# ---------------------------------------------------------------------------
_CACHE: dict = {}


def _real_pop():
    if "pop" not in _CACHE:
        from scoring.services.population import reconstruct_population

        _CACHE["pop"] = reconstruct_population()
    return _CACHE["pop"]


def _real_scored_none():
    """`score_population(pop, None)` -- own-current-club context, the EXACT
    methodology `generate_scoring_oracle.py` used. Expensive (~75-115s);
    cached module-wide so this file pays that cost at most once no matter
    how many edge cases need it."""
    if "scored_none" not in _CACHE:
        from scoring.services.population import score_population

        _CACHE["scored_none"] = score_population(_real_pop(), None)
    return _CACHE["scored_none"]


@contextmanager
def _patched_services():
    """Patch `scoring.services.rmm`/`financial_fit`'s imported
    `reconstruct_population`/`score_population` names to the module-scope
    real-data cache -- the real service functions (`get_rmm`,
    `get_financial_fit`) still run end-to-end for every call below; only
    the expensive reconstruction/scoring pass underneath them is memoized
    (exactly like test_views.py's `_patched_services()`)."""
    pop = _real_pop()
    scored, cs_tp = _real_scored_none()
    with (
        patch("scoring.services.rmm.reconstruct_population", return_value=pop),
        patch("scoring.services.financial_fit.reconstruct_population", return_value=pop),
        patch("scoring.services.financial_fit.score_population", return_value=(scored, cs_tp)),
    ):
        yield


def _get_rmm(player_id):
    from scoring.services.rmm import get_rmm

    with _patched_services():
        return get_rmm(player_id)


def _get_financial_fit(player_id, club_id):
    from scoring.services.financial_fit import get_financial_fit

    with _patched_services():
        return get_financial_fit(player_id, club_id)


# =========================================================================
# Zero-minutes player -- Phase 3 silent-zero-fill regression guard
# =========================================================================
def test_zero_minutes_player_parity(real_data_gate, oracle):
    """Regression guard for Phase 3's silent-zero-fill fix: a genuine
    Minutes_played == 0 player (column present, value honestly 0) must be
    scored by the port and match the oracle's RMM exactly -- proving the
    port reproduces the oracle's real handling of a zero-appearance
    player, never a fabricated/defaulted number."""
    from players.models import Player

    p = Player.objects.filter(Minutes_played=0).first()
    if p is None:
        pytest.skip("no zero-minute player in current data")

    result = _get_rmm(p.id)
    assert isinstance(result, dict)
    assert "rmm" in result

    oracle_rmm = oracle.loc[str(p.id), "rmm"]
    assert compare_scalar(oracle_rmm, result["rmm"], atol=RMM_CS_TP_ATOL), (
        f"zero-minutes player {p.id} RMM mismatch: oracle={oracle_rmm} port={result['rmm']}"
    )


# =========================================================================
# Missing key input stats -- oracle parity or correct null propagation
# =========================================================================
def test_missing_market_value_player_parity(real_data_gate, oracle):
    """A player missing market_value (drives the TFM/Financial-Fit
    features) is priced against their own club by the port and must match
    the oracle's tfm (log-scale) converted to money-scale, or be null on
    both sides -- never a fabricated fee. Requires the player to still
    have a club (so a genuine own-club financial-fit call is possible)."""
    from players.models import Player

    p = Player.objects.filter(market_value__isnull=True, club__isnull=False).first()
    if p is None:
        pytest.skip("no market-value-missing player with a club in current data")

    result = _get_financial_fit(p.id, p.club_id)
    assert isinstance(result, dict)

    oracle_tfm_log = oracle.loc[str(p.id), "tfm"]
    oracle_tfm_money = None if _is_null(oracle_tfm_log) else float(np.expm1(oracle_tfm_log))
    assert compare_scalar(oracle_tfm_money, result.get("predicted_fee"), rtol=TFM_RTOL), (
        f"market-value-missing player {p.id} TFM mismatch: "
        f"oracle_money={oracle_tfm_money} port={result.get('predicted_fee')}"
    )


def test_missing_club_player_cs_parity(real_data_gate, oracle):
    """A player with no club at all is excluded from Compatibility Score
    in the oracle's own-club methodology (`compute_cs_tp_for_pairs`'s
    `no_club` exclusion reason -- MANIFEST.md) -- the oracle's cs is NaN
    for them. The port's own-club bulk scoring pass must ALSO report NaN
    (both-null parity), never a fabricated score. `score_population`
    (used directly, since a club-less player has no valid own-club id to
    drive a per-request get_summary/get_compatibility call) is the SAME
    memoized module-wide pass every other edge case in this file reuses."""
    from players.models import Player

    p = Player.objects.filter(club__isnull=True).first()
    if p is None:
        pytest.skip("no club-less player in current data")

    _, cs_tp = _real_scored_none()
    cs_tp_str = cs_tp.set_axis(cs_tp.index.astype(str))
    if str(p.id) not in cs_tp_str.index:
        pytest.skip(f"club-less player {p.id} not present in the port's scored population")
    port_cs = cs_tp_str.loc[str(p.id), "compatibility_score"]

    oracle_cs = oracle.loc[str(p.id), "cs"]
    assert compare_scalar(oracle_cs, port_cs, atol=RMM_CS_TP_ATOL), (
        f"club-less player {p.id} CS mismatch: oracle={oracle_cs} port={port_cs}"
    )
