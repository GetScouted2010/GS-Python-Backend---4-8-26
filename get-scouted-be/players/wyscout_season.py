"""Adapter: a Wyscout(+Transfermarkt) season export -> the Players.csv schema.

Written for the 2025-2026 pull (`dataset/missing_data/wyscout_with_TM_data.csv`,
18,365 rows, 208 columns), which carries the same ~116 stat columns as
Players.csv but in a different shape. Everything below was found by
comparing the two files against real data, not assumed:

1. ENCODING -- the file is cp1252, NOT UTF-8. Reading it as UTF-8 (or with
   `errors="replace"`) silently corrupts club names ("Saint-Étienne" ->
   "Saint-�tienne"), which would then fail to match the Club table.

2. COLUMN NAMES -- raw Wyscout style ("Minutes played", "Duels won, %")
   instead of Players.csv's underscore style ("Minutes_played",
   "Duels_won_percentage"). `to_players_csv_name` translates them; the rule
   is verified against Players.csv's own header in the tests.

3. UNIQUE IDs COLLIDE -- the file's `UniqueID` is a separate numbering
   scheme. 7,255 of its 18,365 IDs also exist in Players.csv, and NONE of
   those are the same person (ID 35583 is Becir Omeragic here, M. Roerslev
   in Players.csv). `import_players` upserts on `unique_id`, so importing
   these IDs verbatim would silently overwrite 7,255 real 2022-24 rows with
   unrelated players. IDs are therefore shifted by a fixed offset
   (DEFAULT_ID_OFFSET) so they can never collide, and stay stable across
   re-imports (idempotent upsert).

4. POSITION -- the file's `Main_Position` column is NOT trustworthy: for 3,180
   rows (17%) it was overwritten by the provider's pipeline and contradicts
   the player's own recorded positions (a goalkeeper stored as "LB", a
   striker as "RB"). Two facts, both measured on the real file, identify the
   right source:
     - `Main_Position_Original` agrees with the file's `Position` column on
       100% of rows (18,349 of 18,349), and
     - across every one of the 3,180 disputed rows, `Position` is among the
       positions the player is recorded playing (`WYS Position`) 100% of the
       time, while `Main_Position` is only 39.5% of the time (and never right
       when `Position` is wrong).
   `Main_Position_Original` also uses exactly the old data's vocabulary
   (LCB, RCMF, LWB, ...), with none of the coarse AM/CM/DM/FWD labels. So
   `Main_Position` is taken from `Main_Position_Original` and `Position` is
   derived from it with Players.csv's own rule (MAIN_POSITION_TO_GROUP: every
   Main_Position maps to exactly one Position across ~41k rows) -- which
   reproduces the file's own `Position` column exactly.
   (An earlier version of this adapter trusted `Main_Position` and got ~17%
   of positions wrong; scoring the season against the provider's own numbers
   is what exposed it.)

5. DATES -- `Contract expires` is ISO (2026-06-30); the shared row builder
   parses dd/mm/YYYY. Converted here.

6. LEAGUE / CLUB NAMES -- several competitions and clubs are spelled
   differently from the existing rows. Normalized through the shared alias
   maps (clubs/leagues.py, clubs/name_normalization.py).

8. COARSE `Main_Position` LABELS -- the overwritten `Main_Position` column
   also carries AM/CM/DM/FWD, values the older data never had and that the
   scoring model's position table does not all know ("AM" is missing from it,
   which would silently mis-score those players). Reading
   `Main_Position_Original` (item 4) avoids them entirely;
   MAIN_POSITION_CANONICAL only backstops a file that lacks that column.

9. MARKET VALUE -- 25.5% of rows have no Wyscout market value. Where the
   Transfermarkt column has one, it fills the gap (1,863 of 4,686 rows).
   Wyscout stays primary, for continuity with the older seasons.

10. EXACT DUPLICATES -- 11 groups are the same real player recorded twice
   (same name, club, age, position; split minutes). They are dropped with the
   same rule as `dedupe_players` (keep the most minutes) so they are never
   inserted and `import_all`'s dedupe step never fights this import.

7. SAME NAME, DIFFERENT CLUB -- the Club table is keyed by name alone, but
   6 names in this file are two real clubs in two countries ("Liverpool" =
   England AND Uruguay, "River Plate", "Nacional", "Fortaleza", "Aris",
   "Athletic Club"). Left alone, e.g. Uruguayan Liverpool players would land
   in English Liverpool's squad. `resolve_club_identities` splits them.
"""

