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
import shutil

import pytest
from django.core.management import call_command

from players.models import Player, PlayerRoleScore


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


def _run_position_roles(positions_dir, report_dir):
    call_command(
        "import_position_roles",
        positions_dir=str(positions_dir),
        report_dir=str(report_dir),
    )


@pytest.mark.django_db
def test_role_score_coverage(fixture_dir, tmp_path):
    """Backs must_haves truths for Plan 01-06:

    - Non-GK players with a Positions row get one PlayerRoleScore row per role
      column; GK players get exactly zero rows (no GK Positions file exists).
    - Role headers are sanitized into role_name while role_name_raw preserves
      the original CSV header string.
    - Re-running the import is idempotent (zero net PlayerRoleScore change).

    `import_position_roles` looks for the 9 REAL Positions/*.csv filenames
    (e.g. "CB with league.csv") via FILE_TO_POSITION, not the fixture's own
    filename -- so this test copies `positions_CB_sample.csv` into a temp dir
    under the exact real filename the command expects. The other 8 expected
    filenames are absent from that temp dir, exercising the command's
    "tolerate missing files" behavior for a partial fixture set.
    """
    _seed_clubs(fixture_dir, tmp_path / "clubs")
    _run_command(fixture_dir, tmp_path / "players")

    positions_dir = tmp_path / "positions"
    positions_dir.mkdir()
    shutil.copy(
        fixture_dir / "positions_CB_sample.csv",
        positions_dir / "CB with league.csv",
    )

    _run_position_roles(positions_dir, tmp_path / "roles")

    # CB players from the fixture (UniqueID 1, 2, 5, 7) each get >=1 role row.
    for uid in (1, 2, 5, 7):
        player = Player.objects.get(unique_id=uid)
        assert player.role_scores.count() >= 1

    # GK players (UniqueID 6, 14) get exactly zero role rows -- by design,
    # since there is no GK Positions/*.csv file in the source dataset.
    for uid in (6, 14):
        gk_player = Player.objects.get(unique_id=uid)
        assert gk_player.role_scores.count() == 0

    # Sanitized role_name + preserved raw header for the LCB role column
    # ("Wide_Centre-Back_(LCB)" -> "wide_centre_back_lcb").
    lcb_row = PlayerRoleScore.objects.get(
        player=Player.objects.get(unique_id=1), role_name="wide_centre_back_lcb"
    )
    assert lcb_row.role_name_raw == "Wide_Centre-Back_(LCB)"
    assert lcb_row.position_group == "CB"

    count_after_first_run = PlayerRoleScore.objects.count()
    assert count_after_first_run > 0

    # Re-run: idempotent upsert on (player, role_name) -> zero net change.
    _run_position_roles(positions_dir, tmp_path / "roles_run2")
    assert PlayerRoleScore.objects.count() == count_after_first_run
