---
phase: 03-scoring-engine-curation-correctness-oracle
plan: 06
subsystem: scoring
tags: [sklearn, random-forest, tfm, financial-fit, ml-artifact, joblib]

# Dependency graph
requires:
  - phase: 03-01
    provides: reconstruct.py's ORM->script-shaped DataFrame bridge (build_players_df, build_transfers_df)
  - phase: 03-04
    provides: impact.compute_rmm_column (Player Impact / RMM, merged in as player_impact)
  - phase: 03-05
    provides: deterministic_scores.compute_cs_tp_for_pairs (compatibility_score/performance_score/role_pct, merged onto players_df)
provides:
  - "tfm_model.py: verbatim ports of parse_money_to_numeric/safe_div/season_to_year/contract_to_years_left, build_transfer_value_dataset (line 4935, last-wins), train_transfer_value_model (line 5569), add_value_labels (line 5676)"
  - "train_tfm_model management command: reconstructs real data, explicitly merges Plan 04/05 cross-plan features onto players_df BEFORE build_transfer_value_dataset, trains the RF pipeline, joblib-dumps a versioned TFM artifact + metrics sidecar"
  - "get-scouted-be/scoring/ml_artifacts/tfm_value_model_v1.joblib + .metrics.json (gitignored build artifacts, regenerable via `manage.py train_tfm_model`)"
affects: [03-07, phase-04-scoring-engine-port, phase-05-scoring-parity-testing]

# Tech tracking
tech-stack:
  added: [scikit-learn, joblib]
  patterns:
    - "Cross-plan feature merge happens in the management command (Task 2), not inside build_transfer_value_dataset itself — keeps the faithful-port function signature unchanged while satisfying the 33-feature recipe's real preconditions"
    - "_OPTIONAL_PLAYER_COLUMNS name-adaptation table lets faithfully-ported code accept this project's real lowercase column names (player_impact, compatibility_score, ...) without changing any hyperparameter, threshold, or feature-selection logic"

key-files:
  created:
    - get-scouted-be/scoring/characterization/tfm_model.py
    - get-scouted-be/scoring/management/__init__.py
    - get-scouted-be/scoring/management/commands/__init__.py
    - get-scouted-be/scoring/management/commands/train_tfm_model.py
    - get-scouted-be/scoring/tests/test_tfm_model.py
  modified: []

key-decisions:
  - "RandomForestRegressor artifact is explicitly labeled TFM (Financial Fit), NOT Transfer Probability, per 03-CONTEXT.md's resolved Score-to-Artifact Mapping — the metrics.json sidecar's `score` field states this verbatim so no downstream consumer can misread it"
  - "Merge-column-name-collision quirk in the source's buy/sell club-profile merge sequence (pandas default _x/_y suffixing) is preserved unchanged per CONTEXT.md's don't-touch-non-bug-quirks rule — this is why not all 33 nominal feature names survive into model_df on real data (23/33 present in the actual training run; missing ones are club-level aggregate duplicates that lose their canonical name to the suffix collision, not silently dropped data)"
  - "Interface shape adapted from the source's (pipeline, model_df, feature_cols) return to (fitted_pipeline, metrics_dict) per this plan's explicit output contract — every hyperparameter, feature, and metric computation is unchanged"
  - "No zero-fill fixes were needed in this plan beyond column-naming adaptations — every feature absence is genuine 'column not present', handled identically to source (SimpleImputer for real per-row NaNs, silent exclusion from feature_cols for genuinely absent columns)"

patterns-established:
  - "Management commands that consume multiple prior plans' outputs do the explicit merge inline with an assert/warn guard (missing cross-plan columns triggers a stdout WARNING) rather than silently trusting upstream wiring"

requirements-completed: []

# Metrics
duration: ~20min (2 task commits) + wrap-up verification
completed: 2026-07-22
---

# Phase 03 Plan 06: TFM sklearn Training + Versioned Artifact Summary

**Faithful reproduction of the source script's RandomForestRegressor transfer-value model (the Financial Fit/TFM artifact, confirmed NOT Transfer Probability), with explicit cross-plan feature wiring from Plans 04 and 05, joblib-versioned for Phase 4+.**

## Performance

- **Duration:** ~20 min active work (2 task commits), plus this wrap-up session verifying and completing the plan record
- **Tasks:** 2
- **Files created:** 5

## Accomplishments

