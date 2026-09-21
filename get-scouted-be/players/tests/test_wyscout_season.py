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
        # The real file's pattern: `Main_Position` was overwritten (here a CF),
        # while `Main_Position_Original` and `Position` agree (a left CB).
        "Main_Position": "CF",
        "Main_Position_Original": "LCB",
        "Position": "CB",
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


def test_main_position_comes_from_the_original_column_not_the_overwritten_one():
    # The overwritten `Main_Position` says CF; the trustworthy
    # `Main_Position_Original` says LCB, and the file's own `Position` (CB)
    # agrees with it. The player is a centre-back.
    frame, stats = adapt_wyscout_frame(_raw(), season="2025-2026")

    assert frame["Main_Position"].iloc[0] == "LCB"
    assert frame["Position"].iloc[0] == "CB"
    assert stats["position_disagrees_with_file_position_column"] == 0


def test_a_file_whose_position_contradicts_the_original_is_counted():
    # Guard: if the source's columns ever drift apart again, the import
    # report says so instead of silently picking a side.
    frame, stats = adapt_wyscout_frame(_raw(Position="CF"), season="2025-2026")

    assert frame["Position"].iloc[0] == "CB"  # still derived from the Original
    assert stats["position_disagrees_with_file_position_column"] == 1


def test_the_original_column_never_produces_coarse_labels():
    for label, group in (("CF", "FWD"), ("LAMF", "AM"), ("RDMF", "DM"), ("RCMF", "CM"), ("LWB", "LB")):
        frame, _ = adapt_wyscout_frame(
            _raw(Main_Position_Original=label, Position=group), season="2025-2026"
        )
        assert frame["Main_Position"].iloc[0] == label
        assert frame["Position"].iloc[0] == group


@pytest.mark.parametrize(
    "coarse, rewritten, group", [("AM", "AMF", "AM"), ("DM", "DMF", "DM"), ("FWD", "CF", "FWD"), ("CM", "CM", "CM")]
)
def test_without_the_original_column_coarse_labels_fall_back_to_the_old_vocabulary(
    coarse, rewritten, group
):
    # Backstop for a file lacking `Main_Position_Original`: "AM" is not in the
    # scoring model's position table (it would silently mis-score), so the
    # coarse labels are rewritten to their old-vocabulary twins ("CM" has none).
    raw = _raw(Main_Position=coarse, Position=group).drop(columns=["Main_Position_Original"])

    frame, _ = adapt_wyscout_frame(raw, season="2025-2026")

    assert frame["Main_Position"].iloc[0] == rewritten
    assert frame["Position"].iloc[0] == group


def test_junk_zero_main_position_yields_no_position_and_is_counted():
    frame, stats = adapt_wyscout_frame(
        _raw(Main_Position="0", Main_Position_Original="0", Position="0"), season="2025-2026"
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


# ---------------------------------------------------------------------------
# Market value: Transfermarkt fills the gaps Wyscout leaves
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw, expected",
    [("€ 3.00 m", 3_000_000), ("€ 75 k", 75_000), ("€ 1.20 bn", 1_200_000_000), ("€ 500 k", 500_000)],
)
def test_transfermarkt_value_parsing(raw, expected):
    from players.wyscout_season import parse_tm_market_value

    assert parse_tm_market_value(raw) == expected


def test_transfermarkt_value_parsing_rejects_junk():
    from players.wyscout_season import parse_tm_market_value

    assert parse_tm_market_value(None) is None
    assert parse_tm_market_value(float("nan")) is None
    assert parse_tm_market_value("unknown") is None


def test_missing_wyscout_market_value_is_filled_from_transfermarkt():
    frame, stats = adapt_wyscout_frame(
        _raw(**{"Market value": None, "TM_Market value": "€ 3.00 m"}), season="2025-2026"
    )
    assert frame["Market_value"].iloc[0] == 3_000_000
    assert stats["market_value_filled_from_transfermarkt"] == 1


def test_wyscout_market_value_wins_when_both_exist():
    frame, stats = adapt_wyscout_frame(
        _raw(**{"Market value": "700000.0", "TM_Market value": "€ 3.00 m"}), season="2025-2026"
    )
    assert frame["Market_value"].iloc[0] == 700_000
    assert stats["market_value_filled_from_transfermarkt"] == 0


