"""Behavior tests for get_nl_query_parser() (Plan 09-02, AI-05).

Test 3 deliberately never imports AnthropicNLQueryParser in its call path --
it only asserts the factory function is importable from players.ai.factory
and satisfies the NLQueryParser interface, proving calling code needs no
concrete-class knowledge to swap providers.
"""

import pytest
from django.test import override_settings

from players.ai.base import NLQueryParser
from players.ai.factory import get_nl_query_parser


@override_settings(LLM_PROVIDER="anthropic")
def test_returns_anthropic_parser_for_anthropic_provider():
    from players.ai.anthropic_parser import AnthropicNLQueryParser

    parser = get_nl_query_parser()

    assert isinstance(parser, AnthropicNLQueryParser)
    assert isinstance(parser, NLQueryParser)


@override_settings(LLM_PROVIDER="bogus")
def test_unknown_provider_raises_value_error():
    with pytest.raises(ValueError, match="bogus"):
        get_nl_query_parser()


@override_settings(LLM_PROVIDER="anthropic")
def test_factory_is_the_sole_import_needed_by_calling_code():
    import players.ai.factory as factory_module

    assert hasattr(factory_module, "get_nl_query_parser")

    parser = factory_module.get_nl_query_parser()

    assert isinstance(parser, NLQueryParser)
