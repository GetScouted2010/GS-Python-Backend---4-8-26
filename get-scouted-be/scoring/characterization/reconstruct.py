"""ORM -> script-shaped DataFrame reconstruction layer.

`pixel-perfect-clone-60729/docs/impact_model_v4.1.py` (the original,
untested 15,700-line scoring script Phases 4-6 port function-by-function)
can only ever run against DataFrames whose column NAMES match its
hardcoded string literals -- it was written against an Excel/xlsx export
with human-readable, space-separated column headers, not the underscore
snake_case names this project's Django models use (see
`docs/FIELD_MAPPING.md`, the single source of truth for every rename
applied below -- do not re-derive column names from scratch here).

This module is the one and only place that bridges real migrated Postgres
data (Player, PlayerRoleScore, Club, Transfer) into those four
script-shaped DataFrames:

    build_players_df()       -> one row per Player, script-literal column names
    build_role_scores_wide() -> PlayerRoleScore long->wide pivot, one row per player
    build_team_styles_df()   -> one row per Club, 8 playing-style columns + "Team"
    build_transfers_df()     -> one row per Transfer, script-literal column names

Every downstream calculator (Phase 4+) should call `assert_columns_present`
before reading columns off these DataFrames, so a reconstruction bug (a
missing/renamed column) surfaces as a loud `ValueError`, not a silently
zero-filled/NaN score (03-RESEARCH.md Pitfall 3, CONCERNS.md's
silent-default bug class -- exactly what this phase exists to prevent).
"""

from __future__ import annotations

import logging
import re

import pandas as pd

from clubs.models import Club
from players.models import Player, PlayerRoleScore
from transfers.models import Transfer

logger = logging.getLogger(__name__)


def assert_columns_present(df: pd.DataFrame, required: list[str], name: str) -> None:
    """Raise loudly if any `required` column is absent from `df`.

    Callers must use this instead of `.get(col, default)`-style silent
    fallbacks -- a reconstruction bug should fail fast, not produce a
    plausible-looking but wrong (e.g. zero-filled) score downstream.
    """
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{name} missing columns: {missing}")


# =========================================================================
# 1. build_players_df
# =========================================================================

# FIELD_MAPPING.md section 1a: identifier/meta/profile columns. These are
# lowercase, Django-conventional field names on Player (the "maximize
# completeness but use lowercase for non-stat fields" locked decision) that
# still need renaming to the space/underscore literal impact_model_v4.1.py
# reads internally.
_IDENTIFIER_RENAME = {
    "player": "Player",
    "season": "Season",
    "league": "League",
    "positions": "Positions",
    "main_position": "Main_Position",
    "position": "Position",
    "age": "Age",
    "market_value": "Market value",
    "contract_expires": "Contract expires",
    "birth_country": "Birth country",
    "passport_country": "Passport country",
    "foot": "Foot",
    "height": "Height",
    "on_loan": "On loan",
}

