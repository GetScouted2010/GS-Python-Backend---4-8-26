"""Grounding validator: numeric-token extraction + tolerance-match validation
of LLM narrative prose against a grounding dict (AI-03/AI-04).

This is the hard programmatic guarantee behind "no report ever contains an
LLM-invented number" -- prompt instructions alone ("only use these numbers")
are well-known to not fully prevent hallucination, so every generated
narrative is checked here BEFORE being returned to the client. Shared by both
the player scouting-report slice (Plan 03) and the club-insights slice
(Plan 04); never embedded inline in a view.

No existing money/percentage-formatting helper exists anywhere in the
codebase (grep-confirmed) -- this is built from scratch with stdlib `re`,
matching players/ai/fallback.py's existing hand-rolled regex-parsing style.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Tolerance constants -- deliberately module-level so they are easy to adjust.
# These will be empirically tuned against real LLM output during Plan 03/04
# manual verification (10-RESEARCH.md Open Question 1).
# ---------------------------------------------------------------------------
DEFAULT_REL_TOL = 0.05
DEFAULT_ABS_TOL = 0.5

# Matches: "€2.3M", "$5,000,000", "23", "7.4/10", "15%", "2.34 million", "23yo"
NUMERIC_TOKEN_RE = re.compile(
    r"""
    [€$]?\s*
    (?P<num>\d[\d,]*(?:\.\d+)?)
    \s*
    (?P<suffix>million|mil|m\b|thousand|k\b|%|percent)?
    """,
    re.IGNORECASE | re.VERBOSE,
)


def _normalize(num_str: str, suffix: str | None) -> float:
    """Strip thousands separators and scale by the matched suffix (if any).
    million/mil/m => *1_000_000; thousand/k => *1_000; percent/%/plain
    numbers/ratios pass through unscaled."""
    value = float(num_str.replace(",", ""))
    suffix = (suffix or "").lower()
    if suffix in ("million", "mil", "m"):
        return value * 1_000_000
    if suffix in ("thousand", "k"):
        return value * 1_000
    return value


def extract_numeric_tokens(text: str) -> list[float]:
    """Extract every numeric token in `text`, normalized to a raw,
    scale-agnostic float."""
    return [
        _normalize(m.group("num"), m.group("suffix"))
        for m in NUMERIC_TOKEN_RE.finditer(text)
    ]


def flatten_grounding_values(grounding: dict) -> list[float]:
    """Recursively walk the grounding dict, collecting every int/float leaf.
    Strings/None/bools are explicitly excluded; get_summary()'s and the
    club-insights dict's nested breakdown/component structures require
    recursion into dicts AND lists/tuples, not a flat .values() call."""
    values: list[float] = []

    def _walk(node):
        if isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                _walk(v)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            values.append(float(node))

    _walk(grounding)
    return values


def is_grounded(
    value: float,
    grounding_values: list[float],
    rel_tol: float = DEFAULT_REL_TOL,
    abs_tol: float = DEFAULT_ABS_TOL,
) -> bool:
    """Tolerant match: handles LLM rounding ("€2.3M" from raw 2,340,000;
    "7.4/10" from raw 7.42; "15%" from a raw 0.1523 fraction OR a raw 15.23
    already-percent value -- both scale candidates are checked). rel_tol=5%
    covers realistic prose rounding; abs_tol handles near-zero values where
    relative tolerance is meaningless."""
    candidates = {value, value / 100, value * 100}
    for gv in grounding_values:
        threshold = max(abs_tol, rel_tol * max(abs(gv), 1))
        for cand in candidates:
            if abs(cand - gv) <= threshold:
                return True
    return False


def _is_ratio_denominator(text: str, match: re.Match) -> bool:
    """True when `match` is immediately preceded (ignoring whitespace) by a
    "/", e.g. the "10" in "7.4/10". A ratio denominator like this is a fixed
    rating-scale marker, not a data claim the LLM could hallucinate -- it is
    structurally safe and excluded from grounding-checking (10-RESEARCH.md
    Pitfall 3: incidental non-data numbers producing validator
    false-positives)."""
    i = match.start() - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    return i >= 0 and text[i] == "/"


def validate_grounding(
    narrative_text: str,
    grounding: dict,
    rel_tol: float = DEFAULT_REL_TOL,
    abs_tol: float = DEFAULT_ABS_TOL,
) -> list[float]:
    """Return the list of numeric tokens extracted from `narrative_text` that
    fail to trace back (within tolerance) to any numeric leaf in `grounding`.
    Empty list == fully grounded -- this is the pass/fail signal the calling
    generator uses to decide whether to retry or raise ReportGeneratorError.
    Ratio denominators (e.g. the "10" in "7.4/10") are structurally exempted
    -- see `_is_ratio_denominator`."""
    grounding_values = flatten_grounding_values(grounding)
    ungrounded: list[float] = []
    for m in NUMERIC_TOKEN_RE.finditer(narrative_text):
        if _is_ratio_denominator(narrative_text, m):
            continue
        value = _normalize(m.group("num"), m.group("suffix"))
        if not is_grounded(value, grounding_values, rel_tol, abs_tol):
            ungrounded.append(value)
    return ungrounded
