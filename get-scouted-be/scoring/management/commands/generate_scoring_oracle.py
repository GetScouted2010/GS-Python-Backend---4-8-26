"""Generate the correctness-oracle snapshot (03-07-PLAN.md Task 1) --
Phase 3 Success Criterion 2.

Runs the curated RMM (Plan 04), Compatibility Score/Transfer Probability
(Plan 05), and TFM (Plan 06) calculators TOGETHER over the full
reconstructed real-player population and writes a single versioned CSV:

    player_id, player_name, main_position, rmm, cs, tfm, transfer_probability

This is the convergence point (03-CONTEXT.md "Oracle Snapshot Scope") --
the ground truth Phase 5's parity tests diff the eventual production port
against. Column-merge order matters and is spelled out explicitly here,
following the same cross-plan wiring pattern `train_tfm_model.py`
(Plan 06) established:

    1. RMM (`impact.compute_rmm_column`) is computed FIRST and explicitly
       merged onto players_df as "player_impact" -- Performance Score
       (inside compute_cs_tp_for_pairs) and the TFM feature build both read
       this column and would silently see NaN across the whole population
       without this merge.
    2. Compatibility Score / Financial Score / Performance Score / role_pct
       / Transfer Probability (`deterministic_scores.compute_cs_tp_for_pairs`)
       are computed per player against their OWN CURRENT club
       (`club_context=None`), then compatibility_score/performance_score/
       role_pct are merged back onto players_df -- the TFM feature build
       reads these too.
    3. TFM (`tfm_model.build_oracle_player_features` + the joblib artifact)
       is computed last, once players_df carries all three upstream
       columns.

Never zero-fills: any player excluded from a score (no club, unresolved
role fit, missing artifact features) is left NaN in that column, never a
fabricated 0 -- consistent with every other module ported in this phase.
"""

from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from scoring.characterization.deterministic_scores import compute_cs_tp_for_pairs
from scoring.characterization.impact import compute_rmm_column
from scoring.characterization.reconstruct import (
    build_players_df,
    build_role_scores_wide,
    build_team_styles_df,
    build_transfers_df,
)
from scoring.characterization.tfm_model import build_oracle_player_features

ORACLE_DIR = Path(settings.BASE_DIR) / "scoring" / "oracle"
DEFAULT_ARTIFACT_PATH = Path(settings.BASE_DIR) / "scoring" / "ml_artifacts" / "tfm_value_model_v1.joblib"
MANIFEST_PATH = ORACLE_DIR / "MANIFEST.md"

ORACLE_COLUMNS = [
    "player_id",
    "player_name",
    "main_position",
    "rmm",
    "cs",
    "tfm",
    "transfer_probability",
]


def _git_commit_hash() -> str:
    try:
        return (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=settings.BASE_DIR)
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


