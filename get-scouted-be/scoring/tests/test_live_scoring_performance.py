"""Live-service warm-process performance regression (SCORE-07, gap-closure).

Plan 06-04's test_scoring_performance.py proves the ISOLATED
get_scored_population()/denormalized-field reads are fast, but never calls
the live service functions -- the exact blind spot that let the original
Phase 6 gap (9.15s get_rmm, 44.2s get_compatibility per request) ship. This
module drives the REAL get_* service functions on a WARM process and proves:

  (a) each own-club call is sub-second (flat per-entity retrieval), and
  (b) the full-population pandas entry points (add_player_impact,
      build_oracle_player_features) are NOT invoked per own-club request --
      a structural guard that survives future machine-speed changes a bare
      wall-clock threshold would not.

Patch-target note (load-bearing -- do not "simplify" without re-reading
this): `unittest.mock.patch` intercepts a NAME BINDING, not a function
object. `add_player_impact` is called from inside
`scoring.services.population.score_population()`, which resolved the name
via its own `from scoring.characterization.impact import add_player_impact`
at import time -- so the only patch target that can actually intercept that
call is `scoring.services.population.add_player_impact` (patching
`scoring.characterization.impact.add_player_impact` instead would silently
never be invoked, since population.py's own module dict entry is a separate
binding untouched by patching the origin module's attribute -- the classic
"patch where it's looked up, not where it's defined" mock pitfall). Same
reasoning for `build_oracle_player_features`, called from inside
`scoring.services.financial_fit.financial_fit_from_population()` via that
module's own imported name -- patched at
`scoring.services.financial_fit.build_oracle_player_features`. The three
`score_population` patches below are already correct as `scoring.services.
{compatibility,transfer_probability,summary}.score_population`, since each
of those services calls `score_population` via its own locally-imported
name -- confirmed by reading each service module directly.

Skips cleanly on an empty test DB (the project's real-data-test convention).
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.django_db

# Generous ceiling: a warm-process own-club call is a DataFrame-row slice /
# indexed DB read (sub-ms to low-ms in practice); 1.0s leaves ample headroom
# for CI noise while still catching a regression to the 9-44s full-pass.
WARM_CALL_CEILING_S = 1.0


def _pick_own_club_player():
    from players.models import Player

    p = (
        Player.objects.filter(impact_score__isnull=False, club__isnull=False)
        .values_list("id", "club_id")
        .first()
    )
    return p  # (player_id, club_id) or None


def _warm():
    from scoring.services.population import get_scored_population

    get_scored_population()  # one-time cold build; not timed


def test_get_rmm_warm_is_fast_and_runs_no_full_population_pass(real_data_available):
    pick = _pick_own_club_player()
    if pick is None:
        pytest.skip("No player with a denormalized impact_score + club -- run recompute_scores first")
    player_id, _club_id = pick
    _warm()

    from scoring.services import rmm

    # add_player_impact (the full-population RMM pass) must NOT run per request now.
    # Patched where score_population() looks it up (population.py's own imported
    # name) -- see module docstring's patch-target note.
    with patch("scoring.services.population.add_player_impact") as m_impact:
        t0 = time.perf_counter()
        result = rmm.get_rmm(player_id)
        elapsed = time.perf_counter() - t0
        m_impact.assert_not_called()

    assert result["rmm"] is not None
    assert elapsed < WARM_CALL_CEILING_S, f"warm get_rmm took {elapsed:.3f}s (regression to full-population pass?)"


def test_get_compatibility_own_club_warm_is_fast(real_data_available):
    pick = _pick_own_club_player()
    if pick is None:
        pytest.skip("No player with a denormalized impact_score + club -- run recompute_scores first")
    player_id, club_id = pick
    _warm()

    from scoring.services import compatibility

    # score_population (the full-population scoring pass) must NOT run for own-club.
    with patch("scoring.services.compatibility.score_population") as m_score:
        t0 = time.perf_counter()
        compatibility.get_compatibility(player_id, club_id)
        elapsed = time.perf_counter() - t0
        m_score.assert_not_called()

    assert elapsed < WARM_CALL_CEILING_S, f"warm get_compatibility took {elapsed:.3f}s"


def test_get_transfer_probability_own_club_warm_is_fast(real_data_available):
    pick = _pick_own_club_player()
    if pick is None:
        pytest.skip("No player with a denormalized impact_score + club -- run recompute_scores first")
    player_id, club_id = pick
    _warm()

    from scoring.services import transfer_probability

    with patch("scoring.services.transfer_probability.score_population") as m_score:
        t0 = time.perf_counter()
        transfer_probability.get_transfer_probability(player_id, club_id)
        elapsed = time.perf_counter() - t0
        m_score.assert_not_called()

    assert elapsed < WARM_CALL_CEILING_S, f"warm get_transfer_probability took {elapsed:.3f}s"


def test_get_financial_fit_own_club_is_o1_denormalized_read(real_data_available):
    from players.models import Player

    p = (
        Player.objects.filter(
            impact_score__isnull=False, club__isnull=False, financial_fit_score__isnull=False
        )
        .values_list("id", "club_id")
        .first()
    )
    if p is None:
        pytest.skip("No player with a denormalized financial_fit_score + club -- run recompute_scores first")
    player_id, club_id = p

    from scoring.services import financial_fit

    # build_oracle_player_features (the full-population TFM feature build) must
    # NOT run for the own-club case -- it reads the denormalized field instead.
    # Patched where financial_fit_from_population() looks it up (financial_fit.py's
    # own imported name) -- see module docstring's patch-target note.
    with patch("scoring.services.financial_fit.build_oracle_player_features") as m_feat:
        t0 = time.perf_counter()
        result = financial_fit.get_financial_fit(player_id, club_id)
        elapsed = time.perf_counter() - t0
        m_feat.assert_not_called()

    assert "predicted_fee" in result
    assert elapsed < WARM_CALL_CEILING_S, f"own-club get_financial_fit took {elapsed:.3f}s (should be an O(1) DB read)"


def test_get_summary_own_club_warm_is_fast(real_data_available):
    pick = _pick_own_club_player()
    if pick is None:
        pytest.skip("No player with a denormalized impact_score + club -- run recompute_scores first")
    player_id, club_id = pick
    _warm()

    from scoring.services import summary

    with patch("scoring.services.summary.score_population") as m_score:
        t0 = time.perf_counter()
        result = summary.get_summary(player_id, club_id)
        elapsed = time.perf_counter() - t0
        m_score.assert_not_called()

    assert set(result.keys()) == {"rmm", "compatibility", "financial_fit", "transfer_probability"}
    assert elapsed < WARM_CALL_CEILING_S, f"warm get_summary took {elapsed:.3f}s"
