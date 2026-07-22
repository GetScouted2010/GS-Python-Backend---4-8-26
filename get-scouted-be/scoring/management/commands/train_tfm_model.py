"""Train and version the Financial Fit (TFM) sklearn artifact
(03-06-PLAN.md).

Reconstructs real migrated Postgres data into the script-shaped DataFrames
`tfm_model.build_transfer_value_dataset` expects, explicitly merges in the
4 cross-plan feature columns the 33-feature recipe needs --
`player_impact` (Plan 04's `impact.compute_rmm_column`) and
`compatibility_score`/`performance_score`/`role_pct` (Plan 05's
`deterministic_scores.compute_cs_tp_for_pairs`) -- BEFORE calling
`build_transfer_value_dataset`, so the source's own
`[c for c in feature_cols if c in model_df.columns]` filter does not
silently drop them (03-06-PLAN.md's central cross-plan wiring concern).

Trains the exact-recipe RandomForestRegressor Pipeline
(`tfm_model.train_transfer_value_model`), joblib-dumps the whole fitted
Pipeline as a versioned artifact, and writes a metrics sidecar JSON
explicitly labeling it TFM (Financial Fit) -- NOT Transfer Probability
(03-CONTEXT.md's resolved Score-to-Artifact Mapping) -- with the MAE/R²
recorded for reference (no minimum quality bar enforced per this plan).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import sklearn
from django.conf import settings
from django.core.management.base import BaseCommand

from scoring.characterization.deterministic_scores import compute_cs_tp_for_pairs
from scoring.characterization.impact import compute_rmm_column
from scoring.characterization.reconstruct import (
    build_players_df,
    build_role_scores_wide,
    build_team_styles_df,
    build_transfers_df,
)
from scoring.characterization.tfm_model import (
    build_transfer_value_dataset,
    train_transfer_value_model,
)

DEFAULT_ARTIFACT_PATH = Path(settings.BASE_DIR) / "scoring" / "ml_artifacts" / "tfm_value_model_v1.joblib"

# The 4 cross-plan feature columns the 33-feature recipe needs -- see
# module docstring / 03-06-PLAN.md "CROSS-PLAN FEATURE ORIGINS".
_CROSS_PLAN_FEATURE_COLUMNS = ["player_impact", "compatibility_score", "performance_score", "role_pct"]


class Command(BaseCommand):
    help = (
        "Reconstruct real transfer data, merge Plan 04's Player Impact (RMM) "
        "and Plan 05's Compatibility/Performance Score + role_pct onto "
        "players_df, train the faithful transfer-value RandomForestRegressor "
        "Pipeline (Financial Fit / TFM artifact -- NOT Transfer Probability), "
        "and joblib-dump the fitted pipeline as a versioned artifact with a "
        "metrics sidecar."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default=str(DEFAULT_ARTIFACT_PATH),
            help=(
                "Output path for the joblib artifact "
                f"(default: {DEFAULT_ARTIFACT_PATH})."
            ),
        )

    def handle(self, *args, **options):
        out_path = Path(options["out"])
        out_path.parent.mkdir(parents=True, exist_ok=True)

        self.stdout.write("Reconstructing real migrated data...")
        transfers_df = build_transfers_df()
        players_df = build_players_df()
        team_styles_df = build_team_styles_df()
        role_scores_wide = build_role_scores_wide()

        self.stdout.write("Merging Plan 04 Player Impact (RMM) onto players_df...")
        rmm = compute_rmm_column(players_df)
        players_df["player_impact"] = players_df["player_id"].map(rmm)

        self.stdout.write(
            "Merging Plan 05 Compatibility/Performance Score + role_pct "
            "onto players_df (per player vs. their current club)..."
        )
        cs_tp = compute_cs_tp_for_pairs(
            players_df,
            team_styles_df,
            role_scores_wide,
            club_context=None,
            player_impact=rmm,
        )
        players_df = players_df.merge(
            cs_tp[["compatibility_score", "performance_score", "role_pct"]].reset_index(),
            on="player_id",
            how="left",
        )

        missing = [c for c in _CROSS_PLAN_FEATURE_COLUMNS if c not in players_df.columns]
        if missing:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: cross-plan feature columns missing from players_df "
                    f"before build_transfer_value_dataset runs: {missing} -- the "
                    "33-feature recipe will silently drop these."
                )
            )

        self.stdout.write("Building the transfer-value dataset (33-feature recipe)...")
        model_df = build_transfer_value_dataset(transfers_df, players_df)
        self.stdout.write(f"model_df rows after fee/season filtering: {len(model_df)}")

        self.stdout.write("Training the RandomForestRegressor pipeline (random_state=42)...")
        pipeline, metrics = train_transfer_value_model(model_df)

        joblib.dump(pipeline, out_path)
        self.stdout.write(self.style.SUCCESS(f"Wrote TFM artifact: {out_path}"))

        metrics_path = out_path.with_suffix("").with_suffix(".metrics.json")
        metrics_payload = {
            "mae_money": metrics["mae_money"],
            "r2_log": metrics["r2_log"],
            "n_train": metrics["n_train"],
            "n_test": metrics["n_test"],
            "feature_cols": metrics["feature_cols"],
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "sklearn_version": sklearn.__version__,
            "source": "impact_model_v4.1.py train_transfer_value_model@5569",
            "score": "TFM (Financial Fit) -- NOT Transfer Probability",
        }
        with open(metrics_path, "w") as f:
            json.dump(metrics_payload, f, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Wrote metrics sidecar: {metrics_path}"))

        self.stdout.write(
            f"MAE (money-scale): {metrics['mae_money']:,.0f}  |  "
            f"R² (log-scale): {metrics['r2_log']:.3f}  |  "
            f"n_train={metrics['n_train']}  n_test={metrics['n_test']}"
        )
