"""Tests for the correct_club_leagues management command.

Each test pins one rule from the command's docstring. The evidence file is
written in cp1252, like the real Wyscout export.
"""

from __future__ import annotations

import csv
import itertools

import pytest
from django.core.management import call_command

from clubs.models import Club
from players.models import Player
from players.season import DEFAULT_SEASON

pytestmark = pytest.mark.django_db

HEADER = [
    "UniqueID", "Season", "League", "Player", "Team within selected timeframe",
    "Main_Position", "Position", "Contract expires",
]
_uid = itertools.count(1)
_old_uid = itertools.count(1_700_000_001)


def _row(team, league, player):
    return {
        "UniqueID": next(_uid), "Season": "2025-2026", "League": league, "Player": player,
        "Team within selected timeframe": team, "Main_Position": "CF", "Position": "CF",
        "Contract expires": "2028-06-30",
    }


def _run(tmp_path, rows, **opts):
    path = tmp_path / "season.csv"
    with open(path, "w", newline="", encoding="cp1252") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    call_command("correct_club_leagues", csv=str(path), report_dir=str(tmp_path), **opts)


def _league(name):
    return Club.objects.get(name=name).league


def _squad(club, names):
    for n in names:
        Player.objects.create(unique_id=next(_old_uid), player=n, club=club, season=DEFAULT_SEASON)


def test_wrong_country_league_is_corrected(tmp_path):
    Club.objects.create(name="Panathinaikos", league="La Liga (Spain)")

    _run(tmp_path, [_row("Panathinaikos", "Super League (Greece)", "P1")])

    assert _league("Panathinaikos") == "Super League (Greece)"


def test_promotion_or_relegation_within_a_country_is_left_alone(tmp_path):
    # Metz: Ligue 2 in the older seasons, Ligue 1 in 2025-2026. Club.league is
    # one value and older seasons still resolve through it -- overwriting it
    # would make last season's league wrong.
    Club.objects.create(name="Metz", league="Ligue 2 (France)")

    _run(tmp_path, [_row("Metz", "Ligue 1 (France)", "P1")])

    assert _league("Metz") == "Ligue 2 (France)"


def test_same_country_holds_for_labels_without_a_country_in_them(tmp_path):
    Club.objects.create(name="Pisa", league="Serie B")  # Italy, no "(Italy)" in the label

    _run(tmp_path, [_row("Pisa", "Serie A (Italy)", "P1")])

    assert _league("Pisa") == "Serie B"


def test_club_agreeing_with_the_file_is_unchanged(tmp_path):
    Club.objects.create(name="Arsenal", league="Premier League (England)")

    _run(tmp_path, [_row("Arsenal", "Premier League (England)", "P1")])

    assert _league("Arsenal") == "Premier League (England)"


def test_alias_spelling_is_normalized_even_for_a_club_not_in_the_file(tmp_path):
    Club.objects.create(name="Grimsby Town", league="EFL League Two (England)")
    Club.objects.create(name="Other FC", league="Premier League (England)")

    _run(tmp_path, [_row("Other FC", "Premier League (England)", "P1")])

    assert _league("Grimsby Town") == "EFL League Two"


def test_empty_league_is_filled_from_the_file(tmp_path):
    Club.objects.create(name="No League FC", league=None)

    _run(tmp_path, [_row("No League FC", "Liga MX (Mexico)", "P1")])

    assert _league("No League FC") == "Liga MX (Mexico)"


def test_possible_name_collision_is_not_applied(tmp_path):
    # Stored as a Spanish club with a real 6-player squad; the file's club of
    # the same name is Uruguayan and shares NONE of those players -- probably
    # two different clubs, so a human decides.
    club = Club.objects.create(name="Nacional", league="La Liga (Spain)")
    _squad(club, ["a1", "a2", "a3", "a4", "a5", "a6"])

    _run(tmp_path, [_row("Nacional", "Primera Division (Uruguay)", "u1")])

    assert _league("Nacional") == "La Liga (Spain)"


