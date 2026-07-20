"""Root-level pytest conftest.

pytest only auto-discovers a conftest.py's fixtures for test files in the same
directory or a descendant directory. `core/tests/conftest.py`'s `fixture_dir`
fixture is meant to be shared by every app's import tests (clubs/, players/,
transfers/), which live as siblings of core/tests/, not descendants of it -- so
it must be re-exported from this repo-root conftest.py to actually be visible
there.
"""

from core.tests.conftest import fixture_dir  # noqa: F401
