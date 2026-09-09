"""Concrete AnthropicNLQueryParser (AI-01 / AI-05, Plan 09-02).

Uses the Anthropic Messages API with FORCED tool-use so the model's output is
schema-constrained rather than free text -- the tool's input_schema mirrors
the real PlayerFilter/ClubFilter whitelist exactly (see players/filters.py
and clubs/filters.py). LLM output is still treated as UNTRUSTED: `_validate`
drops any key outside the whitelist and any hallucinated position/league
enum value before it can reach the ORM.
"""

import anthropic
from django.conf import settings

from clubs.leagues import REAL_LEAGUES
from players.ai.base import NLQueryParser, NLQueryParserError, ParsedQuery

# The CLEAN 10-value Player.position group (never main_position's 22 values).
REAL_POSITIONS = {"AM", "CB", "CM", "DM", "FWD", "GK", "LB", "LW", "RB", "RW"}

# REAL_LEAGUES moved to clubs/leagues.py (A3 fix) -- it's now the shared
# whitelist of in-scope leagues, not a private copy of this parser's.

# The 8 ClubFilter style fields, emitted by the LLM as club__<field>_min keys.
STYLE_FIELD_KEYS = {
    "club__control_possession_min",
    "club__gegenpressing_min",
    "club__direct_play_min",
    "club__tiki_taka_min",
    "club__counter_attack_min",
    "club__wing_play_min",
    "club__low_block_min",
    "club__defensive_counter_attack_min",
}

# The full whitelist key set the tool schema exposes -- anything outside this
# set is dropped by _validate, no matter what the LLM returns.
WHITELIST_KEYS = {
    "position",
    "league",
    "age_min",
    "age_max",
    "market_value_min",
    "market_value_max",
    "impact_score_min",
    "compatibility_score_min",
    "financial_fit_score_min",
    "transfer_probability_score_min",
} | STYLE_FIELD_KEYS

FILTER_TOOL = {
    "name": "extract_player_filters",
    "description": (
        "Extract structured player search filters from a natural-language "
        "scouting query. Omit any field the query does not address -- do "
        "not guess or invent values."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "position": {
                "type": "string",
                "enum": sorted(REAL_POSITIONS),
                "description": "Player's position group.",
            },
            "league": {
                "type": "string",
                "enum": sorted(REAL_LEAGUES),
                "description": "Player's league.",
            },
            "age_min": {"type": "integer", "description": "Minimum age (inclusive)."},
            "age_max": {"type": "integer", "description": "Maximum age (inclusive)."},
            "market_value_min": {
                "type": "integer",
                "description": "Minimum market value in currency units.",
            },
            "market_value_max": {
                "type": "integer",
                "description": "Maximum market value in currency units.",
            },
            "impact_score_min": {
                "type": "number",
                "description": "Minimum Impact (RMM) score threshold.",
            },
            "compatibility_score_min": {
                "type": "number",
                "description": "Minimum compatibility score threshold.",
            },
            "financial_fit_score_min": {
                "type": "number",
                "description": "Minimum financial fit score threshold.",
            },
            "transfer_probability_score_min": {
                "type": "number",
                "description": "Minimum transfer probability score threshold.",
            },
            "club__control_possession_min": {"type": "number"},
            "club__gegenpressing_min": {"type": "number"},
            "club__direct_play_min": {"type": "number"},
            "club__tiki_taka_min": {"type": "number"},
            "club__counter_attack_min": {"type": "number"},
            "club__wing_play_min": {"type": "number"},
            "club__low_block_min": {"type": "number"},
            "club__defensive_counter_attack_min": {"type": "number"},
        },
        "additionalProperties": False,
    },
}


class AnthropicNLQueryParser(NLQueryParser):
    """Forced tool-use extraction against the Anthropic Messages API.

    Constructor accepts an optional injected `client` for testability -- the
    real anthropic.Anthropic() client is constructed lazily inside parse(),
    never in __init__, so tests can inject a fake client without tripping
    the autouse `_block_real_anthropic_calls` guard (players/tests/conftest.py).
    """

    def __init__(self, client=None):
        self._client = client

    def parse(self, query: str) -> ParsedQuery:
        client = self._client or anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        try:
            response = client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=512,
                tools=[FILTER_TOOL],
                tool_choice={"type": "tool", "name": "extract_player_filters"},
                messages=[{"role": "user", "content": query}],
            )
            tool_block = next(b for b in response.content if b.type == "tool_use")
            raw_filters = dict(tool_block.input)
        except anthropic.APIError as exc:
            # Parent class -- covers RateLimitError, InternalServerError,
            # APIConnectionError, APITimeoutError, all APIStatusError
            # subclasses (auth/permission/not-found/bad-request/etc).
            raise NLQueryParserError("Anthropic API call failed") from exc
        except (StopIteration, KeyError, TypeError, AttributeError) as exc:
            raise NLQueryParserError(
                "Anthropic returned an unusable/malformed response"
            ) from exc

        return ParsedQuery(filters=self._validate(raw_filters), raw_query=query)

    def _validate(self, raw_filters: dict) -> dict:
        """Treat LLM output as UNTRUSTED. Drop unknown keys and hallucinated
        position/league enum values before anything reaches the ORM."""
        validated = {}
        for key, value in raw_filters.items():
            if key not in WHITELIST_KEYS:
                continue
            if key == "position" and value not in REAL_POSITIONS:
                continue
            if key == "league" and value not in REAL_LEAGUES:
                continue
            validated[key] = value
        return validated
