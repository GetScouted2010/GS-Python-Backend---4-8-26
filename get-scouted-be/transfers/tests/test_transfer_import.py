"""Tests for the import_transfers management command.

Backs must_haves truths for Plan 01-08 -- the single highest-risk trap in
Phase 1: transferdata's `UniqueID` column is a CLUB id (207 distinct values,
1:1 with `Club`), NOT a player id, despite sharing an identical column name
with Players.csv's player-level `UniqueID`. A naive import that joins
`transferdata.UniqueID` to `Player.unique_id` "succeeds" (every UniqueID does
exist as *some* player's UniqueID) but silently attaches transfers to the
wrong players entirely.

- test_uniqueid_is_club_not_player: proves the importer never makes that
  join -- Genk's UniqueID=81 transfers must not link to the unrelated
  player who happens to share that numeric id (D. Solanke, Tottenham
  Hotspur).
- test_every_row_imports_unmatched_kept: every fixture row imports (none
  dropped); a transfer whose Player name has no match in Players.csv is
  still inserted with player=None, not skipped.
- test_idempotent_rerun: re-running the import produces zero net Transfer
  change (upsert on the 6-column composite event key).
- test_dealing_club_is_string: dealing_club stays a plain string even for a
  counterparty absent from the Club table -- no stub Club row is created.
"""

import pytest
from django.core.management import call_command

from clubs.models import Club
from players.models import Player
from transfers.models import Transfer


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


def _seed_transfer_clubs(fixture_dir):
    """Create Club rows for every distinct transferdata_sample.csv `Club`
    value not already covered by players_sample.csv/playstyles_sample.csv.

    In production, `transferdata.Club`'s 207 distinct values are a verified
    strict subset of the ~1,059-club universe derived from the full
    Players.csv (01-RESEARCH.md) -- i.e. transfer clubs virtually always
    resolve. The small, deliberately-minimal players_sample.csv fixture (6
    clubs) doesn't happen to overlap transferdata_sample.csv's clubs (Genk,
    Kortrijk, etc.), which is fine for the UniqueID-trap purpose those
    fixtures were built for, but would leave `Transfer.club` null for every
    fixture row here -- and Postgres unique constraints treat multiple NULLs
    as non-conflicting, which breaks the composite-key idempotent upsert this
    plan must verify. Seeding these clubs (matching the real dataset's
    verified near-100% coverage) exercises the realistic, intended path.
    """
    import csv

    with open(fixture_dir / "transferdata_sample.csv") as f:
        club_names = {row["Club"] for row in csv.DictReader(f)}
    existing = set(Club.objects.filter(name__in=club_names).values_list("name", flat=True))
    Club.objects.bulk_create([Club(name=name) for name in club_names - existing])


def _run_transfers(fixture_dir, report_dir):
    call_command(
        "import_transfers",
        transfers_csv=str(fixture_dir / "transferdata_sample.csv"),
        report_dir=str(report_dir),
    )


def _source_row_count(fixture_dir):
    with open(fixture_dir / "transferdata_sample.csv") as f:
        # subtract 1 for the header row
        return sum(1 for _ in f) - 1


def _seed_all(fixture_dir, tmp_path):
    _seed_clubs(fixture_dir, tmp_path / "clubs")
    _seed_players(fixture_dir, tmp_path / "players")
    _seed_transfer_clubs(fixture_dir)


@pytest.mark.django_db
def test_uniqueid_is_club_not_player(fixture_dir, tmp_path):
    _seed_all(fixture_dir, tmp_path)
    _run_transfers(fixture_dir, tmp_path / "transfers")

    # UniqueID=81 is genuinely club-scoped in the fixture (Genk, 4 rows,
    # 3 different players) AND also happens to collide with a real player's
    # UniqueID (D. Solanke, Tottenham Hotspur) in players_sample.csv.
    trap_player = Player.objects.get(unique_id=81)

    genk_transfers = Transfer.objects.filter(source_unique_id=81)
    assert genk_transfers.count() == 4

    genk_club = Club.objects.filter(name="Genk").first()

    for t in genk_transfers:
        # The importer must never have joined transferdata.UniqueID to
        # Player.unique_id -- none of these Genk transfers may be linked to
        # the unrelated player who happens to share the numeric id 81.
        assert t.player_id != trap_player.id
        # A buggy UniqueID->Player->Player.club join would incorrectly set
        # club to Tottenham Hotspur (trap_player's club); prove it doesn't --
        # club must be resolved from the Club NAME column ("Genk") only.
        assert t.club != trap_player.club
        assert t.club == genk_club
        assert t.source_unique_id == 81


@pytest.mark.django_db
def test_every_row_imports_unmatched_kept(fixture_dir, tmp_path):
    _seed_all(fixture_dir, tmp_path)
    report_dir = tmp_path / "transfers"
    _run_transfers(fixture_dir, report_dir)

    expected = _source_row_count(fixture_dir)
    assert Transfer.objects.count() == expected

    # "Random Player C" (Standard Liège, transferdata UniqueID=400) does not
    # appear anywhere in players_sample.csv -- must still be imported with
    # player=None rather than dropped.
    unmatched = Transfer.objects.get(player_name_raw="Random Player C")
    assert unmatched.player is None

    # The report's (field, issue) sample list is capped at 10 ids (see
    # ImportReport.add_field_issue) -- with 12/12 fixture rows unmatched here,
    # not every name is guaranteed a slot in the sample, so only assert the
    # issue category itself is present, not this specific name.
    json_files = list(report_dir.glob("*.json"))
    assert json_files, "expected an import report JSON file to be written"
    report_text = json_files[0].read_text()
    assert "unmatched_name" in report_text


@pytest.mark.django_db
def test_idempotent_rerun(fixture_dir, tmp_path):
    _seed_all(fixture_dir, tmp_path)

    _run_transfers(fixture_dir, tmp_path / "run1")
    count_after_first_run = Transfer.objects.count()
    assert count_after_first_run > 0

    _run_transfers(fixture_dir, tmp_path / "run2")
    count_after_second_run = Transfer.objects.count()

    assert count_after_second_run == count_after_first_run


@pytest.mark.django_db
def test_dealing_club_is_string(fixture_dir, tmp_path):
    _seed_all(fixture_dir, tmp_path)
    _run_transfers(fixture_dir, tmp_path / "transfers")

    # "Independent FC" is a Dealing_Club counterparty that never appears as a
    # Club value anywhere in the fixture -- must still import as a plain
    # string with no stub Club row ever created for it.
    transfer = Transfer.objects.filter(dealing_club="Independent FC").first()
    assert transfer is not None
    assert transfer.dealing_club == "Independent FC"
    assert not Club.objects.filter(name="Independent FC").exists()
