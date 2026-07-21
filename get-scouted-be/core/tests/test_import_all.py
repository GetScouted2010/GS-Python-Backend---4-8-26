"""Integration test for the `import_all` whole-pipeline orchestrator.

Backs must_haves truths for Plan 01-09:
- `import_all` runs every import command in the correct dependency order
  (clubs -> players -> position roles -> compatibility -> transfers) in one
  invocation.
- Running `import_all` twice end-to-end produces zero net row change across
  all five tables (whole-pipeline idempotency).
- The run produces one combined import report with a `reconciliation`
  section.

Marked `integration` (not run on every quick `-k "not integration"` pass)
since it exercises all five sub-commands in sequence, same as the individual
per-command integration/idempotency tests in clubs/players/transfers do.
"""

from __future__ import annotations

import csv
import json
import shutil

import pytest
from django.core.management import call_command

from clubs.models import Club
from players.models import Player, PlayerClubCompatibility, PlayerRoleScore
from transfers.models import Transfer

ALL_TABLES = (
    (Club, "Club"),
    (Player, "Player"),
    (PlayerRoleScore, "PlayerRoleScore"),
    (PlayerClubCompatibility, "PlayerClubCompatibility"),
    (Transfer, "Transfer"),
)


def _table_counts() -> dict[str, int]:
    return {name: model.objects.count() for model, name in ALL_TABLES}


def _seed_transfer_clubs(fixture_dir) -> None:
    """Pre-seed Club rows for transferdata_sample.csv's Club values not
    already covered by players_sample.csv/playstyles_sample.csv.

    Mirrors `transfers/tests/test_transfer_import.py`'s `_seed_transfer_clubs`.
    Without this, `Transfer.club` is null for every fixture row (the small
    players fixture's 6 clubs don't overlap transferdata_sample.csv's clubs
    like Genk/Kortrijk), and Postgres treats multiple NULLs in the
    `uniq_transfer_event` constraint as non-conflicting -- which would break
    the SECOND `import_all` run's idempotency for the Transfer table
    specifically (duplicate inserts instead of a no-op upsert). In the real
    dataset, transferdata's clubs are a verified near-100% subset of the
    Players.csv-derived club universe, so this null-club case barely occurs
    there; this seeding step exists only so the small fixture set behaves
    the same realistic way for this whole-pipeline idempotency proof.

    `import_all`'s own `import_clubs_playstyles` step only inserts/updates
    the clubs it derives from players_csv/playstyles_csv -- it never deletes
    or otherwise touches unrelated pre-existing Club rows, so these seeded
    rows survive both `import_all` runs in this test.
    """
    with open(fixture_dir / "transferdata_sample.csv") as f:
        club_names = {row["Club"] for row in csv.DictReader(f)}
    existing = set(
        Club.objects.filter(name__in=club_names).values_list("name", flat=True)
    )
    Club.objects.bulk_create([Club(name=name) for name in club_names - existing])


def _build_positions_dir(fixture_dir, tmp_path):
    """`import_position_roles` looks for the 9 REAL Positions/*.csv filenames
    via FILE_TO_POSITION, not the fixture's own filename -- copy the CB
    sample fixture into a temp dir under the real expected filename."""
    positions_dir = tmp_path / "positions"
    positions_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(
        fixture_dir / "positions_CB_sample.csv",
        positions_dir / "CB with league.csv",
    )
    return positions_dir


def _build_cs_dir(fixture_dir, tmp_path):
    """Same real-filename requirement as positions, for CS_*.csv files."""
    cs_dir = tmp_path / "cs"
    cs_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(fixture_dir / "compatibility_CB_sample.csv", cs_dir / "CS_CB_25.csv")
    shutil.copy(
        fixture_dir / "cs_field_mapping_sample.json", cs_dir / "cs_field_mapping.json"
    )
    return cs_dir


def _run_import_all(fixture_dir, tmp_path, report_dir):
    positions_dir = _build_positions_dir(fixture_dir, tmp_path)
    cs_dir = _build_cs_dir(fixture_dir, tmp_path)
    call_command(
        "import_all",
        players_csv=str(fixture_dir / "players_sample.csv"),
        playstyles_csv=str(fixture_dir / "playstyles_sample.csv"),
        transfers_csv=str(fixture_dir / "transferdata_sample.csv"),
        positions_dir=str(positions_dir),
        cs_dir=str(cs_dir),
        report_dir=str(report_dir),
    )


@pytest.mark.django_db
@pytest.mark.integration
def test_import_all_idempotent(fixture_dir, tmp_path):
    _seed_transfer_clubs(fixture_dir)

    report_dir_1 = tmp_path / "reports_run1"
    _run_import_all(fixture_dir, tmp_path / "run1", report_dir_1)

    counts_after_first = _table_counts()
    assert all(count > 0 for count in counts_after_first.values()), counts_after_first

    report_dir_2 = tmp_path / "reports_run2"
    _run_import_all(fixture_dir, tmp_path / "run2", report_dir_2)

    counts_after_second = _table_counts()

    assert counts_after_second == counts_after_first

    combined_json_files = sorted(
        report_dir_2.glob("import_all_*.json"), key=lambda p: p.stat().st_mtime
    )
    assert combined_json_files, "expected a combined import_all report to be written"

    combined_data = json.loads(combined_json_files[-1].read_text())
    assert "reconciliation" in combined_data
    assert combined_data["reconciliation"], "reconciliation section must not be empty"
    for entry in combined_data["reconciliation"]:
        assert {"table", "source_rows", "db_rows", "delta"} <= entry.keys()

    reconciled_tables = {entry["table"] for entry in combined_data["reconciliation"]}
    assert reconciled_tables == {name for _, name in ALL_TABLES}