from __future__ import annotations

import re

import pandas as pd

from clubs.leagues import normalize_league_name
from clubs.name_normalization import CLUB_NAME_LEAGUE_ALIASES, normalize_club_name
from core.import_utils import DEFAULT_NA_VALUES
from players.management.commands.import_players import DTYPES

SOURCE_ENCODING = "cp1252"

# 2025-2026 raw IDs span 34,453-52,817 and Players.csv's span 0-41,707, so
# any offset >= ~52k is collision-free; 1,000,000 leaves ample headroom and
# is trivially recognisable (unique_id >= 1_000_000 == a Wyscout-season row).
# MUST stay the same on every re-import of the same season, or the upsert
# would create duplicates instead of updating in place.
DEFAULT_ID_OFFSET = 1_000_000

# Players.csv's own Main_Position -> Position rule, extracted from the real
# file (every one of the 21 non-junk Main_Position values maps to exactly one
# Position). The four coarse-only values (AM/CM/DM/FWD) appear only in the
# 2025-2026 file's Main_Position and are already group names.
MAIN_POSITION_TO_GROUP: dict[str, str] = {
    "AMF": "AM", "LAMF": "AM", "RAMF": "AM", "AM": "AM",
    "CB": "CB", "LCB": "CB", "RCB": "CB",
    "CF": "FWD", "FWD": "FWD",
    "DMF": "DM", "LDMF": "DM", "RDMF": "DM", "DM": "DM",
    "GK": "GK",
    "LB": "LB", "LWB": "LB",
    "LCMF": "CM", "RCMF": "CM", "CM": "CM",
    "LW": "LW", "LWF": "LW",
    "RB": "RB", "RWB": "RB",
    "RW": "RW", "RWF": "RW",
}

# Post-rename names the adapter reads unconditionally.
_REQUIRED_COLUMNS = {
    "UniqueID", "Season", "League", "Player", "Team_within_selected_timeframe",
    "Main_Position", "Position", "Contract_expires",
}

# Coarse labels -> the equivalent label the older data already uses. Only a
# backstop: `Main_Position_Original` (the source actually used) never contains
# them. "CM" has no twin (the old data only has LCMF/RCMF) and is left as is.
MAIN_POSITION_CANONICAL: dict[str, str] = {"AM": "AMF", "DM": "DMF", "FWD": "CF"}

# Columns whose Players.csv name is not derivable from the raw name by rule.
_RENAME_OVERRIDES: dict[str, str] = {
    # Players.csv's multi-position list ("AMF, LW, RW") is this file's
    # `WYS Position`, not its `Position3`.
    "WYS Position": "Positions",
}


def to_players_csv_name(raw: str) -> str:
    """Translate a raw Wyscout column name to its Players.csv equivalent.

    "Duels won, %"                         -> "Duels_won_percentage"
    "Average pass length, m"               -> "Average_pass_length_m"
    "Accurate short / medium passes, %"    -> "Accurate_short_medium_passes_percentage"
    "Non-penalty goals per 90"             -> "Non_penalty_goals_per_90"
    "Count Medium Acceleration per 90 (1.5 m/s² to 3 m/s²)"
                                           -> "Count_Medium_Acceleration_per_90_(1_DOT_5_m/s²_to_3_m/s²)"

    Deliberately conservative: a hyphen is only rewritten BETWEEN letters
    (so "(-3 m/s²)" keeps its sign) and a slash only when spaced (so "km/h"
    and "Meter/Min" are untouched).
    """
    name = raw.strip()
    if name in _RENAME_OVERRIDES:
        return _RENAME_OVERRIDES[name]
    name = name.replace(", %", "_percentage").replace(", m", "_m")
    name = name.replace("1.5 m/s", "1_DOT_5_m/s")
    name = re.sub(r"\s+/\s+", "_", name)
    name = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "_", name)
    return name.replace(" ", "_")