# FIELD_MAPPING.md section 1b: the ~99 numeric stat columns. Django field
# names already mirror the CSV's Snake_Case_With_Caps verbatim (locked
# naming decision), so the keys below are the real Player model field
# names; the values are the literal, human-readable strings
# impact_model_v4.1.py's calculators read. Columns FIELD_MAPPING.md marks
# "not referenced" are intentionally omitted -- they're still migrated data
# but the scoring engine never reads them, so no rename is needed.
_STAT_RENAME = {
    "Matches_played": "Matches played",
    "Minutes_played": "Minutes played",
    "Goals": "Goals",
    "Assists": "Assists",
    "Duels_per_90": "Duels per 90",
    "Duels_won_percentage": "Duels won, %",
    "Successful_defensive_actions_per_90": "Successful defensive actions per 90",
    "Defensive_duels_per_90": "Defensive duels per 90",
    "Defensive_duels_won_percentage": "Defensive duels won, %",
    "Aerial_duels_per_90": "Aerial duels per 90",
    "Aerial_duels_won_percentage": "Aerial duels won, %",
    "Sliding_tackles_per_90": "Sliding tackles per 90",
    "Shots_blocked_per_90": "Shots blocked per 90",
    "Interceptions_per_90": "Interceptions per 90",
    "PAdj_Interceptions": "PAdj Interceptions",
    "Fouls_per_90": "Fouls per 90",
    "Yellow_cards_per_90": "Yellow cards per 90",
    "Red_cards_per_90": "Red cards per 90",
    "Successful_attacking_actions_per_90": "Successful attacking actions per 90",
    "Goals_per_90": "Goals per 90",
    "Non_penalty_goals_per_90": "Non-penalty goals per 90",
    "xG_per_90": "xG per 90",
    "Head_goals_per_90": "Head goals per 90",
    "Shots_per_90": "Shots per 90",
    "Shots_on_target_percentage": "Shots on target, %",
    "Goal_conversion_percentage": "Goal conversion, %",
    "Assists_per_90": "Assists per 90",
    "Crosses_per_90": "Crosses per 90",
    "Accurate_crosses_percentage": "Accurate crosses, %",
    "Crosses_from_left_flank_per_90": "Crosses from left flank per 90",
    "Crosses_from_right_flank_per_90": "Crosses from right flank per 90",
    "Crosses_to_goalie_box_per_90": "Crosses to goalie box per 90",
    "Dribbles_per_90": "Dribbles per 90",
    "Successful_dribbles_percentage": "Successful dribbles, %",
    "Offensive_duels_per_90": "Offensive duels per 90",
    "Offensive_duels_won_percentage": "Offensive duels won, %",
    "Touches_in_box_per_90": "Touches in box per 90",
    "Progressive_runs_per_90": "Progressive runs per 90",
    "Accelerations_per_90": "Accelerations per 90",
    "Received_passes_per_90": "Received passes per 90",
    "Received_long_passes_per_90": "Received long passes per 90",
    "Fouls_suffered_per_90": "Fouls suffered per 90",
    "Passes_per_90": "Passes per 90",
    "Accurate_passes_percentage": "Accurate passes, %",
    "Forward_passes_per_90": "Forward passes per 90",
    "Accurate_forward_passes_percentage": "Accurate forward passes, %",
    "Back_passes_per_90": "Back passes per 90",
    "Accurate_back_passes_percentage": "Accurate back passes, %",
    "Lateral_passes_per_90": "Lateral passes per 90",
    "Short_medium_passes_per_90": "Short / medium passes per 90",
    "Accurate_short_medium_passes_percentage": "Accurate short / medium passes, %",
    "Long_passes_per_90": "Long passes per 90",
    "Accurate_long_passes_percentage": "Accurate long passes, %",
    "Average_long_pass_length_m": "Average long pass length, m",
    "xA_per_90": "xA per 90",
    "Shot_assists_per_90": "Shot assists per 90",
    "Smart_passes_per_90": "Smart passes per 90",
    "Accurate_smart_passes_percentage": "Accurate smart passes, %",
    "Key_passes_per_90": "Key passes per 90",
    "Passes_to_final_third_per_90": "Passes to final third per 90",
    "Accurate_passes_to_final_third_percentage": "Accurate passes to final third, %",
    "Passes_to_penalty_area_per_90": "Passes to penalty area per 90",
    "Accurate_passes_to_penalty_area_percentage": "Accurate passes to penalty area, %",
    "Through_passes_per_90": "Through passes per 90",
    "Accurate_through_passes_percentage": "Accurate through passes, %",
    "Deep_completions_per_90": "Deep completions per 90",
    "Deep_completed_crosses_per_90": "Deep completed crosses per 90",
    "Progressive_passes_per_90": "Progressive passes per 90",
    "Accurate_progressive_passes_percentage": "Accurate progressive passes, %",
    "Conceded_goals_per_90": "Conceded goals per 90",
    "Shots_against_per_90": "Shots against per 90",
    "Clean_sheets": "Clean sheets",
    "Save_rate_percentage": "Save rate, %",
    "xG_against_per_90": "xG against per 90",
    "Prevented_goals_per_90": "Prevented goals per 90",
    "Back_passes_received_as_GK_per_90": "Back passes received as GK per 90",
    "Exits_per_90": "Exits per 90",
}

_PLAYERS_REQUIRED_COLUMNS = [
    "player_id",
    "Player",
    "Team",
    "Main_Position",
    "Position",
    "Minutes played",
    "Minutes",
    "Market value",
]

# Phase 6 denormalized final-score fields (players/models.py::Player) are
# pipeline OUTPUTS written by the recompute_scores command, never scoring
# INPUTS -- population reconstruction must NEVER read them back. Excluding
# them here is load-bearing: `compatibility_score` in particular collides
# with the freshly-computed cs_tp["compatibility_score"] that
# generate_scoring_oracle.py:177, train_tfm_model.py:98, and
# financial_fit.py::_merge_tfm_feature_columns merge back onto players_df
# `on="player_id"`. If the raw field leaked in, that merge would silently
# yield compatibility_score_x/_y suffix columns -> KeyError in the oracle
# and a silent NaN TFM feature in the live Financial Fit path
# (tfm_model.py:799). See this module's docstring: fail-loud, never
# silently-corrupt.
_DENORMALIZED_SCORE_FIELDS = frozenset(
    {
        "impact_score",
        "compatibility_score",
        "financial_fit_score",
        "transfer_probability_score",
    }
)


