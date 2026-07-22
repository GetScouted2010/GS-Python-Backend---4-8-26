---
phase: 03-scoring-engine-curation-correctness-oracle
verified: 2026-07-22T14:03:17Z
status: passed
score: 4/4 must-haves verified
---

# Phase 3: Scoring Engine Curation & Correctness Oracle Verification Report

**Phase Goal:** The authoritative logic inside the untested, duplicated 15,700-line scoring script is identified and characterized against real data before a single line is ported, so the port has a ground truth to be checked against.
**Verified:** 2026-07-22T14:03:17Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Phase Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Every function defined more than once in impact_model_v4.1.py is catalogued, with the authoritative (final) definition identified and documented. | VERIFIED | `scoring/docs/DUPLICATE_FUNCTIONS.md` lists all 20 duplicated names with kept/rejected lines and reasons (18 mechanically last-wins-resolved). `scoring/docs/ESCALATION_REVIEW.md` extracts all 4 bodies each of the 2 four-definition names with pairwise diffs and contains filled `DECISION: 12192` / `REASON: ...` and `DECISION: 12329` / `REASON: ...` (not placeholders — real, specific reasoning). `test_curation_map.py::test_duplicate_set_matches_source` independently re-derives the 20-name set from the source file and asserts it matches, guarding against drift. |
| 2 | Running the original script against the real migrated dataset produces a stored, versioned snapshot of its output (RMM, CS, TFM, Transfer Probability) for every position group. | VERIFIED | `scoring/oracle/scoring_oracle_v1_2026-07-22.csv` exists: 41,708 data rows (matches live `Player.objects.count()` exactly), columns exactly `player_id, player_name, main_position, rmm, cs, tfm, transfer_probability`. `scoring/oracle/MANIFEST.md` records `snapshot_version: v1`, git commit, row count, sklearn version, and per-score population/context/exclusion-count notes. |
| 3 | Non-deterministic/sklearn-trained components (e.g. Transfer Probability) are identified and separated from purely deterministic calculators, with handling documented. | VERIFIED | 03-CONTEXT.md's resolved mapping (RandomForestRegressor = TFM, NOT Transfer Probability) is implemented and documented: `scoring/characterization/deterministic_scores.py` contains zero `import sklearn`/`from sklearn` (grep-verified, and `test_no_sklearn_import` passes) and implements the exact deterministic formula (`0.30`/`0.20` weights present). `scoring/characterization/tfm_model.py` contains the faithfully-reproduced `RandomForestRegressor(n_estimators=300, max_depth=12, min_samples_leaf=3, random_state=42, ...)` pipeline. The trained artifact `scoring/ml_artifacts/tfm_value_model_v1.joblib` (6.99MB) exists on disk with a `.metrics.json` sidecar recording finite `mae_money`/`r2_log` and explicitly labeling itself "TFM (Financial Fit) -- NOT Transfer Probability". |
| 4 | A written curation map exists showing, per score, which original functions and columns feed it. | VERIFIED | `scoring/docs/CURATION_MAP.md` (278 lines) has a dedicated section per score (RMM, Compatibility Score, Financial Fit/TFM, Transfer Probability), each listing authoritative functions with source line numbers, input columns, whole-dataset-dependency notes, and cross-score data flow. It cross-references both `DUPLICATE_FUNCTIONS.md` and `ESCALATION_REVIEW.md`, includes a "Fixes applied" table aggregating all modules' `APPLIED_FIXES`, and documents 2 open forks for Phase 4. |

