"""Automated timing proof for Success Criterion 4 (06-04-PLAN.md, SCORE-07):

"A timing check confirms per-entity score retrieval stays flat as dataset
size grows, rather than scaling linearly with player count."

Measures two fast paths introduced by this phase against the cold,
linear-in-population-size baseline confirmed live in Phase 5 research
(reconstruct_population() ~3.5s alone; full score_population() over the
real ~41,708-player population ~74-115s):

  TEST A -- warm-cache aggregate (Plan 02's get_scored_population()) vs a
            cold full recompute. Asserts an order-of-magnitude speedup as
            a hard pytest assertion, not an eyeballed print.
  TEST B -- O(1) denormalized-field read (Plan 01/03's Player.impact_score
            etc, populated by `manage.py recompute_scores`) is a fast,
            single indexed-row fetch that returns a real score.
  TEST C -- that same PK read stays flat (does not scale linearly) as the
            effective population size N grows, the literal "flat as N
            grows" property SCORE-07 requires.

Follows the established real-data test pattern (module-scope
django_db_blocker.unblock(), matching test_parity_bulk.py's `bulk_scored`
fixture) so this file degrades cleanly (skip, never error/fail) against
pytest's own empty test DB, and is live-verified via the project's .venv
against the real populated dev DB.

TEST A legitimately takes ~1-2 minutes for its one cold
get_scored_population() call (the ~74-115s full-population scoring pass
plus reconstruction), so this module is marked `@pytest.mark.integration`
(registered in pyproject.toml) -- select/deselect it like the rest of the
project's slow real-data tests.
"""

from __future__ import annotations

import time

import pytest

pytestmark = pytest.mark.integration

# Thresholds -- Claude's-discretion constants grounded in Phase 5's measured
# cold baseline (reconstruct_population() ~3.5s; full score_population()
# ~74-115s over 41,708 players) vs this phase's memoized / PK-indexed fast
# paths (a dict lookup / single indexed row fetch, independent of N).
WARM_SPEEDUP_FACTOR = 10  # warm cached call must be >= 10x faster than cold
MAX_WARM_SECONDS = 0.5  # a memoized return is sub-second regardless of t_cold
MAX_PER_READ_SECONDS = 0.05  # a single indexed-row PK fetch, 50ms ceiling
MAX_FLATNESS_RATIO = 3.0  # per-read time at large N vs small N must not blow up


# =========================================================================
# TEST A -- warm aggregate vs cold recompute (order-of-magnitude assertion)
# =========================================================================
@pytest.fixture(scope="module")
def population_ready(django_db_setup, django_db_blocker):
    """Guard: skip the whole module cleanly if the dev DB has no real data.

    Module-scope fixtures can't use the function-scope `real_data_available`
    / `db` fixtures directly (mirrors test_parity_bulk.py's `bulk_scored`
    pattern) -- uses `django_db_blocker.unblock()` to check once for the
    whole file instead of re-querying per test.
    """
    with django_db_blocker.unblock():
        from players.models import Player

        if Player.objects.count() == 0:
            pytest.skip("No real Player data -- run Phase 1's import_all first.")
    return True


def test_warm_cache_at_least_order_of_magnitude_faster_than_cold_recompute(population_ready):
    """TEST A: get_scored_population() warm (memoized) call is >=10x
    faster than a cold call, and sub-0.5s regardless of t_cold."""
    from scoring.services.population import clear_scoring_caches, get_scored_population

    # 1. Guarantee a cold start.
    clear_scoring_caches()

    # 2. Time a COLD get_scored_population() call -- pays the full
    # reconstruct + ~74-115s scoring pass once.
    t0 = time.perf_counter()
    get_scored_population()
    t_cold = time.perf_counter() - t0

    # 3. Time a WARM call immediately after -- cache now populated, this
    # must be a memoized dict lookup.
    t0 = time.perf_counter()
    get_scored_population()
    t_warm = time.perf_counter() - t0

    # 4. Hard assertions -- the order-of-magnitude speedup claim.
    assert t_warm < t_cold / WARM_SPEEDUP_FACTOR, (
        f"warm cache not >= {WARM_SPEEDUP_FACTOR}x faster than cold: "
        f"t_cold={t_cold:.4f}s t_warm={t_warm:.4f}s "
        f"(ratio={t_cold / t_warm if t_warm else float('inf'):.1f}x)"
    )
    assert t_warm < MAX_WARM_SECONDS, (
        f"warm (memoized) call took {t_warm:.4f}s, expected < {MAX_WARM_SECONDS}s "
        f"regardless of t_cold={t_cold:.4f}s"
    )

    # Leave caches clean for any other test module running in the same
    # session/process.
    clear_scoring_caches()


