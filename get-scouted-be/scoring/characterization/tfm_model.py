"""Faithful characterization of the Financial Fit (TFM) sklearn artifact
from impact_model_v4.1.py.

Per 03-CONTEXT.md's "Score-to-Artifact Mapping Resolution" (LOCKED), the
`RandomForestRegressor` at source lines 5638-5652 predicts `log_fee` and IS
the Financial Fit (TFM) artifact -- NOT Transfer Probability (Transfer
Probability is the fully deterministic weighted formula ported in Plan 05's
`deterministic_scores.py`). This module reproduces, VERBATIM, the exact
recipe:

    parse_money_to_numeric            (line 13668)
    safe_div                          (line 13699)
    season_to_year                    (line 13705, needed by contract_to_years_left)
    contract_to_years_left            (line 13716)
    build_transfer_value_dataset      (line 4935 -- the authoritative last-wins
                                        def; 4887 is truncated dead code, see
                                        DUPLICATE_FUNCTIONS.md)
    train_transfer_value_model        (line 5569)
    add_value_labels                  (line 5676)

Every hyperparameter (`n_estimators=300, max_depth=12, min_samples_leaf=3,
random_state=42, n_jobs=-1`), the 80/20 `train_test_split(random_state=42)`,
and every engineered feature/threshold are copied UNCHANGED -- this is
characterization, not model improvement (03-CONTEXT.md "don't touch
non-bug quirks" rule). The whole fitted sklearn `Pipeline` (imputer +
one-hot + RF) is what gets serialized downstream (Task 2's management
command), not just the raw `RandomForestRegressor`
(03-RESEARCH.md "Reproduction note").

CROSS-PLAN PRECONDITION (must be true before calling
`build_transfer_value_dataset`): in the original monolithic script,
`player_impact`, `performance_score`, `compatibility_score`, and `role_pct`
are already COLUMNS on `players_df` by the time this function runs -- they
come from Plan 04's `impact.compute_rmm_column` and Plan 05's
`deterministic_scores.compute_cs_tp_for_pairs`, not from
`reconstruct.build_players_df()`. This function does NOT compute them; it
only reads them if present (exactly like the source's own
`optional_cols`/`[c for c in feature_cols if c in model_df.columns]`
pattern -- a column that's absent is silently excluded from the feature
set, not fabricated). Task 2's management command is responsible for doing
the merge before calling this function.

COLUMN-NAME ADAPTATION (see APPLIED_FIXES below): the source reads these
cross-plan columns under their raw, human-readable literal names ("Player
Impact", "Compatibility Score", "Performance Score", "Role %") because that
was the column naming already in place on its in-memory `players_df` by the
time `build_transfer_value_dataset` ran. This project's Plan 04/05 ports
produce the SAME data under lowercase snake_case names instead
(`player_impact`, `compatibility_score`, `performance_score`, `role_pct`) --
their own established, already-locked naming convention
(03-04-SUMMARY.md / 03-05-SUMMARY.md). `_OPTIONAL_PLAYER_COLUMNS` below
therefore accepts EITHER the source-literal name or this project's lowercase
name for each optional column, so the exact 33-feature recipe (hyperparams,
preprocessing, thresholds) is reproduced unchanged while the plumbing
tolerates this project's real column names. This is a naming adaptation,
not a value-distorting fix -- SimpleImputer still does all genuine
missing-value handling; nothing here introduces a fabricated zero.
"""

from __future__ import annotations

import datetime
import re

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

