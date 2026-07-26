"""Verifies the autouse safety-net fixture (clubs/tests/conftest.py) blocks
any real, billed anthropic.Anthropic() client construction during tests.

Per-app duplicate of players/tests/test_ai_safety_net.py -- clubs/tests/ is
a sibling of players/tests/, so it needs its own proof the guard is active
before any club-insights-generating test (10-04-PLAN.md Task 2/3) runs."""

import anthropic
import pytest


def test_real_anthropic_client_construction_is_blocked():
    with pytest.raises(RuntimeError):
        anthropic.Anthropic(api_key="x")
