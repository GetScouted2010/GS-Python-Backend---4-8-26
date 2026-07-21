"""Faithful port of impact_model_v4.1.py's role-fit + Compatibility Score
assembly.

Ported from `pixel-perfect-clone-60729/docs/impact_model_v4.1.py`:

    STYLE_COLUMNS / STYLE_ALIASES / ROLE_STYLE_WEIGHTS ....... lines ~2000-2340
    standardize_team_style_columns / normalize_series ........ lines 2342-2354
    normalize_role_vector_from_row / build_team_style_vector .. lines 2356-2374
    compute_team_role_demand .................................. lines 2376-2388
    sharpen_distribution / weighted_overlap_score ............. lines 2390-2413
    get_top_roles_string / get_top_roles_relative_to_best ...... lines 2415-2444
    calculate_subjective_role_fit_for_player_to_team (def@2446)  lines 2446-2511
    "Compatibility Score" assembly ............................ lines 3798-3802
    get_role_scores_from_dataset / extract_playing_style_from_dataset
        (identical duplicates at def@1055/def@3133 and def@3120) -- used here
        only to recover the player's OWN best-fitting role (needed for the
        Compatibility Score "matches team's best-fit role" bonus term and for
        the `role_pct` upstream feature Plan 06/07 consume).

`ROLE_COLUMNS_BY_POSITION` is imported from `reconstruct.py` rather than
redefined here -- the two literal dicts in the source (lines 824-904 in
impact_model_v4.1.py, and reconstruct.py's coverage-validation copy) are
verified identical; duplicating a third copy here would just create another
instance of the "authoritative duplicated function" problem this phase exists
to eliminate (03-CONTEXT.md).

Weights/thresholds in ROLE_STYLE_WEIGHTS are copied verbatim -- do not
"simplify" or re-derive them.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from scoring.characterization.reconstruct import ROLE_COLUMNS_BY_POSITION

# =========================================================================
# APPLIED_FIXES -- deviations from a byte-literal port, and why.
# =========================================================================
APPLIED_FIXES = [
    (
        "calculate_subjective_role_fit_for_player_to_team: the source computes "
        "build_team_style_vector() unconditionally, which normalize_series() "
        "silently zero-fills when a club's STYLE_COLUMNS values are all NaN "
        "(pd.to_numeric(..., errors='coerce').fillna(0.0)) -- the ~77%-null "
        "case documented in FIELD_MAPPING.md section 3. Chased through "
        "compute_team_role_demand -> weighted_overlap_score, an all-NaN club "
        "style vector deterministically produces Role Fit Score == 0.0, a "
        "confidently-wrong 'this player has zero fit here' result rather than "
        "an honest 'we don't know'. This port adds an explicit guard: if the "
        "target club's style vector has no non-NaN STYLE_COLUMNS values, "
        "return the same NaN/blank result dict the source already returns for "
        "its other early-exit branches (unmatched position/team/empty role "
        "vector), instead of proceeding to a zero-filled computation."
    ),
    (
        "get_player_own_best_role: the source's get_role_scores_from_dataset / "
        "extract_playing_style_from_dataset read `float(row.get(role, 0))`, "
        "which only substitutes 0 when the column is entirely ABSENT, not when "
        "the cell value is NaN (a wide-pivoted role_scores_wide column can be "
        "present-but-NaN for a player who simply wasn't scored on that role). "
        "A stray NaN reaching `max(scores, key=scores.get)` produces "
        "undefined/non-deterministic ordering. This port explicitly coerces "
        "NaN role-score cells to 'not a candidate' (excluded, not zero-filled) "
        "before taking the max, and returns (None, np.nan, {}) -- not (None, "
        "0, {}) -- when no role has a real value, consistent with this "
        "project's 'no silent zero-fill' rule (CONCERNS.md)."
    ),
]


# =========================================================================
# Role-fit config (impact_model_v4.1.py lines ~2000-2340, verbatim)
# =========================================================================
STYLE_COLUMNS = [
    "Control Possession",
    "Gegenpressing",
    "Direct Play",
    "Defensive Counter Attack",
    "Tiki Taka",
    "Counter Attack",
    "Wing Play",
    "Low Block",
]

STYLE_ALIASES = {
    "Defensive Counter Attacking": "Defensive Counter Attack",
}

ROLE_STYLE_WEIGHTS: dict[str, dict[str, dict[str, float]]] = {
    "CF": {
        "Deep-Lying Forward": {
            "Control Possession": 0.90, "Gegenpressing": 0.55, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.95, "Counter Attack": 0.35,
            "Wing Play": 0.30, "Low Block": 0.05,
        },
        "Target Forward": {
            "Control Possession": 0.25, "Gegenpressing": 0.35, "Direct Play": 0.95,
            "Defensive Counter Attack": 0.80, "Tiki Taka": 0.10, "Counter Attack": 0.55,
            "Wing Play": 0.90, "Low Block": 0.45,
        },
        "Poacher": {
            "Control Possession": 0.20, "Gegenpressing": 0.35, "Direct Play": 0.85,
            "Defensive Counter Attack": 0.35, "Tiki Taka": 0.25, "Counter Attack": 0.95,
            "Wing Play": 0.60, "Low Block": 0.10,
        },
        "Complete Forward": {
            "Control Possession": 0.70, "Gegenpressing": 0.65, "Direct Play": 0.55,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.75, "Counter Attack": 0.60,
            "Wing Play": 0.75, "Low Block": 0.05,
        },
        "Advanced Forward": {
            "Control Possession": 0.45, "Gegenpressing": 0.65, "Direct Play": 0.75,
            "Defensive Counter Attack": 0.30, "Tiki Taka": 0.35, "Counter Attack": 0.85,
            "Wing Play": 0.60, "Low Block": 0.05,
        },
        "Pressing Forward": {
            "Control Possession": 0.55, "Gegenpressing": 1.00, "Direct Play": 0.45,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.45, "Counter Attack": 0.70,
            "Wing Play": 0.45, "Low Block": 0.00,
        },
        "Trequartista": {
            "Control Possession": 0.65, "Gegenpressing": 0.20, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.05, "Tiki Taka": 0.85, "Counter Attack": 0.45,
            "Wing Play": 0.55, "Low Block": 0.00,
        },
    },
    "AMF": {
        "Shadow Striker": {
            "Control Possession": 0.45, "Gegenpressing": 0.55, "Direct Play": 0.40,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.70, "Counter Attack": 0.85,
            "Wing Play": 0.35, "Low Block": 0.05,
        },
        "Advanced Playmaker": {
            "Control Possession": 0.95, "Gegenpressing": 0.60, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 1.00, "Counter Attack": 0.30,
            "Wing Play": 0.45, "Low Block": 0.00,
        },
        "Enganche": {
            "Control Possession": 0.90, "Gegenpressing": 0.25, "Direct Play": 0.10,
            "Defensive Counter Attack": 0.05, "Tiki Taka": 0.95, "Counter Attack": 0.20,
            "Wing Play": 0.30, "Low Block": 0.00,
        },
        "Trequartista": {
            "Control Possession": 0.65, "Gegenpressing": 0.25, "Direct Play": 0.25,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.85, "Counter Attack": 0.55,
            "Wing Play": 0.65, "Low Block": 0.00,
        },
    },
    "CM": {
        "Box-To-Box Midfielder": {
            "Control Possession": 0.55, "Gegenpressing": 0.90, "Direct Play": 0.40,
            "Defensive Counter Attack": 0.35, "Tiki Taka": 0.40, "Counter Attack": 0.80,
            "Wing Play": 0.60, "Low Block": 0.20,
        },
        "Carrilero": {
            "Control Possession": 0.75, "Gegenpressing": 0.70, "Direct Play": 0.25,
            "Defensive Counter Attack": 0.25, "Tiki Taka": 0.55, "Counter Attack": 0.35,
            "Wing Play": 0.75, "Low Block": 0.05,
        },
        "Ball Winning Midfielder (Defend)": {
            "Control Possession": 0.35, "Gegenpressing": 0.95, "Direct Play": 0.45,
            "Defensive Counter Attack": 0.75, "Tiki Taka": 0.20, "Counter Attack": 0.65,
            "Wing Play": 0.25, "Low Block": 0.80,
        },
        "Central Midfielder (Support)": {
            "Control Possession": 0.70, "Gegenpressing": 0.60, "Direct Play": 0.50,
            "Defensive Counter Attack": 0.45, "Tiki Taka": 0.55, "Counter Attack": 0.45,
            "Wing Play": 0.50, "Low Block": 0.35,
        },
        "Advanced Playmaker (Attack)": {
            "Control Possession": 0.85, "Gegenpressing": 0.55, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.95, "Counter Attack": 0.30,
            "Wing Play": 0.50, "Low Block": 0.05,
        },
        "Advanced Playmaker (Support)": {
            "Control Possession": 0.88, "Gegenpressing": 0.58, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.12, "Tiki Taka": 0.92, "Counter Attack": 0.32,
            "Wing Play": 0.48, "Low Block": 0.05,
        },
        "Mezzala": {
            "Control Possession": 0.55, "Gegenpressing": 0.75, "Direct Play": 0.25,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.70, "Counter Attack": 0.45,
            "Wing Play": 0.80, "Low Block": 0.05,
        },
    },
    "DMF": {
        "Regista": {
            "Control Possession": 0.95, "Gegenpressing": 0.45, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.15, "Tiki Taka": 1.00, "Counter Attack": 0.20,
            "Wing Play": 0.45, "Low Block": 0.05,
        },
        "Deep Lying Playmaker": {
            "Control Possession": 0.95, "Gegenpressing": 0.45, "Direct Play": 0.35,
            "Defensive Counter Attack": 0.40, "Tiki Taka": 0.95, "Counter Attack": 0.25,
            "Wing Play": 0.20, "Low Block": 0.30,
        },
        "Half Back": {
            "Control Possession": 0.85, "Gegenpressing": 0.60, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.70, "Tiki Taka": 0.70, "Counter Attack": 0.20,
            "Wing Play": 0.10, "Low Block": 0.40,
        },
        "Anchor": {
            "Control Possession": 0.55, "Gegenpressing": 0.45, "Direct Play": 0.35,
            "Defensive Counter Attack": 0.90, "Tiki Taka": 0.20, "Counter Attack": 0.35,
            "Wing Play": 0.10, "Low Block": 0.95,
        },
        "Segundo Volante": {
            "Control Possession": 0.65, "Gegenpressing": 0.85, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.45, "Counter Attack": 0.70,
            "Wing Play": 0.35, "Low Block": 0.05,
        },
        "Ball Winning Midfielder": {
            "Control Possession": 0.35, "Gegenpressing": 0.95, "Direct Play": 0.45,
            "Defensive Counter Attack": 0.75, "Tiki Taka": 0.20, "Counter Attack": 0.65,
            "Wing Play": 0.25, "Low Block": 0.80,
        },
        "Roaming Playmaker": {
            "Control Possession": 0.85, "Gegenpressing": 0.70, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.85, "Counter Attack": 0.40,
            "Wing Play": 0.45, "Low Block": 0.10,
        },
    },
    "CB": {
        "Wide Centre-Back (LCB)": {
            "Control Possession": 0.70, "Gegenpressing": 0.80, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.65, "Counter Attack": 0.35,
            "Wing Play": 0.60, "Low Block": 0.10,
        },
        "No-Nonsense Centre-Back": {
            "Control Possession": 0.15, "Gegenpressing": 0.30, "Direct Play": 0.90,
            "Defensive Counter Attack": 0.95, "Tiki Taka": 0.05, "Counter Attack": 0.55,
            "Wing Play": 0.20, "Low Block": 0.95,
        },
        "Ball Playing Defender": {
            "Control Possession": 0.95, "Gegenpressing": 0.70, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.15, "Tiki Taka": 0.95, "Counter Attack": 0.20,
            "Wing Play": 0.25, "Low Block": 0.05,
        },
        "Wide Centre-Back (RCB)": {
            "Control Possession": 0.70, "Gegenpressing": 0.80, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.65, "Counter Attack": 0.35,
            "Wing Play": 0.60, "Low Block": 0.10,
        },
        "Libero": {
            "Control Possession": 0.90, "Gegenpressing": 0.60, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.90, "Counter Attack": 0.25,
            "Wing Play": 0.35, "Low Block": 0.05,
        },
    },
    "LB": {
        "No-Nonsense Full-Back": {
            "Control Possession": 0.20, "Gegenpressing": 0.35, "Direct Play": 0.75,
            "Defensive Counter Attack": 0.90, "Tiki Taka": 0.10, "Counter Attack": 0.40,
            "Wing Play": 0.35, "Low Block": 0.95,
        },
        "Full-Back": {
            "Control Possession": 0.65, "Gegenpressing": 0.45, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.75, "Tiki Taka": 0.35, "Counter Attack": 0.25,
            "Wing Play": 0.45, "Low Block": 0.80,
        },
        "Complete Wing-Back": {
            "Control Possession": 0.70, "Gegenpressing": 0.75, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.70, "Counter Attack": 0.35,
            "Wing Play": 1.00, "Low Block": 0.00,
        },
        "Wing-Back": {
            "Control Possession": 0.60, "Gegenpressing": 0.75, "Direct Play": 0.35,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.45, "Counter Attack": 0.40,
            "Wing Play": 0.95, "Low Block": 0.10,
        },
        "Inverted Wing-Back": {
            "Control Possession": 0.90, "Gegenpressing": 0.75, "Direct Play": 0.10,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.95, "Counter Attack": 0.15,
            "Wing Play": 0.40, "Low Block": 0.00,
        },
        "Inverted Full-Back": {
            "Control Possession": 0.88, "Gegenpressing": 0.65, "Direct Play": 0.10,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.88, "Counter Attack": 0.15,
            "Wing Play": 0.25, "Low Block": 0.10,
        },
    },
    "RB": {
        "Full-Back": {
            "Control Possession": 0.65, "Gegenpressing": 0.45, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.75, "Tiki Taka": 0.35, "Counter Attack": 0.25,
            "Wing Play": 0.45, "Low Block": 0.80,
        },
        "Complete Wing-Back": {
            "Control Possession": 0.70, "Gegenpressing": 0.75, "Direct Play": 0.30,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.70, "Counter Attack": 0.35,
            "Wing Play": 1.00, "Low Block": 0.00,
        },
        "Wing-Back": {
            "Control Possession": 0.60, "Gegenpressing": 0.75, "Direct Play": 0.35,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.45, "Counter Attack": 0.40,
            "Wing Play": 0.95, "Low Block": 0.10,
        },
        "Inverted Full-Back": {
            "Control Possession": 0.88, "Gegenpressing": 0.65, "Direct Play": 0.10,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.88, "Counter Attack": 0.15,
            "Wing Play": 0.25, "Low Block": 0.10,
        },
        "Inverted Wing-Back": {
            "Control Possession": 0.90, "Gegenpressing": 0.75, "Direct Play": 0.10,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.95, "Counter Attack": 0.15,
            "Wing Play": 0.40, "Low Block": 0.00,
        },
        "No-Nonsense Full-Back": {
            "Control Possession": 0.20, "Gegenpressing": 0.35, "Direct Play": 0.75,
            "Defensive Counter Attack": 0.90, "Tiki Taka": 0.10, "Counter Attack": 0.40,
            "Wing Play": 0.35, "Low Block": 0.95,
        },
    },
    "RW": {
        "Winger (Support)": {
            "Control Possession": 0.40, "Gegenpressing": 0.50, "Direct Play": 0.80,
            "Defensive Counter Attack": 0.25, "Tiki Taka": 0.30, "Counter Attack": 0.80,
            "Wing Play": 1.00, "Low Block": 0.05,
        },
        "Inverted Winger": {
            "Control Possession": 0.80, "Gegenpressing": 0.70, "Direct Play": 0.25,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.85, "Counter Attack": 0.40,
            "Wing Play": 0.55, "Low Block": 0.00,
        },
        "Advanced Playmaker (Attack)": {
            "Control Possession": 0.85, "Gegenpressing": 0.55, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.95, "Counter Attack": 0.30,
            "Wing Play": 0.50, "Low Block": 0.05,
        },
        "Inside Forward": {
            "Control Possession": 0.55, "Gegenpressing": 0.70, "Direct Play": 0.55,
            "Defensive Counter Attack": 0.15, "Tiki Taka": 0.55, "Counter Attack": 0.75,
            "Wing Play": 0.45, "Low Block": 0.00,
        },
        "Winger (Defend)": {
            "Control Possession": 0.25, "Gegenpressing": 0.70, "Direct Play": 0.55,
            "Defensive Counter Attack": 0.55, "Tiki Taka": 0.15, "Counter Attack": 0.55,
            "Wing Play": 0.85, "Low Block": 0.40,
        },
        "Advanced Playmaker (Support)": {
            "Control Possession": 0.88, "Gegenpressing": 0.58, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.12, "Tiki Taka": 0.92, "Counter Attack": 0.32,
            "Wing Play": 0.48, "Low Block": 0.05,
        },
    },
    "LW": {
        "Advanced Playmaker (Support)": {
            "Control Possession": 0.88, "Gegenpressing": 0.58, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.12, "Tiki Taka": 0.92, "Counter Attack": 0.32,
            "Wing Play": 0.48, "Low Block": 0.05,
        },
        "Winger (Support)": {
            "Control Possession": 0.40, "Gegenpressing": 0.50, "Direct Play": 0.80,
            "Defensive Counter Attack": 0.25, "Tiki Taka": 0.30, "Counter Attack": 0.80,
            "Wing Play": 1.00, "Low Block": 0.05,
        },
        "Winger (Defend)": {
            "Control Possession": 0.25, "Gegenpressing": 0.70, "Direct Play": 0.55,
            "Defensive Counter Attack": 0.55, "Tiki Taka": 0.15, "Counter Attack": 0.55,
            "Wing Play": 0.85, "Low Block": 0.40,
        },
        "Inverted Winger": {
            "Control Possession": 0.80, "Gegenpressing": 0.70, "Direct Play": 0.25,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.85, "Counter Attack": 0.40,
            "Wing Play": 0.55, "Low Block": 0.00,
        },
        "Advanced Playmaker (Attack)": {
            "Control Possession": 0.85, "Gegenpressing": 0.55, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.95, "Counter Attack": 0.30,
            "Wing Play": 0.50, "Low Block": 0.05,
        },
        "Trequartista (Support)": {
            "Control Possession": 0.65, "Gegenpressing": 0.25, "Direct Play": 0.25,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.85, "Counter Attack": 0.55,
            "Wing Play": 0.65, "Low Block": 0.00,
        },
        "Inside Forward (Attack)": {
            "Control Possession": 0.55, "Gegenpressing": 0.70, "Direct Play": 0.55,
            "Defensive Counter Attack": 0.15, "Tiki Taka": 0.55, "Counter Attack": 0.75,
            "Wing Play": 0.45, "Low Block": 0.00,
        },
    },
    "GK": {
        "Goalkeeper (Defend)": {
            "Control Possession": 0.20, "Gegenpressing": 0.30, "Direct Play": 0.55,
            "Defensive Counter Attack": 0.75, "Tiki Taka": 0.10, "Counter Attack": 0.40,
            "Wing Play": 0.20, "Low Block": 0.95,
        },
        "Sweeper Keeper (Balanced)": {
            "Control Possession": 0.75, "Gegenpressing": 0.80, "Direct Play": 0.20,
            "Defensive Counter Attack": 0.20, "Tiki Taka": 0.75, "Counter Attack": 0.25,
            "Wing Play": 0.15, "Low Block": 0.10,
        },
        "Sweeper Keeper (Build-Up)": {
            "Control Possession": 0.95, "Gegenpressing": 0.75, "Direct Play": 0.10,
            "Defensive Counter Attack": 0.10, "Tiki Taka": 0.95, "Counter Attack": 0.10,
            "Wing Play": 0.10, "Low Block": 0.05,
        },
        "Goalkeeper (Ball-Playing)": {
            "Control Possession": 0.90, "Gegenpressing": 0.65, "Direct Play": 0.15,
            "Defensive Counter Attack": 0.15, "Tiki Taka": 0.85, "Counter Attack": 0.15,
            "Wing Play": 0.10, "Low Block": 0.10,
        },
    },
}


# =========================================================================
# Position normalisation (impact_model_v4.1.py lines 909-942, verbatim)
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


def normalise_position(pos: Any) -> Any:
    """Verbatim port of impact_model_v4.1.py's `normalise_position` (line 939)."""
    if pd.isna(pos):
        return pos
    return POSITION_NORMALISATION.get(str(pos).strip(), str(pos).strip())


