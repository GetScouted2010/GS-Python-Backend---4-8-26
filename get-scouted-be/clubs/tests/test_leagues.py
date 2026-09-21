"""Tests for clubs/leagues.py's league-label aliases (2025-2026 Wyscout pull).

The 2025-2026 file names the same competitions differently from Players.csv
("Scottish Premiership (Scotland)" vs "SPL"). Left as-is, one league would
exist under two labels.
"""

from __future__ import annotations

from clubs.leagues import LEAGUE_ALIASES, REAL_LEAGUES, normalize_league_name

# The one alias whose target is a NEW league (a corrupt-accent fix), not an
# existing in-scope label.
_NEW_LEAGUE_ACCENT_FIX = "Primera Divisio´n (Uruguay)"


def test_every_alias_targets_an_existing_in_scope_league():
    # Guards against a typo'd target silently creating yet another label for
    # a league that already exists.
    for source, target in LEAGUE_ALIASES.items():
        if source == _NEW_LEAGUE_ACCENT_FIX:
            continue
        assert target in REAL_LEAGUES, f"{source!r} -> {target!r} is not an existing league"


def test_no_alias_maps_a_label_onto_itself():
    assert all(source != target for source, target in LEAGUE_ALIASES.items())


def test_canonical_labels_are_never_alias_sources():
    # Would make normalization non-idempotent / chain aliases.
    assert not (set(LEAGUE_ALIASES) & set(LEAGUE_ALIASES.values()))
    assert not (set(LEAGUE_ALIASES) & REAL_LEAGUES)


def test_confirmed_aliases():
    assert normalize_league_name("Scottish Premiership (Scotland)") == "SPL"
    assert normalize_league_name("2. Bundesliga (Germany)") == "Bundesliga 2"
    assert normalize_league_name("Belgian Pro League (Belgium)") == "Pro League (Belgium)"
    assert normalize_league_name("MLS (USA/Canada)") == "MLS (USA)"
    assert normalize_league_name("Segunda Divisio´n (Spain)") == "La Liga 2"


def test_corrupt_accent_in_a_new_league_is_repaired():
    assert normalize_league_name("Primera Divisio´n (Uruguay)") == "Primera Division (Uruguay)"


def test_strips_whitespace_and_leaves_other_labels_alone():
    assert normalize_league_name("  Ligue 1 (France) ") == "Ligue 1 (France)"
    assert normalize_league_name("Liga MX (Mexico)") == "Liga MX (Mexico)"


def test_distinct_leagues_that_look_alike_are_not_aliased():
    # A different country's league with a similar name must stay separate.
    assert normalize_league_name("Premier League (Russia)") == "Premier League (Russia)"
    assert normalize_league_name("Super Liga (Serbia)") == "Super Liga (Serbia)"
    assert normalize_league_name("Super Liga (Slovakia)") == "Super Liga (Slovakia)"
