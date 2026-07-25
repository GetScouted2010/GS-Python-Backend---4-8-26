"""Verifies the autouse safety-net fixture (players/tests/conftest.py) blocks
any real, billed anthropic.Anthropic() client construction during tests."""

import anthropic
import pytest


def test_real_anthropic_client_construction_is_blocked():
    with pytest.raises(RuntimeError):
        anthropic.Anthropic(api_key="x")
