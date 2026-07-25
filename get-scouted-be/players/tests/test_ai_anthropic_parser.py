"""Behavior tests for AnthropicNLQueryParser (Plan 09-02).

Every test injects a fake client via the constructor's `client=` seam, so
no test ever constructs a real anthropic.Anthropic() -- the autouse
`_block_real_anthropic_calls` guard (conftest.py) would raise RuntimeError
if one tried. Real `anthropic` is imported only for its exception classes.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from players.ai.anthropic_parser import AnthropicNLQueryParser
from players.ai.base import NLQueryParserError, ParsedQuery


def _fake_tool_response(tool_input: dict):
    """Build a fake Anthropic Messages response whose content contains a
    single tool_use block with the given `.input`."""
    tool_block = SimpleNamespace(type="tool_use", input=tool_input)
    return SimpleNamespace(content=[tool_block])


def _fake_text_only_response():
    """A response with no tool_use block -- only text, simulating a
    malformed/unexpected reply."""
    text_block = SimpleNamespace(type="text", text="I'm not sure how to help.")
    return SimpleNamespace(content=[text_block])


def _fake_client(response=None, side_effect=None):
    client = MagicMock()
    if side_effect is not None:
        client.messages.create.side_effect = side_effect
    else:
        client.messages.create.return_value = response
    return client


def _real_request():
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


class TestAnthropicNLQueryParserHappyPath:
    def test_happy_path_maps_tool_use_input_to_parsed_query(self):
        client = _fake_client(
            response=_fake_tool_response(
                {"position": "LB", "market_value_max": 5000000}
            )
        )
        parser = AnthropicNLQueryParser(client=client)

        result = parser.parse("young left backs under 5 million")

        assert result == ParsedQuery(
            filters={"position": "LB", "market_value_max": 5000000},
            raw_query="young left backs under 5 million",
        )

    def test_style_field_key_survives_unchanged(self):
        client = _fake_client(
            response=_fake_tool_response({"club__control_possession_min": 15})
        )
        parser = AnthropicNLQueryParser(client=client)

        result = parser.parse("possession-heavy clubs")

        assert result.filters == {"club__control_possession_min": 15}

    def test_invalid_enum_dropped_but_valid_fields_kept(self):
        client = _fake_client(
            response=_fake_tool_response({"position": "STRIKER", "age_max": 21})
        )
        parser = AnthropicNLQueryParser(client=client)

        result = parser.parse("young strikers")

        assert "position" not in result.filters
        assert result.filters == {"age_max": 21}


class TestAnthropicNLQueryParserErrorHandling:
    @pytest.mark.parametrize(
        "make_error",
        [
            lambda: anthropic.RateLimitError(
                "rate limited",
                response=httpx.Response(429, request=_real_request()),
                body=None,
            ),
            lambda: anthropic.APITimeoutError(request=_real_request()),
            lambda: anthropic.APIConnectionError(request=_real_request()),
        ],
    )
    def test_api_error_subclasses_raise_nl_query_parser_error(self, make_error):
        client = _fake_client(side_effect=make_error())
        parser = AnthropicNLQueryParser(client=client)

        with pytest.raises(NLQueryParserError):
            parser.parse("anything")

    def test_malformed_response_with_no_tool_use_block_raises(self):
        client = _fake_client(response=_fake_text_only_response())
        parser = AnthropicNLQueryParser(client=client)

        with pytest.raises(NLQueryParserError):
            parser.parse("anything")


class TestAnthropicNLQueryParserDependencyInjection:
    def test_injected_client_prevents_any_real_network_call(self):
        """Documents the DI contract: constructing with an injected client
        never touches anthropic.Anthropic(), so the autouse guard in
        conftest.py is never triggered."""
        client = _fake_client(response=_fake_tool_response({"position": "GK"}))
        parser = AnthropicNLQueryParser(client=client)

        result = parser.parse("goalkeepers")

        client.messages.create.assert_called_once()
        assert result.filters == {"position": "GK"}
