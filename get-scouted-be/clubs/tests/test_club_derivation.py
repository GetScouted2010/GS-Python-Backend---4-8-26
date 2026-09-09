"""Tests for the import_clubs_playstyles management command.

Backs must_haves truths for Plan 01-04:
- Club.league = mode of League across a team's player rows, alphabetical tie-break.
- Club.playing_style_* populates only for clubs present in Playstyles.csv (~77%
  null is expected, not an error).
- Re-running the command produces zero net Club row change (idempotent upsert
  on Club.name).
"""

import pytest
from django.core.management import call_command

from clubs.models import Club


def _run_command(fixture_dir, report_dir):
    call_command(
        "import_clubs_playstyles",
        players_csv=str(fixture_dir / "players_sample.csv"),
        playstyles_csv=str(fixture_dir / "playstyles_sample.csv"),
        report_dir=str(report_dir),
    )


@pytest.mark.django_db
def test_league_mode(fixture_dir, tmp_path):
    _run_command(fixture_dir, tmp_path)

    # Manchester City: 4 rows Premier League (England), 1 row La Liga (Spain) --
    # a clear mode, not a tie.
    man_city = Club.objects.get(name="Manchester City")
    assert man_city.league == "Premier League (England)"

    # Sevilla: exactly 1 row Bundesliga (Germany), 1 row La Liga (Spain) -- a
    # genuine 1-1 tie. Alphabetically "Bundesliga (Germany)" sorts before
    # "La Liga (Spain)", so it wins the tie-break.
    sevilla = Club.objects.get(name="Sevilla")
    assert sevilla.league == "Bundesliga (Germany)"

    # The tie must be recorded in the written report.
    json_files = list(tmp_path.glob("*.json"))
    assert json_files, "expected an import report JSON file to be written"
    report_text = json_files[0].read_text()
    assert "Sevilla" in report_text
    assert "clubs_with_ambiguous_league" in report_text


@pytest.mark.django_db
def test_playing_style_coverage(fixture_dir, tmp_path):
    _run_command(fixture_dir, tmp_path)

    # playstyles_sample.csv covers Manchester City and Arsenal only.
    man_city = Club.objects.get(name="Manchester City")
    assert man_city.control_possession is not None

    arsenal = Club.objects.get(name="Arsenal")
    assert arsenal.control_possession is not None

    # Clubs absent from Playstyles.csv have ALL 8 style fields null.
    real_madrid = Club.objects.get(name="Real Madrid")
    style_fields = [
        "control_possession",
        "gegenpressing",
        "direct_play",
        "defensive_counter_attack",
        "tiki_taka",
        "counter_attack",
        "wing_play",
        "low_block",
    ]
    for field in style_fields:
        assert getattr(real_madrid, field) is None

    bayern = Club.objects.get(name="Bayern München")
    for field in style_fields:
        assert getattr(bayern, field) is None

    json_files = list(tmp_path.glob("*.json"))
    report_text = json_files[0].read_text()
    assert "playing_style_coverage_rate" in report_text

    total_clubs = Club.objects.count()
    covered_clubs = Club.objects.exclude(control_possession=None).count()
    expected_rate = round(covered_clubs / total_clubs, 4)
    assert f'"playing_style_coverage_rate": {expected_rate}' in report_text


@pytest.mark.django_db
def test_club_idempotent(fixture_dir, tmp_path):
    _run_command(fixture_dir, tmp_path / "run1")
    count_after_first_run = Club.objects.count()
    assert count_after_first_run > 0

    _run_command(fixture_dir, tmp_path / "run2")
    count_after_second_run = Club.objects.count()

    assert count_after_second_run == count_after_first_run


# --- A3 fix: whitespace-variant club names must not become two Club rows ---


def test_derive_club_league_strips_whitespace_variants():
    import pandas as pd

    from clubs.management.commands.import_clubs_playstyles import derive_club_league

    players_df = pd.DataFrame(
        {
            "Team_within_selected_timeframe": ["LASK", "LASK ", " LASK"],
            "League": ["Bundesliga (Austria)", "Bundesliga (Austria)", "Bundesliga (Austria)"],
        }
    )

    league_map, _, _ = derive_club_league(players_df)

    # All three whitespace variants must collapse to ONE key.
    assert league_map == {"LASK": "Bundesliga (Austria)"}


def test_load_playstyles_strips_whitespace_variants():
    import pandas as pd

    from clubs.management.commands.import_clubs_playstyles import load_playstyles

    playstyles_df = pd.DataFrame(
        {
            "Team": ["LASK "],
            "UniqueID": [1],
            "Control_Possession": [10.0],
            "Gegenpressing": [10.0],
            "Direct_Play": [10.0],
            "Defensive_Counter_Attack": [10.0],
            "Tiki_Taka": [10.0],
            "Counter_Attack": [10.0],
            "Wing_Play": [10.0],
            "Low_Block": [10.0],
        }
    )

    styles = load_playstyles(playstyles_df)

    assert "LASK" in styles
    assert "LASK " not in styles