def read_wyscout_csv(path) -> pd.DataFrame:
    """Read the raw export: cp1252, every cell as a string (typing happens
    explicitly in `adapt_wyscout_frame`, never by pandas inference)."""
    return pd.read_csv(
        path,
        encoding=SOURCE_ENCODING,
        dtype=str,
        na_values=list(DEFAULT_NA_VALUES),
        keep_default_na=True,
        low_memory=False,
    )


def _coerce_types(df: pd.DataFrame) -> pd.DataFrame:
    """Apply import_players' explicit dtype map to a string-typed frame."""
    for col, dtype in DTYPES.items():
        if col not in df.columns:
            continue
        if dtype == "string":
            df[col] = df[col].astype("string")
        elif dtype == "Float64":
            df[col] = pd.to_numeric(df[col], errors="coerce").astype("Float64")
        elif dtype in ("Int64", "int64"):
            numeric = pd.to_numeric(df[col], errors="coerce")
            df[col] = numeric.round().astype("Int64")
    return df


# A league group only counts as a distinct club if it is substantial: the
# file's rows are 99.24% league-consistent per club, so a single stray row
# under a second league is contamination, not a second club. All six real
# collisions in the 2025-2026 file have >= 21 rows and >= 40% share per group.
COLLISION_MIN_ROWS = 8
COLLISION_MIN_SHARE = 0.15


def _country_of(league: str) -> str:
    """"Primera Division (Uruguay)" -> "Uruguay"; a label with no
    parenthetical is returned unchanged."""
    match = re.search(r"\(([^)]+)\)\s*$", league)
    return match.group(1) if match else league


def resolve_club_identities(
    df: pd.DataFrame, existing_club_league: dict[str, str | None]
) -> list[dict]:
    """Split names that are really two clubs (mutates `df` in place).

    For a club name that appears under >= 2 substantial leagues, each league
    group is assigned, in order of preference:
      1. an explicit (name, league) alias  (CLUB_NAME_LEAGUE_ALIASES), else
      2. the plain name, if it is ALREADY a Club whose league equals this
         group's league (strong evidence it is that club), else
      3. "<name> (<country>)" -- a new, unambiguous Club.

    Never guesses a winner by size: when the existing Club's league doesn't
    match any group (e.g. a legacy-mislabelled "River Plate"), every group
    gets a suffixed name and the existing Club is left untouched for a
    later, reviewed merge. Returns one decision dict per split group so the
    import report shows exactly what was done.
    """
    decisions: list[dict] = []
    valid = df["Team_within_selected_timeframe"].notna() & df["League"].notna()
    for name, group in df[valid].groupby("Team_within_selected_timeframe"):
        counts = group["League"].value_counts()
        total = int(counts.sum())
        substantial = [
            league
            for league, n in counts.items()
            if n >= COLLISION_MIN_ROWS and n / total >= COLLISION_MIN_SHARE
        ]
        if len(substantial) < 2:
            continue
        existing_league = existing_club_league.get(name)
        for league in sorted(substantial):
            if (name, league) in CLUB_NAME_LEAGUE_ALIASES:
                assigned = CLUB_NAME_LEAGUE_ALIASES[(name, league)]
            elif existing_league == league:
                assigned = name
            else:
                assigned = f"{name} ({_country_of(league)})"
            if assigned != name:
                mask = (df["Team_within_selected_timeframe"] == name) & (df["League"] == league)
                df.loc[mask, "Team_within_selected_timeframe"] = assigned
            decisions.append(
                {"source_name": name, "league": league, "rows": int(counts[league]),
                 "assigned_club": assigned}
            )
    return decisions


def parse_tm_market_value(value) -> float | None:
    """Transfermarkt's "€ 3.00 m" / "€ 75 k" / "€ 1.2 bn" -> a number."""
    if not isinstance(value, str):
        return None
    text = value.lower().replace("€", "").replace("£", "").replace(",", "").strip()
    try:
        if text.endswith("bn"):
            return float(text[:-2]) * 1e9
        if text.endswith("m"):
            return float(text[:-1]) * 1e6
        if text.endswith("k"):
            return float(text[:-1]) * 1e3
        return float(text)
    except ValueError:
        return None


