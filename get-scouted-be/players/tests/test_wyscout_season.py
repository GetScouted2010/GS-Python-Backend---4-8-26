"""Tests for players/wyscout_season.py -- the 2025-2026 Wyscout adapter.

Every expectation below was taken from the REAL files (Players.csv header,
`dataset/missing_data/wyscout_with_TM_data.csv`), not invented -- see the
module docstring in players/wyscout_season.py for what each rule protects
against.
"""

from __future__ import annotations

import pandas as pd
import pytest

from players.wyscout_season import (
    DEFAULT_ID_OFFSET,
    MAIN_POSITION_TO_GROUP,
    adapt_wyscout_frame,
    resolve_club_identities,
    to_players_csv_name,
)

# ---------------------------------------------------------------------------
# Column-name translation: raw Wyscout name -> Players.csv name.
# Pairs verified against the real Players.csv header (134/135 of its columns
# are reproduced by this rule on the real file).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("Minutes played", "Minutes_played"),
        ("Team within selected timeframe", "Team_within_selected_timeframe"),
        ("Duels won, %", "Duels_won_percentage"),
        ("Accurate back passes, %", "Accurate_back_passes_percentage"),
        ("Average pass length, m", "Average_pass_length_m"),
        ("Average long pass length, m", "Average_long_pass_length_m"),
        ("Accurate short / medium passes, %", "Accurate_short_medium_passes_percentage"),
        ("Short / medium passes per 90", "Short_medium_passes_per_90"),
        ("Non-penalty goals", "Non_penalty_goals"),
        ("Non-penalty goals per 90", "Non_penalty_goals_per_90"),
        ("xG per 90", "xG_per_90"),
        ("Aerial duels per 90.1", "Aerial_duels_per_90.1"),
        # km/h and m/s must NOT have their slash/sign rewritten
        ("Max Speed (km/h)", "Max_Speed_(km/h)"),
        ("Count HI per 90 (+20 km/h)", "Count_HI_per_90_(+20_km/h)"),
        ("Meter/Min", "Meter/Min"),
        (
            "Count High Deceleration per 90 (-3 m/s²)",
            "Count_High_Deceleration_per_90_(-3_m/s²)",
        ),
        (
            "Count Medium Acceleration per 90 (1.5 m/s² to 3 m/s²)",
            "Count_Medium_Acceleration_per_90_(1_DOT_5_m/s²_to_3_m/s²)",
        ),
        (
            "Count Medium Deceleration per 90 (-1.5 m/s² to -3 m/s²)",
            "Count_Medium_Deceleration_per_90_(-1_DOT_5_m/s²_to_-3_m/s²)",
        ),
        # Not derivable by rule -- explicit override.
        ("WYS Position", "Positions"),
        # Already-correct names pass through.
        ("UniqueID", "UniqueID"),
        ("Main_Position", "Main_Position"),
    ],
)
def test_to_players_csv_name(raw, expected):
    assert to_players_csv_name(raw) == expected


# ---------------------------------------------------------------------------
# adapt_wyscout_frame
# ---------------------------------------------------------------------------


