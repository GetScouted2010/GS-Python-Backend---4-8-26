"""Shared fixtures for scoring/tests/.

Unlike clubs/players/transfers/core's import tests (which use small
hand-seeded fixture CSVs), this phase's characterization tests query REAL
migrated Phase 1 data directly from the dev database -- see
03-VALIDATION.md "Wave 0 Requirements". `real_data_available` lets those
tests degrade gracefully (skip with a clear message) when run against an
empty database instead of failing confusingly.
"""

import pytest


@pytest.fixture
def real_data_available(db):
    """Skip the current test if the dev DB has no migrated Player rows.

    Depends on pytest-django's `db` fixture (rather than being marked with
    `@pytest.mark.django_db` directly -- marks cannot be applied to fixture
    functions) to get database access.
    """
    from players.models import Player

    if Player.objects.count() == 0:
        pytest.skip(
            "No real Player data in the dev DB -- run Phase 1's import_all "
            "management command first to populate real migrated data."
        )
