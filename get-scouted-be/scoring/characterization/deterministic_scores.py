"""RESOLVED MAPPING (03-CONTEXT.md "Score-to-Artifact Mapping Resolution",
2026-07-21): Transfer Probability is a fully DETERMINISTIC, non-ML weighted
formula (`pixel-perfect-clone-60729/docs/impact_model_v4.1.py` lines
3809-3814, inside `external_target_shortlist_absolute_vectorized`
def@3275) -- NO sklearn, no trained artifact, trivially reproducible from
Compatibility Score + Performance Score + Financial Score + contract_fit.
The `RandomForestRegressor` elsewhere in the source (lines ~5638-5652) is the
**Financial Fit (TFM)** artifact (Plan 06's concern), not this. This module
implements the deterministic arithmetic only.

  This module imports NO scikit-learn. (grep-verifiable: this file contains
  no sklearn import statement of any kind.)

Ported, faithfully, from impact_model_v4.1.py:

    classify_fit ................................. line 1029-1037
    _fit_to_score / _avg_non_null / _clip_score .. local closures, line ~3315-3333
    classify_age_fit .............................. line 2698-2721
    "Performance Score" ........................... line 3790-3796
    "Compatibility Score" ......................... line 3798-3802 (role_fit.py)
    "Financial Score" .............................. line 3804-3807
    "Transfer Probability %" (tp) .................. line 3809-3814, round@3840
    contract_fit banding ........................... line 3734-3741

`compute_cs_tp_for_pairs` is new (not in the source) -- it is this project's
cross-plan wiring contract: the per-player-vs-club-context CS/Financial/
Performance/contract_fit/role_pct/Transfer-Probability recipe that Plan 06's
`build_transfer_value_dataset` feature set and Plan 07's oracle both merge
onto `players_df`.

Scope notes (what this plan does NOT port, and why):
  - Similarity To Target Player % (the player-to-target-player cosine-
    similarity term inside Compatibility Score) requires the full
    `calculate_player_to_team_player_similarity` + target-team-players-pool
    machinery, which is not in this plan's scope (03-05-PLAN.md read_first).
    `compute_cs_tp_for_pairs` always passes `similarity_pct=NaN` into
    `compatibility_score`, which correctly excludes it from the non-null
    average rather than fabricating a value.
  - Performance Score's "team/target percentile" terms (Perf vs Team %, Perf
    vs Own League %, Perf vs TargetLeague %, Impact Delta vs Team Avg)
    require `external_target_shortlist_absolute_vectorized`'s league-wide
    POSITION_METRICS percentile machinery, out of this plan's scope. Player
    Impact (RMM, Plan 04's `compute_rmm_column`) is the one REQUIRED,
    explicitly-wired anchor term; the percentile terms are accepted as
    optional keyword args (NaN by default) so a later phase can wire them in
    without changing this function's contract.
  - Financial Score's `avg_age`/`avg_mv` baseline: the source computes these
    from a club's TRANSFER-ARRIVAL history (`club_transfer_profile`, needs
    `transfers_df`). This plan's `compute_cs_tp_for_pairs` signature
    (03-05-PLAN.md interfaces block) does not take `transfers_df`, so this
    port instead baselines age/market-value fit against the target club's
    CURRENT squad (from `players_df`) -- a documented adaptation, not a
    silent substitution. `financial_score()` itself (the pure 2-term
    average) is unchanged from the source.
"""

from __future__ import annotations

import datetime
import logging

import numpy as np
import pandas as pd

from scoring.characterization.reconstruct import assert_columns_present
from scoring.characterization.role_fit import (
    _avg_non_null,
    _clip_score,
    calculate_subjective_role_fit_for_player_to_team,
    compatibility_score,
    get_player_own_best_role,
    normalise_position,
)

logger = logging.getLogger(__name__)

APPLIED_FIXES = [
    (
        "compute_cs_tp_for_pairs's Financial Score baseline (avg_age/avg_mv) "
        "uses the target club's CURRENT squad (players_df grouped by Team), "
        "not the source's transfer-ARRIVALS history (club_transfer_profile), "
        "because this plan's compute_cs_tp_for_pairs signature (03-05-PLAN.md) "
        "does not take transfers_df. financial_score() itself -- the pure "
        "_avg_non_null([_fit_to_score(age_fit), _fit_to_score(mv_fit)]) "
        "assembly -- is an exact port; only the age/mv baseline source differs."
    ),
]


# =========================================================================
# Small pure helpers (verbatim ports of source-local closures/functions)
# =========================================================================
def _fit_to_score(label: str) -> float:
    """Verbatim port of the local `_fit_to_score` closure (line 3327)."""
    return {
        "Great Fit": 100.0,
        "Moderate Fit": 60.0,
        "Poor Fit": 20.0,
        "Unknown": np.nan,
    }.get(label, np.nan)


