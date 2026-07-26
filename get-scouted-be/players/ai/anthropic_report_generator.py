"""Concrete AnthropicReportGenerator (AI-03 / AI-04, Plan 10-02).

Uses the Anthropic Messages API with PLAIN (non-tool-use) generation --
unlike Phase 9's AnthropicNLQueryParser, forced tool-use extraction kwargs
are never passed to the Messages API call. The model writes free-form
narrative prose broken into named `## <Header>`
markdown sections. Every generated narrative is validated against the
grounding dict (players/ai/grounding.py) BEFORE being returned; on a
grounding failure the generator retries generation exactly once with
corrective feedback naming the offending numbers, then raises
ReportGeneratorError rather than ever returning a partially-fabricated
report.
"""

from __future__ import annotations

import json
import re

import anthropic
from django.conf import settings

from players.ai.grounding import validate_grounding
from players.ai.report_generator import (
    GeneratedReport,
    ReportGenerator,
    ReportGeneratorError,
)

# The exact, ordered `## <Header>` markdown sections the model must emit for
# each report_type. Order here drives both the prompt instructions and the
# parser's required-header set.
PLAYER_SECTIONS = ["Strengths", "Weaknesses", "Tactical Fit", "Financial Fit", "Best Use Case"]
CLUB_SECTIONS = ["Recruitment Gaps", "Over-Aged Positions", "Financial Constraints"]

SECTIONS_BY_TYPE = {
    "player_scouting_report": PLAYER_SECTIONS,
    "club_insights": CLUB_SECTIONS,
}

# Bounded retry: one original attempt + one corrective retry, never unbounded.
MAX_ATTEMPTS = 2


def _header_to_key(header: str) -> str:
    """"Best Use Case" -> "best_use_case"; "Over-Aged Positions" ->
    "over_aged_positions"."""
    return header.lower().replace(" ", "_").replace("-", "_")


class AnthropicReportGenerator(ReportGenerator):
    """Concrete plain-text (non-tool-use) Anthropic report generator.

    Constructor accepts an optional injected `client` for testability -- the
    real anthropic.Anthropic() client is constructed lazily inside generate(),
    never in __init__, mirroring AnthropicNLQueryParser's DI seam exactly so
    tests can inject a fake client without tripping the autouse
    `_block_real_anthropic_calls` guard (players/tests/conftest.py).
    """

    def __init__(self, client=None):
        self._client = client

    def generate(self, grounding: dict, report_type: str) -> GeneratedReport:
        sections = SECTIONS_BY_TYPE.get(report_type)
        if sections is None:
            raise ReportGeneratorError(f"Unknown report_type: {report_type!r}")

        ungrounded: list[float] | None = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            prompt = self._build_prompt(grounding, sections, ungrounded)
            text = self._call_model(prompt)
            narrative = self._parse_sections(text, sections)

            ungrounded = validate_grounding(text, grounding)
            if not ungrounded:
                return GeneratedReport(narrative=narrative, grounding=grounding)

            if attempt == MAX_ATTEMPTS:
                raise ReportGeneratorError(
                    "report contained ungrounded numbers after retry"
                )

        # Unreachable given MAX_ATTEMPTS >= 1, kept for safety.
        raise ReportGeneratorError("report generation failed")

    def _call_model(self, prompt: str) -> str:
        client = self._client or anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        try:
            response = client.messages.create(
                model=settings.ANTHROPIC_REPORT_MODEL,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIError as exc:
            # Parent class -- covers RateLimitError, InternalServerError,
            # APIConnectionError, APITimeoutError, all APIStatusError
            # subclasses (auth/permission/not-found/bad-request/etc).
            raise ReportGeneratorError("Anthropic API call failed") from exc

        text = "".join(
            block.text
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        if not text.strip():
            raise ReportGeneratorError("Anthropic returned an unusable/empty response")
        return text

    def _build_prompt(
        self,
        grounding: dict,
        sections: list[str],
        ungrounded: list[float] | None,
    ) -> str:
        headers = "\n".join(f"## {section}" for section in sections)
        prompt = (
            "You are a football scouting analyst writing a report. Use ONLY "
            "the numbers present in the following JSON grounding data -- "
            "NEVER invent, estimate, or extrapolate any number that is not "
            "explicitly present in this data:\n\n"
            f"{json.dumps(grounding)}\n\n"
            "Structure your response with EXACTLY these markdown headers, in "
            "this exact order, each on its own line:\n\n"
            f"{headers}\n\n"
            "Write substantive prose under each header, grounded strictly in "
            "the provided data above."
        )
        if ungrounded:
            prompt += (
                "\n\nCORRECTION REQUIRED: your previous response contained "
                f"the following numbers that do NOT appear anywhere in the "
                f"grounding data: {ungrounded}. Rewrite the full report, "
                "removing or correcting every figure not present in the "
                "grounding data above -- do not repeat this mistake."
            )
        return prompt

    def _parse_sections(self, text: str, sections: list[str]) -> dict:
        pattern = r"^##\s+(" + "|".join(re.escape(s) for s in sections) + r")\s*$"
        parts = re.split(pattern, text, flags=re.MULTILINE)

        found: dict[str, str] = {}
        # parts[0] is any preamble before the first header (discarded); after
        # that, parts alternate: header, body, header, body, ...
        for i in range(1, len(parts), 2):
            header = parts[i].strip()
            body = parts[i + 1].strip() if i + 1 < len(parts) else ""
            found[_header_to_key(header)] = body

        expected_keys = {_header_to_key(s) for s in sections}
        if set(found.keys()) != expected_keys:
            missing = sorted(expected_keys - set(found.keys()))
            raise ReportGeneratorError(
                f"malformed report: missing section headers {missing}"
            )
        return found