**Score:** 4/4 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scoring/characterization/reconstruct.py` | ORM→DataFrame bridge (4 builders + assert_columns_present) | VERIFIED | 410 lines. Contains `build_players_df`, `build_role_scores_wide`, `build_team_styles_df`, `build_transfers_df`, `assert_columns_present`. No `.fillna(0)` on the team-styles path (only a docstring mention that it deliberately does NOT do this). |
| `scoring/apps.py` | ScoringConfig | VERIFIED | Contains `class ScoringConfig`; `scoring` registered in `INSTALLED_APPS` (config/settings/base.py:40) and `testpaths` (pyproject.toml). `manage.py check` passes. |
| `requirements/base.txt` | scikit-learn + joblib pins | VERIFIED | `scikit-learn>=1.5,<2.0` and `joblib>=1.4,<2.0` present; both importable in venv (sklearn 1.9.0, joblib 1.5.3). |
| `scoring/docs/DUPLICATE_FUNCTIONS.md` | 20-name duplicate catalogue | VERIFIED | 84 lines; all 20 names present incl. `prepare_team_and_transfer_signal`; contains `ESCALATION PENDING`, `13733`+`required` (pick_first_existing signature-flip note), `financial_fit_label` under nested/out-of-scope section. |
| `scoring/docs/ESCALATION_REVIEW.md` | 4-way diffs + recorded DECISION/REASON | VERIFIED | 646 lines; both `DECISION:`/`REASON:` pairs filled with substantive, specific reasoning (12192 and 12329), not placeholder text; all 8 line-number anchors present. |
| `scoring/characterization/impact.py` | RMM calculators + add_player_impact | VERIFIED | 1039 lines. Contains `_build_std_lookup`, all 8 `_calc_*_impact_raw`, `add_player_impact`, `compute_rmm_column`, `APPLIED_FIXES` (1 real fix: Minutes-column-absent raises instead of zero-filling), `league_weights` preserved verbatim. |
| `scoring/characterization/role_fit.py` | Role-fit + Compatibility Score component | VERIFIED | 719 lines. Contains `calculate_subjective_role_fit_for_player_to_team`, `compatibility_score`, `APPLIED_FIXES` (NaN club styles → NaN, not zero). |
| `scoring/characterization/deterministic_scores.py` | Transfer Probability + CS/TP orchestrator | VERIFIED | 438 lines. Contains `transfer_probability`, `contract_fit`, `financial_score`, `performance_score`, `compute_cs_tp_for_pairs` (signature includes `player_impact`); no sklearn import; formula weights `0.30`/`0.20` present. |
| `scoring/characterization/tfm_model.py` | build_transfer_value_dataset + train_transfer_value_model | VERIFIED | 811 lines. Contains `RandomForestRegressor`, `Pipeline`, `ColumnTransformer`, exact hyperparameters, `APPLIED_FIXES`, plus `build_oracle_player_features` (new, for per-player oracle prediction). |
| `scoring/management/commands/train_tfm_model.py` | Training command → joblib artifact | VERIFIED | 144 lines. Contains `class Command`, `joblib.dump`, explicitly merges `compute_rmm_column`/`compute_cs_tp_for_pairs` outputs onto `players_df` before training; writes `.metrics.json` sidecar. `manage.py train_tfm_model --help` exits 0. |
| `scoring/ml_artifacts/tfm_value_model_v1.joblib` | Trained sklearn Pipeline | VERIFIED (on disk) | 6.99MB file present on disk (gitignored per `.gitignore`, regenerable via `manage.py train_tfm_model`). Sidecar `tfm_value_model_v1.metrics.json` present with finite `mae_money=2,343,934` and `r2_log=0.921`. |
| `scoring/management/commands/generate_scoring_oracle.py` | Full-population oracle generator | VERIFIED | 290 lines. Contains `class Command`, `compute_rmm_column`, explicit `player_impact` merge before CS/TFM steps, all 7 oracle columns referenced. `manage.py generate_scoring_oracle --help` exits 0. |
| `scoring/oracle/scoring_oracle_v1_2026-07-22.csv` | Versioned oracle snapshot | VERIFIED | 41,708 rows (matches live Player count exactly), exactly 7 columns as specified. |
| `scoring/oracle/MANIFEST.md` | Snapshot metadata | VERIFIED | Contains `snapshot_version`, commit hash, row count, per-score population/context notes with exclusion counts. |
| `scoring/docs/CURATION_MAP.md` | Master curation map | VERIFIED | 278 lines (> 80 min). Contains `RMM`, `Compatibility Score`, `Financial Fit`, `Transfer Probability` sections, `add_player_impact`, `RandomForestRegressor`, `3809`, resolved-mapping statement, references to both `DUPLICATE_FUNCTIONS` and `ESCALATION_REVIEW`, a "Fixes applied" table, and 2 open Phase-4 forks. |
| `scoring/tests/*.py` (6 test files) | Test coverage for all above | VERIFIED | 38 tests total: 31 passed, 7 skipped (skips are all due to pytest-django's isolated/empty test database — a documented, expected pattern via the `real_data_available` fixture; the actual dev DB has 41,708 real players and the oracle was generated against it). 0 failures. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `config/settings/base.py` | scoring app | INSTALLED_APPS entry | WIRED | `"scoring",` present at line 40 |
| `reconstruct.py` | Player/Club/Transfer ORM | `.objects.values()`/`.objects.all()` | WIRED | Confirmed in build_players_df/build_team_styles_df/build_transfers_df |
| `test_curation_map.py` | `DUPLICATE_FUNCTIONS.md` | file read + string assertions | WIRED | `test_all_20_names_present`, `test_duplicate_set_matches_source`, `test_two_escalations_flagged` all pass |
| `ESCALATION_REVIEW.md` | `DUPLICATE_FUNCTIONS.md` | escalation handoff reference | WIRED | Both docs cross-reference each other explicitly |
| `impact.py` | `reconstruct.build_players_df` | import + call (via compute_rmm_column consumers) | WIRED | `impact.py` imports `assert_columns_present` from reconstruct; `compute_rmm_column(players_df)` consumed by management commands |
| `deterministic_scores.py` | `role_fit.py` | import for compatibility component | WIRED | `role_fit.calculate_subjective_role_fit_for_player_to_team` used inside `compute_cs_tp_for_pairs` |
| `deterministic_scores.compute_cs_tp_for_pairs` | `impact.compute_rmm_column` | explicit `player_impact` series parameter | WIRED | grep confirms `player_impact=rmm` passed at both call sites (train_tfm_model.py, generate_scoring_oracle.py) |
| `train_tfm_model.py` | `impact.compute_rmm_column` + `deterministic_scores.compute_cs_tp_for_pairs` | merge onto players_df before build_transfer_value_dataset | WIRED | Lines 84-96: `rmm = compute_rmm_column(...)`, `players_df["player_impact"] = ...`, `cs_tp = compute_cs_tp_for_pairs(..., player_impact=rmm)` |
| `train_tfm_model.py` | `scoring/ml_artifacts/` | `joblib.dump` | WIRED | Artifact + metrics.json present on disk, dated 2026-07-22T13:09:29Z |
| `generate_scoring_oracle.py` | `compute_rmm_column`/`compute_cs_tp_for_pairs`/tfm artifact | full-population merge + predict | WIRED | Lines 155-215 confirm exact merge order (RMM first, then CS/perf/role_pct, then TFM) producing the 41,708-row CSV |
| `CURATION_MAP.md` | `DUPLICATE_FUNCTIONS.md` + `ESCALATION_REVIEW.md` | cross-reference | WIRED | Both filenames referenced explicitly in the "Resolved escalations" section |

### Requirements Coverage

Phase 3 owns no requirement IDs directly (confirmed consistent across all 7 plans' frontmatter, ROADMAP.md's phase note, and REQUIREMENTS.md's "Phase note" — all state Phase 3 is prerequisite risk-mitigation work enabling SCORE-01 through SCORE-07 in Phases 4-6). No orphaned requirements found for Phase 3 in REQUIREMENTS.md.

### Anti-Patterns Found

None. Scanned all characterization modules and management commands for TODO/FIXME/XXX/HACK/PLACEHOLDER/"not implemented" patterns — zero matches. All functions specified in plan `must_haves.artifacts.contains` fields are present with substantive bodies (438-1039 lines per module), not stubs.

### Human Verification Required

None required for this phase's automated deliverables. One item worth noting for awareness (not a gap): the Compatibility Score / Transfer Probability columns in the oracle are non-null for only 15,051/41,708 players (36%), because ~77% of clubs have null playing-style vectors in the source data (a real data-quality characteristic documented in FIELD_MAPPING.md §3 and correctly propagated as NaN, not zero-filled or fabricated). This is expected behavior per the phase's "never silently zero-fill" design and is explicitly recorded with exclusion counts in MANIFEST.md — flagged here only so Phase 4/5 readers are not surprised by the coverage rate.

### Gaps Summary

No gaps found. All 4 phase success criteria are verified against actual code and generated artifacts (not just SUMMARY claims): the duplicate-function catalogue is complete and independently regression-tested against the source file; the escalation decisions are genuinely filled in (not placeholders) with specific reasoning; the oracle snapshot exists with the exact expected row count and columns, matching the live database; the sklearn/deterministic split is correctly implemented and verified by a dedicated no-sklearn-import test; and the master curation map documents every score's functions, columns, fixes, and open forks, cross-referencing the other two audit docs. The full test suite (31 tests) passes with zero failures; the 7 skips are an expected and documented pattern (empty pytest-django test database) unrelated to the phase's real-data deliverables, which were verified directly against the actual generated files.

---

*Verified: 2026-07-22T14:03:17Z*
*Verifier: Claude (gsd-verifier)*
