"""Recompute the four own-club final scores for the whole population and
write them onto Player's denormalized fields (06-03-PLAN.md) -- the
SCORE-07 operator-triggered rebuild trigger.

Reuses `generate_scoring_oracle.py`'s proven RMM-first orchestration
EXACTLY (RMM computed first and merged onto players_df as `player_impact`
BEFORE `compute_cs_tp_for_pairs` runs -- that ordering is load-bearing,
`compute_cs_tp_for_pairs` raises `ValueError` if `player_impact` is
missing) but writes the result onto `Player.impact_score` /
`Player.compatibility_score` / `Player.financial_fit_score` /
`Player.transfer_probability_score` via a single atomic `bulk_update`,
instead of a CSV.

This follows the explicit-management-command convention Phase 1/Phase 3
already established (`import_all`, `generate_scoring_oracle`,
`train_tfm_model`) -- deliberately NOT Django signals, which
`bulk_create`/`bulk_update` never fire. Re-run this command whenever the
underlying data changes (a fresh Phase 1 import, a TFM retrain, etc); it
is the sole writer of the 4 denormalized fields (see
`players/migrations/0002_denormalized_scores.py` -- no RunPython backfill
there, all rows start NULL).

Money-scale note: the TFM pipeline's raw `predict()` output is LOG-SCALE
(matches the oracle CSV's `tfm` column, ~13.11-17.09) --
`financial_fit_score` MUST be `np.expm1(predicted_fee)` (see
`financial_fit.py:118`'s identical unwrap), never the raw log-scale value.

Never zero-fills: every NaN (no club, unresolved role fit, missing
club-aggregate context, ...) is written as a real SQL NULL via
`bulk_update`, never a fabricated 0 -- GK/LB/RB structurally have NULL
compatibility_score/transfer_probability_score (confirmed in Phase 5),
and this command must preserve that.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction

from players.models import Player
from players.season import scoring_groups
from scoring.characterization.deterministic_scores import compute_cs_tp_for_pairs
from scoring.characterization.impact import compute_rmm_column
from scoring.characterization.reconstruct import (
    build_players_df,
    build_role_scores_wide,
    build_team_styles_df,
    build_transfers_df,
)
from scoring.characterization.tfm_model import build_oracle_player_features
from scoring.services.population import clear_scoring_caches, get_tfm_pipeline, group_has_players


class Command(BaseCommand):
    help = (
        "Recompute the 4 own-club final scores (impact/compatibility/"
        "financial_fit/transfer_probability) for the whole population and "
        "bulk_update them onto Player's denormalized fields (SCORE-07)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="bulk_update batch size (default: 1000).",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]

        # Clear the Plan 02 in-process caches FIRST so this command reads
        # freshly-imported data, not a stale in-process cache left over
        # from a prior request in the same process.
        clear_scoring_caches()

        # One population at a time: each is percentile-ranked ONLY against
        # itself (players/season.py -- the legacy pool of older seasons, and
        # 2025-2026 on its own). Scoring one never moves another's numbers.
        pipeline, feature_cols = get_tfm_pipeline()
        objs = []
        for group in scoring_groups():
            if not group_has_players(group):
                self.stdout.write(f"[{group}] no players in this population yet -- skipped.")
                continue
            objs.extend(self._score_group(group, pipeline, feature_cols))

        # =====================================================
        # 6. Write via bulk_update inside a transaction -- atomic so a
        #    live request never observes a half-written intermediate
        #    state; it keeps reading the OLD denormalized values until the
        #    whole update commits.
        # =====================================================
        self.stdout.write(f"Writing {len(objs)} players via bulk_update (batch_size={batch_size})...")
        with transaction.atomic():
            Player.objects.bulk_update(
                objs,
                [
                    "impact_score",
                    "compatibility_score",
                    "financial_fit_score",
                    "transfer_probability_score",
                ],
                batch_size=batch_size,
            )

        # Clear the caches again so the next live request rebuilds the
        # in-process aggregate against the just-refreshed data.
        clear_scoring_caches()

        # =====================================================
        # 7. Report per-field non-null counts so the operator can eyeball
        #    that null-propagation happened, not silent zero-fill.
        # =====================================================
        impact_non_null = sum(o.impact_score is not None for o in objs)
        cs_non_null = sum(o.compatibility_score is not None for o in objs)
        fin_non_null = sum(o.financial_fit_score is not None for o in objs)
        tp_non_null = sum(o.transfer_probability_score is not None for o in objs)

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated {len(objs)} players.\n"
                f"  impact_score: {impact_non_null} non-null\n"
                f"  compatibility_score: {cs_non_null} non-null (GK/LB/RB null by design)\n"
                f"  financial_fit_score: {fin_non_null} non-null\n"
                f"  transfer_probability_score: {tp_non_null} non-null (GK/LB/RB null by design)"
            )
        )

    def _score_group(self, group, pipeline, feature_cols):
        """Score ONE population and return the unsaved Player objects
        carrying its four denormalized scores."""
        # =====================================================
        # 1. Reconstruct the full real population once.
        # =====================================================
        self.stdout.write(f"[{group}] Reconstructing real migrated data...")
        players_df = build_players_df(group)
        role_scores_wide = build_role_scores_wide(group)
        team_styles_df = build_team_styles_df()
        transfers_df = build_transfers_df()
        total_players = len(players_df)
        self.stdout.write(f"[{group}] players_df: {total_players} rows")

        # =====================================================
        # 2. RMM -- computed FIRST, merged onto players_df as
        #    player_impact BEFORE compute_cs_tp_for_pairs runs (that
        #    function raises ValueError if player_impact is missing --
        #    this ordering is load-bearing, never reorder it).
        # =====================================================
        self.stdout.write("Computing RMM (Player Impact)...")
        rmm = compute_rmm_column(players_df)
        players_df["player_impact"] = players_df["player_id"].map(rmm)

        # =====================================================
        # 3. Compatibility Score / Transfer Probability -- own current
        #    club (club_context=None), matching the oracle/Phase 5
        #    methodology.
        # =====================================================
        self.stdout.write(
            "Computing Compatibility Score / Transfer Probability per "
            "player vs. their own current club..."
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
        # 4. TFM (Financial Fit) -- players_df now carries player_impact/
        #    compatibility_score/performance_score/role_pct.
        # =====================================================
        self.stdout.write(f"[{group}] Building per-player TFM features (current club as buying context)...")
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
        # Never fabricate a fee for a player we have no club context for.
        predicted_fee = predicted_fee.where(oracle_features["_has_club_context"], np.nan)

        # Convert to MONEY-scale for the denormalized field
        # (financial_fit.py:118 precedent) -- the raw predict() output is
        # log-scale (matches the oracle's tfm column, ~13.11-17.09).
        # np.expm1(np.nan) is nan, so NaN stays NaN here.
        financial_money = np.expm1(predicted_fee)

        # =====================================================
        # 5. Assemble per-player values keyed by player_id (UUID). Both
        #    cs_tp and oracle_features/predicted_fee are indexed by
        #    player_id (see compute_cs_tp_for_pairs/build_oracle_player_features
        #    docstrings), matching players_df["player_id"].
        # =====================================================
        impact_by_pid = players_df.set_index("player_id")["player_impact"]
        cs_by_pid = cs_tp["compatibility_score"]
        tp_by_pid = cs_tp["transfer_probability"]
        fin_by_pid = financial_money

        objs = []
        for pid in players_df["player_id"]:
            impact_v = impact_by_pid.get(pid)
            cs_v = cs_by_pid.get(pid)
            fin_v = fin_by_pid.get(pid)
            tp_v = tp_by_pid.get(pid)
            objs.append(
                Player(
                    id=pid,
                    impact_score=None if pd.isna(impact_v) else float(impact_v),
                    compatibility_score=None if pd.isna(cs_v) else float(cs_v),
                    financial_fit_score=None if pd.isna(fin_v) else float(fin_v),
                    transfer_probability_score=None if pd.isna(tp_v) else float(tp_v),
                )
            )

        return objs
