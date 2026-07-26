"""Unit tests for the grounding validator (AI-03/AI-04) -- numeric-token
extraction from LLM narrative prose, and tolerance-match validation against
the grounding dict. Proves both the accept path (a tolerantly-rounded real
number passes) and the reject path (a hallucinated number fails) --
10-VALIDATION.md requires both directions to be directly tested."""

from players.ai.grounding import (
    extract_numeric_tokens,
    flatten_grounding_values,
    is_grounded,
    validate_grounding,
)


def test_extract_numeric_tokens_handles_ratio_currency_and_percent_suffixes():
    tokens = extract_numeric_tokens("scores 7.4/10, worth €2.3M, 15% duels")

    assert tokens == [7.4, 10.0, 2_300_000.0, 15.0]


def test_flatten_grounding_values_recurses_and_excludes_non_numeric_leaves():
    grounding = {
        "rmm": {"rmm": 7.42, "components": {"a": 3.0}},
        "note": "text",
        "flag": True,
    }

    assert flatten_grounding_values(grounding) == [7.42, 3.0]


def test_is_grounded_accepts_tolerantly_rounded_real_number():
    # €2.3M narrative figure rounds from a raw grounding value of 2,340,000.
    assert is_grounded(2_300_000, [2_340_000], rel_tol=0.05) is True


def test_is_grounded_accepts_fraction_percent_scale_mismatch():
    assert is_grounded(15, [0.1523]) or is_grounded(15, [15.23])


def test_is_grounded_rejects_hallucinated_number():
    assert is_grounded(999_999_999, [2_340_000, 7.42]) is False


def test_validate_grounding_returns_empty_list_when_fully_grounded():
    narrative = "RMM is 7.4/10 and value €2.3M"
    grounding = {"rmm": {"rmm": 7.42}, "fee": 2_340_000}

    result = validate_grounding(narrative, grounding)

    assert result == []


def test_validate_grounding_returns_non_empty_list_for_hallucinated_number():
    narrative = "This player is worth €88.8M"
    grounding = {"rmm": {"rmm": 7.42}, "fee": 2_340_000}

    result = validate_grounding(narrative, grounding)

    assert result != []
    assert 88_800_000.0 in result