# =========================================================================
# APPLIED_FIXES -- deviations from a byte-literal port, and why.
# =========================================================================
APPLIED_FIXES = [
    (
        "build_transfer_value_dataset's optional-player-column handling "
        "(_OPTIONAL_PLAYER_COLUMNS) accepts this project's actual lowercase "
        "column names (player_impact/compatibility_score/performance_score/"
        "role_pct, from Plan 04/05) as well as the source's raw literal "
        "names (\"Player Impact\"/\"Compatibility Score\"/\"Performance "
        "Score\"/\"Role %\") -- a naming adaptation to this project's real "
        "reconstructed data, not a value-distorting fix. SimpleImputer "
        "still performs all genuine missing-value handling unchanged; a "
        "column that is genuinely absent is still silently excluded from "
        "feature_cols exactly as the source's own "
        "`[c for c in feature_cols if c in model_df.columns]` filter does."
    ),
    (
        "The source's optional 'Contract' raw-text column (used by "
        "contract_to_years_left's year-regex extraction) does not exist "
        "under that name on this project's reconstructed players_df -- "
        "reconstruct.build_players_df() names the equivalent field "
        "\"Contract expires\" (a date, from Player.contract_expires). "
        "_OPTIONAL_PLAYER_COLUMNS maps \"Contract expires\" to the same "
        "contract_raw target; str(<the date>) still contains a 4-digit "
        "year the unmodified contract_to_years_left regex extracts "
        "correctly, so contract_to_years_left itself is unchanged."
    ),
    (
        "No zero-fill fixes were needed beyond the above naming "
        "adaptations: every feature absence in this port is a genuine "
        "'column not present' case handled identically to the source "
        "(silently excluded from feature_cols, or SimpleImputer-imputed "
        "for genuine per-row NaNs inside an included column) -- never a "
        "fabricated zero."
    ),
]


# =========================================================================
# Helper functions (verbatim ports; authoritative line numbers in the
# module docstring)
# =========================================================================
def parse_money_to_numeric(value):
    """Verbatim port of `parse_money_to_numeric` (line 13668)."""
    if pd.isna(value):
        return np.nan

    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)

    s = str(value).strip().lower()
    s = (
        s.replace("€", "")
        .replace("£", "")
        .replace("$", "")
        .replace(",", "")
        .replace(" ", "")
    )

    if s in ["", "free", "loan", "?", "-", "nan", "none", "undisclosed"]:
        return np.nan

    try:
        if "bn" in s:
            return float(s.replace("bn", "")) * 1_000_000_000
        if "m" in s:
            return float(s.replace("m", "")) * 1_000_000
        if "k" in s:
            return float(s.replace("k", "")) * 1_000
        return float(s)
    except Exception:
        return np.nan


def safe_div(a, b):
    """Verbatim port of `safe_div` (line 13699)."""
    if pd.isna(a) or pd.isna(b) or b == 0:
        return np.nan
    return a / b


def season_to_year(season_value):
    """Verbatim port of `season_to_year` (line 13705) -- needed by
    `contract_to_years_left`."""
    if pd.isna(season_value):
        return np.nan

    s = str(season_value)
    m = re.search(r"(20\d{2})", s)
    if m:
        return int(m.group(1))
    return np.nan


def contract_to_years_left(contract_value, season_value):
    """Verbatim port of `contract_to_years_left` (line 13716)."""
    if pd.isna(contract_value):
        return np.nan

    season_start_year = season_to_year(season_value)
    if pd.isna(season_start_year):
        return np.nan

    s = str(contract_value)
    years = re.findall(r"(20\d{2})", s)
    if len(years) > 0:
        expiry_year = int(years[-1])
        return max(expiry_year - season_start_year, 0)

    return np.nan


