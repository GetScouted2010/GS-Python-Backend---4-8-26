"""Tests for clubs/name_normalization.py (A3 fix)."""

import pytest

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


# --- 2025-2026 Wyscout pull: diacritic-stripped spellings of EXISTING clubs ---


def test_diacritic_stripped_spellings_map_to_the_existing_club_name():
    assert normalize_club_name("Besiktas") == "Beşiktaş"
    assert normalize_club_name("Lech Poznan") == "Lech Poznań"
    assert normalize_club_name("Istanbul Basaksehir") == "İstanbul Başakşehir"
    assert normalize_club_name("Sønderjyske") == "SønderjyskE"
    assert normalize_club_name("Kasimpasa") == "Kasımpaşa"


def test_athletic_club_is_deliberately_not_a_name_only_alias():
    # In the 2025-2026 file "Athletic Club" is BOTH Athletic Bilbao (La Liga)
    # AND an unrelated Brazilian Serie B club. A name-only alias would merge
    # them, so it must stay a (name, league) alias -- see the test below.
    assert normalize_club_name("Athletic Club") == "Athletic Club"


def test_athletic_club_alias_is_keyed_on_name_and_league():
    from clubs.name_normalization import CLUB_NAME_LEAGUE_ALIASES

    assert CLUB_NAME_LEAGUE_ALIASES == {("Athletic Club", "La Liga (Spain)"): "Athletic Bilbao"}


@pytest.mark.parametrize(
    "name",
    ["Gent II", "Real Sociedad B", "Boulogne", "Juventud", "Liverpool", "Nacional", "River Plate"],
)
def test_lookalike_but_different_clubs_are_never_aliased(name):
    # Traps found while scanning the 2025-2026 file: each of these looks like
    # another club but is a distinct one (reserve sides, other countries).
    assert normalize_club_name(name) == name