def _raw(**overrides) -> pd.DataFrame:
    """A minimal raw frame shaped like the real file (all strings)."""
    row = {
        "UniqueID": "35583",
        "Season": "2025-2026",
        "League": "Scottish Premiership (Scotland)",
        "Player": "Test Player",
        "Team within selected timeframe": "Besiktas",
        "Main_Position": "LCB",
        "Position": "CF",  # the source column disagrees with Main_Position
        "Contract expires": "2029-06-30",
        "Age": "24",
        "Market value": "700000.0",
        "Minutes played": "1500",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_unique_ids_are_offset_so_they_cannot_collide_with_players_csv():
    frame, stats = adapt_wyscout_frame(_raw(), season="2025-2026")

    assert frame["UniqueID"].iloc[0] == 35583 + DEFAULT_ID_OFFSET
    assert stats["id_offset"] == DEFAULT_ID_OFFSET
    # The real Players.csv tops out at 41,707 and the real 2025-2026 file at
    # 52,817 -- the offset must clear both with room to spare.
    assert DEFAULT_ID_OFFSET > 52_817


def test_columns_are_renamed_and_typed():
    frame, _ = adapt_wyscout_frame(_raw(), season="2025-2026")

    assert frame["Minutes_played"].iloc[0] == 1500
    assert str(frame["Age"].dtype) == "Int64"
    assert frame["Market_value"].iloc[0] == 700000  # "700000.0" -> integral Int64


def test_league_alias_is_normalized():
    frame, _ = adapt_wyscout_frame(_raw(), season="2025-2026")
    assert frame["League"].iloc[0] == "SPL"


def test_club_alias_is_normalized():
    frame, _ = adapt_wyscout_frame(_raw(), season="2025-2026")
    assert frame["Team_within_selected_timeframe"].iloc[0] == "Beşiktaş"


def test_position_is_derived_from_main_position_not_the_source_column():
    # Source says "CF" (-> FWD) but Main_Position is LCB -> CB, the meaning
    # every other season uses. The disagreement is counted, not applied.
    frame, stats = adapt_wyscout_frame(_raw(), season="2025-2026")

    assert frame["Position"].iloc[0] == "CB"
    assert stats["position_disagrees_with_source_column"] == 1


def test_position_agreeing_with_source_is_not_counted_as_disagreement():
    frame, stats = adapt_wyscout_frame(
        _raw(Main_Position="CF", Position="CF"), season="2025-2026"
    )
    assert frame["Position"].iloc[0] == "FWD"
    assert stats["position_disagrees_with_source_column"] == 0


@pytest.mark.parametrize("coarse", ["AM", "CM", "DM", "FWD"])
def test_coarse_main_position_values_are_already_group_names(coarse):
    frame, _ = adapt_wyscout_frame(_raw(Main_Position=coarse, Position=coarse), season="2025-2026")
    assert frame["Position"].iloc[0] == coarse


def test_junk_zero_main_position_yields_no_position_and_is_counted():
    frame, stats = adapt_wyscout_frame(
        _raw(Main_Position="0", Position="0"), season="2025-2026"
    )
    assert pd.isna(frame["Position"].iloc[0])
    assert stats["position_underivable"] == 1


def test_iso_contract_date_is_converted_to_the_importers_format():
    frame, stats = adapt_wyscout_frame(_raw(), season="2025-2026")
    assert frame["Contract_expires"].iloc[0] == "30/06/2029"
    assert stats["contract_expires_unparseable"] == 0


def test_zero_contract_placeholder_is_counted_separately_from_malformed():
    frame, stats = adapt_wyscout_frame(
        pd.concat(
            [_raw(**{"Contract expires": "0"}),
             _raw(UniqueID="2", **{"Contract expires": "not-a-date"})],
            ignore_index=True,
        ),
        season="2025-2026",
    )
    assert frame["Contract_expires"].isna().all()
    assert stats["contract_expires_placeholder_zero"] == 1
    assert stats["contract_expires_unparseable"] == 1


def test_wrong_season_file_is_rejected():
    with pytest.raises(ValueError, match="Wrong file"):
        adapt_wyscout_frame(_raw(Season="2024-2025"), season="2025-2026")


def test_duplicate_source_ids_are_rejected():
    dup = pd.concat([_raw(), _raw()], ignore_index=True)
    with pytest.raises(ValueError, match="unique"):
        adapt_wyscout_frame(dup, season="2025-2026")


def test_columns_collapsing_onto_one_name_are_rejected():
    raw = _raw()
    raw["Minutes_played"] = "1"  # the renamed form of "Minutes played" already present
    with pytest.raises(ValueError, match="collapse"):
        adapt_wyscout_frame(raw, season="2025-2026")


def test_main_position_table_is_the_players_csv_rule():
    # Spot-check the rule extracted from the real Players.csv (each
    # Main_Position maps to exactly one Position across ~41k rows).
    assert MAIN_POSITION_TO_GROUP["CF"] == "FWD"
    assert MAIN_POSITION_TO_GROUP["LWB"] == "LB"
    assert MAIN_POSITION_TO_GROUP["RCMF"] == "CM"
    assert MAIN_POSITION_TO_GROUP["LAMF"] == "AM"
    assert set(MAIN_POSITION_TO_GROUP.values()) == {
        "AM", "CB", "CM", "DM", "FWD", "GK", "LB", "LW", "RB", "RW",
    }


# ---------------------------------------------------------------------------
# resolve_club_identities: same NAME, different real clubs.
# ---------------------------------------------------------------------------


def _clubs_frame(rows):
    return pd.DataFrame(rows, columns=["Team_within_selected_timeframe", "League"])


def test_group_matching_the_existing_clubs_league_keeps_the_plain_name():
    df = _clubs_frame(
        [("Liverpool", "Premier League (England)")] * 22
        + [("Liverpool", "Primera Division (Uruguay)")] * 23
    )
    decisions = resolve_club_identities(df, {"Liverpool": "Premier League (England)"})

    by_league = {d["league"]: d["assigned_club"] for d in decisions}
    assert by_league == {
        "Premier League (England)": "Liverpool",
        "Primera Division (Uruguay)": "Liverpool (Uruguay)",
    }
    assert set(df["Team_within_selected_timeframe"]) == {"Liverpool", "Liverpool (Uruguay)"}


def test_no_group_matching_the_existing_league_suffixes_every_group():
    # A legacy-mislabelled existing club must not be handed either group by
    # guesswork (or by size) -- both are split off, existing club untouched.
    df = _clubs_frame(
        [("River Plate", "Primera Division (Argentina)")] * 21
        + [("River Plate", "Primera Division (Uruguay)")] * 26
    )
    resolve_club_identities(df, {"River Plate": "La Liga (Spain)"})

    assert set(df["Team_within_selected_timeframe"]) == {
        "River Plate (Argentina)", "River Plate (Uruguay)",
    }


def test_explicit_name_and_league_alias_wins():
    # "Athletic Club" is Athletic Bilbao in La Liga but an unrelated
    # Brazilian club in Serie B -- the alias is keyed on (name, league).
    df = _clubs_frame(
        [("Athletic Club", "La Liga (Spain)")] * 24
        + [("Athletic Club", "Brazil Serie B (Brazil)")] * 21
    )
    resolve_club_identities(df, {"Athletic Bilbao": "La Liga (Spain)"})

    spain = df[df["League"] == "La Liga (Spain)"]["Team_within_selected_timeframe"]
    brazil = df[df["League"] == "Brazil Serie B (Brazil)"]["Team_within_selected_timeframe"]
    assert set(spain) == {"Athletic Bilbao"}
    assert set(brazil) == {"Athletic Club (Brazil)"}


def test_stray_contaminated_rows_do_not_create_a_phantom_club():
    # 40 rows in one league + 2 stray rows under another is contamination,
    # not a second club (the real file is 99.24% league-consistent).
    df = _clubs_frame(
        [("Metz", "Ligue 1 (France)")] * 40 + [("Metz", "Ligue 2 (France)")] * 2
    )
    decisions = resolve_club_identities(df, {})

    assert decisions == []
    assert set(df["Team_within_selected_timeframe"]) == {"Metz"}


def test_single_league_names_are_left_alone():
    df = _clubs_frame([("Arsenal", "Premier League (England)")] * 30)
    assert resolve_club_identities(df, {}) == []


def test_missing_required_column_is_a_clear_error_not_a_keyerror():
    raw = _raw().drop(columns=["Contract expires"])
    with pytest.raises(ValueError, match="missing required column"):
        adapt_wyscout_frame(raw, season="2025-2026")
