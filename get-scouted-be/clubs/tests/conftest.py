"""Shared fixtures for clubs/tests/ (Phase 7, Phase 10).

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


@pytest.fixture(autouse=True)
def _block_real_anthropic_calls(monkeypatch):
    """Safety net: no test may fire a real, billed Anthropic API call.
    Replaces anthropic.Anthropic with a guard that raises on instantiation.
    Tests that exercise club-insights generation MUST inject a fake
    generator/client (patch the caller's own binding) -- never rely on
    ANTHROPIC_API_KEY being unset.

    Per-app duplicate of players/tests/conftest.py's guard (verbatim copy):
    pytest conftest fixtures are directory-scoped, and clubs/tests/ is a
    sibling of players/tests/ (not a descendant), so the players guard does
    NOT cover this directory. Mirrors this project's established
    per-app-duplication convention (e.g. ClubExportView's duplicated Echo
    class)."""
    import anthropic

    class _GuardAnthropic:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(
                "Real anthropic.Anthropic() construction blocked in tests. "
                "Inject a fake client or patch the parser binding instead."
            )

    monkeypatch.setattr(anthropic, "Anthropic", _GuardAnthropic)
