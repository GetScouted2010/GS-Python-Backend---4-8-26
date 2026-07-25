"""Tier-2 deterministic keyword fallback extractor (AI-02).

`keyword_extract(query)` maps free text onto the PlayerFilter whitelist using
only stdlib `re` -- no LLM, no network, never raises. This is the search
view's guaranteed-to-succeed fallback tier when the LLM call fails (Plan 04):
whatever it cannot confidently extract, it simply omits (returns `{}` when it
extracts nothing usable, never an error).

Three extractors, each independent and best-effort:
1. Position -- regex/synonym matching onto the 10 real position codes
   (AM/CB/CM/DM/FWD/GK/LB/LW/RB/RW). Longest/most-specific synonym phrases
   are checked and the leftmost match in the query wins.
2. Money -- a "<number><m/k/million/thousand>" pattern (optionally preceded
   by a €/$ sign), scaled to raw euros (never left as "5"). Direction words
   ("under"/"below"/"less than" -> market_value_max; "over"/"above"/"more
   than" -> market_value_min) select which bound to set; a bare amount with
   no direction word defaults to market_value_max (reads as a budget
   ceiling, e.g. "strikers under a budget of €5M" style asks).
3. League -- substring match against the 25 real league strings. Several
   real leagues share a base term ("Bundesliga", "Serie", "La Liga",
   "Ligue", "EFL") -- these are NEVER guessed from the bare base term alone;
   a qualifier (country name/adjective, or the specific number/word that
   disambiguates) must also be present in the query. This mirrors the
   project's "degrade, never fabricate" principle (09-CONTEXT.md).

NOTE: age ("young"/"veteran" etc.) is intentionally NOT mapped by this
extractor -- it is not required by 09-03-PLAN.md and free-text age
descriptors are too fuzzy to whitelist deterministically without risking a
wrong guess.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Position synonyms -- each entry maps to one of the 10 real position codes.
# Patterns use \b word boundaries and IGNORECASE matching; multi-word phrases
# and 2-letter codes are grouped per-code so a single leftmost match across
# all codes is chosen (no cross-code ambiguity within a single code's group).
# ---------------------------------------------------------------------------
POSITION_PATTERNS: dict[str, re.Pattern[str]] = {
    "AM": re.compile(r"\battacking\s*midfield(?:er)?s?\b|\bam\b", re.IGNORECASE),
    "CB": re.compile(
        r"\bcent(?:re|er)[\s-]*backs?\b|\bdefender\s*\(\s*centre\s*\)|\bcb\b",
        re.IGNORECASE,
    ),
    "CM": re.compile(r"\bcentral\s*midfield(?:er)?s?\b|\bcm\b", re.IGNORECASE),
    "DM": re.compile(r"\bdefensive\s*midfield(?:er)?s?\b|\bdm\b", re.IGNORECASE),
    "FWD": re.compile(r"\bstrikers?\b|\bforwards?\b|\bfwd\b", re.IGNORECASE),
    "GK": re.compile(r"\bgoalkeepers?\b|\bkeepers?\b|\bgk\b", re.IGNORECASE),
    "LB": re.compile(r"\bleft[\s-]*backs?\b|\blb\b", re.IGNORECASE),
    "LW": re.compile(r"\bleft\s*wing(?:er)?s?\b|\blw\b", re.IGNORECASE),
    "RB": re.compile(r"\bright[\s-]*backs?\b|\brb\b", re.IGNORECASE),
    "RW": re.compile(r"\bright\s*wing(?:er)?s?\b|\brw\b", re.IGNORECASE),
}

# ---------------------------------------------------------------------------
# Money: "<number>(m|million|k|thousand)" optionally preceded by €/$.
# ---------------------------------------------------------------------------
_MONEY_RE = re.compile(
    r"[€$]?\s*(\d+(?:\.\d+)?)\s*(million|m|thousand|k)\b", re.IGNORECASE
)
_UNDER_RE = re.compile(r"\b(under|below|less than)\b", re.IGNORECASE)
_OVER_RE = re.compile(r"\b(over|above|more than)\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# League matching. Each pattern matches only when the query unambiguously
# identifies ONE of the 25 real leagues. Shared base terms ("bundesliga",
# "serie", "la liga", "ligue", "efl") require a qualifier (country
# name/adjective, or the disambiguating number/word) to also appear;
# otherwise none of that group's patterns match and `league` is left unset.
# ---------------------------------------------------------------------------
LEAGUE_PATTERNS: dict[str, re.Pattern[str]] = {
    "Allsvenskan (Sweden)": re.compile(r"\ballsvenskan\b", re.IGNORECASE),
    "Bundesliga (Austria)": re.compile(
        r"\bbundesliga\b.*\b(austria|austrian)\b|\b(austria|austrian)\b.*\bbundesliga\b",
        re.IGNORECASE,
    ),
    "Bundesliga (Germany)": re.compile(
        r"\bbundesliga\b.*\b(german|germany)\b|\b(german|germany)\b.*\bbundesliga\b",
        re.IGNORECASE,
    ),
    "Bundesliga 2": re.compile(r"\bbundesliga\s*2\b", re.IGNORECASE),
    "Challenger Pro League": re.compile(r"\bchallenger pro league\b", re.IGNORECASE),
    "EFL Championship": re.compile(
        r"\befl\b.*\bchampionship\b|\bchampionship\b.*\befl\b", re.IGNORECASE
    ),
    "EFL League One": re.compile(
        r"\befl\b.*\bleague one\b|\bleague one\b.*\befl\b", re.IGNORECASE
    ),
    "Eerste Divisie": re.compile(r"\beerste divisie\b", re.IGNORECASE),
    "Eliteserien": re.compile(r"\beliteserien\b", re.IGNORECASE),
    "Eredivisie (Netherlands)": re.compile(r"\beredivisie\b", re.IGNORECASE),
    "La Liga (Spain)": re.compile(
        r"\bla liga\b.*\b(spain|spanish)\b|\b(spain|spanish)\b.*\bla liga\b",
        re.IGNORECASE,
    ),
    "La Liga 2": re.compile(r"\bla liga\s*2\b", re.IGNORECASE),
    "Liga Portugal 2": re.compile(r"\bliga portugal\s*2\b", re.IGNORECASE),
    "Ligue 1 (France)": re.compile(r"\bligue\s*1\b", re.IGNORECASE),
    "Ligue 2 (France)": re.compile(r"\bligue\s*2\b", re.IGNORECASE),
    "MLS (USA)": re.compile(r"\bmls\b", re.IGNORECASE),
    "Premier League (England)": re.compile(r"\bpremier league\b", re.IGNORECASE),
    "Primeira Liga (Portugal)": re.compile(r"\bprimeira liga\b", re.IGNORECASE),
    "Pro League (Belgium)": re.compile(r"\bpro league\b", re.IGNORECASE),
    "SPL": re.compile(r"\bspl\b", re.IGNORECASE),
    "Serie A (Brazil)": re.compile(
        r"\bserie\s*a\b.*\b(brazil|brazilian)\b|\b(brazil|brazilian)\b.*\bserie\s*a\b",
        re.IGNORECASE,
    ),
    "Serie A (Italy)": re.compile(
        r"\bserie\s*a\b.*\b(italy|italian)\b|\b(italy|italian)\b.*\bserie\s*a\b",
        re.IGNORECASE,
    ),
    "Serie B": re.compile(r"\bserie\s*b\b", re.IGNORECASE),
    "Super Lig (Turkey)": re.compile(r"\bsuper lig\b", re.IGNORECASE),
    "Superliga (Denmark)": re.compile(r"\bsuperliga\b", re.IGNORECASE),
}


def _extract_position(query: str) -> str | None:
    best_code = None
    best_start = None
    for code, pattern in POSITION_PATTERNS.items():
        match = pattern.search(query)
        if match and (best_start is None or match.start() < best_start):
            best_start = match.start()
            best_code = code
    return best_code


def _extract_money(query: str) -> dict:
    match = _MONEY_RE.search(query)
    if not match:
        return {}

    amount = float(match.group(1))
    suffix = match.group(2).lower()
    if suffix in ("million", "m"):
        raw = int(amount * 1_000_000)
    else:
        raw = int(amount * 1_000)

    if _UNDER_RE.search(query):
        return {"market_value_max": raw}
    if _OVER_RE.search(query):
        return {"market_value_min": raw}
    # No direction word: a bare amount reads as a budget ceiling.
    return {"market_value_max": raw}


def _extract_league(query: str) -> str | None:
    matches = [name for name, pattern in LEAGUE_PATTERNS.items() if pattern.search(query)]
    if len(matches) == 1:
        return matches[0]
    return None  # zero matches, or ambiguous (multiple) -- never guess


def keyword_extract(query: str) -> dict:
    """Deterministic, no-LLM tier-2 extractor. Returns {} (never raises) when
    nothing usable can be extracted. Keys are exact PlayerFilter whitelist
    keys (position, market_value_min/max, league)."""
    if not query or not query.strip():
        return {}

    result: dict = {}

    position = _extract_position(query)
    if position:
        result["position"] = position

    result.update(_extract_money(query))

    league = _extract_league(query)
    if league:
        result["league"] = league

    return result
