"""Pure-Python unit tests for players/ai/fallback.py::keyword_extract
(09-03-PLAN.md Task 1) -- the deterministic, no-LLM tier-2 fallback (AI-02).

No DB access, no network, no anthropic import at all -- these tests only
exercise stdlib `re` matching, so the autouse `_block_real_anthropic_calls`
safety net (players/tests/conftest.py) never fires here.

Naming: keyword/money/position/league behavior tests include "keyword" in
their function name so `pytest -k keyword` selects them (09-VALIDATION.md).
"""

from players.ai.fallback import keyword_extract


# ---------------------------------------------------------------------------
# Test 1: money parsing
# ---------------------------------------------------------------------------
def test_keyword_extract_money_under_scales_to_raw_euros():
    result = keyword_extract("strikers under €5M")

    assert result["market_value_max"] == 5_000_000


def test_keyword_extract_money_over_scales_to_raw_euros():
    result = keyword_extract("defenders over 10m")

    assert result["market_value_min"] == 10_000_000


# ---------------------------------------------------------------------------
# Test 2: position synonyms
# ---------------------------------------------------------------------------
def test_keyword_extract_position_centre_back_synonyms():
    for phrase in ("centre back", "center back", "CB", "defender(centre)"):
        assert keyword_extract(phrase)["position"] == "CB", phrase


def test_keyword_extract_position_left_back_synonyms():
    for phrase in ("left-back", "left back", "LB"):
        assert keyword_extract(phrase)["position"] == "LB", phrase


def test_keyword_extract_position_striker_synonyms():
    for phrase in ("striker", "forward", "FWD"):
        assert keyword_extract(phrase)["position"] == "FWD", phrase


def test_keyword_extract_position_goalkeeper_synonyms():
    for phrase in ("keeper", "goalkeeper", "GK"):
        assert keyword_extract(phrase)["position"] == "GK", phrase


# ---------------------------------------------------------------------------
# Test 3: league substring matching (unambiguous)
# ---------------------------------------------------------------------------
def test_keyword_extract_league_unambiguous_full_name_match():
    result = keyword_extract("plays in the Premier League")

    assert result["league"] == "Premier League (England)"


# ---------------------------------------------------------------------------
# Test 4: ambiguous league base terms are never guessed
# ---------------------------------------------------------------------------
def test_league_ambiguous_bare_bundesliga_not_guessed():
    result = keyword_extract("bundesliga")

    assert "league" not in result


def test_league_ambiguous_bare_serie_not_guessed():
    result = keyword_extract("serie")

    assert "league" not in result


def test_league_qualified_german_bundesliga_disambiguates():
    result = keyword_extract("german bundesliga")

    assert result["league"] == "Bundesliga (Germany)"


# ---------------------------------------------------------------------------
# Test 5: nothing usable -> {} (never an exception)
# ---------------------------------------------------------------------------
def test_keyword_extract_nothing_usable_returns_empty_dict():
    assert keyword_extract("asdfghjkl nonsense") == {}


def test_keyword_extract_empty_string_returns_empty_dict():
    assert keyword_extract("") == {}


# ---------------------------------------------------------------------------
# Test 6: combined query
# ---------------------------------------------------------------------------
def test_keyword_extract_combined_query():
    result = keyword_extract("young left backs under 5m in ligue 1")

    assert result["position"] == "LB"
    assert result["market_value_max"] == 5_000_000
    assert result["league"] == "Ligue 1 (France)"