def classify_fit(value: float, avg: float, tol_great: float, tol_moderate: float) -> str:
    """Verbatim port of `classify_fit` (line 1029)."""
    if pd.isna(value) or pd.isna(avg):
        return "Unknown"
    diff = abs(value - avg)
    if diff <= tol_great:
        return "Great Fit"
    elif diff <= tol_moderate:
        return "Moderate Fit"
    return "Poor Fit"


def classify_age_fit(player_age: float, avg_age: float) -> str:
    """Verbatim port of `classify_age_fit` (line 2698)."""
    if pd.isna(player_age) or pd.isna(avg_age):
        return "Unknown"

    diff = player_age - avg_age

    if diff < 0:
        if abs(diff) <= 3:
            return "Great Fit"
        elif abs(diff) <= 5:
            return "Moderate Fit"
        else:
            return "Poor Fit"
    else:
        if diff <= 2:
            return "Great Fit"
        elif diff <= 4:
            return "Moderate Fit"
        else:
            return "Poor Fit"


# =========================================================================
# Financial Score (impact_model_v4.1.py line 3804-3807)
# =========================================================================
def financial_score(age_fit_label: str, mv_fit_label: str) -> float:
    """Faithful port of the "Financial Score" assembly (line 3804-3807):

        financial_score = _avg_non_null([
            _fit_to_score(age_fit), _fit_to_score(mv_fit),
        ])

    `age_fit_label`/`mv_fit_label` are the "Great Fit"/"Moderate Fit"/
    "Poor Fit"/"Unknown" labels from `classify_age_fit`/`classify_fit` --
    this is the "cheap deterministic TFM candidate" 03-CONTEXT.md and
    03-RESEARCH.md flag; its ML sibling (RandomForestRegressor -> log_fee) is
    the actual TFM artifact ported in Plan 06.
    """
    return _avg_non_null([_fit_to_score(age_fit_label), _fit_to_score(mv_fit_label)])


# =========================================================================
# Performance Score (impact_model_v4.1.py line 3790-3796)
# =========================================================================
def performance_score(
    player_impact: float,
    perf_team_pct: float = np.nan,
    perf_target_pct: float = np.nan,
    perf_own_pct: float = np.nan,
    impact_delta_vs_team_avg: float = np.nan,
) -> float:
    """Faithful port of the "Performance Score" blend (line 3790-3796):

        performance_score = _avg_non_null([
            clip(player_impact), clip(perf_team_pct), clip(perf_target_pct),
            clip(perf_own_pct),
            clip(50 + 2*impact_delta_vs_team_avg) if not NaN else NaN,
        ])

    `player_impact` is Plan 04's Player Impact (RMM) value
    (`impact.compute_rmm_column(players_df)`, one row per player_id) -- it is
    REQUIRED and is never recomputed here (03-05-PLAN.md's explicit
    cross-plan wiring). If `player_impact` is NaN, the entire performance
    score is NaN -- never silently zero-filled -- because RMM is the one
    anchor term this plan can always supply; without it there is nothing
    non-null left to average in the common case.

    The remaining four terms (perf_team_pct / perf_target_pct / perf_own_pct
    / impact_delta_vs_team_avg) require the league-wide POSITION_METRICS
    percentile machinery inside `external_target_shortlist_absolute_vectorized`
    (out of this plan's scope -- see module docstring). They default to NaN,
    which `_avg_non_null` correctly excludes rather than fabricating; callers
    (a later phase) may pass them in without changing this function's shape.
    """
    if pd.isna(player_impact):
        return np.nan

    return _avg_non_null(
        [
            _clip_score(player_impact),
            _clip_score(perf_team_pct),
            _clip_score(perf_target_pct),
            _clip_score(perf_own_pct),
            _clip_score(50 + (2 * impact_delta_vs_team_avg))
            if pd.notna(impact_delta_vs_team_avg)
            else np.nan,
        ]
    )


