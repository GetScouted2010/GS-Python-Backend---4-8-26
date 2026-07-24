"""Tier-2 API-sample parity test (05-03-PLAN.md) -- SCORE-06.

Runs a seeded, stratified ~30-player sample through the REAL Phase 4
per-request service functions (Task 1: `get_rmm`/`get_compatibility`/
`get_financial_fit`/`get_transfer_probability`/`get_summary`) and, for a
handful of those same players, through the REAL authenticated DRF
endpoints (Task 2), comparing every returned score against the same oracle
CSV Plan 02's bulk path is diffed against.

This is the wiring-bug half of SCORE-06: the bulk path
(`score_population(pop, None)` over the whole population, Plan 02) and the
per-request path (the 5 `get_*` service functions, and the 5 DRF views
built on top of them) are separately-written orchestration code that
happen to call the same underlying `compute_cs_tp_for_pairs`/
`add_player_impact`/TFM pipeline -- only a sample driven through the REAL
per-request code proves they still agree. This is the exact class of bug
Phase 4 already shipped once (the CS `role_scores_wide` merge, fixed in
04-03) -- a bulk-only parity suite structurally cannot catch it, since it
never calls the per-request functions at all.

Sample construction queries the real Player table, so it happens inside a
MODULE-SCOPE `sample` fixture (`django_db_setup` + `django_db_blocker`,
Plan 02/04's established heavy-real-data pattern) rather than at
collection time: pytest-django repoints the ORM's connection from the dev
DB to a fresh (usually empty) test DB the moment the first
`django_db_setup`-dependent fixture actually runs, so building the sample
from a raw collection-time query would silently diff against player ids
the real test-time connection can no longer see (verified live during this
plan's own execution). `pytest.mark.parametrize(..., indirect=True)` is
therefore applied over a STATIC index range (`SAMPLE_SLOTS`/
`ENDPOINT_SLOTS`, a generous fixed upper bound) with the real,
DB-dependent sample resolved lazily inside the `player_case`/
`endpoint_case` fixtures -- unused slots (or an entirely empty DB) skip
cleanly with the same message `real_data_available` uses elsewhere in this
suite, while every present slot still reports as its OWN individual
pytest pass/fail (a single mismatching player is a single failing test
case, not an opaque loop).

Memoization: `reconstruct_population()`/`score_population()` are computed
AT MOST ONCE for the whole module (test_views.py's own `_CACHE`/`_pop()`/
`_scored()` pattern, copied verbatim) -- `score_population(pop, None)`
(own-current-club methodology, matching the oracle) is the ONLY scored
context ever computed. Per 05-03-PLAN.md's interfaces note,
`score_population(pop, club_name)` for a player's OWN club name yields an
IDENTICAL cs_tp row for that player as `score_population(pop, None)` (both
reduce to "this player vs their own club"), so patching every service's
`score_population` import to always return the SAME cached `None`-context
result is correct regardless of which specific club argument the real
service/view code happens to pass in.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from django.db.models import Count
from rest_framework.test import APIClient

from scoring.tests._parity_helpers import (
    GROUPS_WITH_NULL_CS_TP,
    POSITION_GROUPS,
    RMM_CS_TP_ATOL,
    TFM_RTOL,
    compare_scalar,
    load_oracle_df,
)

pytestmark = pytest.mark.django_db

TOP_CLUB_COUNT = 10
PER_NON_NULL_GROUP = 4
NON_NULL_GROUPS = [g for g in POSITION_GROUPS if g not in GROUPS_WITH_NULL_CS_TP]

# Generous, FIXED upper bounds for the indirect-parametrize index ranges --
# the real sample size (up to 3 null-group + up to 7*PER_NON_NULL_GROUP
# non-null-group players, ~31) is resolved at test-run time from the
# actual DB; unused slots skip cleanly (see `player_case`/`endpoint_case`).
SAMPLE_SLOTS = 40
ENDPOINT_SLOTS = 6

_NO_DATA_MESSAGE = (
    "No real Player data in the dev DB -- run Phase 1's import_all "
    "management command first to populate real migrated data."
)


def _is_null(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v)


# ---------------------------------------------------------------------------
# Sample construction (real DB query -- see the module docstring for why
# this MUST run inside a fixture that depends on `django_db_setup`, not at
# collection time).
# ---------------------------------------------------------------------------
def _build_sample() -> list[tuple[str, str]]:
    """Seeded, stratified sample of ~30 (player_id_str, position_group)
    tuples, drawn from the ~10 clubs with the most players -- bounds the
    number of distinct clubs `get_financial_fit`'s Team-override path can
    hit (the only place per-player club identity affects a
    `score_population` context beyond the single shared `None`-context CS/
    TP/summary cache). Explicitly includes 1 GK/LB/RB player each (null
    CS/TP by design -- MANIFEST.md) plus up to `PER_NON_NULL_GROUP`
    players from each of the 7 non-null position groups, preferring
    players with a non-null oracle `cs` so the non-null-group assertions
    are actually exercised (not vacuously both-null)."""
    from players.models import Player

    oracle = load_oracle_df()
    rng = np.random.default_rng(42)  # fixed seed for reproducibility

    top_club_ids = list(
        Player.objects.exclude(club_id__isnull=True)
        .values("club_id")
        .annotate(n=Count("id"))
        .order_by("-n")[:TOP_CLUB_COUNT]
        .values_list("club_id", flat=True)
    )
    candidate_ids = {
        str(pid) for pid in Player.objects.filter(club_id__in=top_club_ids).values_list("id", flat=True)
    }
    pool = oracle.loc[oracle.index.isin(candidate_ids)]

    sample: list[tuple[str, str]] = []

    # GK/LB/RB -- 1 each, to exercise correct CS/TP null propagation.
    for group in sorted(GROUPS_WITH_NULL_CS_TP):
        group_pool = pool[pool["position_group"] == group]
        if group_pool.empty:
            continue
        seed = int(rng.integers(0, 2**31 - 1))
        chosen = group_pool.sample(n=1, random_state=seed)
        sample.extend((pid, group) for pid in chosen.index)

    # A handful from each non-null group, preferring non-null CS rows.
    for group in NON_NULL_GROUPS:
        group_pool = pool[(pool["position_group"] == group) & pool["cs"].notna()]
        if group_pool.empty:
            group_pool = pool[pool["position_group"] == group]
        if group_pool.empty:
            continue
        n = min(PER_NON_NULL_GROUP, len(group_pool))
        seed = int(rng.integers(0, 2**31 - 1))
        chosen = group_pool.sample(n=n, random_state=seed)
        sample.extend((pid, group) for pid in chosen.index)

    return sample


@pytest.fixture(scope="module")
def sample(django_db_setup, django_db_blocker):
    """The seeded stratified sample, built AT MOST ONCE for the whole
    module. Uses `django_db_blocker.unblock()` (05-02-PLAN.md's
    established heavy-real-data pattern) because a module-scope fixture
    cannot request the function-scope `real_data_available`/`db` fixtures
    directly. Returns `[]` on an empty dev DB -- every dependent test then
    skips cleanly via `player_case` below."""
    with django_db_blocker.unblock():
        from players.models import Player

        if Player.objects.count() == 0:
            return []
        return _build_sample()


@pytest.fixture
def player_case(sample, request):
    idx = request.param
    if idx >= len(sample):
        pytest.skip(_NO_DATA_MESSAGE)
    return sample[idx]


@pytest.fixture(scope="module")
def endpoint_sample(sample):
    """~5 players for the DRF endpoint parity subset: 1 GK/LB/RB (null
    CS/TP -- checks the endpoint returns the null envelope gracefully, not
    a 500) plus a handful of non-null-group players."""
    null_group_cases = [c for c in sample if c[1] in GROUPS_WITH_NULL_CS_TP][:1]
    non_null_cases = [c for c in sample if c[1] not in GROUPS_WITH_NULL_CS_TP][:4]
    return null_group_cases + non_null_cases


@pytest.fixture
def endpoint_case(endpoint_sample, request):
    idx = request.param
    if idx >= len(endpoint_sample):
        pytest.skip(_NO_DATA_MESSAGE)
    return endpoint_sample[idx]


@pytest.fixture
def auth_client():
    """A DRF APIClient force-authenticated as a real accounts.User --
    copied verbatim from test_views.py's `auth_client` fixture (still
    exercises the same global IsAuthenticated permission gate a real
    Bearer token would)."""
    from accounts.models import User

    user = User.objects.create_user(email="parity-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# Module-wide memoization cache -- mirrors test_views.py's `_CACHE` /
# `_pop()` / `_scored()` pattern. `reconstruct_population()` (~3.5s) and
# `score_population(pop, None)` (~75-115s) are each computed AT MOST ONCE
# for the whole file, then patched onto each service module's imported
# names for every sampled player below.
# ---------------------------------------------------------------------------
_CACHE: dict = {}


def _pop():
    if "pop" not in _CACHE:
        from scoring.services.population import reconstruct_population

        _CACHE["pop"] = reconstruct_population()
    return _CACHE["pop"]


def _scored(club_name):
    scored_cache = _CACHE.setdefault("scored", {})
    if club_name not in scored_cache:
        from scoring.services.population import score_population

        scored_cache[club_name] = score_population(_pop(), club_name)
    return scored_cache[club_name]


def _own_club_id(pid):
    from players.models import Player

    return Player.objects.get(id=pid).club_id


# =========================================================================
# Task 1: per-request SERVICE function parity
# =========================================================================
@pytest.mark.parametrize("player_case", range(SAMPLE_SLOTS), indirect=True)
def test_rmm_service_parity(player_case):
    from scoring.services.rmm import get_rmm

    pid, _group = player_case
    oracle = load_oracle_df()

    with patch("scoring.services.rmm.reconstruct_population", return_value=_pop()):
        result = get_rmm(pid)

    assert compare_scalar(oracle.loc[str(pid), "rmm"], result.get("rmm"), atol=RMM_CS_TP_ATOL), (
        f"player {pid} RMM mismatch: oracle={oracle.loc[str(pid), 'rmm']} port={result.get('rmm')}"
    )


@pytest.mark.parametrize("player_case", range(SAMPLE_SLOTS), indirect=True)
def test_cs_service_parity(player_case):
    from scoring.services.compatibility import get_compatibility

    pid, group = player_case
    oracle = load_oracle_df()
    own_club_id = _own_club_id(pid)

    with (
        patch("scoring.services.compatibility.reconstruct_population", return_value=_pop()),
        patch("scoring.services.compatibility.score_population", return_value=_scored(None)),
    ):
        result = get_compatibility(pid, own_club_id)

    oracle_cs = oracle.loc[str(pid), "cs"]
    port_cs = result.get("compatibility_score")
    if group in GROUPS_WITH_NULL_CS_TP:
        assert _is_null(oracle_cs), f"expected null oracle CS for {group} player {pid}"
        assert _is_null(port_cs), f"port fabricated a CS value for {group} player {pid}: {port_cs}"
    assert compare_scalar(oracle_cs, port_cs, atol=RMM_CS_TP_ATOL), (
        f"player {pid} CS mismatch: oracle={oracle_cs} port={port_cs}"
    )


@pytest.mark.parametrize("player_case", range(SAMPLE_SLOTS), indirect=True)
def test_tp_service_parity(player_case):
    from scoring.services.transfer_probability import get_transfer_probability

    pid, group = player_case
    oracle = load_oracle_df()
    own_club_id = _own_club_id(pid)

    with (
        patch("scoring.services.transfer_probability.reconstruct_population", return_value=_pop()),
        patch("scoring.services.transfer_probability.score_population", return_value=_scored(None)),
    ):
        result = get_transfer_probability(pid, own_club_id)

    oracle_tp = oracle.loc[str(pid), "transfer_probability"]
    port_tp = result.get("transfer_probability")
    if group in GROUPS_WITH_NULL_CS_TP:
        assert _is_null(oracle_tp), f"expected null oracle TP for {group} player {pid}"
        assert _is_null(port_tp), f"port fabricated a TP value for {group} player {pid}: {port_tp}"
    assert compare_scalar(oracle_tp, port_tp, atol=RMM_CS_TP_ATOL), (
        f"player {pid} TP mismatch: oracle={oracle_tp} port={port_tp}"
    )


@pytest.mark.parametrize("player_case", range(SAMPLE_SLOTS), indirect=True)
def test_tfm_service_parity(player_case):
    from scoring.services.financial_fit import get_financial_fit

    pid, _group = player_case
    oracle = load_oracle_df()
    own_club_id = _own_club_id(pid)

    with (
        patch("scoring.services.financial_fit.reconstruct_population", return_value=_pop()),
        patch("scoring.services.financial_fit.score_population", return_value=_scored(None)),
    ):
        result = get_financial_fit(pid, own_club_id)

    oracle_tfm_log = oracle.loc[str(pid), "tfm"]
    oracle_money = None if _is_null(oracle_tfm_log) else float(np.expm1(oracle_tfm_log))
    assert compare_scalar(oracle_money, result.get("predicted_fee"), rtol=TFM_RTOL), (
        f"player {pid} TFM mismatch: oracle_money={oracle_money} port={result.get('predicted_fee')}"
    )


@pytest.mark.parametrize("player_case", range(SAMPLE_SLOTS), indirect=True)
def test_summary_service_parity(player_case):
    """`get_summary` reconciles to the SAME oracle values as the 4
    standalone `get_*` service functions above -- proving the summary
    orchestrator's own reconstruct+score pass (and its `role_scores_wide`
    merge for CS) agrees with both the individual services AND the
    oracle."""
    from scoring.services.summary import get_summary

    pid, group = player_case
    oracle = load_oracle_df()
    own_club_id = _own_club_id(pid)

    with (
        patch("scoring.services.summary.reconstruct_population", return_value=_pop()),
        patch("scoring.services.summary.score_population", return_value=_scored(None)),
    ):
        result = get_summary(pid, own_club_id)

    assert compare_scalar(oracle.loc[str(pid), "rmm"], result["rmm"].get("rmm"), atol=RMM_CS_TP_ATOL)

    oracle_cs = oracle.loc[str(pid), "cs"]
    port_cs = result["compatibility"].get("compatibility_score")
    if group in GROUPS_WITH_NULL_CS_TP:
        assert _is_null(oracle_cs)
        assert _is_null(port_cs)
    assert compare_scalar(oracle_cs, port_cs, atol=RMM_CS_TP_ATOL)

    oracle_tfm_log = oracle.loc[str(pid), "tfm"]
    oracle_money = None if _is_null(oracle_tfm_log) else float(np.expm1(oracle_tfm_log))
    assert compare_scalar(oracle_money, result["financial_fit"].get("predicted_fee"), rtol=TFM_RTOL)

    oracle_tp = oracle.loc[str(pid), "transfer_probability"]
    port_tp = result["transfer_probability"].get("transfer_probability")
    if group in GROUPS_WITH_NULL_CS_TP:
        assert _is_null(oracle_tp)
        assert _is_null(port_tp)
    assert compare_scalar(oracle_tp, port_tp, atol=RMM_CS_TP_ATOL)


# =========================================================================
# Task 2: DRF endpoint parity for a handful of sampled players
# =========================================================================
def test_endpoints_require_authentication():
    """Cross-cutting auth-gate check (mirrors test_views.py) -- an
    unauthenticated GET to a scoring endpoint returns 401, confirming the
    parity suite also proves the auth gate stays intact end-to-end."""
    client = APIClient()
    placeholder_id = uuid.uuid4()
    response = client.get(f"/api/scoring/players/{placeholder_id}/impact/")
    assert response.status_code == 401


@pytest.mark.parametrize("endpoint_case", range(ENDPOINT_SLOTS), indirect=True)
def test_endpoint_parity(endpoint_case, auth_client):
    pid, group = endpoint_case
    oracle = load_oracle_df()
    own_club_id = _own_club_id(pid)

    with (
        patch("scoring.services.rmm.reconstruct_population", return_value=_pop()),
        patch("scoring.services.compatibility.reconstruct_population", return_value=_pop()),
        patch("scoring.services.compatibility.score_population", return_value=_scored(None)),
        patch("scoring.services.financial_fit.reconstruct_population", return_value=_pop()),
        patch("scoring.services.financial_fit.score_population", return_value=_scored(None)),
        patch("scoring.services.transfer_probability.reconstruct_population", return_value=_pop()),
        patch("scoring.services.transfer_probability.score_population", return_value=_scored(None)),
    ):
        resp = auth_client.get(f"/api/scoring/players/{pid}/impact/")
        assert resp.status_code == 200
        assert compare_scalar(oracle.loc[str(pid), "rmm"], resp.json()["rmm"], atol=RMM_CS_TP_ATOL)

        resp = auth_client.get(f"/api/scoring/players/{pid}/clubs/{own_club_id}/compatibility/")
        assert resp.status_code == 200
        oracle_cs = oracle.loc[str(pid), "cs"]
        port_cs = resp.json().get("compatibility_score")
        if group in GROUPS_WITH_NULL_CS_TP:
            assert _is_null(oracle_cs)
            assert _is_null(port_cs)
        assert compare_scalar(oracle_cs, port_cs, atol=RMM_CS_TP_ATOL)

        resp = auth_client.get(f"/api/scoring/players/{pid}/clubs/{own_club_id}/financial-fit/")
        assert resp.status_code == 200
        oracle_tfm_log = oracle.loc[str(pid), "tfm"]
        oracle_money = None if _is_null(oracle_tfm_log) else float(np.expm1(oracle_tfm_log))
        assert compare_scalar(oracle_money, resp.json().get("predicted_fee"), rtol=TFM_RTOL)

        resp = auth_client.get(f"/api/scoring/players/{pid}/clubs/{own_club_id}/transfer-probability/")
        assert resp.status_code == 200
        oracle_tp = oracle.loc[str(pid), "transfer_probability"]
        port_tp = resp.json().get("transfer_probability")
        if group in GROUPS_WITH_NULL_CS_TP:
            assert _is_null(oracle_tp)
            assert _is_null(port_tp)
        assert compare_scalar(oracle_tp, port_tp, atol=RMM_CS_TP_ATOL)

        resp = auth_client.get(f"/api/scoring/players/{pid}/summary/?club_id={own_club_id}")
        assert resp.status_code == 200