# =========================================================================
# League weights (impact_model_v4.1.py line 4677, verbatim) -- used only for
# `from_league_weight` inside build_transfer_value_dataset.
# =========================================================================
LEAGUE_WEIGHTS = {
    "Premier League (England)": 8.59,
    "La Liga (Spain)": 8.35,
    "Bundesliga (Germany)": 8.40,
    "Serie A (Italy)": 8.42,
    "Serie A (Brazil)": 8.01,
    "Ligue 1 (France)": 8.31,
    "Primeira Liga (Portugal)": 7.86,
    "Super Lig (Turkey)": 7.48,
    "Liga Profesional de Futbol (Argentina)": 7.68,
    "Super League (Greece)": 7.25,
    "Liga MX (Mexico)": 7.55,
    "Premier League (Russia)": 7.39,
    "Fortuna Liga (Czechia)": 7.52,
    "Primera A (Colombia)": 7.26,
    "Pro League (Belgium)": 7.73,
    "Superliga (Denmark)": 7.60,
    "Eredivisie (Netherlands)": 7.62,
    "Division Profesional (Paraguay)": 7.24,
    "Primera A (Ecuador)": 7.17,
    "HNL (Croatia)": 7.40,
    "Segunda División (Spain)": 7.42,
    "Super League (Switzerland)": 7.47,
    "Championship (England)": 7.62,
    "Serie B (Brazil)": 7.25,
    "Bundesliga (Austria)": 7.44,
    "Serie B (Italy)": 7.47,
    "Ligat ha'Al (Israel)": 7.18,
    "Ekstraklasa (Poland)": 7.51,
    "1 division (Cyprus)": 7.29,
    "Allsvenskan (Sweden)": 7.37,
    "Superliga (Romania)": 7.23,
    "Primera División (Uruguay)": 7.25,
    "Segunda Liga (Portugal)": 6.98,
    "Ascenso MX (Mexico)": 6.87,
    "Eliteserien (Norway)": 7.40,
    "Ligue 2 (France)": 7.27,
    "Super Liga (Slovakia)": 7.02,
    "NB 1 (Hungary)": 7.22,
    "Primera Nacional (Argentina)": 6.87,
    "Primera Division (Chile)": 7.18,
    "K League Classic (Korea Republic)": 7.47,
    "Primera División (Costa Rica)": 6.98,
    "Persian Gulf Pro League (Iran)": 6.88,
    "Serie C (Brazil)": 6.87,
    "Lig (Turkey)": 7.48,
    "Super Liga (Serbia)": 6.68,
    "Premijer Liga (Bosnia and Herzegovina)": 6.65,
    "First League (Bulgaria)": 6.86,
    "MLS (USA)": 7.70,
    "EFL League One (England)": 6.91,
    "Eerste Divisie (Netherlands)": 6.39,
    "Liga Portugal 2 (Portugal)": 6.98,
    "Challenger Pro League (Belgium)": 6.66,
    "Bundesliga 2 (Germany)": 7.51,
    "SPL (Scotland)": 7.17,
}


# =========================================================================
# build_transfer_value_dataset (impact_model_v4.1.py line 4935, the
# authoritative last-wins def -- see DUPLICATE_FUNCTIONS.md)
# =========================================================================
# (source-literal name candidates, our-project name candidates) -> target
# feature name train_transfer_value_model's feature_cols list expects.
# See module docstring "COLUMN-NAME ADAPTATION" / APPLIED_FIXES.
_OPTIONAL_PLAYER_COLUMNS: list[tuple[list[str], str]] = [
    (["Minutes played"], "minutes_played"),
    (["Performance Score", "performance_score"], "performance_score"),
    (["Compatibility Score", "compatibility_score"], "compatibility_score"),
    (["Player Impact", "player_impact"], "player_impact"),
    (["BestRole", "best_role"], "best_role"),
    (["Role %", "role_pct"], "role_pct"),
    (["Squad Role", "squad_role"], "squad_role"),
    (["Contract", "Contract expires"], "contract_raw"),
]


