"""Contract tests for the provider-agnostic NLQueryParser interface (AI-05).

These tests define the shape every concrete parser implementation (Plan 02's
AnthropicNLQueryParser, and any future provider) must satisfy. No network
calls -- this module never touches the anthropic package.
"""

import pytest

from players.ai.base import NLQueryParser, NLQueryParserError, ParsedQuery


def test_nl_query_parser_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        NLQueryParser()


def test_concrete_subclass_can_be_instantiated_and_parse_returns_parsed_query():
    class _Concrete(NLQueryParser):
        def parse(self, query: str) -> ParsedQuery:
            return ParsedQuery(filters={"position": "CB"}, raw_query=query)

    parser = _Concrete()
    result = parser.parse("a centre back")

    assert isinstance(result, ParsedQuery)
    assert result.filters == {"position": "CB"}
    assert result.raw_query == "a centre back"


def test_parsed_query_exposes_filters_and_raw_query():
    parsed = ParsedQuery(filters={"position": "CB"}, raw_query="a centre back")

    assert parsed.filters == {"position": "CB"}
    assert parsed.raw_query == "a centre back"


def test_nl_query_parser_error_is_an_exception_subclass():
    assert issubclass(NLQueryParserError, Exception)
