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


@pytest.mark.django_db
def test_build_players_df_excludes_denormalized_output_fields(real_data_available):
    df = build_players_df()
    leaked = {"impact_score", "compatibility_score",
              "financial_fit_score", "transfer_probability_score"} & set(df.columns)
    assert not leaked, f"denormalized OUTPUT fields leaked into reconstruction: {leaked}"


@pytest.mark.django_db
def test_cs_tp_merge_stays_single_compatibility_score_column(real_data_available):
    import pandas as pd
    players_df = build_players_df()
    # cs_tp-shaped frame exactly as compute_cs_tp_for_pairs returns before
    # generate_scoring_oracle.py:177 / financial_fit.py:57 merge it back on.
    cs_tp = pd.DataFrame(
        {"player_id": players_df["player_id"], "compatibility_score": 1.0}
    )
    merged = players_df.merge(cs_tp, on="player_id", how="left")
    assert "compatibility_score" in merged.columns
    assert "compatibility_score_x" not in merged.columns
    assert "compatibility_score_y" not in merged.columns
    # single, unsuffixed column -> generate_scoring_oracle.py:215's
    # players_df[[..., "compatibility_score"]] and tfm_model.py:799's
    # `col in players.columns` both stay correct post-migration.
    assert list(merged.columns).count("compatibility_score") == 1
