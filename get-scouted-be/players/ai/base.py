"""Provider-agnostic natural-language search interface (AI-05).

This is the contract every concrete NLQueryParser implementation (Plan 02's
AnthropicNLQueryParser, and any future provider) must satisfy. Calling code
never imports a concrete class directly -- it goes through
players.ai.factory.get_nl_query_parser(), which reads settings.LLM_PROVIDER.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedQuery:
    """The structured output of any NLQueryParser. `filters` keys are
    restricted to the PlayerFilter/style whitelist by the concrete parser;
    `raw_query` preserves the original free text for RecentActivity logging."""

    filters: dict = field(default_factory=dict)
    raw_query: str = ""


class NLQueryParserError(Exception):
    """Raised by a concrete parser when the underlying provider call fails or
    returns an unusable response. The search view catches THIS to fall back to
    the deterministic tier-2 keyword extractor (never surfaced to the client)."""


class NLQueryParser(ABC):
    """Provider-agnostic natural-language -> structured-filter interface (AI-05).
    One method. Concrete implementations (AnthropicNLQueryParser, any future
    provider) are selected by players.ai.factory.get_nl_query_parser() reading
    settings.LLM_PROVIDER -- calling code never imports a concrete class."""

    @abstractmethod
    def parse(self, query: str) -> ParsedQuery:
        """Map free text onto the fixed real-field whitelist. Raise
        NLQueryParserError on provider failure / malformed output."""