# =========================================================================
# Team style vector + role demand (impact_model_v4.1.py lines 2342-2413)
# =========================================================================
def standardize_team_style_columns(team_styles_df: pd.DataFrame) -> pd.DataFrame:
    """Verbatim port (line 2342)."""
    team_styles_df = team_styles_df.copy()
    for old_name, new_name in STYLE_ALIASES.items():
        if old_name in team_styles_df.columns and new_name not in team_styles_df.columns:
            team_styles_df = team_styles_df.rename(columns={old_name: new_name})
    return team_styles_df


def normalize_series(s: pd.Series) -> pd.Series:
    """Verbatim port (line 2349). NOTE: this is the source's own zero-fill
    behaviour (`fillna(0.0)`) -- kept faithful here for use as a general
    numeric-vector normalizer; the all-NaN-club-styles case is intercepted
    *before* this is called in `calculate_subjective_role_fit_for_player_to_team`
    (see APPLIED_FIXES) so the zero-fill never silently reaches a Role Fit
    Score.
    """
    s = pd.to_numeric(s, errors="coerce").fillna(0.0).clip(lower=0.0)
    total = s.sum()
    if total == 0:
        return pd.Series([0.0] * len(s), index=s.index)
    return s / total


def normalize_role_vector_from_row(player_row: pd.Series, position: str) -> pd.Series:
    """Verbatim port (line 2356)."""
    role_cols = ROLE_COLUMNS_BY_POSITION.get(position, [])
    existing = [r for r in role_cols if r in player_row.index]

    if not existing:
        return pd.Series(dtype=float)

    vals = pd.Series(
        {role: pd.to_numeric(player_row.get(role, 0), errors="coerce") for role in existing}
    )
    vals = vals.fillna(0.0).clip(lower=0.0)

    total = vals.sum()
    if total == 0:
        return pd.Series([0.0] * len(existing), index=existing)

    return vals / total