class Command(BaseCommand):
    help = (
        "Run the curated RMM/CS/TFM/Transfer-Probability calculators over the "
        "full reconstructed real-player population and write a single "
        "versioned oracle CSV + MANIFEST.md (Phase 3 Success Criterion 2)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            default=None,
            help=(
                "Output CSV path (default: "
                "scoring/oracle/scoring_oracle_v1_<YYYY-MM-DD>.csv)."
            ),
        )
        parser.add_argument(
            "--artifact",
            default=str(DEFAULT_ARTIFACT_PATH),
            help=f"Path to the trained TFM joblib artifact (default: {DEFAULT_ARTIFACT_PATH}).",
        )

    def handle(self, *args, **options):
        ORACLE_DIR.mkdir(parents=True, exist_ok=True)

        artifact_path = Path(options["artifact"])
        metrics_path = artifact_path.with_suffix("").with_suffix(".metrics.json")
        if not artifact_path.exists():
            raise CommandError(
                f"No TFM artifact found at {artifact_path} -- run "
                "`python manage.py train_tfm_model` first to produce one."
            )
        pipeline = joblib.load(artifact_path)
        if metrics_path.exists():
            with open(metrics_path) as f:
                tfm_metrics = json.load(f)
            feature_cols = tfm_metrics.get("feature_cols", [])
            sklearn_version = tfm_metrics.get("sklearn_version", sklearn.__version__)
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: no metrics sidecar found at {metrics_path} -- "
                    "introspecting the fitted pipeline's preprocessor for "
                    "its expected feature columns instead."
                )
            )
            feature_cols = []
            for _, _, cols in pipeline.named_steps["preprocessor"].transformers_:
                if isinstance(cols, (list, tuple)):
                    feature_cols.extend(cols)
            sklearn_version = sklearn.__version__

        # =====================================================
        # 1. Reconstruct the full real population once.
        # =====================================================
        self.stdout.write("Reconstructing real migrated data...")
        players_df = build_players_df()
        role_scores_wide = build_role_scores_wide()
        team_styles_df = build_team_styles_df()
        transfers_df = build_transfers_df()
        total_players = len(players_df)
        self.stdout.write(f"players_df: {total_players} rows")

        # =====================================================
        # 2. RMM (Plan 04) -- computed first, explicitly merged onto
        #    players_df as player_impact BEFORE anything downstream reads
        #    it (Performance Score inside step 3, TFM features in step 4).
        # =====================================================
        self.stdout.write("Computing RMM (Player Impact) and merging onto players_df...")
        rmm = compute_rmm_column(players_df)
        players_df["player_impact"] = players_df["player_id"].map(rmm)

        # =====================================================
        # 3. Compatibility Score / Financial Score / Performance Score /
        #    role_pct / Transfer Probability (Plan 05) -- per player
        #    against their OWN current club. Merge compatibility_score/
        #    performance_score/role_pct back onto players_df (TFM feature
        #    build in step 4 reads these); keep the full cs_tp result
        #    around separately for the oracle's transfer_probability column.
        # =====================================================
        self.stdout.write(
            "Computing Compatibility Score / Transfer Probability per player "
            "vs. their own current club..."
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

        # =====================================================
        # 4. TFM (Plan 06) -- players_df now carries player_impact/
        #    compatibility_score/performance_score/role_pct. Build one
        #    feature row per player (current club as buying-club context)
        #    and predict.
        # =====================================================
        self.stdout.write("Building per-player TFM features (current club as buying context)...")
        oracle_features = build_oracle_player_features(players_df, transfers_df)

        missing_feature_cols = [c for c in feature_cols if c not in oracle_features.columns]
        if missing_feature_cols:
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: TFM feature columns the artifact expects are "
                    f"missing from oracle_features: {missing_feature_cols} -- "
                    "filling with NaN (SimpleImputer will impute)."
                )
            )
            for c in missing_feature_cols:
                oracle_features[c] = np.nan

        self.stdout.write("Predicting TFM (predicted_fee) per player...")
        X = oracle_features[feature_cols]
        predicted_fee = pd.Series(pipeline.predict(X), index=oracle_features.index)
        # Never fabricate a fee for a player we have no club context for --
        # a from-scratch prediction off an (almost) entirely-imputed row is
        # not an honest score (see build_oracle_player_features docstring).
        predicted_fee = predicted_fee.where(oracle_features["_has_club_context"], np.nan)

        # =====================================================
        # 5. Assemble the oracle DataFrame -- exactly these 7 columns.
        # =====================================================
        oracle_df = players_df[["player_id", "Player", "Main_Position", "player_impact", "compatibility_score"]].copy()
        oracle_df = oracle_df.rename(
            columns={
                "Player": "player_name",
                "Main_Position": "main_position",
                "player_impact": "rmm",
                "compatibility_score": "cs",
            }
        )
        oracle_df["tfm"] = oracle_df["player_id"].map(predicted_fee)
        oracle_df["transfer_probability"] = oracle_df["player_id"].map(cs_tp["transfer_probability"])
        oracle_df = oracle_df[ORACLE_COLUMNS]

        # =====================================================
        # 6. Write the versioned CSV.
        # =====================================================
        if options["out"]:
            out_path = Path(options["out"])
        else:
            out_path = ORACLE_DIR / f"scoring_oracle_v1_{date.today().isoformat()}.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        oracle_df.to_csv(out_path, index=False)
        self.stdout.write(self.style.SUCCESS(f"Wrote oracle snapshot: {out_path} ({len(oracle_df)} rows)"))

        # =====================================================
        # 7. Write/update MANIFEST.md.
        # =====================================================
        exclusion_counts = cs_tp.attrs.get("exclusion_counts", {})
        rmm_non_null = int(oracle_df["rmm"].notna().sum())
        cs_non_null = int(oracle_df["cs"].notna().sum())
        tfm_non_null = int(oracle_df["tfm"].notna().sum())
        tp_non_null = int(oracle_df["transfer_probability"].notna().sum())

        manifest = f"""# Scoring Oracle Snapshot -- MANIFEST

snapshot_version: v1

- Generated: {datetime.now(timezone.utc).isoformat()}
- Git commit: {_git_commit_hash()}
- Row count: {len(oracle_df)} (of {total_players} reconstructed players)
- Output file: `{out_path.relative_to(settings.BASE_DIR) if str(out_path).startswith(str(settings.BASE_DIR)) else out_path}`
- sklearn version: {sklearn_version}
- TFM artifact used: `{artifact_path.relative_to(settings.BASE_DIR) if str(artifact_path).startswith(str(settings.BASE_DIR)) else artifact_path}`

## Per-score population & context

- **RMM (`rmm`)**: context-free per player (`impact.compute_rmm_column`) --
  position-relative percentile of the player's own stats, no club
  comparison involved. Non-null for {rmm_non_null}/{len(oracle_df)} players.
  Never zero-filled -- a player excluded from a position group's percentile
  computation is left NaN.
- **Compatibility Score (`cs`)**: per player vs. their OWN CURRENT club
  (`Player.club` FK, `deterministic_scores.compute_cs_tp_for_pairs` with
  `club_context=None`). Non-null for {cs_non_null}/{len(oracle_df)} players.
  NaN (not 0) when the player has no club, the club's playing-style vector
  is entirely unknown, or the player's position has no role-score coverage
  -- exclusion counts from this run: `{exclusion_counts}`.
- **TFM (`tfm`)**: `predicted_fee` from the trained RandomForestRegressor
  Pipeline (Financial Fit, NOT Transfer Probability -- see
  `docs/CURATION_MAP.md`'s resolved mapping), evaluated per player with
  their CURRENT club as buying-club context
  (`tfm_model.build_oracle_player_features`). Non-null for
  {tfm_non_null}/{len(oracle_df)} players -- NaN for players with no
  resolvable current club (no real transfer-value context to price
  against), never a value fabricated from an all-imputed feature row.
- **Transfer Probability (`transfer_probability`)**: the fully
  deterministic weighted formula (0.30*Compatibility + 0.20*Performance +
  0.20*Financial + 0.30*contract_fit), evaluated per player vs. their own
  current club in the same `compute_cs_tp_for_pairs` call as Compatibility
  Score. Non-null for {tp_non_null}/{len(oracle_df)} players -- propagates
  to NaN whenever any of its inputs (including RMM via Performance Score)
  is NaN.
"""
        with open(MANIFEST_PATH, "w") as f:
            f.write(manifest)
        self.stdout.write(self.style.SUCCESS(f"Wrote manifest: {MANIFEST_PATH}"))