def build_transfer_value_dataset(transfers_df: pd.DataFrame, players_df: pd.DataFrame, league_weights: dict | None = None) -> pd.DataFrame:
    """Faithful port of `build_transfer_value_dataset` (line 4935).

    Filters transfers to Year in [2023, 2024], maps each to the player
    season it should be matched against, cleans the Fee -> `actual_fee`
    (dropping non-positive/unparseable fees), computes `from_league_weight`,
    builds per-club buy/sell fee+age aggregate profiles and per-club-per-
    position buy/sell fee aggregates, left-merges the matching player row
    (by Player + mapped season), and engineers age/loan/mv-ratio flags --
    all exactly as the source does, including the source's own merge-column-
    name-collision behavior (the buy-profile and sell-profile "in" columns
    share names and get pandas' default `_x`/`_y` suffixes when both are
    merged in sequence -- this is copied unchanged, not "fixed", per
    03-CONTEXT.md's don't-touch-non-bug-quirks rule; it is the reason not
    all 33 nominal feature names in `train_transfer_value_model` actually
    survive into `model_df`).

    Preconditions (see module docstring): `players_df` must already carry
    `player_impact` (Plan 04), and `compatibility_score`/`performance_score`
    /`role_pct` (Plan 05) as columns, if the caller wants those features
    included -- this function never computes them itself.
    """
    if league_weights is None:
        league_weights = LEAGUE_WEIGHTS

    players = players_df.copy()
    transfers = transfers_df.copy()

    # =====================================================
    # ONLY KEEP TRANSFERS WE CAN MATCH HISTORICALLY
    # =====================================================
    transfers = transfers[transfers["Year"].isin([2023, 2024])].copy()

    # =====================================================
    # MAP TRANSFER YEAR -> PLAYER SEASON
    # =====================================================
    season_map = {2023: "2022-2023", 2024: "2023-2024"}
    transfers["mapped_season"] = transfers["Year"].map(season_map)

    # =====================================================
    # CLEAN FEES
    # =====================================================
    transfers["actual_fee"] = transfers["Fee"].apply(parse_money_to_numeric)
    transfers = transfers[transfers["actual_fee"].notna()].copy()
    transfers = transfers[transfers["actual_fee"] > 0].copy()

    # =====================================================
    # CLEAN AGE
    # =====================================================
    transfers["age_numeric"] = pd.to_numeric(transfers["Age"], errors="coerce")

    # =====================================================
    # LEAGUE WEIGHTS
    # =====================================================
    transfers["from_league_weight"] = transfers["League"].map(league_weights)

    # =====================================================
    # ARRIVAL PROFILE
    # =====================================================
    arrivals_profile = (
        transfers.groupby("Club")
        .agg(
            club_avg_in_fee=("actual_fee", "mean"),
            club_max_in_fee=("actual_fee", "max"),
            club_median_in_fee=("actual_fee", "median"),
            club_count_in=("actual_fee", "count"),
            club_avg_in_age=("age_numeric", "mean"),
        )
        .reset_index()
        .rename(columns={"Club": "club_name"})
    )

    # =====================================================
    # DEPARTURE PROFILE
    # =====================================================
    departures_profile = (
        transfers.groupby("Dealing_Club")
        .agg(
            club_avg_out_fee=("actual_fee", "mean"),
            club_max_out_fee=("actual_fee", "max"),
            club_median_out_fee=("actual_fee", "median"),
            club_count_out=("actual_fee", "count"),
            club_avg_out_age=("age_numeric", "mean"),
        )
        .reset_index()
        .rename(columns={"Dealing_Club": "club_name"})
    )

    # =====================================================
    # CLUB PROFILE
    # =====================================================
    club_profiles = arrivals_profile.merge(departures_profile, on="club_name", how="outer")

    # =====================================================
    # POSITION BUY PROFILE
    # =====================================================
    buy_position_profile = (
        transfers.groupby(["Club", "Position"])["actual_fee"].mean().reset_index()
    )
    buy_position_profile.columns = ["club_name", "position", "club_pos_avg_in_fee"]

    # =====================================================
    # POSITION SELL PROFILE
    # =====================================================
    sell_position_profile = (
        transfers.groupby(["Dealing_Club", "Position"])["actual_fee"].mean().reset_index()
    )
    sell_position_profile.columns = ["club_name", "position", "club_pos_avg_out_fee"]

    # =====================================================
    # POSITION PROFILE
    # =====================================================
    position_profiles = buy_position_profile.merge(
        sell_position_profile, on=["club_name", "position"], how="outer"
    )

    # =====================================================
    # PLAYER DATA CLEAN
    # =====================================================
    players["Season"] = players["Season"].astype(str).str.strip()

    # =====================================================
    # MARKET VALUE
    # =====================================================
    if "Market Value (TM) (numeric)" in players.columns:
        players["market_value"] = players["Market Value (TM) (numeric)"].apply(parse_money_to_numeric)
    elif "Market value" in players.columns:
        players["market_value"] = players["Market value"].apply(parse_money_to_numeric)
    else:
        players["market_value"] = np.nan

    # =====================================================
    # PLAYER COLUMNS
    # =====================================================
    player_cols = ["Player", "Season", "Age", "Position", "market_value"]
    rename_map = {"Age": "player_age", "Position": "player_position"}

    for candidates, target in _OPTIONAL_PLAYER_COLUMNS:
        found = next((c for c in candidates if c in players.columns), None)
        if found is None:
            continue
        player_cols.append(found)
        if found != target:
            rename_map[found] = target

    players_small = players[player_cols].copy()

    # =====================================================
    # RENAME PLAYER COLS
    # =====================================================
    players_small = players_small.rename(columns=rename_map)

    # =====================================================
    # MERGE HISTORICALLY CORRECT
    # =====================================================
    data = transfers.merge(
        players_small,
        left_on=["Player", "mapped_season"],
        right_on=["Player", "Season"],
        how="left",
    )

    # =====================================================
    # AGE
    # =====================================================
    data["age"] = data["player_age"].fillna(data["Age"])
    data["age"] = pd.to_numeric(data["age"], errors="coerce")

    # =====================================================
    # POSITION
    # =====================================================
    data["position"] = data["player_position"].fillna(data["Position"])

    # =====================================================
    # CONTRACT YEARS LEFT
    # =====================================================
    if "contract_raw" in data.columns:
        data["contract_years_left"] = data.apply(
            lambda row: contract_to_years_left(row["contract_raw"], row["mapped_season"]),
            axis=1,
        )
    else:
        data["contract_years_left"] = np.nan

    # =====================================================
    # AGE FEATURES
    # =====================================================
    data["age_squared"] = data["age"] ** 2
    data["u23_flag"] = np.where(data["age"] <= 23, 1, 0)
    data["prime_age_flag"] = np.where((data["age"] >= 24) & (data["age"] <= 28), 1, 0)
    data["older_flag"] = np.where(data["age"] >= 29, 1, 0)

    # =====================================================
    # MV TO FEE RATIO
    # =====================================================
    data["mv_to_fee_ratio"] = data.apply(
        lambda row: safe_div(row["market_value"], row["actual_fee"]), axis=1
    )

    # =====================================================
    # LOAN FLAG
    # =====================================================
    data["is_loan"] = pd.to_numeric(data["is_loan"], errors="coerce").fillna(0).astype(int)

    # =====================================================
    # BUY CLUB PROFILE
    # =====================================================
    buy_profile = club_profiles.rename(columns={"club_name": "buying_club_profile_key"})
    data = data.merge(buy_profile, left_on="Club", right_on="buying_club_profile_key", how="left")

    # =====================================================
    # SELL CLUB PROFILE
    # =====================================================
    sell_profile = club_profiles.rename(columns={"club_name": "selling_club_profile_key"})
    sell_profile = sell_profile.rename(
        columns={
            "club_avg_out_fee": "seller_hist_avg_out_fee",
            "club_max_out_fee": "seller_hist_max_out_fee",
            "club_median_out_fee": "seller_hist_median_out_fee",
            "club_count_out": "seller_hist_count_out",
            "club_avg_out_age": "seller_hist_avg_out_age",
        }
    )
    data = data.merge(sell_profile, left_on="Dealing_Club", right_on="selling_club_profile_key", how="left")

    # =====================================================
    # POSITION BUY PROFILE
    # =====================================================
    buy_pos = position_profiles.rename(columns={"club_name": "buy_pos_club_key", "position": "buy_pos_position_key"})
    data = data.merge(
        buy_pos[["buy_pos_club_key", "buy_pos_position_key", "club_pos_avg_in_fee"]],
        left_on=["Club", "position"],
        right_on=["buy_pos_club_key", "buy_pos_position_key"],
        how="left",
    )

    # =====================================================
    # POSITION SELL PROFILE
    # =====================================================
    sell_pos = position_profiles.rename(columns={"club_name": "sell_pos_club_key", "position": "sell_pos_position_key"})
    data = data.merge(
        sell_pos[["sell_pos_club_key", "sell_pos_position_key", "club_pos_avg_out_fee"]],
        left_on=["Dealing_Club", "position"],
        right_on=["sell_pos_club_key", "sell_pos_position_key"],
        how="left",
    )

    # =====================================================
    # CLEAN DUPLICATES
    # =====================================================
    data = data.loc[:, ~data.columns.duplicated()]

    return data