def build_team_style_vector(team_row: pd.Series) -> pd.Series:
    """Verbatim port (line 2372). See APPLIED_FIXES -- callers must guard
    against an all-NaN `team_row` before invoking this, or downstream demand/
    overlap math will silently treat "unknown style" as "zero style"."""
    raw = pd.Series(
        {style: pd.to_numeric(team_row.get(style, 0), errors="coerce") for style in STYLE_COLUMNS}
    )
    return normalize_series(raw)


def compute_team_role_demand(position: str, team_style_vector: pd.Series) -> pd.Series:
    """Verbatim port (line 2376)."""
    role_map = ROLE_STYLE_WEIGHTS.get(position, {})
    if not role_map:
        return pd.Series(dtype=float)

    demand = {}
    for role, style_weight_map in role_map.items():
        role_weights = pd.Series(style_weight_map).reindex(STYLE_COLUMNS).fillna(0.0)
        demand[role] = float((team_style_vector * role_weights).sum())

    demand = pd.Series(demand)
    demand = normalize_series(demand)
    return demand


def sharpen_distribution(series_like: pd.Series, power: float = 2.0) -> pd.Series:
    """Verbatim port (line 2390)."""
    s = pd.to_numeric(series_like, errors="coerce").fillna(0.0).clip(lower=0.0)

    if s.sum() == 0:
        return s

    s = s**power
    total = s.sum()

    if total == 0:
        return s * 0.0

    return s / total


