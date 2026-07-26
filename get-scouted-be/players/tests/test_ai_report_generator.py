"""Contract tests for the provider-agnostic ReportGenerator interface
(AI-03/AI-04). These tests define the shape every concrete implementation
(Plan 03's AnthropicReportGenerator, and any future provider) must satisfy.
No network calls -- this module never touches the anthropic package."""

import pytest

from players.ai.report_generator import (
    GeneratedReport,
    ReportGenerator,
    ReportGeneratorError,
)


def test_generated_report_defaults_to_empty_independent_dicts():
    report_a = GeneratedReport()
    report_b = GeneratedReport()

    assert report_a.narrative == {}
    assert report_a.grounding == {}

    report_a.narrative["strengths"] = "x"
    assert report_b.narrative == {}  # independent instances, not a shared default


def test_generated_report_round_trips_narrative_and_grounding():
    report = GeneratedReport(
        narrative={"strengths": "x"}, grounding={"rmm": 1}
    )

    assert report.narrative == {"strengths": "x"}
    assert report.grounding == {"rmm": 1}


def test_report_generator_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ReportGenerator()


def test_report_generator_error_is_an_exception_subclass():
    assert issubclass(ReportGeneratorError, Exception)


def test_concrete_subclass_can_be_instantiated_and_generate_returns_generated_report():
    class _Concrete(ReportGenerator):
        def generate(self, grounding: dict, report_type: str) -> GeneratedReport:
            return GeneratedReport(
                narrative={"strengths": "grounded prose"}, grounding=grounding
            )

    generator = _Concrete()
    result = generator.generate({"rmm": {"rmm": 7.4}}, "player_scouting_report")

    assert isinstance(result, GeneratedReport)
    assert result.narrative == {"strengths": "grounded prose"}
    assert result.grounding == {"rmm": {"rmm": 7.4}}