def drop_exact_duplicates(df: pd.DataFrame) -> int:
    """Drop rows that are the same observation as another (mutates `df`).

    Same rule as `players/management/commands/dedupe_players.py`: identical
    (player, club, age, position) -- season is constant within one file --
    keeps the row with the most minutes, then most matches, then the lowest
    UniqueID. Rows with any part of the key missing are never grouped.
    Returns how many rows were dropped.
    """
    key = ["Player", "Team_within_selected_timeframe", "Age", "Position"]
    if not set(key) <= set(df.columns):
        return 0
    complete = df[key].notna().all(axis=1)
    nan = pd.Series(float("nan"), index=df.index)
    minutes = pd.to_numeric(df.get("Minutes_played", nan), errors="coerce").fillna(-1)
    matches = pd.to_numeric(df.get("Matches_played", nan), errors="coerce").fillna(-1)
    ranked = (
        df[complete]
        .assign(_minutes=minutes, _matches=matches)
        .sort_values(["_minutes", "_matches", "UniqueID"], ascending=[False, False, True])
    )
    losers = ranked[ranked.duplicated(key, keep="first")].index
    df.drop(index=losers, inplace=True)
    return len(losers)


def extract_role_scores(raw: pd.DataFrame, frame: pd.DataFrame) -> pd.DataFrame:
    """Long-form role scores (UniqueID, Position, role_name_raw, score) for the
    rows that survived into `frame`, straight from the RAW file.

    The role columns are read from `raw` because `adapt_wyscout_frame`
    renames columns for the Players.csv schema, and the model matches role
    names by their exact original spelling ("Box-To-Box Midfielder"). Only
    non-null scores are returned; a role a player has no score for is simply
    absent (never a fabricated zero). Every role name the model knows is
    present in the file, and the file's spelling matches the model's exactly.
    """
    from scoring.characterization.reconstruct import ROLE_COLUMNS_BY_POSITION

    wanted = {r for roles in ROLE_COLUMNS_BY_POSITION.values() for r in roles}
    role_columns = sorted(wanted & set(raw.columns))
    scores = raw.loc[frame.index, role_columns].apply(pd.to_numeric, errors="coerce")
    scores["UniqueID"] = frame["UniqueID"]
    scores["Position"] = frame["Position"]
    long = scores.melt(
        id_vars=["UniqueID", "Position"],
        value_vars=role_columns,
        var_name="role_name_raw",
        value_name="score",
    )
    return long.dropna(subset=["score", "Position"]).reset_index(drop=True)


