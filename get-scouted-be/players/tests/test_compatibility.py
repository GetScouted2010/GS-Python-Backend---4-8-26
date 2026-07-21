"""Tests for the import_compatibility_scores management command.

Backs must_haves truths for Plan 01-07:
- The wide Compatibility Scores matrix (UniqueID, Position, N club columns)
  normalizes to one PlayerClubCompatibility row per player-club pair.
- Each club column header resolves to a Club FK via exact match then
  cs_field_mapping.json; unresolved headers keep club=null with
  club_name_raw preserved and are logged exactly once (not per row).
- Re-running the import produces zero net PlayerClubCompatibility change,
  including the null-club rows -- this is the specific reason the upsert key
  is (player, club_name_raw), not (player, club) (see 01-RESEARCH.md Open
  Question 2: Postgres treats multiple NULLs as non-conflicting).

`import_compatibility_scores` looks for the 9 REAL CS_*.csv filenames (e.g.
"CS_CB_25.csv") via FILE_TO_POSITION, not the fixture's own filename -- so
every test here copies `compatibility_CB_sample.csv` into a temp dir under
that exact real filename, alongside a small `cs_field_mapping_sample.json`
copied in as `cs_field_mapping.json`. The other 8 expected filenames are
absent from that temp dir, exercising the command's "tolerate missing files"
behavior for a partial fixture set.
"""

import json
import shutil

import pytest
from django.core.management import call_command

from players.models import Player, PlayerClubCompatibility

# compatibility_CB_sample.csv has UniqueID 1, 2, 5, 7, all CB -- all four
# exist as CB players in players_sample.csv.
CB_PLAYER_UIDS = (1, 2, 5, 7)

# The fixture's 6 club columns: 4 resolvable (all derived as real Clubs from
# players_sample.csv's Team_within_selected_timeframe column), 2 deliberately
# unresolvable (no matching Club row exists in the seeded test DB, even after
# the cs_field_mapping.json reverse-lookup for the sanitized "St_DOT_ Louis
# City" header resolves it to display name "St. Louis City").
RESOLVABLE_CLUBS = ("Manchester City", "Arsenal", "Real Madrid", "Bayern München")
UNRESOLVABLE_HEADERS = ("AGF", "St_DOT_ Louis City")


def _seed_clubs(fixture_dir, report_dir):
    call_command(
        "import_clubs_playstyles",
        players_csv=str(fixture_dir / "players_sample.csv"),
        playstyles_csv=str(fixture_dir / "playstyles_sample.csv"),
        report_dir=str(report_dir),
    )


def _seed_players(fixture_dir, report_dir):
    call_command(
        "import_players",
        players_csv=str(fixture_dir / "players_sample.csv"),
        report_dir=str(report_dir),
    )


def _cs_dir(fixture_dir, tmp_path):
    """Build a temp Compatability Scores dir with only the CB file present,
    under the real filename the command's FILE_TO_POSITION expects."""
    cs_dir = tmp_path / "cs"
    cs_dir.mkdir(exist_ok=True)
    shutil.copy(
        fixture_dir / "compatibility_CB_sample.csv", cs_dir / "CS_CB_25.csv"
    )
    shutil.copy(
        fixture_dir / "cs_field_mapping_sample.json", cs_dir / "cs_field_mapping.json"
    )
    return cs_dir


def _run_command(cs_dir, report_dir, **kwargs):
    call_command(
        "import_compatibility_scores",
        cs_dir=str(cs_dir),
        report_dir=str(report_dir),
        **kwargs,
    )


