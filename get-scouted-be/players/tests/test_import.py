"""Tests for the import_players management command.

Backs must_haves truths for Plan 01-05:
- Importing Players.csv creates one Player row per source row, resolving the
  club FK from Team_within_selected_timeframe.
- Missing/dirty values (blank Market_value, Foot='0'/'unknown', blank
  Contract_expires) import as null/flagged and are logged in the report --
  the row is never skipped.
- The 14 movement columns land in extended_stats keyed by original CSV name;
  Total_Score lands in legacy_total_score.
- Re-running the import produces zero net Player row change (idempotent
  upsert on unique_id).

(test_role_score_coverage and related tests are added by Plan 06 to THIS SAME
file -- keep it importable and additive.)
"""

import datetime

import pytest
from django.core.management import call_command

from players.models import Player


def _seed_clubs(fixture_dir, report_dir):
    call_command(
        "import_clubs_playstyles",
        players_csv=str(fixture_dir / "players_sample.csv"),
        playstyles_csv=str(fixture_dir / "playstyles_sample.csv"),
        report_dir=str(report_dir),
    )


def _run_command(fixture_dir, report_dir):
    call_command(
        "import_players",
        players_csv=str(fixture_dir / "players_sample.csv"),
        report_dir=str(report_dir),
    )


def _source_row_count(fixture_dir):
    with open(fixture_dir / "players_sample.csv") as f:
        # subtract 1 for the header row
        return sum(1 for _ in f) - 1


@pytest.mark.django_db
def test_player_row_count(fixture_dir, tmp_path):
    _seed_clubs(fixture_dir, tmp_path / "clubs")
    _run_command(fixture_dir, tmp_path / "players")

    expected = _source_row_count(fixture_dir)
    assert Player.objects.count() == expected

    # No crash resolving club FKs -- every player's club is either resolved
    # or null, and at least one player resolves to a real Club.
    assert Player.objects.filter(club__isnull=False).exists()
    for player in Player.objects.all():
        # Accessing club_id never raises regardless of resolved/null state.
        assert player.club_id is None or isinstance(player.club_id, int)


@pytest.mark.django_db
def test_player_missing_field_handling(fixture_dir, tmp_path):
    _seed_clubs(fixture_dir, tmp_path / "clubs")
    _run_command(fixture_dir, tmp_path / "players")

    # UniqueID=2 (Player B): blank Market_value -> null, never skipped.
    player_b = Player.objects.get(unique_id=2)
    assert player_b.market_value is None

    # UniqueID=1 (Player A): Contract_expires "30/06/2027" parses explicitly.
    player_a = Player.objects.get(unique_id=1)
    assert player_a.contract_expires == datetime.date(2027, 6, 30)

    # UniqueID=3 (Player C): blank Contract_expires -> null, never skipped.
    player_c = Player.objects.get(unique_id=3)
    assert player_c.contract_expires is None

    # UniqueID=5 (Player E): Foot='unknown' -- imported, not skipped.
    player_e = Player.objects.get(unique_id=5)
    assert player_e.foot == "unknown"

    # UniqueID=7 (Player G): Foot='0' -- imported, not skipped.
    player_g = Player.objects.get(unique_id=7)
    assert player_g.foot == "0"

    json_files = list((tmp_path / "players").glob("*.json"))
    assert json_files, "expected an import report JSON file to be written"
    report_text = json_files[0].read_text()
    assert "invalid_value:'unknown'" in report_text
    assert "invalid_value:'0'" in report_text

    # No fixture row is missing from the DB -- every row was imported despite
    # the flagged issues above.
    assert Player.objects.count() == _source_row_count(fixture_dir)

    # Runtime check of must_haves truth #3: extended_stats + legacy_total_score.
    # UniqueID=1 (Player A) has Total_Score=75.5, Total_Distance_per_90=10500.5,
    # and Max_Speed_(km/h)=33.2 seeded in players_sample.csv specifically for
    # this assertion.
    assert player_a.legacy_total_score == 75.5
    assert player_a.extended_stats
    assert player_a.extended_stats["Max_Speed_(km/h)"] == 33.2
    assert player_a.extended_stats["Total_Distance_per_90"] == 10500.5


@pytest.mark.django_db
def test_reimport_idempotent(fixture_dir, tmp_path):
    _seed_clubs(fixture_dir, tmp_path / "clubs")

    _run_command(fixture_dir, tmp_path / "run1")
    count_after_first_run = Player.objects.count()
    assert count_after_first_run > 0

    _run_command(fixture_dir, tmp_path / "run2")
    count_after_second_run = Player.objects.count()

    assert count_after_second_run == count_after_first_run