def adapt_wyscout_frame(
    raw: pd.DataFrame,
    *,
    season: str,
    id_offset: int = DEFAULT_ID_OFFSET,
    existing_club_league: dict[str, str | None] | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Return `(frame, stats)`: `raw` reshaped into the Players.csv schema
    (so `import_players._build_player_kwargs` can consume its rows unchanged)
    plus a dict of adaptation counts for the import report.

    Raises ValueError if the file isn't the requested season (guards against
    pointing the command at the wrong file), lacks a required column, if two
    source columns collapse to one target name, or if the source UniqueIDs are
    null/non-unique.
    """
    df = raw.copy()

    renamed = {c: to_players_csv_name(c) for c in df.columns}
    duplicated_targets = sorted(
        {t for t in renamed.values() if list(renamed.values()).count(t) > 1}
    )
    if duplicated_targets:
        raise ValueError(
            f"Source columns collapse onto the same Players.csv name: {duplicated_targets}"
        )
    df = df.rename(columns=renamed)

    missing_required = sorted(_REQUIRED_COLUMNS - set(df.columns))
    if missing_required:
        raise ValueError(f"Source file is missing required column(s): {missing_required}")

    seasons_in_file = set(df["Season"].dropna().unique())
    if seasons_in_file != {season}:
        raise ValueError(
            f"Expected every row to be season {season!r}, but the file contains "
            f"{sorted(seasons_in_file)}. Wrong file?"
        )

    ids = pd.to_numeric(df["UniqueID"], errors="coerce")
    if ids.isna().any() or ids.duplicated().any():
        raise ValueError("Source UniqueID must be present and unique on every row.")
    df["UniqueID"] = ids.astype("int64") + id_offset

    df["League"] = df["League"].map(
        lambda v: normalize_league_name(v) if isinstance(v, str) else v
    )
    df["Team_within_selected_timeframe"] = df["Team_within_selected_timeframe"].map(
        lambda v: normalize_club_name(v) if isinstance(v, str) else v
    )

    club_identity_decisions = resolve_club_identities(df, existing_club_league or {})

    # See module docstring item 4: `Main_Position` is overwritten for ~17% of
    # rows; `Main_Position_Original` is the trustworthy one.
    source_position = df["Position"]
    if "Main_Position_Original" in df.columns:
        df["Main_Position"] = df["Main_Position_Original"].where(
            df["Main_Position_Original"].notna(), df["Main_Position"]
        )
    df["Position"] = df["Main_Position"].map(MAIN_POSITION_TO_GROUP)
    # NaN on either side (junk "0" Main_Position rows, or an unmapped value)
    # means "no derivable group" -- never disagreement. Expected to be 0: a
    # nonzero count means the source's columns have drifted apart again.
    comparable = df["Position"].notna() & source_position.notna()
    source_as_group = source_position.map(
        {"CF": "FWD", "AMF": "AM", "DMF": "DM"}
    ).fillna(source_position)
    position_disagreements = int(
        (comparable & (df["Position"] != source_as_group)).sum()
    )

    main_position_rewritten = int(df["Main_Position"].isin(MAIN_POSITION_CANONICAL).sum())
    df["Main_Position"] = df["Main_Position"].replace(MAIN_POSITION_CANONICAL)

    market_value_filled_from_tm = 0
    if "TM_Market_value" in df.columns:
        wyscout_mv = pd.to_numeric(df["Market_value"], errors="coerce")
        # to_numeric: a column with no parseable value at all is all-None
        # (object dtype), which `.round()` below would reject.
        tm_mv = pd.to_numeric(df["TM_Market_value"].map(parse_tm_market_value), errors="coerce")
        fill = wyscout_mv.isna() & tm_mv.notna()
        market_value_filled_from_tm = int(fill.sum())
        if market_value_filled_from_tm:
            df["Market_value"] = df["Market_value"].where(~fill, tm_mv.round().astype("Int64").astype(str))

    raw_contract = df["Contract_expires"]
    parsed_contract = pd.to_datetime(raw_contract, format="%Y-%m-%d", errors="coerce")
    # The source (like Players.csv) writes a literal "0" for "no contract
    # date"; count it apart from genuinely malformed values.
    contract_placeholder_zero = int((raw_contract == "0").sum())
    contract_unparseable = int(
        (raw_contract.notna() & (raw_contract != "0") & parsed_contract.isna()).sum()
    )
    df["Contract_expires"] = parsed_contract.dt.strftime("%d/%m/%Y")

    df = _coerce_types(df)
    exact_duplicates_dropped = drop_exact_duplicates(df)

    # The four denormalized scores are computed by `recompute_scores`, never
    # sourced from a CSV -- their absence is expected, not a gap.
    computed_not_sourced = {
        "impact_score", "compatibility_score",
        "financial_fit_score", "transfer_probability_score",
    }
    expected = set(DTYPES) - {"UniqueID"} - computed_not_sourced
    stats = {
        "rows": len(df),
        "rows_in_source": len(raw),
        "id_offset": id_offset,
        "position_underivable": int(df["Position"].isna().sum()),
        "position_disagrees_with_file_position_column": position_disagreements,
        "contract_expires_placeholder_zero": contract_placeholder_zero,
        "contract_expires_unparseable": contract_unparseable,
        "expected_columns_absent_from_source": sorted(expected - set(df.columns)),
        "main_position_rewritten_to_old_vocabulary": main_position_rewritten,
        "market_value_filled_from_transfermarkt": market_value_filled_from_tm,
        "exact_duplicates_dropped": exact_duplicates_dropped,
        "club_identity_decisions": club_identity_decisions,
    }
    return df, stats
