"""Shared fixtures for players/tests/ (Phase 7).

real_data_available lets the CRUD integration tests degrade gracefully
(skip with a clear message) when run against the empty pytest test DB --
Phase 1's real migrated data (41,708 players) lives only in the dev DB,
never copied into test_getscouted. Mirrors scoring/tests/conftest.py.
"""

import pytest


@pytest.fixture
def real_data_available(db):
    from players.models import Player

    if Player.objects.count() == 0:
        pytest.skip(
            "No real Player data in the dev DB -- run Phase 1's import_all "
            "management command first to populate real migrated data."
        )
