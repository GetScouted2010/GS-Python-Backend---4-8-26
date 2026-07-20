"""
Shared pytest fixtures for the whole get-scouted-be test suite.

Tests that need database access should use pytest-django's built-in
`db` fixture (or the `@pytest.mark.django_db` marker) -- no custom
wrapper fixture is defined here, pytest-django already provides it
once `DJANGO_SETTINGS_MODULE` is configured (see pyproject.toml).
"""

import pytest
from pathlib import Path


@pytest.fixture
def fixture_dir() -> Path:
    """Canonical path to core/tests/fixtures/, derived from this file's location.

    Every import test uses this to locate its small, hand-seeded sample CSV
    instead of the full-size real dataset files.
    """
    return Path(__file__).resolve().parent / "fixtures"