def weighted_overlap_score(
    player_role_vector: pd.Series, team_role_demand: pd.Series, power: float = 2.0
) -> float:
    """Verbatim port (line 2405)."""
    common_roles = sorted(set(player_role_vector.index).intersection(team_role_demand.index))
    if not common_roles:
        return 0.0

    p = sharpen_distribution(player_role_vector[common_roles], power=power)
    t = sharpen_distribution(team_role_demand[common_roles], power=power)

    return float(np.minimum(p, t).sum() * 100)


def get_top_roles_string(series_like: pd.Series, top_n: int = 3, multiply_100: bool = True) -> str:
    """Verbatim port (line 2415)."""
    if len(series_like) == 0:
        return ""
    top_items = series_like.sort_values(ascending=False).head(top_n).items()
    out = []
    for name, val in top_items:
        score = val * 100 if multiply_100 else val
        out.append(f"{name}: {round(score, 2)}")
    return " | ".join(out)


def get_top_roles_relative_to_best(series_like: pd.Series, top_n: int = 3) -> str:
    """Verbatim port (line 2425)."""
    if len(series_like) == 0:
        return ""

    s = pd.to_numeric(series_like, errors="coerce").fillna(0.0)
    s = s.sort_values(ascending=False).head(top_n)

    if s.empty:
        return ""

    best = float(s.iloc[0])
    if best <= 0:
        return " | ".join([f"{name}: 0.0" for name in s.index])

    out = []
    for name, val in s.items():
        relative_score = (float(val) / best) * 100
        out.append(f"{name}: {round(relative_score, 2)}")

    return " | ".join(out)


