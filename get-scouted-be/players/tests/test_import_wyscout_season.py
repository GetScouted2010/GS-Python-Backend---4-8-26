"""DB-backed tests for the `import_wyscout_season` management command.

Critical properties: the import is ADDITIVE (never touches an existing
season's rows or an existing Club), idempotent, and refuses to run if it
would overwrite another season's rows. See players/wyscout_season.py.
"""

from __future__ import annotations

import csv

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from clubs.models import Club
from players.models import Player
from players.wyscout_season import DEFAULT_ID_OFFSET

pytestmark = pytest.mark.django_db

OTHER_SEASON = "2024-2025"  # any season other than the one being imported

HEADER = [
    "UniqueID", "Season", "League", "Player", "Team within selected timeframe",
    "Main_Position", "Position", "Contract expires", "Age", "Market value",
    "Minutes played", "Foot",
]


def _row(uid, team, league="Premier League (England)", **kw):
    row = {
        "UniqueID": uid, "Season": "2025-2026", "League": league,
        "Player": f"Player {uid}", "Team within selected timeframe": team,
        "Main_Position": "CF", "Position": "CF", "Contract expires": "2028-06-30",
        "Age": 25, "Market value": 1_000_000, "Minutes played": 1800, "Foot": "right",
    }
    row.update(kw)
    return row


def _write_csv(path, rows):
    # cp1252, like the real file -- NOT utf-8.
    with open(path, "w", newline="", encoding="cp1252") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADER)
        writer.writeheader()
        writer.writerows(rows)
    return str(path)


def _run(tmp_path, rows, **opts):
    csv_path = _write_csv(tmp_path / "season.csv", rows)
    call_command(
        "import_wyscout_season", csv=csv_path, report_dir=str(tmp_path), **opts
    )


@pytest.fixture
def arsenal(db):
    return Club.objects.create(name="Arsenal", league="Premier League (England)")


def test_imports_rows_under_offset_ids(tmp_path, arsenal):
    _run(tmp_path, [_row(10, "Arsenal"), _row(11, "Arsenal")])

    players = Player.objects.filter(season="2025-2026").order_by("unique_id")
    assert [p.unique_id for p in players] == [DEFAULT_ID_OFFSET + 10, DEFAULT_ID_OFFSET + 11]
    assert all(p.club_id == arsenal.id for p in players)
    assert players[0].position == "FWD"  # derived from Main_Position CF
    assert players[0].market_value == 1_000_000
    assert players[0].contract_expires.isoformat() == "2028-06-30"


def test_scores_are_left_null(tmp_path, arsenal):
    _run(tmp_path, [_row(10, "Arsenal")])

    p = Player.objects.get(season="2025-2026")
    assert p.impact_score is None
    assert p.compatibility_score is None
    assert p.financial_fit_score is None
    assert p.transfer_probability_score is None


def test_creates_missing_clubs_with_league_from_the_season_rows(tmp_path, arsenal):
    _run(tmp_path, [_row(10, "Boca Juniors", league="Primera Division (Argentina)")])

    club = Club.objects.get(name="Boca Juniors")
    assert club.league == "Primera Division (Argentina)"
    assert Player.objects.get(season="2025-2026").club_id == club.id


def test_existing_clubs_are_never_modified(tmp_path, arsenal):
    # The season rows say Arsenal are in a different league -- the Club row
    # must not change (a reviewed correction is a separate, explicit step).
    _run(tmp_path, [_row(10, "Arsenal", league="EFL Championship")])

    arsenal.refresh_from_db()
    assert arsenal.league == "Premier League (England)"
    assert Club.objects.filter(name="Arsenal").count() == 1


def test_existing_seasons_are_untouched(tmp_path, arsenal):
    old = Player.objects.create(
        unique_id=10, player="Old Player", season=OTHER_SEASON, club=arsenal, age=30
    )

    # Source UniqueID 10 == the existing player's unique_id. Without the
    # offset this would overwrite `old`; with it, it cannot.
    _run(tmp_path, [_row(10, "Arsenal")])

    old.refresh_from_db()
    assert (old.player, old.season, old.age) == ("Old Player", OTHER_SEASON, 30)
    assert Player.objects.count() == 2


def test_accented_club_names_survive_the_cp1252_read(tmp_path, arsenal):
    _run(tmp_path, [_row(10, "Saint-Étienne", league="Ligue 2 (France)")])
    assert Club.objects.filter(name="Saint-Étienne").exists()


def test_is_idempotent(tmp_path, arsenal):
    rows = [_row(10, "Arsenal"), _row(11, "Nowhere FC")]
    _run(tmp_path, rows)
    clubs_after_first = Club.objects.count()
    _run(tmp_path, rows)

    assert Player.objects.filter(season="2025-2026").count() == 2
    assert Club.objects.count() == clubs_after_first


def test_same_name_clubs_in_two_countries_are_kept_apart(tmp_path):
    Club.objects.create(name="Liverpool", league="Premier League (England)")
    rows = [_row(i, "Liverpool", league="Premier League (England)") for i in range(20, 30)]
    rows += [_row(i, "Liverpool", league="Primera Division (Uruguay)") for i in range(30, 40)]

    _run(tmp_path, rows)

    english = Club.objects.get(name="Liverpool")
    uruguayan = Club.objects.get(name="Liverpool (Uruguay)")
    assert Player.objects.filter(club=english).count() == 10
    assert Player.objects.filter(club=uruguayan).count() == 10


def test_refuses_to_overwrite_another_seasons_rows(tmp_path, arsenal):
    # A mistyped --id-offset (here 0) would make the source IDs land on an
    # existing row of a different season. The command must refuse, not upsert.
    Player.objects.create(unique_id=10, player="Old Player", season=OTHER_SEASON, club=arsenal)

    with pytest.raises(CommandError, match="DIFFERENT season"):
        _run(tmp_path, [_row(10, "Arsenal")], id_offset=0)

    assert Player.objects.get(unique_id=10).player == "Old Player"


def test_dry_run_writes_nothing(tmp_path, arsenal):
    _run(tmp_path, [_row(10, "New Club FC")], dry_run=True)

    assert not Player.objects.filter(season="2025-2026").exists()
    assert not Club.objects.filter(name="New Club FC").exists()


def test_rejects_a_file_for_a_different_season(tmp_path, arsenal):
    with pytest.raises(CommandError, match="Wrong file"):
        _run(tmp_path, [_row(10, "Arsenal", Season="2024-2025")])


def test_rejects_an_unregistered_season(tmp_path, arsenal):
    with pytest.raises(CommandError, match="not a registered season"):
        _run(tmp_path, [_row(10, "Arsenal")], season="2031-2032")


def test_a_failure_part_way_leaves_nothing_behind(tmp_path, arsenal, monkeypatch):
    # Clubs + players are written in ONE transaction: if the player write
    # blows up, the clubs created just before it must roll back too.
    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure mid-import")

    monkeypatch.setattr(Player.objects, "bulk_create", boom)

    with pytest.raises(RuntimeError):
        _run(tmp_path, [_row(10, "Brand New Club")])

    assert not Club.objects.filter(name="Brand New Club").exists()
