"""Behavior tests for get_report_generator() (Plan 10-02, AI-05).

Test 3 deliberately never imports AnthropicReportGenerator in its call path --
it only asserts the factory function is importable from players.ai.report_factory
and satisfies the ReportGenerator interface, proving calling code needs no
concrete-class knowledge to swap providers.
"""

import pytest
from django.test import override_settings

from players.ai.report_factory import get_report_generator
from players.ai.report_generator import ReportGenerator


@override_settings(LLM_PROVIDER="anthropic")
def test_returns_anthropic_generator_for_anthropic_provider():
    from players.ai.anthropic_report_generator import AnthropicReportGenerator

    generator = get_report_generator()

    assert isinstance(generator, AnthropicReportGenerator)
    assert isinstance(generator, ReportGenerator)


@override_settings(LLM_PROVIDER="bogus")
def test_unknown_provider_raises_value_error():
    with pytest.raises(ValueError, match="bogus"):
        get_report_generator()


@override_settings(LLM_PROVIDER="anthropic")
def test_factory_is_the_sole_import_needed_by_calling_code():
    import players.ai.report_factory as report_factory_module

    assert hasattr(report_factory_module, "get_report_generator")

    generator = report_factory_module.get_report_generator()

    assert isinstance(generator, ReportGenerator)
