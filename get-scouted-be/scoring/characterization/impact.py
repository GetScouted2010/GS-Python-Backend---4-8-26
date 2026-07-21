"""Faithful characterization of RMM ("Player Impact") from impact_model_v4.1.py.

Per 03-RESEARCH.md, `add_player_impact` is the least-ambiguous of the 4 v1
scores: single-definition (not duplicated elsewhere in the 15,700-line
script), context-free (population-relative, not club-context-dependent like
"Performance Score"), and this phase's recommended RMM primitive. This
module extracts, VERBATIM, the one genuinely clean part of the script:

    _build_std_lookup                    (impact_model_v4.1.py line ~1392)
    _calc_gk_impact_raw                  (line ~1413)
    _calc_cb_impact_raw                  (line ~1473)
    _calc_fb_impact_raw                  (line ~1539)
    _calc_cmf_impact_raw                 (line ~1616)
    _calc_dmf_impact_raw                 (line ~1694)
    _calc_amf_impact_raw                 (line ~1773)
    _calc_winger_impact_raw              (line ~1851)
    _calc_cf_impact_raw                  (line ~1928)
    add_player_impact / _position_percentile (line ~2725 / ~1260)

Every threshold, weight, and the `league_weights` dict are preserved
UNCHANGED -- these are deliberate tuning choices per 03-CONTEXT.md's
"don't touch non-bug quirks" rule, not bugs to improve. `league_weights` is
not read anywhere in this RMM code path (it belongs to Performance
Score / Transfer Probability, ported in later phases) but is carried here
verbatim per this plan's explicit read_first/acceptance-criteria directive
so it is available, untouched, to whichever later phase needs it.

The one exception -- the phase's narrow fix-threshold for a MISSING-column
silent-default that mathematically distorts the score -- is documented
below and is the only intentional deviation from the source script.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from scoring.characterization.reconstruct import assert_columns_present

# =========================================================================
# APPLIED FIXES
# =========================================================================
# Recorded here (not just in a commit message) so Plan 07 can copy these
# into the curation map's "Fixes applied" section verbatim.
APPLIED_FIXES = [
    {
        "column": "Minutes",
        "source_behavior": (
            "impact_model_v4.1.py's _ensure_minutes(df) (line ~1249): if "
            "neither 'Minutes' nor any of ['Minutes played', 'Mins played', "
            "'Time Played'] is present as a column, it silently does "
            "`df['Minutes'] = 0` for every row in the whole dataframe. "
            "Every _calc_*_impact_raw then multiplies "
            "(positive - negative) by _minutes_factor(0) == 0.55 for those "
            "players -- a plausible-looking but fabricated reliability "
            "penalty applied to every player, not an honest 'unknown'. "
            "This is the exact CONCERNS.md 'Fragile Area: Complex Python "
            "Scoring Engine' silent-default pattern."
        ),
        "fix": (
            "This module's _ensure_minutes(df) raises ValueError instead of "
            "defaulting the whole column to 0 when no Minutes-equivalent "
            "column exists at all. Per-row NaN Minutes (an individual "
            "player with unknown minutes, column present) are left as NaN "
            "-- they flow into _minutes_factor via _safe_num's NaN->0.0 "
            "coercion exactly as upstream, which is a per-player accepted "
            "quirk, not the column-missing bug being fixed here."
        ),
        "why": (
            "A missing Minutes-equivalent column is a reconstruction bug "
            "(the ORM->DataFrame bridge failed to provide it), not a "
            "legitimate 'nobody played' population state -- it should fail "
            "loudly (assert_columns_present-style) rather than silently "
            "distort every player's RMM by the same fabricated 0.55 floor."
        ),
    }
]


# =========================================================================
# POSITION NORMALISATION (verbatim, impact_model_v4.1.py line ~909)
# =========================================================================
POSITION_NORMALISATION = {
    "Centre-Back": "CB", "Center Back": "CB", "Central Defender": "CB",
    "Left Centre-Back": "CB", "Right Centre-Back": "CB",
    "LCB": "CB", "RCB": "CB", "CB": "CB",

    "Right Back": "RB", "Fullback Right": "RB", "RB": "RB",
    "Right Full-Back": "RB", "RFB": "RB", "Right Wing-Back": "RB", "RWB": "RB",

    "Left Back": "LB", "Fullback Left": "LB", "LB": "LB",
    "Left Full-Back": "LB", "LFB": "LB", "Left Wing-Back": "LB", "LWB": "LB",

    "Defensive Midfield": "DMF", "CDM": "DMF", "DM": "DMF",
    "LDMF": "DMF", "RDMF": "DMF", "DMF": "DMF",

    "Central Midfield": "CM", "CMF": "CM", "Midfielder Centre": "CM",
    "LCMF": "CM", "RCMF": "CM", "CM": "CM",

    "Attacking Midfield": "AMF", "CAM": "AMF",
    "LAMF": "AMF", "RAMF": "AMF", "AMF": "AMF",

    "Right Midfield": "RW", "Right Winger": "RW", "Right Wing": "RW",
    "Right Forward": "RW", "RW": "RW", "RWF": "RW",

    "Left Midfield": "LW", "Left Winger": "LW", "Left Wing": "LW",
    "Left Forward": "LW", "LW": "LW", "LWF": "LW",

    "Centre Forward": "CF", "FWD": "CF", "Forward": "CF", "CF": "CF",
    "Goalkeeper": "GK", "Keeper": "GK", "GK": "GK",
}


def normalise_position(pos):
    """Verbatim, impact_model_v4.1.py line ~939."""
    if pd.isna(pos):
        return pos
    return POSITION_NORMALISATION.get(str(pos).strip(), str(pos).strip())


# =========================================================================
# HELPERS (verbatim, impact_model_v4.1.py lines ~1217-1264)
# =========================================================================
def _safe_num(v, default=0.0):
    try:
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def _pct_to_dec(v):
    v = _safe_num(v, 0.0)
    return v / 100.0 if v > 1 else v


def _get(row, col, default=0.0):
    return _safe_num(row.get(col, default), default)


def _minutes_factor(minutes):
    """Mid-season adjustment (dataset starts in August, snapshot in January)."""
    m = _safe_num(minutes, 0)
    return np.clip(0.55 + 0.45 * (m / 900.0), 0.55, 1.00)


def _reliability_flag(minutes):
    m = _safe_num(minutes, 0)
    if m < 300:
        return "Very Low"
    elif m < 600:
        return "Low"
    elif m < 900:
        return "Medium"
    return "High"


_MINUTES_FALLBACK_CANDIDATES = ["Minutes played", "Mins played", "Time Played"]


def _ensure_minutes(df):
    """Guarantee a "Minutes" column exists -- APPLIED_FIXES[0].

    Source behavior (impact_model_v4.1.py line ~1249) silently set the
    whole "Minutes" column to 0 when absent. That silent zero-fill is
    replaced here with a loud ValueError -- see the module-level
    APPLIED_FIXES docstring entry for the full rationale.
    """
    df = df.copy()
    if "Minutes" in df.columns:
        return df
    for alt in _MINUTES_FALLBACK_CANDIDATES:
        if alt in df.columns:
            df["Minutes"] = df[alt]
            return df
    raise ValueError(
        "add_player_impact: no Minutes-equivalent column found (tried "
        f"['Minutes'] + {_MINUTES_FALLBACK_CANDIDATES}) -- refusing to "
        "silently default the whole 'Minutes' column to 0 (APPLIED_FIXES[0])."
    )


def _position_percentile(series):
    """Verbatim, impact_model_v4.1.py line ~1260."""
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() <= 1:
        return pd.Series(np.full(len(series), 50.0), index=series.index)
    return s.rank(pct=True, method="average").fillna(0.5) * 100


# =========================================================================
# FAILED ACTIONS (verbatim, impact_model_v4.1.py line ~1349)
# =========================================================================
def _failed_actions(row):
    failed_passes = _get(row, "Passes per 90") * (1 - _pct_to_dec(_get(row, "Accurate passes, %")))
    failed_forward_passes = _get(row, "Forward passes per 90") * (1 - _pct_to_dec(_get(row, "Accurate forward passes, %")))
    failed_long_passes = _get(row, "Long passes per 90") * (1 - _pct_to_dec(_get(row, "Accurate long passes, %")))
    failed_prog_passes = _get(row, "Progressive passes per 90") * (1 - _pct_to_dec(_get(row, "Accurate progressive passes, %")))
    failed_final_third_passes = _get(row, "Passes to final third per 90") * (1 - _pct_to_dec(_get(row, "Accurate passes to final third, %")))
    failed_penalty_area_passes = _get(row, "Passes to penalty area per 90") * (1 - _pct_to_dec(_get(row, "Accurate passes to penalty area, %")))
    failed_through_passes = _get(row, "Through passes per 90") * (1 - _pct_to_dec(_get(row, "Accurate through passes, %")))
    failed_smart_passes = _get(row, "Smart passes per 90") * (1 - _pct_to_dec(_get(row, "Accurate smart passes, %")))
    failed_crosses = _get(row, "Crosses per 90") * (1 - _pct_to_dec(_get(row, "Accurate crosses, %")))
    failed_dribbles = _get(row, "Dribbles per 90") * (1 - _pct_to_dec(_get(row, "Successful dribbles, %")))

    lost_off_duels = _get(row, "Offensive duels per 90") * (1 - _pct_to_dec(_get(row, "Offensive duels won, %")))
    lost_def_duels = _get(row, "Defensive duels per 90") * (1 - _pct_to_dec(_get(row, "Defensive duels won, %")))
    lost_aerial_duels = _get(row, "Aerial duels per 90") * (1 - _pct_to_dec(_get(row, "Aerial duels won, %")))

    failed_risky_passes = failed_smart_passes + failed_through_passes + failed_penalty_area_passes + failed_crosses
    failed_simple_passes = max(
        failed_passes - failed_prog_passes - failed_final_third_passes - failed_risky_passes,
        0.0,
    )

    return {
        "failed_passes": failed_passes,
        "failed_simple_passes": failed_simple_passes,
        "failed_forward_passes": failed_forward_passes,
        "failed_long_passes": failed_long_passes,
        "failed_prog_passes": failed_prog_passes,
        "failed_final_third_passes": failed_final_third_passes,
        "failed_penalty_area_passes": failed_penalty_area_passes,
        "failed_through_passes": failed_through_passes,
        "failed_smart_passes": failed_smart_passes,
        "failed_crosses": failed_crosses,
        "failed_risky_passes": failed_risky_passes,
        "failed_dribbles": failed_dribbles,
        "lost_off_duels": lost_off_duels,
        "lost_def_duels": lost_def_duels,
        "lost_aerial_duels": lost_aerial_duels,
    }


# =========================================================================
# STANDARDISATION LOOKUP (verbatim, impact_model_v4.1.py line ~1392)
# =========================================================================
def _build_std_lookup(df, metrics, position_col="Main_Position"):
    out = {}
    for pos, grp in df.groupby(position_col):
        pos_map = {}
        for metric in metrics:
            if metric in grp.columns:
                pos_map[metric] = _position_percentile(grp[metric])
            else:
                pos_map[metric] = pd.Series(np.full(len(grp), 50.0), index=grp.index)
        out[pos] = pos_map
    return out


def _std(row_idx, pos, metric, std_lookup):
    try:
        return float(std_lookup[pos][metric].loc[row_idx])
    except Exception:
        return 50.0


# =========================================================================
# POSITION MODELS (verbatim, impact_model_v4.1.py lines ~1413-1996)
# =========================================================================
def _calc_gk_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = "GK"

    shot_stopping = (
        0.35 * _std(row_idx, pos, "Save rate, %", std_lookup) +
        0.35 * _std(row_idx, pos, "Prevented goals per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Clean sheets", std_lookup) +
        0.10 * _std(row_idx, pos, "Shots against per 90", std_lookup)
    )

    command = (
        0.40 * _std(row_idx, pos, "Exits per 90", std_lookup) +
        0.30 * _std(row_idx, pos, "Aerial duels per 90", std_lookup) +
        0.30 * _std(row_idx, pos, "Aerial duels won, %", std_lookup)
    )

    distribution = (
        0.25 * _std(row_idx, pos, "Passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Accurate passes, %", std_lookup) +
        0.20 * _std(row_idx, pos, "Long passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Accurate long passes, %", std_lookup) +
        0.15 * _std(row_idx, pos, "Average long pass length, m", std_lookup)
    )

    buildup_support = (
        0.45 * _std(row_idx, pos, "Back passes received as GK per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "Passes per 90", std_lookup) +
        0.30 * _std(row_idx, pos, "Accurate passes, %", std_lookup)
    )

    positive = (
        0.42 * shot_stopping +
        0.20 * command +
        0.22 * distribution +
        0.16 * buildup_support
    )

    negative = (
        0.26 * _std(row_idx, pos, "Conceded goals per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "xG against per 90", std_lookup) +
        0.14 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_long_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "lost_aerial_duels", std_lookup) +
        0.08 * _std(row_idx, pos, "Red cards per 90", std_lookup) +
        0.06 * _std(row_idx, pos, "Yellow cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "shot_stopping": shot_stopping,
            "command": command,
            "distribution": distribution,
            "buildup_support": buildup_support,
        }

    return raw, positive, negative


def _calc_cb_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = "CB"

    defensive_actions = (
        0.45 * _std(row_idx, pos, "Successful defensive actions per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Sliding tackles per 90", std_lookup) +
        0.15 * _std(row_idx, pos, "Shots blocked per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "PAdj Interceptions", std_lookup)
    )

    duel_dominance = (
        0.35 * _std(row_idx, pos, "Defensive duels per 90", std_lookup) +
        0.65 * _std(row_idx, pos, "Defensive duels won, %", std_lookup)
    )

    aerial = (
        0.35 * _std(row_idx, pos, "Aerial duels per 90", std_lookup) +
        0.65 * _std(row_idx, pos, "Aerial duels won, %", std_lookup)
    )

    reading = (
        0.55 * _std(row_idx, pos, "Interceptions per 90", std_lookup) +
        0.45 * _std(row_idx, pos, "PAdj Interceptions", std_lookup)
    )

    buildup = (
        0.30 * _std(row_idx, pos, "Progressive passes per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "Accurate progressive passes, %", std_lookup) +
        0.25 * _std(row_idx, pos, "Passes to final third per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Accurate passes, %", std_lookup)
    )

    positive = (
        0.28 * defensive_actions +
        0.22 * duel_dominance +
        0.22 * aerial +
        0.16 * reading +
        0.12 * buildup
    )

    negative = (
        0.20 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.14 * _std(row_idx, pos, "failed_prog_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_final_third_passes", std_lookup) +
        0.08 * _std(row_idx, pos, "failed_long_passes", std_lookup) +
        0.16 * _std(row_idx, pos, "lost_def_duels", std_lookup) +
        0.14 * _std(row_idx, pos, "lost_aerial_duels", std_lookup) +
        0.08 * _std(row_idx, pos, "Fouls per 90", std_lookup) +
        0.04 * _std(row_idx, pos, "Yellow cards per 90", std_lookup) +
        0.06 * _std(row_idx, pos, "Red cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "defensive_actions": defensive_actions,
            "duel_dominance": duel_dominance,
            "aerial": aerial,
            "reading": reading,
            "buildup": buildup,
        }

    return raw, positive, negative


def _calc_fb_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = normalise_position(row.get("Main_Position", row.get("Position", "")))  # LB or RB

    defending = (
        0.30 * _std(row_idx, pos, "Successful defensive actions per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "Defensive duels per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "Defensive duels won, %", std_lookup) +
        0.20 * _std(row_idx, pos, "Interceptions per 90", std_lookup)
    )

    progression = (
        0.24 * _std(row_idx, pos, "Progressive runs per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Progressive passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate progressive passes, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Passes to final third per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accelerations per 90", std_lookup)
    )

    chance_creation = (
        0.24 * _std(row_idx, pos, "Crosses per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate crosses, %", std_lookup) +
        0.16 * _std(row_idx, pos, "Deep completed crosses per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "xA per 90", std_lookup) +
        0.14 * _std(row_idx, pos, "Key passes per 90", std_lookup) +
        0.12 * _std(row_idx, pos, "Shot assists per 90", std_lookup)
    )

    control = (
        0.26 * _std(row_idx, pos, "Passes per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Accurate passes, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Forward passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate forward passes, %", std_lookup) +
        0.16 * _std(row_idx, pos, "Received passes per 90", std_lookup)
    )

    duel_work = (
        0.35 * _std(row_idx, pos, "Offensive duels per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "Offensive duels won, %", std_lookup) +
        0.20 * _std(row_idx, pos, "Defensive duels won, %", std_lookup) +
        0.20 * _std(row_idx, pos, "Aerial duels won, %", std_lookup)
    )

    positive = (
        0.24 * defending +
        0.26 * progression +
        0.22 * chance_creation +
        0.16 * control +
        0.12 * duel_work
    )

    negative = (
        0.18 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_prog_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_crosses", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_final_third_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_dribbles", std_lookup) +
        0.14 * _std(row_idx, pos, "lost_def_duels", std_lookup) +
        0.10 * _std(row_idx, pos, "lost_off_duels", std_lookup) +
        0.08 * _std(row_idx, pos, "Fouls per 90", std_lookup) +
        0.04 * _std(row_idx, pos, "Yellow cards per 90", std_lookup) +
        0.02 * _std(row_idx, pos, "Red cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "defending": defending,
            "progression": progression,
            "chance_creation": chance_creation,
            "control": control,
            "duel_work": duel_work,
        }

    return raw, positive, negative


def _calc_cmf_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = "CM"

    ball_progression = (
        0.22 * _std(row_idx, pos, "Progressive passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate progressive passes, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Progressive runs per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Passes to final third per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Accurate passes to final third, %", std_lookup)
    )

    control = (
        0.20 * _std(row_idx, pos, "Passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Accurate passes, %", std_lookup) +
        0.15 * _std(row_idx, pos, "Short / medium passes per 90", std_lookup) +
        0.15 * _std(row_idx, pos, "Accurate short / medium passes, %", std_lookup) +
        0.15 * _std(row_idx, pos, "Received passes per 90", std_lookup) +
        0.15 * _std(row_idx, pos, "Forward passes per 90", std_lookup)
    )

    creation = (
        0.22 * _std(row_idx, pos, "xA per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Shot assists per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Key passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Smart passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Through passes per 90", std_lookup)
    )

    ball_winning = (
        0.24 * _std(row_idx, pos, "Successful defensive actions per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Defensive duels per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Defensive duels won, %", std_lookup) +
        0.16 * _std(row_idx, pos, "Interceptions per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "PAdj Interceptions", std_lookup)
    )

    carrying = (
        0.34 * _std(row_idx, pos, "Dribbles per 90", std_lookup) +
        0.24 * _std(row_idx, pos, "Successful dribbles, %", std_lookup) +
        0.22 * _std(row_idx, pos, "Accelerations per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Fouls suffered per 90", std_lookup)
    )

    positive = (
        0.26 * ball_progression +
        0.22 * control +
        0.18 * creation +
        0.20 * ball_winning +
        0.14 * carrying
    )

    negative = (
        0.20 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_prog_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_final_third_passes", std_lookup) +
        0.08 * _std(row_idx, pos, "failed_smart_passes", std_lookup) +
        0.08 * _std(row_idx, pos, "failed_through_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_dribbles", std_lookup) +
        0.12 * _std(row_idx, pos, "lost_def_duels", std_lookup) +
        0.08 * _std(row_idx, pos, "Fouls per 90", std_lookup) +
        0.07 * _std(row_idx, pos, "Yellow cards per 90", std_lookup) +
        0.05 * _std(row_idx, pos, "Red cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "ball_progression": ball_progression,
            "control": control,
            "creation": creation,
            "ball_winning": ball_winning,
            "carrying": carrying,
        }

    return raw, positive, negative


def _calc_dmf_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = "DMF"

    ball_winning = (
        0.24 * _std(row_idx, pos, "Successful defensive actions per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Defensive duels per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Defensive duels won, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Interceptions per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "PAdj Interceptions", std_lookup)
    )

    control = (
        0.18 * _std(row_idx, pos, "Passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate passes, %", std_lookup) +
        0.16 * _std(row_idx, pos, "Short / medium passes per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "Accurate short / medium passes, %", std_lookup) +
        0.16 * _std(row_idx, pos, "Back passes per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "Accurate back passes, %", std_lookup)
    )

    progression = (
        0.24 * _std(row_idx, pos, "Progressive passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate progressive passes, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Passes to final third per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "Accurate passes to final third, %", std_lookup) +
        0.12 * _std(row_idx, pos, "Long passes per 90", std_lookup) +
        0.12 * _std(row_idx, pos, "Accurate long passes, %", std_lookup)
    )

    distribution = (
        0.34 * _std(row_idx, pos, "Forward passes per 90", std_lookup) +
        0.28 * _std(row_idx, pos, "Accurate forward passes, %", std_lookup) +
        0.20 * _std(row_idx, pos, "Duels won, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Fouls suffered per 90", std_lookup)
    )

    creation = (
        0.24 * _std(row_idx, pos, "Key passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Shot assists per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Smart passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Through passes per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "xA per 90", std_lookup)
    )

    positive = (
        0.28 * ball_winning +
        0.24 * control +
        0.20 * progression +
        0.16 * distribution +
        0.12 * creation
    )

    negative = (
        0.20 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_prog_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_final_third_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_smart_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_through_passes", std_lookup) +
        0.08 * _std(row_idx, pos, "failed_long_passes", std_lookup) +
        0.14 * _std(row_idx, pos, "lost_def_duels", std_lookup) +
        0.08 * _std(row_idx, pos, "Fouls per 90", std_lookup) +
        0.04 * _std(row_idx, pos, "Yellow cards per 90", std_lookup) +
        0.04 * _std(row_idx, pos, "Red cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "ball_winning": ball_winning,
            "control": control,
            "progression": progression,
            "distribution": distribution,
            "creation": creation,
        }

    return raw, positive, negative


def _calc_amf_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = "AMF"

    creation = (
        0.24 * _std(row_idx, pos, "xA per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Key passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Shot assists per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Smart passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Through passes per 90", std_lookup)
    )

    final_third_progression = (
        0.24 * _std(row_idx, pos, "Progressive passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate progressive passes, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Progressive runs per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Passes to penalty area per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Deep completions per 90", std_lookup)
    )

    scoring_threat = (
        0.26 * _std(row_idx, pos, "Goals per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Non-penalty goals per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "xG per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "Shots per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "Touches in box per 90", std_lookup)
    )

    carrying = (
        0.26 * _std(row_idx, pos, "Dribbles per 90", std_lookup) +
        0.22 * _std(row_idx, pos, "Successful dribbles, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Accelerations per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Progressive runs per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "Fouls suffered per 90", std_lookup)
    )

    connection = (
        0.24 * _std(row_idx, pos, "Received passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Accurate passes, %", std_lookup) +
        0.18 * _std(row_idx, pos, "Forward passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Accurate forward passes, %", std_lookup)
    )

    positive = (
        0.28 * creation +
        0.22 * final_third_progression +
        0.20 * scoring_threat +
        0.16 * carrying +
        0.14 * connection
    )

    negative = (
        0.14 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_prog_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_final_third_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_smart_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_through_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_dribbles", std_lookup) +
        0.08 * _std(row_idx, pos, "lost_off_duels", std_lookup) +
        0.10 * _std(row_idx, pos, "finishing_waste", std_lookup) +
        0.07 * _std(row_idx, pos, "Fouls per 90", std_lookup) +
        0.05 * _std(row_idx, pos, "Yellow cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "creation": creation,
            "final_third_progression": final_third_progression,
            "scoring_threat": scoring_threat,
            "carrying": carrying,
            "connection": connection,
        }

    return raw, positive, negative


def _calc_winger_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = normalise_position(row.get("Main_Position", row.get("Position", "")))  # LW or RW

    dribbling = (
        0.28 * _std(row_idx, pos, "Dribbles per 90", std_lookup) +
        0.24 * _std(row_idx, pos, "Successful dribbles, %", std_lookup) +
        0.24 * _std(row_idx, pos, "Progressive runs per 90", std_lookup) +
        0.24 * _std(row_idx, pos, "Accelerations per 90", std_lookup)
    )

    creation = (
        0.22 * _std(row_idx, pos, "xA per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Key passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Shot assists per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Crosses per 90", std_lookup) +
        0.10 * _std(row_idx, pos, "Accurate crosses, %", std_lookup) +
        0.12 * _std(row_idx, pos, "Deep completed crosses per 90", std_lookup)
    )

    threat = (
        0.24 * _std(row_idx, pos, "Goals per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Non-penalty goals per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "xG per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Touches in box per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Shots per 90", std_lookup)
    )

    progression = (
        0.24 * _std(row_idx, pos, "Progressive runs per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Progressive passes per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Passes to penalty area per 90", std_lookup) +
        0.18 * _std(row_idx, pos, "Deep completions per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Received long passes per 90", std_lookup)
    )

    duel_value = (
        0.36 * _std(row_idx, pos, "Offensive duels per 90", std_lookup) +
        0.28 * _std(row_idx, pos, "Offensive duels won, %", std_lookup) +
        0.20 * _std(row_idx, pos, "Fouls suffered per 90", std_lookup) +
        0.16 * _std(row_idx, pos, "Touches in box per 90", std_lookup)
    )

    positive = (
        0.24 * dribbling +
        0.24 * creation +
        0.22 * threat +
        0.18 * progression +
        0.12 * duel_value
    )

    negative = (
        0.10 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_prog_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_crosses", std_lookup) +
        0.16 * _std(row_idx, pos, "failed_dribbles", std_lookup) +
        0.12 * _std(row_idx, pos, "lost_off_duels", std_lookup) +
        0.10 * _std(row_idx, pos, "failed_final_third_passes", std_lookup) +
        0.08 * _std(row_idx, pos, "finishing_waste", std_lookup) +
        0.07 * _std(row_idx, pos, "Fouls per 90", std_lookup) +
        0.03 * _std(row_idx, pos, "Yellow cards per 90", std_lookup) +
        0.02 * _std(row_idx, pos, "Red cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "dribbling": dribbling,
            "creation": creation,
            "threat": threat,
            "progression": progression,
            "duel_value": duel_value,
        }

    return raw, positive, negative


def _calc_cf_impact_raw(row, row_idx, std_lookup, return_components=False):
    pos = "CF"

    finishing = (
        0.35 * _std(row_idx, pos, "Non-penalty goals per 90", std_lookup) +
        0.30 * _std(row_idx, pos, "xG per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Goal conversion, %", std_lookup) +
        0.15 * _std(row_idx, pos, "Shots on target, %", std_lookup)
    )

    box_threat = (
        0.35 * _std(row_idx, pos, "Touches in box per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "Shots per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "xG per 90", std_lookup) +
        0.15 * _std(row_idx, pos, "Progressive runs per 90", std_lookup)
    )

    chance_creation = (
        0.35 * _std(row_idx, pos, "xA per 90", std_lookup) +
        0.25 * _std(row_idx, pos, "Shot assists per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Key passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Smart passes per 90", std_lookup)
    )

    progression = (
        0.35 * _std(row_idx, pos, "Progressive runs per 90", std_lookup) +
        0.30 * _std(row_idx, pos, "Progressive passes per 90", std_lookup) +
        0.20 * _std(row_idx, pos, "Passes to penalty area per 90", std_lookup) +
        0.15 * _std(row_idx, pos, "Accelerations per 90", std_lookup)
    )

    duel_value = (
        0.35 * _std(row_idx, pos, "Offensive duels per 90", std_lookup) +
        0.35 * _std(row_idx, pos, "Offensive duels won, %", std_lookup) +
        0.30 * _std(row_idx, pos, "Aerial duels won, %", std_lookup)
    )

    positive = (
        0.32 * finishing +
        0.24 * box_threat +
        0.18 * chance_creation +
        0.14 * progression +
        0.12 * duel_value
    )

    negative = (
        0.28 * _std(row_idx, pos, "finishing_waste", std_lookup) +
        0.16 * _std(row_idx, pos, "failed_simple_passes", std_lookup) +
        0.14 * _std(row_idx, pos, "failed_prog_passes", std_lookup) +
        0.12 * _std(row_idx, pos, "failed_dribbles", std_lookup) +
        0.10 * _std(row_idx, pos, "lost_off_duels", std_lookup) +
        0.08 * _std(row_idx, pos, "lost_aerial_duels", std_lookup) +
        0.06 * _std(row_idx, pos, "Fouls per 90", std_lookup) +
        0.04 * _std(row_idx, pos, "Yellow cards per 90", std_lookup) +
        0.02 * _std(row_idx, pos, "Red cards per 90", std_lookup)
    )

    raw = (positive - negative) * _minutes_factor(_get(row, "Minutes", 0))

    if return_components:
        return raw, positive, negative, {
            "finishing": finishing,
            "box_threat": box_threat,
            "chance_creation": chance_creation,
            "progression": progression,
            "duel_value": duel_value,
        }

    return raw, positive, negative


# =========================================================================
# LEAGUE WEIGHTS (verbatim, impact_model_v4.1.py line ~3062 / ~4677 --
# identical duplicate dicts in the source; ported once here. NOT read by
# this module's RMM path -- carried untouched per this plan's directive for
# whichever later phase (Performance Score / Transfer Probability) needs it)
# =========================================================================
league_weights = {
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
# MAIN FUNCTION (verbatim, impact_model_v4.1.py line ~2725)
# =========================================================================
def add_player_impact(df):
    df = df.copy()
    df = _ensure_minutes(df)

    if "Main_Position" not in df.columns and "Position" in df.columns:
        df["Main_Position"] = df["Position"]

    df["Main_Position"] = df["Main_Position"].apply(normalise_position)

    failed_rows = df.apply(_failed_actions, axis=1, result_type="expand")
    for col in failed_rows.columns:
        df[col] = failed_rows[col]

    df["finishing_waste"] = (
        df.get("xG per 90", 0).fillna(0).astype(float) -
        df.get("Non-penalty goals per 90", 0).fillna(0).astype(float)
    ).clip(lower=0)

    metrics_needed = [
        "Save rate, %", "Prevented goals per 90", "Clean sheets", "Shots against per 90",
        "Exits per 90", "Aerial duels per 90", "Aerial duels won, %",
        "Passes per 90", "Accurate passes, %", "Long passes per 90", "Accurate long passes, %",
        "Average long pass length, m", "Back passes received as GK per 90",
        "Conceded goals per 90", "xG against per 90",

        "Successful defensive actions per 90", "Sliding tackles per 90", "Shots blocked per 90",
        "Defensive duels per 90", "Defensive duels won, %", "Interceptions per 90",
        "PAdj Interceptions", "Progressive passes per 90", "Accurate progressive passes, %",
        "Passes to final third per 90", "Accurate passes to final third, %",
        "Progressive runs per 90", "Accelerations per 90", "Crosses per 90",
        "Accurate crosses, %", "Deep completed crosses per 90", "xA per 90",
        "Key passes per 90", "Shot assists per 90", "Forward passes per 90",
        "Accurate forward passes, %", "Received passes per 90", "Offensive duels per 90",
        "Offensive duels won, %", "Short / medium passes per 90",
        "Accurate short / medium passes, %", "Back passes per 90", "Accurate back passes, %",
        "Duels won, %", "Fouls suffered per 90", "Smart passes per 90", "Through passes per 90",
        "Passes to penalty area per 90", "Deep completions per 90", "Goals per 90",
        "Non-penalty goals per 90", "xG per 90", "Shots per 90", "Touches in box per 90",
        "Dribbles per 90", "Successful dribbles, %", "Received long passes per 90",
        "Goal conversion, %", "Shots on target, %", "Head goals per 90",

        "Fouls per 90", "Yellow cards per 90", "Red cards per 90",

        "failed_simple_passes", "failed_passes", "failed_forward_passes", "failed_long_passes",
        "failed_prog_passes", "failed_final_third_passes", "failed_penalty_area_passes",
        "failed_through_passes", "failed_smart_passes", "failed_crosses", "failed_risky_passes",
        "failed_dribbles", "lost_off_duels", "lost_def_duels", "lost_aerial_duels",
        "finishing_waste",
    ]

    std_lookup = _build_std_lookup(df, metrics_needed, position_col="Main_Position")

    raw_scores = []
    pos_scores = []
    neg_scores = []
    reliability = []
    component_rows = []

    for idx, row in df.iterrows():
        pos = normalise_position(row.get("Main_Position", row.get("Position", "")))

        if pos == "GK":
            raw, p, n, comps = _calc_gk_impact_raw(row, idx, std_lookup, return_components=True)
        elif pos == "CB":
            raw, p, n, comps = _calc_cb_impact_raw(row, idx, std_lookup, return_components=True)
        elif pos in ["LB", "RB"]:
            raw, p, n, comps = _calc_fb_impact_raw(row, idx, std_lookup, return_components=True)
        elif pos == "CM":
            raw, p, n, comps = _calc_cmf_impact_raw(row, idx, std_lookup, return_components=True)
        elif pos == "DMF":
            raw, p, n, comps = _calc_dmf_impact_raw(row, idx, std_lookup, return_components=True)
        elif pos == "AMF":
            raw, p, n, comps = _calc_amf_impact_raw(row, idx, std_lookup, return_components=True)
        elif pos in ["LW", "RW"]:
            raw, p, n, comps = _calc_winger_impact_raw(row, idx, std_lookup, return_components=True)
        elif pos == "CF":
            raw, p, n, comps = _calc_cf_impact_raw(row, idx, std_lookup, return_components=True)
        else:
            raw, p, n, comps = np.nan, np.nan, np.nan, {}

        raw_scores.append(raw)
        pos_scores.append(p)
        neg_scores.append(n)
        reliability.append(_reliability_flag(row.get("Minutes", 0)))
        component_rows.append(comps)

    df["Player Impact Raw"] = raw_scores
    df["Player Impact Positive"] = pos_scores
    df["Player Impact Negative"] = neg_scores
    df["Impact Reliability"] = reliability
    df["Player Impact"] = np.nan

    for pos in ["GK", "CB", "LB", "RB", "CM", "DMF", "AMF", "LW", "RW", "CF"]:
        mask = df["Main_Position"].apply(normalise_position) == pos
        vals = df.loc[mask, "Player Impact Raw"]
        if vals.notna().sum() == 0:
            continue
        df.loc[mask, "Player Impact"] = _position_percentile(vals).round(2)

    components_df = pd.DataFrame(component_rows)

    if not components_df.empty:
        components_df = components_df.add_prefix("Impact Comp - ")
        df = pd.concat([df.reset_index(drop=True), components_df.reset_index(drop=True)], axis=1)

    return df


# =========================================================================
# ORACLE CONVENIENCE WRAPPER (new, this plan's addition -- not in source)
# =========================================================================
def compute_rmm_column(players_df: pd.DataFrame) -> pd.Series:
    """Return the "Player Impact" (RMM) value per player, indexed by player_id.

    Thin wrapper Plan 07's oracle generator imports so it never has to know
    about `add_player_impact`'s internal column-naming/component-expansion
    details -- just player_id -> RMM (0-100 or NaN).
    """
    assert_columns_present(players_df, ["player_id"], "compute_rmm_column input")

    scored = add_player_impact(players_df)
    result = scored.set_index("player_id")["Player Impact"]
    result.name = "Player Impact"
    return result
