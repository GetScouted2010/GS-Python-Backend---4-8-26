"""Shared fixtures for clubs/tests/ (Phase 7).

Club-scoped mirror of scoring/tests/conftest.py's real_data_available: the
CRUD-02/CRUD-04 integration tests skip cleanly against the empty test DB
(real migrated club/transfer data lives only in the dev DB).
"""

import pytest


@pytest.fixture
def real_data_available(db):
    from clubs.models import Club

    if Club.objects.count() == 0:
        pytest.skip(
            "No real Club data in the dev DB -- run Phase 1's import_all "
            "management command first to populate real migrated data."
        )
