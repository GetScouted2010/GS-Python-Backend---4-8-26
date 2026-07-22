---
phase: 03-scoring-engine-curation-correctness-oracle
plan: 07
subsystem: scoring-oracle-curation-map
tags: [oracle-snapshot, curation-map, rmm, compatibility-score, tfm, transfer-probability, cross-plan-wiring]
requires:
  - phase: 03-scoring-engine-curation-correctness-oracle
    plan: "02"
    provides: DUPLICATE_FUNCTIONS.md (18 mechanically-resolved duplicate-name decisions)
  - phase: 03-scoring-engine-curation-correctness-oracle
    plan: "03"
    provides: ESCALATION_REVIEW.md (2 human-reviewed 4-definition decisions)
  - phase: 03-scoring-engine-curation-correctness-oracle
    plan: "04"
    provides: impact.compute_rmm_column (RMM / Player Impact)
  - phase: 03-scoring-engine-curation-correctness-oracle
    plan: "05"
    provides: deterministic_scores.compute_cs_tp_for_pairs (Compatibility Score / Transfer Probability)
  - phase: 03-scoring-engine-curation-correctness-oracle
    plan: "06"
    provides: tfm_model.build_transfer_value_dataset + train_transfer_value_model + the trained joblib artifact
provides:
  - scoring/oracle/scoring_oracle_v1_<date>.csv (full-population correctness oracle, Phase 3 Success Criterion 2)
  - scoring/oracle/MANIFEST.md (snapshot version/commit/row-count/per-score context)
  - scoring/docs/CURATION_MAP.md (master per-score curation map, Phase 3 Success Criterion 4)
  - tfm_model.build_oracle_player_features (new, per-player TFM feature builder for scoring outside a matched-transfer-event context)
  - management command generate_scoring_oracle
affects:
  - Phase 4 (production port) reads CURATION_MAP.md as the function/column map
  - Phase 5 (parity testing) diffs the port's output against scoring_oracle_v1_<date>.csv
tech-stack:
  added: []
  patterns:
    - "Cross-plan feature merge order: RMM (player_impact) merged onto players_df FIRST, then compatibility_score/performance_score/role_pct, THEN the TFM feature build reads players_df -- same order train_tfm_model.py (Plan 06) established"
    - "Oracle convenience wrappers live alongside their source characterization module (compute_rmm_column in impact.py, compute_cs_tp_for_pairs in deterministic_scores.py, build_oracle_player_features in tfm_model.py) rather than in the command file, keeping the command a thin orchestrator"
    - "Per-player (not per-matched-transfer-event) TFM feature construction: build_oracle_player_features reproduces build_transfer_value_dataset's club-aggregate engineering keyed to each player's CURRENT club as buying+selling context"
key-files:
  created:
    - get-scouted-be/scoring/management/commands/generate_scoring_oracle.py
    - get-scouted-be/scoring/oracle/MANIFEST.md
    - get-scouted-be/scoring/oracle/scoring_oracle_v1_2026-07-22.csv
    - get-scouted-be/scoring/docs/CURATION_MAP.md
    - get-scouted-be/scoring/tests/test_oracle_snapshot.py
  modified:
    - get-scouted-be/scoring/characterization/tfm_model.py (added build_oracle_player_features)
decisions:
  - "TFM oracle predictions use the player's CURRENT club as both buying-club and selling-club aggregate context (there is no real transfer event for a player who isn't moving) -- a documented approximation per build_oracle_player_features's docstring, not a fabricated value; genuinely missing club-history data still flows into the fitted Pipeline's SimpleImputer as NaN"
  - "TFM predictions are only computed for players with a resolvable current club (_has_club_context); every real player in this dataset has one (Player.club is always populated post-Phase-1-import), so tfm is non-null for all 41,708 rows in this run -- the NaN-guard exists for correctness, not because it currently excludes anyone"
  - "Oracle CSV is committed to the repo (not gitignored, unlike the TFM joblib artifact) since 03-CONTEXT.md's Oracle Snapshot Scope explicitly requires it versioned in the repo as Phase 5's ground truth"
metrics:
  duration_minutes: 35
  tasks_completed: 2
  files_created: 5
  files_modified: 1
  completed: 2026-07-22
---

# Phase 3 Plan 07: Oracle Snapshot + Master Curation Map Summary

Ran the curated RMM/CS/TFM/Transfer-Probability calculators together over the full reconstructed
41,708-real-player population to produce a single versioned correctness-oracle CSV, and
consolidated every duplicate-function decision, cross-score wiring note, and applied fix from
Plans 02-06 into one master `CURATION_MAP.md` — completing Phase 3's two headline deliverables.

## What Was Built

**Task 1 — `generate_scoring_oracle` command.** Reconstructs the full population
(`build_players_df`/`build_role_scores_wide`/`build_team_styles_df`/`build_transfers_df`), then
explicitly wires the cross-plan features in the required order: `impact.compute_rmm_column` is
computed first and merged onto `players_df` as `player_impact` BEFORE
`deterministic_scores.compute_cs_tp_for_pairs` runs (Performance Score's 20% RMM term would
otherwise read NaN); `compatibility_score`/`performance_score`/`role_pct` are then merged back
onto `players_df` BEFORE the TFM feature build runs (3 of TFM's 4 cross-plan features would
otherwise be silently excluded by its own `[c for c in feature_cols if c in model_df.columns]`
filter). This mirrors the exact merge order `train_tfm_model.py` (Plan 06) established.