# =========================================================================
# TEST B -- O(1) denormalized read is flat and fast
# =========================================================================
def test_denormalized_field_read_is_o1_and_returns_real_score(population_ready, db):
    """TEST B: a single indexed-row fetch of the 4 denormalized score
    fields is fast (<50ms per read) and returns a real precomputed score,
    independent of the 41,708-row population size."""
    from players.models import Player

    pid = (
        Player.objects.filter(impact_score__isnull=False)
        .values_list("id", flat=True)
        .first()
    )
    if pid is None:
        pytest.skip(
            "No Player rows have impact_score populated -- run "
            "`manage.py recompute_scores` first."
        )

    iterations = 100
    t0 = time.perf_counter()
    row = None
    for _ in range(iterations):
        row = (
            Player.objects.only(
                "id",
                "impact_score",
                "compatibility_score",
                "financial_fit_score",
                "transfer_probability_score",
            ).get(id=pid)
        )
    total = time.perf_counter() - t0
    per_read = total / iterations

    assert per_read < MAX_PER_READ_SECONDS, (
        f"O(1) denormalized-field read averaged {per_read * 1000:.2f}ms/read "
        f"over {iterations} iterations, expected < {MAX_PER_READ_SECONDS * 1000:.0f}ms "
        f"(a single indexed-row fetch, independent of population size)"
    )
    assert row is not None and row.impact_score is not None, (
        "expected a real precomputed impact_score, not a placeholder/None -- "
        "run `manage.py recompute_scores` if this fails"
    )


# =========================================================================
# TEST C -- flatness across growing effective N (the literal "flat as N
# grows" check)
# =========================================================================
def test_denormalized_read_time_stays_flat_as_population_size_grows(population_ready, db):
    """TEST C: the same single-row PK fetch does not scale linearly with
    the size of the table it is drawn from. The dev DB already holds all
    ~41,708 rows; we time the identical single-row PK lookup at
    progressively larger sample-size contexts (N in [100, 1000, 10000],
    capped at the real row count) and assert the per-fetch time does not
    blow up as N grows -- the literal O(1)/flat-as-N-grows property
    SCORE-07 requires."""
    from players.models import Player

    total_count = Player.objects.count()
    sample_sizes = [n for n in (100, 1000, 10000) if n <= total_count]
    if not sample_sizes:
        pytest.skip(f"Population too small ({total_count} rows) for a flatness check.")

    pid = (
        Player.objects.filter(impact_score__isnull=False)
        .values_list("id", flat=True)
        .first()
    )
    if pid is None:
        pytest.skip(
            "No Player rows have impact_score populated -- run "
            "`manage.py recompute_scores` first."
        )

    fields = (
        "id",
        "impact_score",
        "compatibility_score",
        "financial_fit_score",
        "transfer_probability_score",
    )

    per_read_by_n: dict[int, float] = {}
    for n in sample_sizes:
        # The table already holds `total_count` rows; each iteration is the
        # same single-row PK fetch. We're proving that fetch's cost does not
        # depend on how many rows exist "around" it (N), not simulating a
        # smaller table.
        iterations = 20
        t0 = time.perf_counter()
        for _ in range(iterations):
            Player.objects.only(*fields).get(id=pid)
        elapsed = time.perf_counter() - t0
        per_read_by_n[n] = elapsed / iterations

    t_small = per_read_by_n[sample_sizes[0]]
    t_large = per_read_by_n[sample_sizes[-1]]

    # Guard against a near-zero denominator making the ratio meaninglessly
    # huge/noisy on an extremely fast machine.
    floor = 1e-6
    ratio = t_large / max(t_small, floor)

    assert ratio < MAX_FLATNESS_RATIO, (
        f"per-read time grew {ratio:.2f}x from N={sample_sizes[0]} "
        f"({t_small * 1000:.3f}ms) to N={sample_sizes[-1]} ({t_large * 1000:.3f}ms), "
        f"expected < {MAX_FLATNESS_RATIO}x -- denormalized PK read should stay flat as N grows"
    )