def test_wrong_country_is_corrected_when_the_squads_overlap(tmp_path):
    club = Club.objects.create(name="Olympiacos Piraeus", league="Bundesliga 2")
    _squad(club, ["Shared One", "b2", "b3", "b4", "b5", "b6"])

    _run(tmp_path, [_row("Olympiacos Piraeus", "Super League (Greece)", "shared one")])

    assert _league("Olympiacos Piraeus") == "Super League (Greece)"


def test_wrong_country_is_corrected_when_the_older_squad_is_tiny(tmp_path):
    # A club known only through a couple of stray rows has too little history
    # to call a collision -- the case that makes up most real corrections.
    club = Club.objects.create(name="Legia Warszawa", league="La Liga 2")
    _squad(club, ["only1", "only2"])

    _run(tmp_path, [_row("Legia Warszawa", "Ekstraklasa (Poland)", "x")])

    assert _league("Legia Warszawa") == "Ekstraklasa (Poland)"


def test_a_club_absent_from_the_file_is_untouched(tmp_path):
    Club.objects.create(name="Not In File", league="La Liga (Spain)")
    Club.objects.create(name="In File", league="Premier League (England)")

    _run(tmp_path, [_row("In File", "Premier League (England)", "P1")])

    assert _league("Not In File") == "La Liga (Spain)"


def test_a_same_name_club_the_import_split_off_is_never_matched_to_the_original(tmp_path):
    # The season import stores Uruguayan River Plate as "River Plate (Uruguay)".
    # The original "River Plate" must not be touched on its account.
    Club.objects.create(name="River Plate", league="La Liga (Spain)")
    Club.objects.create(name="River Plate (Uruguay)", league="Primera Division (Uruguay)")

    _run(tmp_path, [_row("River Plate (Uruguay)", "Primera Division (Uruguay)", "P1")])

    assert _league("River Plate") == "La Liga (Spain)"
    assert _league("River Plate (Uruguay)") == "Primera Division (Uruguay)"


def test_unknown_country_is_never_applied(tmp_path):
    Club.objects.create(name="Mystery FC", league="Some Unknown League")

    _run(tmp_path, [_row("Mystery FC", "Liga MX (Mexico)", "P1")])

    assert _league("Mystery FC") == "Some Unknown League"


def test_dry_run_changes_nothing(tmp_path):
    Club.objects.create(name="Panathinaikos", league="La Liga (Spain)")
    Club.objects.create(name="Grimsby Town", league="EFL League Two (England)")

    _run(tmp_path, [_row("Panathinaikos", "Super League (Greece)", "P1")], dry_run=True)

    assert _league("Panathinaikos") == "La Liga (Spain)"
    assert _league("Grimsby Town") == "EFL League Two (England)"


def test_second_run_proposes_nothing(tmp_path, capsys):
    Club.objects.create(name="Panathinaikos", league="La Liga (Spain)")
    rows = [_row("Panathinaikos", "Super League (Greece)", "P1")]
    _run(tmp_path, rows)
    capsys.readouterr()

    _run(tmp_path, rows, dry_run=True)

    assert "0 proposed change(s)" in capsys.readouterr().out
    assert _league("Panathinaikos") == "Super League (Greece)"


def test_changes_are_recorded_old_to_new_in_the_report(tmp_path):
    import json

    Club.objects.create(name="Panathinaikos", league="La Liga (Spain)")
    _run(tmp_path, [_row("Panathinaikos", "Super League (Greece)", "P1")])

    report = json.loads(sorted(tmp_path.glob("season_*.json"))[-1].read_text())
    change = report["club_league_correction"]["changes"][0]
    assert (change["club"], change["stored_league"], change["new_league"]) == (
        "Panathinaikos", "La Liga (Spain)", "Super League (Greece)",
    )


def test_a_club_with_a_large_older_squad_is_reviewed_even_if_players_overlap(tmp_path):
    # 12 older players = real history in the stored league, not a stray-row
    # mislabel; one shared name (very possible with abbreviated names like
    # "A. Silva") is not enough to conclude it is the same club.
    club = Club.objects.create(name="Nacional", league="Liga Portugal 2")
    _squad(club, ["A. Silva"] + [f"p{i}" for i in range(11)])

    _run(tmp_path, [_row("Nacional", "Primera Division (Uruguay)", "a. silva")])

    assert _league("Nacional") == "Liga Portugal 2"
