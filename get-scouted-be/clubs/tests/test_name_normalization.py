"""Tests for clubs/name_normalization.py (A3 fix)."""

from clubs.name_normalization import normalize_club_name


def test_strips_whitespace():
    assert normalize_club_name("LASK ") == "LASK"
    assert normalize_club_name(" Esenler Erokspor") == "Esenler Erokspor"


def test_applies_confirmed_alias():
    assert normalize_club_name("Borussia M_gladbach") == "Borussia M'gladbach"


def test_alias_applies_after_stripping():
    assert normalize_club_name(" Borussia M_gladbach ") == "Borussia M'gladbach"


def test_unrelated_name_passes_through_unchanged():
    assert normalize_club_name("Brentford") == "Brentford"
