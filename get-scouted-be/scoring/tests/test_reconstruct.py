"""Tests for scoring.characterization.reconstruct against REAL migrated data.

Per 03-VALIDATION.md "Wave 0 Requirements", this phase's characterization
tests exercise the actual Phase 1-migrated Postgres dataset (41,708 players /
230,139 role scores / 1,060 clubs / 47,201 transfers as of the full-scale
import) rather than factory_boy fixtures -- the whole point is proving the
ORM->DataFrame bridge holds up against the real shape of the data, warts
included. `real_data_available` skips cleanly if the dev DB is empty.
"""

import pytest

from scoring.characterization.reconstruct import (
    build_players_df,
    build_role_scores_wide,
    build_team_styles_df,
    build_transfers_df,
)


@pytest.mark.django_db
def test_build_players_df_has_join_key_and_minutes(real_data_available):
    df = build_players_df()

    assert "player_id" in df.columns
    assert "Minutes" in df.columns
    assert not df.empty


@pytest.mark.django_db
def test_build_role_scores_wide_one_row_per_player_multiple_roles(real_data_available):
    wide = build_role_scores_wide()

    assert "player_id" in wide.columns
    assert wide["player_id"].is_unique

    role_columns = [c for c in wide.columns if c != "player_id"]
    assert len(role_columns) > 1


@pytest.mark.django_db
def test_build_team_styles_df_preserves_nan_no_silent_zero_fill(real_data_available):
    df = build_team_styles_df()

    style_columns = [c for c in df.columns if c != "Team"]
    # ~77% of clubs have no Playstyles.csv coverage (FIELD_MAPPING.md
    # section 3) -- at least one style value must be NaN, proving
    # build_team_styles_df never .fillna(0)'d the gap away.
    assert df[style_columns].isna().any().any()


@pytest.mark.django_db
def test_build_transfers_df_has_required_columns(real_data_available):
    df = build_transfers_df()

    for col in ["Player", "Year", "Fee", "Dealing_Club"]:
        assert col in df.columns
    assert not df.empty