@pytest.mark.django_db
def test_compatibility_normalization(fixture_dir, tmp_path):
    _seed_clubs(fixture_dir, tmp_path / "clubs")
    _seed_players(fixture_dir, tmp_path / "players")

    cs_dir = _cs_dir(fixture_dir, tmp_path)
    _run_command(cs_dir, tmp_path / "compat")

    # 4 CB players x 6 club columns in the fixture.
    expected_count = len(CB_PLAYER_UIDS) * (len(RESOLVABLE_CLUBS) + len(UNRESOLVABLE_HEADERS))
    assert PlayerClubCompatibility.objects.count() == expected_count

    # A resolvable club column resolves to a real Club FK for every player.
    player_a = Player.objects.get(unique_id=1)
    mc_row = PlayerClubCompatibility.objects.get(
        player=player_a, club_name_raw="Manchester City"
    )
    assert mc_row.club is not None
    assert mc_row.club.name == "Manchester City"
    assert mc_row.position_group == "CB"

    # Score values round-trip verbatim from the source CSV.
    # UniqueID=1 (Player A), "Manchester City" column == 88.
    assert mc_row.score == 88.0

    arsenal_row = PlayerClubCompatibility.objects.get(
        player=player_a, club_name_raw="Arsenal"
    )
    assert arsenal_row.club is not None
    assert arsenal_row.club.name == "Arsenal"
    assert arsenal_row.score == 74.0

    # Every row for every CB player got a score, resolved or not.
    for uid in CB_PLAYER_UIDS:
        player = Player.objects.get(unique_id=uid)
        assert player.compatibilities.count() == len(RESOLVABLE_CLUBS) + len(
            UNRESOLVABLE_HEADERS
        )


@pytest.mark.django_db
def test_unresolved_club_header_kept(fixture_dir, tmp_path):
    _seed_clubs(fixture_dir, tmp_path / "clubs")
    _seed_players(fixture_dir, tmp_path / "players")

    cs_dir = _cs_dir(fixture_dir, tmp_path)
    report_dir = tmp_path / "compat"
    _run_command(cs_dir, report_dir)

    player_a = Player.objects.get(unique_id=1)

    # The deliberately-unresolvable sanitized header keeps club=null and
    # preserves the original header string in club_name_raw.
    row = PlayerClubCompatibility.objects.get(
        player=player_a, club_name_raw="St_DOT_ Louis City"
    )
    assert row.club is None
    assert row.club_name_raw == "St_DOT_ Louis City"

    # Every unresolvable header in the fixture ends up null-club, never
    # dropped, for every CB player.
    for uid in CB_PLAYER_UIDS:
        player = Player.objects.get(unique_id=uid)
        for header in UNRESOLVABLE_HEADERS:
            unresolved_row = PlayerClubCompatibility.objects.get(
                player=player, club_name_raw=header
            )
            assert unresolved_row.club is None

    # The report logs each distinct unresolved header exactly once (not once
    # per row -- there are 4 * 4 = 16 null-club rows here, but only 4
    # distinct header strings).
    json_files = list(report_dir.glob("*.json"))
    assert json_files, "expected an import report JSON file to be written"
    report_data = json.loads(json_files[0].read_text())
    unresolved_names = report_data["unresolved_club_names"]
    assert sorted(unresolved_names) == sorted(UNRESOLVABLE_HEADERS)
    assert unresolved_names.count("St_DOT_ Louis City") == 1


@pytest.mark.django_db
def test_compatibility_idempotent(fixture_dir, tmp_path):
    _seed_clubs(fixture_dir, tmp_path / "clubs")
    _seed_players(fixture_dir, tmp_path / "players")

    cs_dir = _cs_dir(fixture_dir, tmp_path)

    _run_command(cs_dir, tmp_path / "run1")
    count_after_first_run = PlayerClubCompatibility.objects.count()
    assert count_after_first_run > 0

    # Re-run: idempotent upsert on (player, club_name_raw) -> zero net
    # change, INCLUDING the null-club rows (the specific reason
    # club_name_raw is the upsert key, not club -- Postgres treats multiple
    # NULLs as non-conflicting, which would otherwise duplicate these rows
    # on every re-run).
    _run_command(cs_dir, tmp_path / "run2")
    count_after_second_run = PlayerClubCompatibility.objects.count()
    assert count_after_second_run == count_after_first_run

    null_club_count = PlayerClubCompatibility.objects.filter(club__isnull=True).count()
    assert null_club_count == len(CB_PLAYER_UIDS) * len(UNRESOLVABLE_HEADERS)
