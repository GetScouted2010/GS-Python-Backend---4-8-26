"""Tests for scoring/docs/DUPLICATE_FUNCTIONS.md, the duplicate-function catalogue.

Per 03-02-PLAN.md, this proves three things:

1. All 20 duplicated top-level names from `impact_model_v4.1.py` are catalogued.
2. The 20-name set independently recomputed from the source file matches the
   hardcoded catalogue set -- so if the source file ever changes, this test
   catches drift between the file and the catalogue, rather than silently
   trusting a stale document.
3. The two 4-definition names (`prepare_team_and_transfer_signal`,
   `player_transfer_history`) are explicitly flagged for escalation, not
   silently resolved.
"""

import re
from pathlib import Path

import pytest

# The verified 20-name inventory (03-RESEARCH.md "Full Duplicate-Function
# Inventory", also inlined in 03-02-PLAN.md's <interfaces> block).
EXPECTED_20_NAMES = {
    "prepare_team_and_transfer_signal",
    "player_transfer_history",
    "season_to_year",
    "safe_div",
    "player_transfer_summary",
    "pick_first_existing",
    "parse_money_to_numeric",
    "get_role_scores_from_dataset",
    "get_position_target_avg_cols",
    "get_position_delta_cols",
    "get_position_component_cols",
    "get_export_columns_for_position",
    "get_2425_transfers",
    "format_financial",
    "export_team_shortlist_xlsx",
    "contract_to_years_left",
    "classify_age_fit",
    "build_wim_player_list_from_players_df",
    "build_transfer_value_dataset",
    "build_general_market_shortlist",
}

# The two names with more than 2 definitions -- must be escalated, never
# mechanically resolved via last-wins.
ESCALATED_NAMES = {
    "prepare_team_and_transfer_signal",
    "player_transfer_history",
}

DUPLICATE_FUNCTIONS_MD = (
    Path(__file__).resolve().parents[1] / "docs" / "DUPLICATE_FUNCTIONS.md"
)


def _find_source_script():
    """Walk up from this file to find pixel-perfect-clone-60729/docs/impact_model_v4.1.py."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pixel-perfect-clone-60729" / "docs" / "impact_model_v4.1.py"
        if candidate.exists():
            return candidate
    return None


@pytest.fixture
def catalogue_text():
    if not DUPLICATE_FUNCTIONS_MD.exists():
        pytest.fail(f"DUPLICATE_FUNCTIONS.md not found at {DUPLICATE_FUNCTIONS_MD}")
    return DUPLICATE_FUNCTIONS_MD.read_text()


def test_all_20_names_present(catalogue_text):
    assert len(EXPECTED_20_NAMES) == 20

    missing = [name for name in EXPECTED_20_NAMES if name not in catalogue_text]
    assert not missing, f"DUPLICATE_FUNCTIONS.md is missing names: {missing}"


def test_duplicate_set_matches_source():
    source_path = _find_source_script()
    if source_path is None:
        pytest.skip(
            "pixel-perfect-clone-60729/docs/impact_model_v4.1.py not found relative to "
            "repo root -- cannot independently verify the duplicate set."
        )

    text = source_path.read_text()
    names = re.findall(r"^def (\w+)\(", text, flags=re.MULTILINE)

    counts = {}
    for name in names:
        counts[name] = counts.get(name, 0) + 1

    actual_duplicate_set = {name for name, count in counts.items() if count > 1}

    assert actual_duplicate_set == EXPECTED_20_NAMES, (
        "Duplicate-name set computed from impact_model_v4.1.py no longer matches the "
        "hardcoded 20-name catalogue -- the source file has drifted from "
        "DUPLICATE_FUNCTIONS.md and the catalogue needs to be regenerated.\n"
        f"In source but not catalogue: {actual_duplicate_set - EXPECTED_20_NAMES}\n"
        f"In catalogue but not source: {EXPECTED_20_NAMES - actual_duplicate_set}"
    )


def test_two_escalations_flagged(catalogue_text):
    assert "ESCALATION PENDING" in catalogue_text
    assert len(ESCALATED_NAMES) == 2

    for name in ESCALATED_NAMES:
        # Find every line mentioning the escalated name and confirm at least
        # one of them also carries the escalation marker (table row or
        # dedicated escalation section).
        lines_with_name = [
            line for line in catalogue_text.splitlines() if name in line
        ]
        assert lines_with_name, f"{name} not found anywhere in DUPLICATE_FUNCTIONS.md"

        flagged = any(
            "ESCALATION PENDING" in line or "ESCALATE" in line
            for line in lines_with_name
        )
        assert flagged, (
            f"{name} appears in DUPLICATE_FUNCTIONS.md but is never associated with an "
            "escalation marker on the same line."
        )
