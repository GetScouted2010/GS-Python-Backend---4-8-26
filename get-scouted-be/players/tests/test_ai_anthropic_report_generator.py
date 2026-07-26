"""Behavior tests for AnthropicReportGenerator (Plan 10-02).

Every test injects a fake client via the constructor's `client=` seam, so no
test ever constructs a real anthropic.Anthropic() -- the autouse
`_block_real_anthropic_calls` guard (conftest.py) would raise RuntimeError if
one tried. Real `anthropic` is imported only for its exception classes.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import httpx
import pytest

from players.ai.anthropic_report_generator import AnthropicReportGenerator
from players.ai.report_generator import GeneratedReport, ReportGeneratorError

PLAYER_GROUNDING = {
    "player_name": "Test Player",
    "age": 23,
    "market_value": 5000000,
    "impact_score": 78.5,
    "compatibility_score": 82.0,
    "financial_fit_score": 65.0,
}

CLUB_GROUNDING = {
    "club_name": "Test FC",
    "squad_size": 25,
    "average_age": 26.4,
    "financial_constraint_index": 40.0,
}

PLAYER_NARRATIVE_TEXT = """\
## Strengths
The player (age 23) has a strong impact score of 78.5.

## Weaknesses
Financial fit sits at 65.0, slightly below ideal.

## Tactical Fit
Compatibility score of 82.0 suggests a strong tactical match.

## Financial Fit
Market value of €5.0M is reasonable for this profile.

## Best Use Case
Best deployed as an impact squad addition given the 78.5 rating.
"""

CLUB_NARRATIVE_TEXT = """\
## Recruitment Gaps
Test FC carries a squad of 25 players.

## Over-Aged Positions
Average squad age is 26.4 years.

## Financial Constraints
The financial constraint index stands at 40.0.
"""

PLAYER_NARRATIVE_MISSING_HEADER = """\
## Strengths
The player has a strong impact score of 78.5.

## Weaknesses
Financial fit sits at 65.0.

## Tactical Fit
Compatibility score of 82.0.

## Financial Fit
Market value of €5.0M.
"""

PLAYER_NARRATIVE_HALLUCINATED = """\
## Strengths
The player has a strong impact score of 78.5.

## Weaknesses
Financial fit sits at 65.0.

## Tactical Fit
Compatibility score of 82.0, and a hidden rating of 999.9.

## Financial Fit
Market value of €5.0M.

## Best Use Case
Best deployed as an impact squad addition.
"""


def _text_response(text: str):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def _fake_client(response=None, side_effect=None):
    client = MagicMock()
    if side_effect is not None:
        client.messages.create.side_effect = side_effect
    else:
        client.messages.create.return_value = response
    return client


def _real_request():
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


class TestAnthropicReportGeneratorHappyPath:
    def test_player_report_returns_section_keyed_narrative(self):
        client = _fake_client(response=_text_response(PLAYER_NARRATIVE_TEXT))
        generator = AnthropicReportGenerator(client=client)

        result = generator.generate(PLAYER_GROUNDING, "player_scouting_report")

        assert isinstance(result, GeneratedReport)
        assert set(result.narrative.keys()) == {
            "strengths",
            "weaknesses",
            "tactical_fit",
            "financial_fit",
            "best_use_case",
        }
        assert result.grounding == PLAYER_GROUNDING

    def test_club_report_returns_section_keyed_narrative(self):
        client = _fake_client(response=_text_response(CLUB_NARRATIVE_TEXT))
        generator = AnthropicReportGenerator(client=client)

        result = generator.generate(CLUB_GROUNDING, "club_insights")

        assert isinstance(result, GeneratedReport)
        assert set(result.narrative.keys()) == {
            "recruitment_gaps",
            "over_aged_positions",
            "financial_constraints",
        }
        assert result.grounding == CLUB_GROUNDING


class TestAnthropicReportGeneratorMalformedOutput:
    def test_missing_header_raises(self):
        client = _fake_client(response=_text_response(PLAYER_NARRATIVE_MISSING_HEADER))
        generator = AnthropicReportGenerator(client=client)

        with pytest.raises(ReportGeneratorError):
            generator.generate(PLAYER_GROUNDING, "player_scouting_report")


class TestAnthropicReportGeneratorApiError:
    def test_api_error_raises_report_generator_error(self):
        client = _fake_client(
            side_effect=anthropic.APITimeoutError(request=_real_request())
        )
        generator = AnthropicReportGenerator(client=client)

        with pytest.raises(ReportGeneratorError):
            generator.generate(PLAYER_GROUNDING, "player_scouting_report")


class TestAnthropicReportGeneratorGroundingRetry:
    def test_grounding_failure_retries_once_then_raises(self):
        client = _fake_client(
            side_effect=[
                _text_response(PLAYER_NARRATIVE_HALLUCINATED),
                _text_response(PLAYER_NARRATIVE_HALLUCINATED),
            ]
        )
        generator = AnthropicReportGenerator(client=client)

        with pytest.raises(ReportGeneratorError):
            generator.generate(PLAYER_GROUNDING, "player_scouting_report")

        assert client.messages.create.call_count == 2

    def test_grounding_failure_retry_recovers(self):
        client = _fake_client(
            side_effect=[
                _text_response(PLAYER_NARRATIVE_HALLUCINATED),
                _text_response(PLAYER_NARRATIVE_TEXT),
            ]
        )
        generator = AnthropicReportGenerator(client=client)

        result = generator.generate(PLAYER_GROUNDING, "player_scouting_report")

        assert isinstance(result, GeneratedReport)
        assert client.messages.create.call_count == 2


class TestAnthropicReportGeneratorDependencyInjection:
    def test_injected_client_used_with_no_tool_kwargs(self):
        """Documents the DI contract: constructing with an injected client
        never touches anthropic.Anthropic(), so the autouse guard in
        conftest.py is never triggered -- and the call is plain generation,
        never forced tool-use."""
        client = _fake_client(response=_text_response(PLAYER_NARRATIVE_TEXT))
        generator = AnthropicReportGenerator(client=client)

        generator.generate(PLAYER_GROUNDING, "player_scouting_report")

        client.messages.create.assert_called_once()
        _, kwargs = client.messages.create.call_args
        assert "tools" not in kwargs
        assert "tool_choice" not in kwargs