_BLANK_ROLE_FIT_RESULT = {
    "Role Fit Score": np.nan,
    "Best Team Fit Role": "",
    "Top Team Fit Roles": "",
    "Top Team Demanded Roles": "",
    "Player Top Roles Detailed": "",
}


def calculate_subjective_role_fit_for_player_to_team(
    player_row: pd.Series, target_team: str, team_styles_df: pd.DataFrame
) -> dict[str, Any]:
    """Faithful port of impact_model_v4.1.py def@2446.

    Returns a dict with "Role Fit Score" (0-100, higher = better fit) plus
    descriptive fields. "Role Fit Score" is NaN (not 0.0) when: the player's
    Main_Position isn't in ROLE_COLUMNS_BY_POSITION, the target club can't be
    matched in `team_styles_df`, the player has no scored roles for their
    position, OR (APPLIED_FIXES) the matched club's playing-style vector is
    entirely NaN -- the source silently zero-fills that last case; this port
    does not.
    """
    position = normalise_position(player_row.get("Main_Position", player_row.get("Position", "")))

    if position not in ROLE_COLUMNS_BY_POSITION:
        return dict(_BLANK_ROLE_FIT_RESULT)

    team_styles_df = standardize_team_style_columns(team_styles_df)

    team_match = team_styles_df[
        team_styles_df["Team"].astype(str).str.strip().str.lower() == str(target_team).strip().lower()
    ]

    if team_match.empty:
        return dict(_BLANK_ROLE_FIT_RESULT)

    team_row = team_match.iloc[0]

    # APPLIED_FIXES: guard against the source's silent zero-fill of an
    # all-NaN club style vector (see module docstring / APPLIED_FIXES[0]).
    raw_styles = pd.to_numeric(team_row.reindex(STYLE_COLUMNS), errors="coerce")
    if raw_styles.isna().all():
        return dict(_BLANK_ROLE_FIT_RESULT)

    player_role_vector = normalize_role_vector_from_row(player_row, position)
    if player_role_vector.empty:
        return dict(_BLANK_ROLE_FIT_RESULT)

    team_style_vector = build_team_style_vector(team_row)
    team_role_demand = compute_team_role_demand(position, team_style_vector)

    if team_role_demand.empty:
        return dict(_BLANK_ROLE_FIT_RESULT)

    role_fit_score = weighted_overlap_score(player_role_vector, team_role_demand, power=2.0)

    aligned = (player_role_vector * team_role_demand).sort_values(ascending=False)
    best_fit_role = aligned.index[0] if len(aligned) else ""
    top_fit_roles = get_top_roles_relative_to_best(aligned, top_n=3)
    top_team_demanded_roles = get_top_roles_string(team_role_demand, top_n=3, multiply_100=True)
    player_top_roles = get_top_roles_string(player_role_vector, top_n=3, multiply_100=True)

    return {
        "Role Fit Score": round(role_fit_score, 2),
        "Best Team Fit Role": best_fit_role,
        "Top Team Fit Roles": top_fit_roles,
        "Top Team Demanded Roles": top_team_demanded_roles,
        "Player Top Roles Detailed": player_top_roles,
    }


