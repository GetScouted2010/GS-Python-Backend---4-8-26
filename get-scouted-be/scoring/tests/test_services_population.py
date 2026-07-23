"""Tests for the shared population/scoring substrate (04-01-PLAN.md).

Every Phase 4 score service (compatibility, financial, performance,
transfer-probability, summary) reuses `reconstruct_population` +
`score_population` + `resolve_club_name` + `get_tfm_pipeline` +
`null_with_reason` from here instead of rebuilding the reconstruct -> RMM
-> Compatibility/Transfer-Probability wiring order or the missing-data
envelope shape themselves.

`resolve_club_name`/`reconstruct_population`/`score_population` need a real
migrated dataset -- `real_data_available` lets those tests skip cleanly
against an empty dev DB (same pattern as scoring/tests/test_reconstruct.py).
`null_with_reason` and `get_tfm_pipeline` are pure/artifact-only and need no
DB access.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from django.conf import settings
from django.http import Http404

from scoring.exceptions import null_with_reason
from scoring.services.population import (
    get_tfm_pipeline,
    reconstruct_population,
    resolve_club_name,
    score_population,
)


def test_null_with_reason_envelope_shape():
    assert null_with_reason("compatibility_score", "club_style_data_unavailable") == {
        "compatibility_score": None,
        "reason": "club_style_data_unavailable",
    }


@pytest.mark.django_db
def test_resolve_club_name_unknown_uuid_raises_http404():
    unknown_id = uuid.uuid4()

    with pytest.raises(Http404):
        resolve_club_name(unknown_id)


def test_get_tfm_pipeline_feature_cols_from_sidecar_and_memoized():
    metrics_path = (
        Path(settings.BASE_DIR) / "scoring" / "ml_artifacts" / "tfm_value_model_v1.metrics.json"
    )
    expected_feature_cols = json.loads(metrics_path.read_text())["feature_cols"]

    pipeline_first, feature_cols_first = get_tfm_pipeline()
    pipeline_second, feature_cols_second = get_tfm_pipeline()

    assert feature_cols_first == expected_feature_cols
    assert len(feature_cols_first) == 23
    # Memoized: repeated calls return the SAME pipeline object, not a fresh
    # joblib.load() each time.
    assert pipeline_first is pipeline_second


@pytest.mark.django_db
def test_reconstruct_population_returns_script_shaped_tables(real_data_available):
    pop = reconstruct_population()

    assert "player_id" in pop.players_df.columns
    assert "Team" in pop.players_df.columns
    assert not pop.players_df.empty

    assert "player_id" in pop.role_scores_wide.columns
    assert "Team" in pop.team_styles_df.columns
    assert not pop.transfers_df.empty


@pytest.mark.django_db
def test_score_population_rmm_first_wiring(real_data_available):
    pop = reconstruct_population()

    scored, cs_tp = score_population(pop, None)

    # RMM (add_player_impact) ran and produced the full breakdown, not just
    # the thin RMM value -- summary/RMM downstream services need this.
    assert "Player Impact" in scored.columns

    for col in [
        "compatibility_score",
        "financial_score",
        "performance_score",
        "contract_fit",
        "transfer_probability",
    ]:
        assert col in cs_tp.columns
    assert not cs_tp.empty

    # score_population never calls compute_cs_tp_for_pairs without
    # player_impact -- that function raises ValueError if player_impact is
    # None (see deterministic_scores.compute_cs_tp_for_pairs docstring). A
    # non-empty result reaching here proves the call didn't raise, i.e.
    # player_impact was supplied. The RMM-first merge additionally means at
    # least one real (non-NaN) performance_score comes through, not every
    # player collapsing to NaN as they would if player_impact were an
    # empty/all-missing series.
    assert cs_tp["performance_score"].notna().any()