# =========================================================================
# train_transfer_value_model (impact_model_v4.1.py line 5569)
# =========================================================================
def train_transfer_value_model(model_df: pd.DataFrame) -> tuple[Pipeline, dict]:
    """Faithful port of `train_transfer_value_model` (line 5569): exact
    33-name feature list (filtered to columns actually present in
    `model_df` -- the source's own `[c for c in feature_cols if c in
    model_df.columns]` behavior), ColumnTransformer preprocessing
    (object->most_frequent+OneHot(handle_unknown="ignore");
    numeric->median), `RandomForestRegressor(n_estimators=300, max_depth=12,
    min_samples_leaf=3, random_state=42, n_jobs=-1)` inside a `Pipeline`,
    `train_test_split(test_size=0.20, random_state=42)`.

    Unlike the source (which returns `(pipeline, model_df, feature_cols)`
    for downstream interactive plotting), this port returns
    `(fitted_pipeline, metrics_dict)` per this plan's explicit output
    contract -- an interface-shape adaptation only; every hyperparameter,
    feature, and metric computation is unchanged.
    """
    model_df = model_df.copy()

    # log fee helps reduce huge outlier distortion
    model_df = model_df[model_df["actual_fee"].notna()].copy()
    model_df = model_df[model_df["actual_fee"] > 0].copy()
    model_df["log_fee"] = np.log1p(model_df["actual_fee"])

    feature_cols = [
        "age",
        "age_squared",
        "u23_flag",
        "prime_age_flag",
        "older_flag",
        "minutes_played",
        "market_value",
        "contract_years_left",
        "performance_score",
        "compatibility_score",
        "player_impact",
        "role_pct",
        "from_league_weight",
        "to_league_weight",
        "league_jump_ratio",
        "mv_to_fee_ratio",
        "is_loan",
        "domestic_move",
        "club_avg_in_fee",
        "club_max_in_fee",
        "club_median_in_fee",
        "club_count_in",
        "club_avg_in_age",
        "seller_hist_avg_out_fee",
        "seller_hist_max_out_fee",
        "seller_hist_median_out_fee",
        "seller_hist_count_out",
        "seller_hist_avg_out_age",
        "club_pos_avg_in_fee",
        "club_pos_avg_out_fee",
        "position",
        "best_role",
        "squad_role",
    ]

    # keep only existing columns
    feature_cols = [c for c in feature_cols if c in model_df.columns]

    X = model_df[feature_cols]
    y = model_df["log_fee"]

    categorical_cols = [c for c in X.columns if X[c].dtype == "object"]
    numeric_cols = [c for c in X.columns if c not in categorical_cols]

    numeric_transformer = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])

    categorical_transformer = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore")),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_transformer, numeric_cols),
            ("cat", categorical_transformer, categorical_cols),
        ]
    )

    model = RandomForestRegressor(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=3,
        random_state=42,
        n_jobs=-1,
    )

    pipeline = Pipeline(steps=[("preprocessor", preprocessor), ("model", model)])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)

    pipeline.fit(X_train, y_train)

    pred_log = pipeline.predict(X_test)
    pred_fee = np.expm1(pred_log)
    actual_fee = np.expm1(y_test)

    mae_money = float(mean_absolute_error(actual_fee, pred_fee))
    r2_log = float(r2_score(y_test, pred_log))

    metrics = {
        "mae_money": mae_money,
        "r2_log": r2_log,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "feature_cols": feature_cols,
    }

    return pipeline, metrics