# =========================================================================
# Compatibility Score assembly (impact_model_v4.1.py lines 3798-3802)
# =========================================================================
def _clip_score(x: Any, low: float = 0.0, high: float = 100.0) -> float:
    """Verbatim port of the local `_clip_score` closure (line 3315)."""
    try:
        if pd.isna(x):
            return np.nan
        return float(np.clip(float(x), low, high))
    except Exception:
        return np.nan


def _avg_non_null(values: list[Any]) -> float:
    """Verbatim port of the local `_avg_non_null` closure (line 3323)."""
    vals = [float(v) for v in values if pd.notna(v)]
    return round(sum(vals) / len(vals), 2) if vals else np.nan


def compatibility_score(role_fit_score: float, similarity_pct: float, bonus: float) -> float:
    """Faithful port of the "Compatibility Score" assembly (line 3798-3802):

        compatibility_score = _avg_non_null([
            clip(role_fit_score), clip(similarity_pct), bonus,
        ])

    `bonus` is the 100.0/70.0 "does the club's best-fit role match this
    player's own best role" term computed by the caller (`compute_cs_tp_for_pairs`
    in deterministic_scores.py) -- it is passed in here, not recomputed,
    keeping this function a pure faithful port of the 3-term average.
    """
    return _avg_non_null([_clip_score(role_fit_score), _clip_score(similarity_pct), bonus])


def get_player_own_best_role(player_row: pd.Series, position: str) -> tuple[str | None, float]:
    """Faithful port of get_role_scores_from_dataset / extract_playing_style_from_dataset
    (identical duplicates, def@1055/def@3133/def@3120), narrowed to what
    compute_cs_tp_for_pairs needs: the player's own top-scoring role (for the
    Compatibility Score bonus term) and that top score (the `role_pct`
    upstream feature).

    See APPLIED_FIXES -- NaN role-score cells are excluded rather than
    zero-filled; if a player has no role scores at all for their position,
    returns (None, np.nan), not (None, 0.0).
    """
    role_cols = ROLE_COLUMNS_BY_POSITION.get(position, [])
    scores = {
        role: pd.to_numeric(player_row.get(role), errors="coerce")
        for role in role_cols
        if role in player_row.index
    }
    scores = {role: val for role, val in scores.items() if pd.notna(val)}

    if not scores:
        return None, np.nan

    best_role = max(scores, key=scores.get)
    return best_role, float(scores[best_role])