def test_no_value_anywhere_stays_missing_never_zero():
    frame, _ = adapt_wyscout_frame(
        _raw(**{"Market value": None, "TM_Market value": None}), season="2025-2026"
    )
    assert pd.isna(frame["Market_value"].iloc[0])


# ---------------------------------------------------------------------------
# Exact duplicates: same rule as dedupe_players (keep the most minutes)
# ---------------------------------------------------------------------------


def test_exact_duplicate_rows_are_dropped_keeping_the_most_minutes():
    raw = pd.concat(
        [
            _raw(UniqueID="1", **{"Minutes played": "500"}),
            _raw(UniqueID="2", **{"Minutes played": "2500"}),
        ],
        ignore_index=True,
    )

    frame, stats = adapt_wyscout_frame(raw, season="2025-2026")

    assert len(frame) == 1
    assert frame["UniqueID"].iloc[0] == 2 + DEFAULT_ID_OFFSET
    assert stats["exact_duplicates_dropped"] == 1


def test_minutes_tie_keeps_the_lowest_unique_id():
    raw = pd.concat(
        [_raw(UniqueID="9"), _raw(UniqueID="3")], ignore_index=True
    )
    frame, _ = adapt_wyscout_frame(raw, season="2025-2026")
    assert frame["UniqueID"].tolist() == [3 + DEFAULT_ID_OFFSET]


def test_different_people_with_the_same_name_are_not_duplicates():
    # Same name, but a different club / age / position -- a name collision,
    # never an exact duplicate.
    raw = pd.concat(
        [
            _raw(UniqueID="1"),
            _raw(UniqueID="2", **{"Team within selected timeframe": "Other FC"}),
            _raw(UniqueID="3", Age="31"),
        ],
        ignore_index=True,
    )
    frame, stats = adapt_wyscout_frame(raw, season="2025-2026")
    assert len(frame) == 3
    assert stats["exact_duplicates_dropped"] == 0


# ---------------------------------------------------------------------------
# Role scores
# ---------------------------------------------------------------------------


def test_role_scores_use_the_models_exact_role_names_and_skip_missing_ones():
    from players.wyscout_season import extract_role_scores

    raw = _raw(**{"Ball Playing Defender": "14.2", "Libero": "23.5", "Poacher": None,
                  "Box-To-Box Midfielder": None})
    frame, _ = adapt_wyscout_frame(raw, season="2025-2026")

    roles = extract_role_scores(raw, frame)

    assert set(roles["role_name_raw"]) == {"Ball Playing Defender", "Libero"}
    assert roles["score"].tolist() == [14.2, 23.5] or set(roles["score"]) == {14.2, 23.5}
    assert set(roles["Position"]) == {"CB"}
    assert set(roles["UniqueID"]) == {35583 + DEFAULT_ID_OFFSET}


def test_role_scores_keep_original_spelling_even_though_columns_are_renamed():
    # "Box-To-Box Midfielder" becomes "Box_To_Box_Midfielder" in the adapted
    # frame, but the scoring model matches roles by the ORIGINAL spelling.
    from players.wyscout_season import extract_role_scores

    raw = _raw(**{"Box-To-Box Midfielder": "50.0"})
    frame, _ = adapt_wyscout_frame(raw, season="2025-2026")

    assert extract_role_scores(raw, frame)["role_name_raw"].tolist() == ["Box-To-Box Midfielder"]


def test_role_scores_only_cover_rows_that_survived_deduplication():
    from players.wyscout_season import extract_role_scores

    raw = pd.concat(
        [
            _raw(UniqueID="1", **{"Minutes played": "100", "Libero": "10.0"}),
            _raw(UniqueID="2", **{"Minutes played": "900", "Libero": "20.0"}),
        ],
        ignore_index=True,
    )
    frame, _ = adapt_wyscout_frame(raw, season="2025-2026")

    roles = extract_role_scores(raw, frame)

    assert roles["score"].tolist() == [20.0]  # the dropped duplicate's score is not carried over