def build_players_df() -> pd.DataFrame:
    """One row per Player, columns renamed to impact_model_v4.1.py's literals.

    `player_id` (the Player UUID) is carried as a stable join key back to
    Postgres -- the script itself has no stable id, only the non-unique
    `Player` display-name string.
    """
    field_names = [
        f.name
        for f in Player._meta.fields
        if f.name not in _DENORMALIZED_SCORE_FIELDS
    ]
    qs = Player.objects.select_related("club").values(*field_names, "club__name")
    df = pd.DataFrame.from_records(list(qs))

    rename_map = {"id": "player_id", "club__name": "Team"}
    rename_map.update(_IDENTIFIER_RENAME)
    rename_map.update(_STAT_RENAME)
    df = df.rename(columns=rename_map)

    # Several impact_model_v4.1.py functions (e.g.
    # build_target_team_position_players, line ~2575) key on a bare
    # "Minutes" column and only fall back to "Minutes played" if it's
    # absent -- provide both explicitly rather than relying on every
    # caller's fallback branch (03-RESEARCH.md "Minutes" naming pitfall).
    if "Minutes played" in df.columns:
        df["Minutes"] = df["Minutes played"]

    assert_columns_present(df, _PLAYERS_REQUIRED_COLUMNS, "build_players_df")
    return df


# =========================================================================
# 2. build_role_scores_wide
# =========================================================================

# Verbatim copy of impact_model_v4.1.py's ROLE_COLUMNS_BY_POSITION keys
# (lines ~824-904), flattened to a set of role-name literals. Used only to
# validate/log PlayerRoleScore column coverage here -- the actual role-fit
# scoring logic (which reads these columns) is ported in Phase 4, not here.
ROLE_COLUMNS_BY_POSITION = {
    "CF": [
        "Deep-Lying Forward", "Target Forward", "Poacher", "Complete Forward",
        "Advanced Forward", "Pressing Forward", "Trequartista",
    ],
    "AMF": ["Shadow Striker", "Advanced Playmaker", "Enganche", "Trequartista"],
    "CM": [
        "Box-To-Box Midfielder", "Carrilero", "Ball Winning Midfielder (Defend)",
        "Central Midfielder (Support)", "Advanced Playmaker (Attack)",
        "Advanced Playmaker (Support)", "Mezzala",
    ],
    "DMF": [
        "Regista", "Deep Lying Playmaker", "Half Back", "Anchor",
        "Segundo Volante", "Ball Winning Midfielder", "Roaming Playmaker",
    ],
    "CB": [
        "Wide Centre-Back (LCB)", "No-Nonsense Centre-Back",
        "Ball Playing Defender", "Wide Centre-Back (RCB)", "Libero",
    ],
    "LB": [
        "No-Nonsense Full-Back", "Full-Back", "Complete Wing-Back",
        "Wing-Back", "Inverted Wing-Back", "Inverted Full-Back",
    ],
    "RB": [
        "Full-Back", "Complete Wing-Back", "Wing-Back", "Inverted Full-Back",
        "Inverted Wing-Back", "No-Nonsense Full-Back",
    ],
    "RW": [
        "Winger (Support)", "Inverted Winger", "Advanced Playmaker (Attack)",
        "Inside Forward", "Winger (Defend)", "Advanced Playmaker (Support)",
    ],
    "LW": [
        "Advanced Playmaker (Support)", "Winger (Support)", "Winger (Defend)",
        "Inverted Winger", "Advanced Playmaker (Attack)",
        "Trequartista (Support)", "Inside Forward (Attack)",
    ],
    "GK": [
        "Goalkeeper (Defend)", "Sweeper Keeper (Balanced)",
        "Sweeper Keeper (Build-Up)", "Goalkeeper (Ball-Playing)",
    ],
}

_ROLE_LABEL_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_role_label(raw: str) -> str:
    """Best-effort underscore->space normalization of a raw role header.

    `PlayerRoleScore.role_name_raw` is the literal CSV column header from
    the 9 Positions/*.csv files (see
    players/management/commands/import_position_roles.py), which is itself
    inconsistent about hyphens/parentheses (e.g. "Wide_Centre-Back_(LCB)"
    vs "Wide_Centre_Back_(RCB)" for the CB position group -- a genuine
    source-data quirk, not an import bug). This normalization recovers an
    exact match against ROLE_COLUMNS_BY_POSITION for the common case
    (underscore-for-space, including collapsing the stray double-space in
    "Advanced _Playmaker") but is not guaranteed to reach 100% coverage --
    `build_role_scores_wide` logs whatever gap remains rather than
    fabricating a match.
    """
    return _ROLE_LABEL_WHITESPACE_RE.sub(" ", raw.replace("_", " ")).strip()


