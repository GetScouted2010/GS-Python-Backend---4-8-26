"""DRF APIClient integration tests for scoring/views.py (04-06-PLAN.md) --
covers all 5 endpoints under /api/scoring/ plus the cross-cutting
authentication gate (IsAuthenticated is the project's global DRF default;
no bespoke permission class is added for these views).

Real population reconstruction/scoring is expensive (~1 min, per
scoring/tests/test_services_financial_fit.py's own note) -- this module
reuses the SAME module-scope caching pattern those service-level test
files already establish: `reconstruct_population`/`score_population` are
computed for the real dev DB AT MOST ONCE per distinct context actually
needed, then the SAME cached results are patched onto each service
module's imported names for every test below. Every test still exercises
the REAL view -> REAL service function chain end-to-end via APIClient (the
service functions themselves -- `cs_breakdown_from_row`,
`financial_fit_from_population`, etc. -- are never mocked); only the
expensive reconstruction/scoring pass is memoized, exactly like the
sibling service-level test files already do.

`real_data_available` (scoring/tests/conftest.py) lets the real-data tests
skip cleanly against an empty dev DB.
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


ENDPOINTS = [
    lambda p, c: f"/api/scoring/players/{p}/impact/",
    lambda p, c: f"/api/scoring/players/{p}/clubs/{c}/compatibility/",
    lambda p, c: f"/api/scoring/players/{p}/clubs/{c}/financial-fit/",
    lambda p, c: f"/api/scoring/players/{p}/clubs/{c}/transfer-probability/",
    lambda p, c: f"/api/scoring/players/{p}/summary/?club_id={c}",
]


# ---------------------------------------------------------------------------
# Auth fixture
# ---------------------------------------------------------------------------
@pytest.fixture
def auth_client():
    """A DRF APIClient force-authenticated as a real accounts.User -- the
    simplest equivalent of a real Bearer-token request for these read-only
    GET tests (mirrors accounts' JWT-authenticated test pattern via
    force_authenticate; still exercises the same global IsAuthenticated
    permission gate a real Bearer token would)."""
    from accounts.models import User

    user = User.objects.create_user(email="scoring-view-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# ---------------------------------------------------------------------------
# Cross-cutting: unauthenticated access is denied on every endpoint
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("build_url", ENDPOINTS)
def test_endpoints_require_authentication(build_url):
    """An unauthenticated GET to every scoring endpoint returns 401/403 --
    inherits the project's global IsAuthenticated + JWTAuthentication
    defaults; no bespoke permission class needed."""
    client = APIClient()
    placeholder_id = uuid.uuid4()
    response = client.get(build_url(placeholder_id, placeholder_id))
    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Real-data population cache (module scope) -- mirrors
# test_services_summary.py / test_services_financial_fit.py's own pattern,
# so this file reconstructs the real population AT MOST ONCE regardless of
# how many endpoint tests run.
# ---------------------------------------------------------------------------
_CACHE: dict = {}


def _real_pop():
    if "pop" not in _CACHE:
        from scoring.services.population import reconstruct_population

        _CACHE["pop"] = reconstruct_population()
    return _CACHE["pop"]


def _real_scored(club_name):
    scored_cache = _CACHE.setdefault("scored", {})
    if club_name not in scored_cache:
        from scoring.services.population import score_population

        scored_cache[club_name] = score_population(_real_pop(), club_name)
    return scored_cache[club_name]


def _pick_player_and_club():
    """A real player with an actually-computed RMM (not NaN) + a real club
    -- cached module-wide so every test reuses the exact same pair (and the
    exact same score_population(pop, club_name) result the compatibility/TP
    tests below patch in)."""
    if "picks" not in _CACHE:
        from clubs.models import Club
        from scoring.characterization.impact import add_player_impact

        pop = _real_pop()
        scored = add_player_impact(pop.players_df.copy())
        scored_valid = scored[scored["Player Impact"].notna()]
        assert not scored_valid.empty, "expected at least one player with a computed RMM"
        player_id = scored_valid.iloc[0]["player_id"]

        club = Club.objects.first()
        assert club is not None, "expected real migrated Club data"

        _CACHE["picks"] = (str(player_id), club)
    return _CACHE["picks"]


@contextmanager
def _patched_services():
    """Patch every scoring.services.* module's imported
    reconstruct_population/score_population names to the module-scope
    real-data cache -- the real view -> real service function chain still
    runs end to end for every test; only the expensive DB
    reconstruction/scoring pass is memoized (exactly like the sibling
    service-level test files already do), so this whole file pays that
    cost at most once per distinct context (club-scoped vs. club-agnostic)
    actually exercised."""
    _, club = _pick_player_and_club()
    pop = _real_pop()
    scored_club, cs_tp_club = _real_scored(club.name)
    scored_none, cs_tp_none = _real_scored(None)

    with (
        patch("scoring.services.rmm.get_scored_population", return_value=(scored_none, cs_tp_none)),
        patch("scoring.services.compatibility.reconstruct_population", return_value=pop),
        patch("scoring.services.compatibility.score_population", return_value=(scored_club, cs_tp_club)),
        patch("scoring.services.compatibility.get_scored_population", return_value=(scored_none, cs_tp_none)),
        patch("scoring.services.financial_fit.reconstruct_population", return_value=pop),
        patch("scoring.services.financial_fit.get_scored_population", return_value=(scored_none, cs_tp_none)),
        patch("scoring.services.transfer_probability.reconstruct_population", return_value=pop),
        patch("scoring.services.transfer_probability.score_population", return_value=(scored_club, cs_tp_club)),
        patch("scoring.services.transfer_probability.get_scored_population", return_value=(scored_none, cs_tp_none)),
        patch("scoring.services.summary.reconstruct_population", return_value=pop),
        patch("scoring.services.summary.score_population", return_value=(scored_club, cs_tp_club)),
        patch("scoring.services.summary.get_scored_population", return_value=(scored_none, cs_tp_none)),
    ):
        yield


# ---------------------------------------------------------------------------
# Per-endpoint real-data tests
# ---------------------------------------------------------------------------
def test_rmm_endpoint_returns_real_score(real_data_available, auth_client):
    player_id, _club = _pick_player_and_club()

    with _patched_services():
        response = auth_client.get(f"/api/scoring/players/{player_id}/impact/")

    assert response.status_code == 200
    assert response.data["rmm"] is not None
    assert "components" in response.data
    assert isinstance(response.data["components"], dict)


def test_compatibility_endpoint(real_data_available, auth_client):
    player_id, club = _pick_player_and_club()

    with _patched_services():
        response = auth_client.get(f"/api/scoring/players/{player_id}/clubs/{club.id}/compatibility/")

    assert response.status_code == 200
    assert "compatibility_score" in response.data
    if response.data["compatibility_score"] is None:
        assert response.data["reason"]
    else:
        assert "components" in response.data


def test_financial_fit_endpoint(real_data_available, auth_client):
    player_id, _club = _pick_player_and_club()

    from clubs.models import Club

    result = None
    with _patched_services():
        for candidate_club in Club.objects.all()[:5]:
            response = auth_client.get(
                f"/api/scoring/players/{player_id}/clubs/{candidate_club.id}/financial-fit/"
            )
            assert response.status_code == 200
            if response.data.get("predicted_fee") is not None:
                result = response.data
                break

    if result is None:
        pytest.skip("No sampled club produced a priced financial_fit result for this player")

    assert result["predicted_fee"] > 1000, (
        f"predicted_fee={result['predicted_fee']} looks log-scale, not money-scale"
    )
    assert "value_verdict" in result


def test_transfer_probability_endpoint(real_data_available, auth_client):
    player_id, club = _pick_player_and_club()

    with _patched_services():
        response = auth_client.get(
            f"/api/scoring/players/{player_id}/clubs/{club.id}/transfer-probability/"
        )

    assert response.status_code == 200
    assert "transfer_probability" in response.data
    if response.data["transfer_probability"] is None:
        assert response.data["reason"]
    else:
        assert set(response.data["components"]) == {"compatibility", "performance", "financial", "contract_fit"}


def test_summary_endpoint(real_data_available, auth_client):
    player_id, club = _pick_player_and_club()

    with _patched_services():
        response = auth_client.get(f"/api/scoring/players/{player_id}/summary/?club_id={club.id}")

    assert response.status_code == 200
    assert set(response.data.keys()) == {"rmm", "compatibility", "financial_fit", "transfer_probability"}


def test_unknown_player_returns_404(real_data_available, auth_client):
    _player_id, club = _pick_player_and_club()
    unknown_player_id = uuid.uuid4()

    with _patched_services():
        response = auth_client.get(f"/api/scoring/players/{unknown_player_id}/impact/")

    assert response.status_code == 404