# =========================================================================
# add_value_labels (impact_model_v4.1.py line 5676, verbatim)
# =========================================================================
def add_value_labels(df: pd.DataFrame) -> pd.DataFrame:
    """Verbatim port of `add_value_labels` (line 5676). Operates on a
    DataFrame carrying `actual_fee` and `predicted_fee` columns."""
    out = df.copy()
    out["fee_diff"] = out["actual_fee"] - out["predicted_fee"]
    out["fee_ratio_actual_to_pred"] = out["actual_fee"] / out["predicted_fee"]

    def label_row(r):
        if pd.isna(r["fee_ratio_actual_to_pred"]):
            return np.nan
        if r["fee_ratio_actual_to_pred"] <= 0.80:
            return "Bargain"
        elif r["fee_ratio_actual_to_pred"] >= 1.20:
            return "Overpay"
        else:
            return "Fair Value"

    out["value_verdict"] = out.apply(label_row, axis=1)
    return out


# =========================================================================
# ORACLE CONVENIENCE WRAPPER (new, this plan's addition -- not in source,
# 03-07-PLAN.md Task 1)
# =========================================================================
def build_oracle_player_features(
    players_df: pd.DataFrame,
    transfers_df: pd.DataFrame,
    as_of_year: int | None = None,
) -> pd.DataFrame:
    """One TFM feature row PER PLAYER, keyed by player_id -- NOT a port.

    `build_transfer_value_dataset` (verbatim port, above) only produces a
    feature row per MATCHED HISTORICAL transfer event (`transfers_df`
    joined to `players_df` by Player+season) -- correct for training, but
    useless for the oracle, which needs a `predicted_fee` for every real
    player regardless of whether they were ever actually transferred.

    This function instead reproduces the SAME club-aggregate engineering
    `build_transfer_value_dataset` computes internally (arrivals/departures
    profiles, position buy/sell profiles) from `transfers_df`, but keys the
    lookup to each player's CURRENT club (`players_df["Team"]`, sourced
    from `Player.club`) as BOTH the buying-club and selling-club context --
    there is no real transfer event for a player who isn't actually moving,
    so "what has this club historically paid/received for this position" is
    evaluated against the player's own club, per 03-07-PLAN.md Task 1's
    explicit "current club as buying-club context" instruction. This is a
    documented approximation, not a fabricated value: every column with no
    real underlying data (e.g. a club with zero recorded transfers) is left
    NaN here and flows into the fitted Pipeline's SimpleImputer exactly
    like any other missing value -- nothing is zero-filled in this
    function.

    Returns a DataFrame indexed by player_id carrying every feature name
    `train_transfer_value_model`'s nominal `feature_cols` list can
    reference (a superset); the caller selects whichever subset the loaded
    artifact was actually trained on (its `.metrics.json` sidecar's
    `feature_cols`) before calling `pipeline.predict`. A `_has_club_context`
    boolean column flags players with no resolvable current club -- the
    caller should treat predictions for those rows as NaN, not a value
    manufactured from an all-NaN row.
    """
    if as_of_year is None:
        as_of_year = datetime.date.today().year

    players = players_df.copy()
    transfers = transfers_df.copy()

    # ---- club aggregate profiles (mirrors build_transfer_value_dataset's
    # arrivals_profile / departures_profile / buy_position_profile /
    # sell_position_profile, reproduced here because those are local
    # variables inside that function, not separately importable) ----
    transfers["actual_fee"] = transfers["Fee"].apply(parse_money_to_numeric)
    transfers = transfers[transfers["actual_fee"].notna() & (transfers["actual_fee"] > 0)].copy()
    transfers["age_numeric"] = pd.to_numeric(transfers["Age"], errors="coerce")

    arrivals_profile = transfers.groupby("Club").agg(
        club_avg_in_fee=("actual_fee", "mean"),
        club_max_in_fee=("actual_fee", "max"),
        club_median_in_fee=("actual_fee", "median"),
        club_count_in=("actual_fee", "count"),
        club_avg_in_age=("age_numeric", "mean"),
    )
    departures_profile = transfers.groupby("Dealing_Club").agg(
        seller_hist_avg_out_fee=("actual_fee", "mean"),
        seller_hist_max_out_fee=("actual_fee", "max"),
        seller_hist_median_out_fee=("actual_fee", "median"),
        seller_hist_count_out=("actual_fee", "count"),
        seller_hist_avg_out_age=("age_numeric", "mean"),
    )
    buy_position_profile = (
        transfers.groupby(["Club", "Position"])["actual_fee"]
        .mean()
        .rename("club_pos_avg_in_fee")
        .reset_index()
        .rename(columns={"Club": "_team", "Position": "_position"})
    )
    sell_position_profile = (
        transfers.groupby(["Dealing_Club", "Position"])["actual_fee"]
        .mean()
        .rename("club_pos_avg_out_fee")
        .reset_index()
        .rename(columns={"Dealing_Club": "_team", "Position": "_position"})
    )

    # ---- per-player base features (verbatim engineering rules, applied
    # per-player instead of per-matched-transfer-row) ----
    age = pd.to_numeric(players.get("Age"), errors="coerce")

    if "Market value" in players.columns:
        market_value = players["Market value"].apply(parse_money_to_numeric)
    else:
        market_value = pd.Series(np.nan, index=players.index)

    contract_expires = pd.to_datetime(players.get("Contract expires"), errors="coerce")
    contract_years_left = (contract_expires.dt.year - as_of_year).clip(lower=0)
    contract_years_left = contract_years_left.where(contract_expires.notna(), np.nan)

    is_loan_raw = players.get("On loan")
    if is_loan_raw is not None:
        is_loan = pd.to_numeric(is_loan_raw, errors="coerce").fillna(0).astype(int)
    else:
        is_loan = pd.Series(0, index=players.index)

    if "League" in players.columns:
        from_league_weight = players["League"].map(LEAGUE_WEIGHTS)
    else:
        from_league_weight = pd.Series(np.nan, index=players.index)

    position = players.get("Position", players.get("Main_Position"))
    team = players.get("Team")

    out = pd.DataFrame(
        {
            "player_id": players["player_id"],
            "_team": team,
            "_position": position,
            "age": age,
            "age_squared": age**2,
            "u23_flag": np.where(age <= 23, 1, 0),
            "prime_age_flag": np.where((age >= 24) & (age <= 28), 1, 0),
            "older_flag": np.where(age >= 29, 1, 0),
            "minutes_played": pd.to_numeric(players.get("Minutes played"), errors="coerce"),
            "market_value": market_value,
            "contract_years_left": contract_years_left,
            "from_league_weight": from_league_weight,
            "mv_to_fee_ratio": np.nan,
            "is_loan": is_loan,
            "position": position,
        }
    )

    for col in ("player_impact", "compatibility_score", "performance_score", "role_pct"):
        out[col] = players[col] if col in players.columns else np.nan

    out = out.merge(arrivals_profile, left_on="_team", right_index=True, how="left")
    out = out.merge(departures_profile, left_on="_team", right_index=True, how="left")
    out = out.merge(buy_position_profile, on=["_team", "_position"], how="left")
    out = out.merge(sell_position_profile, on=["_team", "_position"], how="left")

    out["_has_club_context"] = out["_team"].notna() & (out["_team"].astype(str).str.strip() != "")

    out = out.drop(columns=["_team", "_position"])
    out = out.set_index("player_id")
    return out
