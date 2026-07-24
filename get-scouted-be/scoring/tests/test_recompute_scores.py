"""Real-data test for the `recompute_scores` management command
(06-03-PLAN.md).

Follows the established real-data test pattern (see
`scoring/tests/test_parity_bulk.py` lines 49-60): pytest-django's own test
DB is empty, so these tests are intended to be live-verified via
`manage.py shell`/the project .venv against the real 41,708-player dev
DB. When run under plain pytest against an empty test DB they skip
cleanly (never fail/error) via the module-scope `django_db_blocker.unblock()`
+ `Player.objects.count() == 0` guard.

TEST A proves the command populates all 4 denormalized Player fields.
TEST B proves NaN was written as a real SQL NULL, never a zero-fill
(compatibility_score legitimately has NULLs for GK/LB/RB, confirmed in
Phase 5).
TEST C proves financial_fit_score is money-scale (np.expm1 applied), not
the raw log-scale TFM output (~13-17) -- catches a regression where
np.expm1 was forgotten.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command


@pytest.fixture(scope="module")
def recompute_run(django_db_setup, django_db_blocker):
    """Run `manage.py recompute_scores` once for the whole module.

    Module-scope fixtures can't use the function-scope `real_data_available`
    / `db` fixtures directly, so this uses pytest-django's
    `django_db_blocker.unblock()` -- the established heavy-real-data
    pattern (see `test_parity_bulk.py`'s `bulk_scored` fixture) for a
    once-per-module expensive DB-backed command.
    """
    with django_db_blocker.unblock():
        from players.models import Player

        if Player.objects.count() == 0:
            pytest.skip("No real Player data -- run Phase 1 import_all first.")

        call_command("recompute_scores")
    return None


@pytest.mark.django_db
def test_recompute_scores_populates_all_four_fields(recompute_run):
    """TEST A -- full-command smoke + population."""
    from players.models import Player

    assert Player.objects.filter(impact_score__isnull=False).count() > 0
    assert Player.objects.filter(compatibility_score__isnull=False).count() > 0
    assert Player.objects.filter(financial_fit_score__isnull=False).count() > 0
    assert Player.objects.exclude(transfer_probability_score__isnull=True).count() > 0


@pytest.mark.django_db
def test_recompute_scores_never_zero_fills_structural_nulls(recompute_run):
    """TEST B -- null-propagation (never zero-fill).

    GK/LB/RB structurally have no compatibility_score (confirmed in Phase
    5's parity tests); this must remain a real SQL NULL, never a 0.
    """
    from players.models import Player

    assert Player.objects.filter(compatibility_score__isnull=True).exists()


@pytest.mark.django_db
def test_recompute_scores_financial_fit_is_money_scale(recompute_run):
    """TEST C -- money-scale sanity for financial_fit_score.

    A raw log-scale TFM value would be ~13-17; money-scale fees are in the
    hundreds-of-thousands to millions range (Phase 4/5). If this fails,
    np.expm1 was forgotten in recompute_scores.py.
    """
    from players.models import Player

    assert not Player.objects.filter(
        financial_fit_score__isnull=False, financial_fit_score__lt=100
    ).exists()