# =========================================================================
# contract_fit banding (impact_model_v4.1.py line 3734-3741)
# =========================================================================
def contract_fit(years_left: float) -> float:
    """Faithful port of the contract-expiry banding (line 3734-3741):

        contract_fit = 1.0 if yrs <= 1 else 0.7 if yrs == 2 else 0.4 if yrs == 3 else 0.1

    (Band boundaries, including the source's own quirk that an ALREADY
    EXPIRED contract -- yrs < 0 -- still lands in the yrs<=1 => 1.0 band, are
    copied verbatim -- not "fixed", per 03-CONTEXT.md's "don't touch
    non-bug quirks" rule.)

    `years_left=NaN` (unparseable/missing contract data) returns 0.5, matching
    the source's `except Exception: contract_fit = 0.5` fallback for the same
    case (line 3741) -- this is the source's OWN documented default for
    "unknown", not a zero-fill this port introduces.
    """
    if pd.isna(years_left):
        return 0.5
    if years_left <= 1:
        return 1.0
    elif years_left == 2:
        return 0.7
    elif years_left == 3:
        return 0.4
    else:
        return 0.1


def _years_left_from_contract_expires(contract_expires: object, as_of_year: int) -> float:
    """Helper (not in source): derive `years_left` from a "Contract expires"
    cell (a date/Timestamp/None/NaT) relative to `as_of_year`, matching the
    source's `pd.to_datetime(contract_raw, errors="coerce").year - cur`
    computation (line 3736-3737) without the season-string parsing the
    source did (this function's caller has no `season` argument -- see
    module docstring)."""
    exp = pd.to_datetime(contract_expires, errors="coerce")
    if pd.isna(exp):
        return np.nan
    return float(exp.year - as_of_year)


# =========================================================================
# Transfer Probability (impact_model_v4.1.py line 3809-3814, round@3840)
# =========================================================================
def transfer_probability(
    compatibility_score_value: float,
    performance_score_value: float,
    financial_score_value: float,
    contract_fit_value: float,
) -> float:
    """Faithful port of the deterministic Transfer Probability formula
    (line 3809-3814):

        tp = (
            0.30 * (compatibility_score / 100.0) +
            0.20 * (performance_score / 100.0) +
            0.20 * (financial_score / 100.0) +
            0.30 * contract_fit
        ) * 100

    then `round(float(tp), 1)` (line 3840). NO ML, no sklearn -- this is
    the RESOLVED deterministic mapping (module docstring). Standard
    float-NaN propagation means any NaN input (e.g. performance_score NaN
    because `player_impact` was NaN) makes the whole `tp` NaN -- never
    silently coerced to 0.
    """
    tp = (
        0.30 * (compatibility_score_value / 100.0)
        + 0.20 * (performance_score_value / 100.0)
        + 0.20 * (financial_score_value / 100.0)
        + 0.30 * contract_fit_value
    ) * 100
    return round(float(tp), 1)


# =========================================================================
# compute_cs_tp_for_pairs -- this plan's cross-plan wiring contract
# =========================================================================
_PLAYERS_REQUIRED = ["player_id", "Team", "Main_Position", "Position", "Age", "Market value", "Contract expires"]