- `tfm_model.py`: verbatim ports of `parse_money_to_numeric` (13668), `safe_div` (13699), `season_to_year` (13705), `contract_to_years_left` (13716), `build_transfer_value_dataset` (4935, the authoritative last-wins def), `train_transfer_value_model` (5569), `add_value_labels` (5676) — every hyperparameter (`n_estimators=300, max_depth=12, min_samples_leaf=3, random_state=42, n_jobs=-1`), the 80/20 seeded split, and the full `LEAGUE_WEIGHTS` dict copied unchanged
- `train_tfm_model` management command: reconstructs real Postgres data, explicitly merges Plan 04's `compute_rmm_column` output and Plan 05's `compute_cs_tp_for_pairs` output onto `players_df` as `player_impact`/`compatibility_score`/`performance_score`/`role_pct` BEFORE calling `build_transfer_value_dataset` — the exact cross-plan wiring gap the plan-checker flagged as a blocker during planning, now implemented and verified end-to-end
- 30 tests pass (6 skip cleanly against the empty pytest-django test DB, matching this phase's established pattern) including a regression guard proving the 4 cross-plan columns survive into `model_df` when present
- **Verified against real data this session:** ran `manage.py train_tfm_model` against the live dev database. Result: 1,477 usable transfer rows after fee/season filtering, R²=0.921 (log-scale), MAE≈€2,343,934 (money-scale), 23/33 nominal features present in the final feature set (the other 10 are lost to the source's own preserved merge-suffix-collision quirk, not silently dropped). All 4 cross-plan features (`player_impact`, `compatibility_score`, `performance_score`, `role_pct`) confirmed present in the trained model's `feature_cols` — direct proof the wiring works, not just that it compiles.
- Artifact + metrics sidecar written to `get-scouted-be/scoring/ml_artifacts/tfm_value_model_v1.joblib` / `.metrics.json` (both correctly gitignored as regenerable build products — the `.gitkeep` keeps the directory tracked)

## Task Commits

1. **Task 1: Faithful transfer-value dataset builder + model trainer** — `75b71e9` (feat)
2. **Task 2: train_tfm_model management command → merge Plan 04/05 features → versioned joblib artifact + reload test** — `dbd15bf` (feat)

## Files Created/Modified

- `get-scouted-be/scoring/characterization/tfm_model.py` — `build_transfer_value_dataset`, `train_transfer_value_model`, `add_value_labels`, helper functions, `APPLIED_FIXES`
- `get-scouted-be/scoring/management/__init__.py`, `get-scouted-be/scoring/management/commands/__init__.py` — Django management-command package scaffolding
- `get-scouted-be/scoring/management/commands/train_tfm_model.py` — `Command` class: reconstruct → merge cross-plan features → train → joblib.dump → metrics sidecar
- `get-scouted-be/scoring/tests/test_tfm_model.py` — unit tests + `test_artifact_loads_and_predicts` + `test_metrics_are_finite`

## Decisions Made

See `key-decisions` in frontmatter. Most consequential: labeling the artifact TFM (not Transfer Probability) in the metrics sidecar itself, so the resolved mapping survives into every downstream consumer even if someone reads only the artifact directory and not the curation docs.

## Deviations from Plan

None requiring a fix — the plan's cross-plan wiring concern (the reason this plan depends on 04+05 and runs in wave 3) was implemented as specified in Task 2's action text.

## Issues Encountered

The original executor agent hit two API connection errors mid-session (infrastructure issue, not a task failure) — both task commits were already complete and correct when checked; this wrap-up session verified both commits' content directly, ran the full test suite (30 passed, 6 skipped), and additionally ran the real `manage.py train_tfm_model` command against live dev data to obtain actual MAE/R² numbers and confirm the cross-plan wiring holds outside of synthetic test fixtures.

## User Setup Required

None — `scikit-learn`/`joblib` were already added to `requirements/base.txt` and installed in Plan 03-01.

## Next Phase Readiness

- Plan 07 can now load `scoring/ml_artifacts/tfm_value_model_v1.joblib` for the oracle's `tfm` column, using the same merge pattern (`player_impact` → `compute_rmm_column`; CS/performance/role_pct → `compute_cs_tp_for_pairs`) already proven here
- Real MAE (€2.34M) / R² (0.921) recorded for Phase 5's parity-tolerance decision, per CONTEXT.md's "record for reference only, no minimum quality bar" instruction — R² is well above the "catastrophically negative" sanity-check threshold in 03-VALIDATION.md's manual verification item
- Phase 4's SCORE-03 port should load this artifact via `joblib.load`, not retrain it (03-CONTEXT.md: "NOT retrained per request or on-demand")

---
*Phase: 03-scoring-engine-curation-correctness-oracle*
*Completed: 2026-07-22*

## Self-Check: PASSED

Both task commits (`75b71e9`, `dbd15bf`) verified present in git history and content-reviewed directly. Full `scoring/` test suite green (30 passed, 6 skipped). Additionally verified by running the actual management command against live dev data: artifact + metrics sidecar written, all 4 cross-plan feature columns confirmed present in the trained model's feature set.