def build_role_scores_wide() -> pd.DataFrame:
    """Pivot PlayerRoleScore long (player x role) -> wide (one row per player).

    Columns are the normalized role labels (see `_normalize_role_label`).
    Missing coverage against ROLE_COLUMNS_BY_POSITION is logged, never
    fabricated -- a role a player has no score for should be an absent
    column/NaN, not a manufactured zero (CONCERNS.md silent-default class).
    """
    qs = PlayerRoleScore.objects.values("player_id", "role_name_raw", "score")
    long_df = pd.DataFrame.from_records(list(qs))

    if long_df.empty:
        logger.warning("build_role_scores_wide: PlayerRoleScore table is empty")
        return pd.DataFrame(columns=["player_id"])

    long_df["role_label"] = long_df["role_name_raw"].apply(_normalize_role_label)
    wide = long_df.pivot_table(
        index="player_id", columns="role_label", values="score", aggfunc="mean"
    )
    wide = wide.reset_index()
    wide.columns.name = None

    all_role_names = {
        name for roles in ROLE_COLUMNS_BY_POSITION.values() for name in roles
    }
    missing = sorted(all_role_names - set(wide.columns))
    if missing:
        logger.warning(
            "build_role_scores_wide: %d/%d ROLE_COLUMNS_BY_POSITION role names "
            "have no matching PlayerRoleScore column after normalization "
            "(role_name_raw source data is itself inconsistent about hyphens/"
            "parens -- not fabricated): %s",
            len(missing),
            len(all_role_names),
            missing,
        )

    return wide


# =========================================================================
# 3. build_team_styles_df
# =========================================================================

# impact_model_v4.1.py's STYLE_COLUMNS (line ~2000) + the "Team" column
# calculate_subjective_role_fit_for_player_to_team (line ~2446) matches
# against. Club model fields (clubs/models.py) are unprefixed lowercase.
_CLUB_STYLE_RENAME = {
    "name": "Team",
    "control_possession": "Control Possession",
    "gegenpressing": "Gegenpressing",
    "direct_play": "Direct Play",
    "defensive_counter_attack": "Defensive Counter Attack",
    "tiki_taka": "Tiki Taka",
    "counter_attack": "Counter Attack",
    "wing_play": "Wing Play",
    "low_block": "Low Block",
}

_TEAM_STYLES_REQUIRED_COLUMNS = list(_CLUB_STYLE_RENAME.values())


def build_team_styles_df() -> pd.DataFrame:
    """One row per Club with the 8 playing-style columns + "Team".

    Only ~22.6% of clubs have Playstyles.csv coverage (FIELD_MAPPING.md
    section 3) -- absent style values are left as NaN here, never
    `.fillna(0)`'d. A club with no known style should make
    `weighted_overlap_score` produce a low-confidence/NaN result, not a
    confidently-wrong "this club plays nothing" zero vector.
    """
    fields = ["name"] + [
        k for k in _CLUB_STYLE_RENAME if k != "name"
    ]
    qs = Club.objects.values(*fields)
    df = pd.DataFrame.from_records(list(qs))
    df = df.rename(columns=_CLUB_STYLE_RENAME)

    assert_columns_present(df, _TEAM_STYLES_REQUIRED_COLUMNS, "build_team_styles_df")
    return df


# =========================================================================
# 4. build_transfers_df
# =========================================================================

# impact_model_v4.1.py's build_transfer_value_dataset() (line ~4935) reads
# these literals directly off transfers_df. `player_name_raw` -> "Player"
# is the same best-effort name-string join the original script used (no
# stable transfer-event<->player id exists in the source data -- see
# FIELD_MAPPING.md section 4).
_TRANSFER_RENAME = {
    "player_name_raw": "Player",
    "year": "Year",
    "position": "Position",
    "age_at_transfer": "Age",
    "fee": "Fee",
    "dealing_club": "Dealing_Club",
    "league_name": "League",
    "club__name": "Club",
}

_TRANSFERS_REQUIRED_COLUMNS = [
    "Player",
    "Year",
    "Position",
    "Age",
    "Fee",
    "Dealing_Club",
    "Club",
    "League",
    "is_loan",
]


def build_transfers_df() -> pd.DataFrame:
    """One row per Transfer, columns renamed to impact_model_v4.1.py's literals."""
    fields = [
        "player_name_raw",
        "year",
        "position",
        "age_at_transfer",
        "fee",
        "dealing_club",
        "league_name",
        "is_loan",
    ]
    qs = Transfer.objects.values(*fields, "club__name")
    df = pd.DataFrame.from_records(list(qs))
    df = df.rename(columns=_TRANSFER_RENAME)

    assert_columns_present(df, _TRANSFERS_REQUIRED_COLUMNS, "build_transfers_df")
    return df