TFM needed new machinery: `build_transfer_value_dataset` only produces a feature row per matched
historical transfer *event*, not per player, so it can't answer "what's this player worth" for a
player who was never actually transferred. Added `tfm_model.build_oracle_player_features`
(new, not a port) — reproduces the same club-aggregate engineering (arrivals/departures profiles,
position buy/sell profiles) `build_transfer_value_dataset` computes internally, but keys the
lookup to each player's *current* club as both buying- and selling-club context, and returns one
row per `player_id`. The command loads the trained artifact's `.metrics.json` sidecar for its
exact `feature_cols`, predicts `predicted_fee` for every player, and masks predictions to NaN for
any player with no resolvable club context (none exist in this dataset, but the guard is
correctness-motivated, not currently load-bearing).

The command writes `scoring/oracle/scoring_oracle_v1_<date>.csv` (7 columns exactly: `player_id`,
`player_name`, `main_position`, `rmm`, `cs`, `tfm`, `transfer_probability`) and
`scoring/oracle/MANIFEST.md` (snapshot version, git commit, row count, sklearn version, artifact
filename, per-score population/context notes with exclusion counts).

Ran against the full real dataset: **41,708 rows**. RMM non-null 41,707/41,708 (99.998%, matching
Plan 04's earlier finding). Compatibility Score / Transfer Probability non-null 15,051/41,708
(36.1%) — `unresolved_role_fit` (26,657, mostly clubs with all-NaN playing-style vectors) and 1
`nan_player_impact` account for the rest; never zero-filled. TFM non-null for all 41,708 (every
real player has a `Player.club` FK, so `_has_club_context` is always true in this dataset).

**Task 2 — master `CURATION_MAP.md`.** Per-score sections (RMM, Compatibility Score, Financial
Fit/TFM, Transfer Probability) each listing authoritative functions with source line numbers,
input columns, and whether the score needs whole-dataset context (RMM and TFM: yes, via
`groupby`-based percentiles/club aggregates; Compatibility Score: yes, via club/role lookups;
Transfer Probability: no, row-local given its inputs) — plus an explicit cross-score data-flow
note (`player_impact` → Performance Score/TFM; `compatibility_score`/`performance_score`/
`role_pct` → TFM). Also folds in: the resolved TFM/Transfer-Probability score-to-artifact mapping
(copied from 03-CONTEXT.md, with rationale); the 2 escalated duplicate-function decisions
(`prepare_team_and_transfer_signal`@12192, `player_transfer_history`@12329, cross-referenced to
`DUPLICATE_FUNCTIONS.md`/`ESCALATION_REVIEW.md` rather than duplicated); an aggregated
"Fixes applied" table (6 entries pulled from `impact.py`/`role_fit.py`/`deterministic_scores.py`/
`tfm_model.py`'s `APPLIED_FIXES` lists); and the 2 open Phase-4 forks (Compatibility Score's
legacy-vs-fresh source fork; RMM's Player-Impact-vs-Performance-Score primitive choice) —
documented, not resolved, per this plan's scope.

## Deviations from Plan

### Auto-fixed Issues

None — no bugs or blocking issues were hit during execution; both tasks matched the plan's
described interfaces and cross-plan wiring contracts exactly (the pre-existing
`compute_rmm_column`/`compute_cs_tp_for_pairs`/`build_transfer_value_dataset` functions from
Plans 04-06 all had the exact signatures this plan's read_first block described).

### Notable observation (not a fix, out of this plan's narrow scope)

During the real-data run, sklearn's `SimpleImputer` warned
`Skipping features without any observed values: ['from_league_weight']` while training/predicting
— the trained artifact's `from_league_weight` feature apparently had zero non-null values in the
actual historical-transfer training data (a pre-existing Plan 06 characteristic of the real
`transfers_df`'s `League` string formatting vs. `LEAGUE_WEIGHTS`' keys, not something this plan's
code introduced or is in scope to fix per the deviation rules' scope boundary). Logged here for
visibility; not a blocker for the oracle snapshot (TFM predictions are still non-null for every
player since `SimpleImputer` gracefully no-ops on that one feature).

## Self-Check

- `get-scouted-be/scoring/management/commands/generate_scoring_oracle.py` — FOUND
- `get-scouted-be/scoring/oracle/MANIFEST.md` — FOUND
- `get-scouted-be/scoring/oracle/scoring_oracle_v1_2026-07-22.csv` — FOUND
- `get-scouted-be/scoring/docs/CURATION_MAP.md` — FOUND
- `get-scouted-be/scoring/tests/test_oracle_snapshot.py` — FOUND
- Commit `41a72c9` (Task 1) — FOUND
- Commit `8286b25` (Task 2) — FOUND
- `cd get-scouted-be && ./.venv/bin/pytest scoring/tests/test_oracle_snapshot.py -x -q` — exits 0 (1 passed, 1 skipped)
- `cd get-scouted-be && ./.venv/bin/pytest scoring/tests/ -q` — exits 0 (31 passed, 7 skipped)
- `cd get-scouted-be && ./.venv/bin/python manage.py generate_scoring_oracle --help` — exits 0

## Self-Check: PASSED

## Verification Against Plan's `<verification>` Block

- `./.venv/bin/pytest scoring/tests/ -q` (full phase suite) passes — 31 passed, 7 skipped (skips
  are the same real-data-DB skip pattern every other Phase 3 plan's tests use; pytest's isolated
  test database has no seeded Player rows, matching the established `real_data_available` fixture
  convention).
- Oracle CSV exists with 7 columns and 41,708 rows (~41,708 target, exact match); MANIFEST.md
  records `snapshot_version: v1` + per-score context.
- CURATION_MAP.md covers all 4 scores + duplicate decisions + fixes + open forks (277 lines, well
  over the 80-line minimum).

All four Phase 3 Success Criteria are now satisfied: (1) duplicate catalogue with authoritative
versions (Plans 02+03), (2) versioned full-population oracle snapshot (this plan), (3) sklearn TFM
component separated and versioned (Plan 06), (4) written curation map (this plan).
