"""Provider-agnostic narrative report-generation interface (AI-03/AI-04).

This is the contract every concrete ReportGenerator implementation (Plan 03's
AnthropicReportGenerator, and any future provider) must satisfy. Calling code
never imports a concrete class directly -- it goes through
players.ai.report_factory.get_report_generator(), which reads
settings.LLM_PROVIDER. Mirrors players/ai/base.py's NLQueryParser triad shape
exactly (AI-05's provider-agnostic pattern).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GeneratedReport:
    """The structured output of any ReportGenerator.

    `narrative` is a dict keyed by section name: for a player scouting report
    ("strengths"/"weaknesses"/"tactical_fit"/"financial_fit"/"best_use_case");
    for club insights ("recruitment_gaps"/"over_aged_positions"/
    "financial_constraints"). `grounding` echoes back the exact dict used to
    build the prompt -- transparency/traceability per the locked endpoint
    contract."""

    narrative: dict = field(default_factory=dict)
    grounding: dict = field(default_factory=dict)


class ReportGeneratorError(Exception):
    """Raised by a concrete generator when the provider call fails, returns
    unusable output, OR the grounding validator rejects the result after the
    retry. The calling view catches THIS to return the clean 503 error --
    never a fallback narrative."""


class ReportGenerator(ABC):
    """Provider-agnostic narrative-generation interface (AI-03/AI-04), one
    method. Concrete implementations (AnthropicReportGenerator, any future
    provider) are selected by players.ai.report_factory.get_report_generator()
    reading settings.LLM_PROVIDER -- calling code never imports a concrete
    class."""

    @abstractmethod
    def generate(self, grounding: dict, report_type: str) -> GeneratedReport:
        """Write narrative prose strictly grounded in `grounding`'s numbers.
        Raise ReportGeneratorError on provider failure / malformed output.
        `report_type` is one of "player_scouting_report" or "club_insights"."""