def compute_cs_tp_for_pairs(
    players_df: pd.DataFrame,
    team_styles_df: pd.DataFrame,
    role_scores_wide: pd.DataFrame,
    club_context: str | None,
    player_impact: pd.Series,
    as_of_year: int | None = None,
) -> pd.DataFrame:
    """Per-player Compatibility Score / Financial Score / Performance Score /
    contract_fit / role_pct / Transfer Probability, keyed by player_id.

    Args:
        players_df: `reconstruct.build_players_df()` shape (script-literal
            column names).
        team_styles_df: `reconstruct.build_team_styles_df()` shape.
        role_scores_wide: `reconstruct.build_role_scores_wide()` shape.
        club_context: the target club NAME (must match a `team_styles_df`
            "Team" value) every player's CS/TP is computed against. If
            `None` (the default), each player is evaluated against their OWN
            current club (`players_df`'s "Team" column, sourced from
            `Player.club` FK per `reconstruct.build_players_df`) -- i.e.
            "how well does this player fit the club they're already at".
        player_impact: REQUIRED. `pd.Series` keyed by player_id -- the RMM
            output of Plan 04's `impact.compute_rmm_column(players_df)`.
            This is the explicit cross-plan wiring: Performance Score (20%
            of Transfer Probability) needs Player Impact, which is Plan 04's
            concern, so it MUST be supplied by the caller; it is never
            recomputed or zero-filled here. A player whose `player_impact`
            is NaN (or who is entirely absent from the series) yields NaN
            performance_score and NaN transfer_probability.
        as_of_year: the calendar year `contract_fit`'s years-left banding is
            computed relative to. Defaults to `datetime.date.today().year`
            when omitted (this function has no `season` argument, unlike the
            source's `external_target_shortlist_absolute_vectorized` --
            module docstring). Exposed mainly for deterministic testing.

    Returns:
        DataFrame indexed by player_id with columns: club_context,
        compatibility_score, financial_score, performance_score,
        contract_fit, role_pct, transfer_probability. `compatibility_score`
        / `performance_score` / `role_pct` are the exact upstream feature
        names Plan 06's `build_transfer_value_dataset` recipe and Plan 07's
        oracle merge back onto `players_df`.

        Where a player has no club (own-club mode with no Team), the
        resolved club's playing-style vector is entirely NaN, or the
        player's Main_Position has no role-score coverage, `compatibility_score`
        is forced to NaN (not left to `compatibility_score()`'s bonus-only
        fallback) -- Role Fit Score being NaN means the club match itself is
        unresolved, which must propagate as "unknown", not "70/100 because we
        happened to still have a bonus term". `transfer_probability` then
        propagates to NaN automatically via float-NaN arithmetic.

    `result.attrs["exclusion_counts"]` records how many players were
    excluded for each reason (no_club, unresolved_role_fit, nan_player_impact)
    -- diagnostic only, not part of the return contract Plans 06/07 depend on.
    """
    if player_impact is None:
        raise ValueError("compute_cs_tp_for_pairs: player_impact is required (Plan 04's RMM output)")

    assert_columns_present(players_df, _PLAYERS_REQUIRED, "compute_cs_tp_for_pairs players_df")

    if as_of_year is None:
        as_of_year = datetime.date.today().year

    merged = players_df.merge(role_scores_wide, on="player_id", how="left", suffixes=("", "_role"))

    # Financial Score baseline (APPLIED_FIXES): current-squad avg age/MV per
    # club, computed once (vectorized), not per-row.
    squad_stats = (
        merged.groupby("Team")[["Age", "Market value"]].mean().rename(
            columns={"Age": "_squad_avg_age", "Market value": "_squad_avg_mv"}
        )
    )

    exclusion_counts = {"no_club": 0, "unresolved_role_fit": 0, "nan_player_impact": 0}
    rows = []

    for _, row in merged.iterrows():
        player_id = row["player_id"]
        target_team = club_context if club_context is not None else row.get("Team")
        has_club = pd.notna(target_team) and str(target_team).strip() != ""

        position = normalise_position(row.get("Main_Position", row.get("Position", "")))

        if has_club:
            role_fit_info = calculate_subjective_role_fit_for_player_to_team(row, target_team, team_styles_df)
        else:
            role_fit_info = {"Role Fit Score": np.nan, "Best Team Fit Role": ""}
            exclusion_counts["no_club"] += 1

        own_best_role, own_best_score = get_player_own_best_role(row, position)
        role_pct = round(own_best_score, 2) if pd.notna(own_best_score) else np.nan

        bonus = (
            100.0
            if role_fit_info.get("Best Team Fit Role", "") == own_best_role
            and own_best_role not in (None, "")
            else 70.0
        )

        if pd.isna(role_fit_info.get("Role Fit Score", np.nan)):
            compat_val = np.nan
            if has_club:
                exclusion_counts["unresolved_role_fit"] += 1
        else:
            compat_val = compatibility_score(role_fit_info["Role Fit Score"], np.nan, bonus)

        if has_club:
            squad = squad_stats.reindex([target_team])
            avg_age = squad["_squad_avg_age"].iloc[0] if target_team in squad_stats.index else np.nan
            avg_mv = squad["_squad_avg_mv"].iloc[0] if target_team in squad_stats.index else np.nan
        else:
            avg_age, avg_mv = np.nan, np.nan

        age_fit_label = classify_age_fit(row.get("Age"), avg_age)
        mv_fit_label = (
            classify_fit(row.get("Market value"), avg_mv, avg_mv * 0.25, avg_mv * 0.5)
            if pd.notna(avg_mv)
            else "Unknown"
        )
        financial_val = financial_score(age_fit_label, mv_fit_label)

        player_impact_val = player_impact.get(player_id, np.nan)
        if pd.isna(player_impact_val):
            exclusion_counts["nan_player_impact"] += 1
        performance_val = performance_score(player_impact_val)

        years_left = _years_left_from_contract_expires(row.get("Contract expires"), as_of_year)
        contract_fit_val = contract_fit(years_left)

        tp_val = transfer_probability(compat_val, performance_val, financial_val, contract_fit_val)

        rows.append(
            {
                "player_id": player_id,
                "club_context": target_team,
                "compatibility_score": compat_val,
                "financial_score": financial_val,
                "performance_score": performance_val,
                "contract_fit": contract_fit_val,
                "role_pct": role_pct,
                "transfer_probability": tp_val,
            }
        )

    result = pd.DataFrame(rows).set_index("player_id")
    result.attrs["exclusion_counts"] = exclusion_counts
    logger.info("compute_cs_tp_for_pairs exclusion_counts=%s", exclusion_counts)
    return result
