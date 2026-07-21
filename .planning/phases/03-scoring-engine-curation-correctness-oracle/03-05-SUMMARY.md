---
phase: 03-scoring-engine-curation-correctness-oracle
plan: 05
subsystem: scoring
tags: [pandas, characterization, compatibility-score, transfer-probability, deterministic-formula]

# Dependency graph
requires:
  - phase: 03-01
    provides: reconstruct.py's ORM->script-shaped DataFrame bridge (build_players_df, build_role_scores_wide, build_team_styles_df, assert_columns_present)
provides:
  - "role_fit.py: calculate_subjective_role_fit_for_player_to_team (faithful port of def@2446) + compatibility_score() (the line 3798-3802 _avg_non_null assembly) + get_player_own_best_role (role_pct/bonus support)"
  - "deterministic_scores.py: contract_fit(), financial_score(), performance_score(), transfer_probability() (the deterministic, non-ML 0.30/0.20/0.20/0.30 weighted formula, confirmed NOT the RandomForestRegressor) + compute_cs_tp_for_pairs() cross-plan wiring contract"
  - "compute_cs_tp_for_pairs(players_df, team_styles_df, role_scores_wide, club_context, player_impact) -> per-player compatibility_score/financial_score/performance_score/contract_fit/role_pct/transfer_probability, keyed by player_id"
affects: [03-06, 03-07, phase-04-scoring-engine-port]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "APPLIED_FIXES module-level list documenting every deviation from a byte-literal source port, with the exact source zero-fill chain traced and why it's wrong"
    - "NaN propagation over zero-fill: unresolved club/role-fit/player_impact forces dependent scores to NaN via explicit checks, not left to _avg_non_null's own bonus-only fallback"
    - "Cross-plan wiring via explicit required parameters (player_impact) rather than in-function recomputation, so Plan 04's RMM stays the single source of truth"

key-files:
  created:
    - get-scouted-be/scoring/characterization/role_fit.py
    - get-scouted-be/scoring/characterization/deterministic_scores.py
    - get-scouted-be/scoring/tests/test_deterministic_scores.py
  modified: []

key-decisions:
  - "Compatibility Score's role-fit team-style guard: an all-NaN club playing-style vector now returns NaN Role Fit Score instead of the source's silent zero-fill (build_team_style_vector -> normalize_series fillna(0.0) chain), which deterministically produced a confidently-wrong 0.0 fit for the ~77%-null-styles case"
  - "compute_cs_tp_for_pairs's similarity_pct term is always NaN (Similarity To Target Player % requires the full target-team-players-pool machinery, out of this plan's read_first scope) -- correctly excluded by _avg_non_null rather than fabricated"
  - "performance_score() takes only player_impact as its required anchor; the team/target percentile terms (Perf vs Team/Own/Target %, Impact Delta vs Team Avg) are optional NaN-default kwargs since they need the league-wide POSITION_METRICS machinery this plan doesn't port -- callers may wire them in later without changing the function's shape"
  - "Financial Score's avg_age/avg_mv baseline uses the target club's CURRENT squad (players_df grouped by Team) instead of the source's transfer-arrivals history (club_transfer_profile), because compute_cs_tp_for_pairs's plan-defined signature omits transfers_df -- documented as an APPLIED_FIXES entry, not a silent substitution"
  - "contract_fit(years_left=NaN) returns 0.5, matching the source's own except-based fallback for unparseable contract data (not a zero-fill this port introduces)"
  - "ROLE_COLUMNS_BY_POSITION is imported from reconstruct.py rather than redefined a third time, since the two existing copies (source script, reconstruct.py's validation copy) were verified identical -- avoids adding another 'authoritative duplicate' instance"

patterns-established:
  - "compute_cs_tp_for_pairs emits result.attrs['exclusion_counts'] (no_club / unresolved_role_fit / nan_player_impact) as a diagnostic side-channel, keeping the DataFrame return contract itself unchanged for Plan 06/07 consumers"

requirements-completed: []

# Metrics
duration: 25min
completed: 2026-07-21
---

# Phase 03 Plan 05: Compatibility Score + Deterministic Transfer Probability Summary

**Faithful pandas port of Compatibility Score's role-fit engine and the confirmed-deterministic (no ML) Transfer Probability weighted formula, with an explicit player_impact wiring point for Plan 04's RMM.**

## Performance

- **Duration:** ~25 min
- **Tasks:** 2
- **Files modified:** 3 (2 created characterization modules, 1 test file)

## Accomplishments

- `role_fit.py`: verbatim port of `calculate_subjective_role_fit_for_player_to_team` (def@2446), `weighted_overlap_score`, `compute_team_role_demand`, `build_team_style_vector`, the full `ROLE_STYLE_WEIGHTS`/`STYLE_COLUMNS` config, and `compatibility_score()` (the line 3798-3802 `_avg_non_null` assembly)
- Guarded the silent zero-fill bug: a club whose playing-style vector is entirely NaN now returns NaN Role Fit Score, not a confidently-wrong 0.0 (traced the full `build_team_style_vector -> normalize_series -> compute_team_role_demand -> weighted_overlap_score` chain to confirm the source's actual zero-fill behavior before fixing it)
- `deterministic_scores.py`: `transfer_probability()` implements the exact `0.30*compat + 0.20*perf + 0.20*financial + 0.30*contract_fit` formula (line 3809-3814) -- confirmed via 03-CONTEXT.md's resolved Score-to-Artifact mapping to be deterministic arithmetic, NOT the RandomForestRegressor (that's Plan 06's TFM artifact)
- `performance_score()` takes Plan 04's Player Impact (RMM) as a required explicit input; NaN `player_impact` propagates to NaN performance_score and NaN transfer_probability, proven by a dedicated test
- `compute_cs_tp_for_pairs()`: the cross-plan wiring contract emitting per-player `compatibility_score`/`financial_score`/`performance_score`/`contract_fit`/`role_pct`/`transfer_probability`, keyed by player_id, that Plan 06's feature recipe and Plan 07's oracle both merge onto `players_df`
- 11 tests: hand-computed Role Fit Score, all-NaN-styles guard, Compatibility Score assembly, exact Transfer Probability arithmetic, contract_fit band boundaries (including the already-expired quirk preserved verbatim), no-sklearn-import assertion, player_impact-NaN-propagation, and an end-to-end `compute_cs_tp_for_pairs` synthetic case

## Task Commits

1. **Task 1: Faithful role-fit port (Compatibility Score component)** - `d6b8b62` (feat)
2. **Task 2: Deterministic Transfer Probability + Financial/Performance components** - `c586883` (feat)

## Files Created/Modified

- `get-scouted-be/scoring/characterization/role_fit.py` - `calculate_subjective_role_fit_for_player_to_team`, role-fit config (`ROLE_STYLE_WEIGHTS`, `STYLE_COLUMNS`, `POSITION_NORMALISATION`), `compatibility_score()`, `get_player_own_best_role()`, `APPLIED_FIXES`
- `get-scouted-be/scoring/characterization/deterministic_scores.py` - `contract_fit()`, `financial_score()`, `performance_score()`, `transfer_probability()`, `compute_cs_tp_for_pairs()`, `APPLIED_FIXES`
- `get-scouted-be/scoring/tests/test_deterministic_scores.py` - 11 tests across both modules

## Decisions Made

See `key-decisions` in frontmatter. The most consequential: the all-NaN-club-styles guard (prevents a systematic ~77%-of-clubs bias toward artificially low Role Fit Scores) and the explicit `player_impact` NaN-propagation contract (prevents Performance Score/Transfer Probability from silently reporting a misleadingly-confident score for players RMM couldn't be computed for).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] All-NaN club playing-style vector silently zero-filled in the source, corrected to NaN**
- **Found during:** Task 1 (reading impact_model_v4.1.py lines 2342-2413 per read_first)
- **Issue:** `build_team_style_vector` -> `normalize_series` (`fillna(0.0)`) -> `compute_team_role_demand` -> `weighted_overlap_score` chain deterministically produces Role Fit Score == 0.0 for any club with no Playstyles.csv coverage (~77% of clubs, FIELD_MAPPING.md section 3) -- a confidently-wrong "zero fit" instead of "unknown fit"
- **Fix:** Added an explicit guard in `calculate_subjective_role_fit_for_player_to_team`: if the matched club's STYLE_COLUMNS values are entirely NaN, return the same blank/NaN result dict already used for the source's other early-exit branches (unmatched position/team/empty role vector)
- **Files modified:** get-scouted-be/scoring/characterization/role_fit.py
- **Verification:** `test_calculate_subjective_role_fit_all_nan_club_styles_yields_nan_not_zero` passes
- **Committed in:** d6b8b62 (Task 1 commit)

**2. [Rule 2 - Missing Critical] get_role_scores_from_dataset's NaN-cell zero-fill excluded instead**
- **Found during:** Task 2 (needed the player's own best-role/score for the Compatibility Score bonus term and the `role_pct` upstream feature)
- **Issue:** the source's `float(row.get(role, 0))` only substitutes 0 when a column is entirely ABSENT, not when a wide-pivoted role-score cell is present-but-NaN (a player simply not scored on that role) -- an unguarded NaN reaching `max(scores, key=scores.get)` produces undefined ordering
- **Fix:** `get_player_own_best_role` explicitly excludes NaN role-score cells before taking the max, returning `(None, np.nan)` rather than `(None, 0.0)` when no role has a real value
- **Files modified:** get-scouted-be/scoring/characterization/role_fit.py
- **Verification:** `test_get_player_own_best_role_excludes_nan_not_zero_fill` passes
- **Committed in:** d6b8b62 (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 2 - Missing Critical, preventing silent zero-fill bugs that would systematically bias scores)
**Impact on plan:** Both fixes are directly aligned with the plan's own must_haves ("NaN club styles left as NaN, not zero-filled") and this project's core "no silent zero-fill" rule (CONCERNS.md). No scope creep.

## Issues Encountered

`compute_cs_tp_for_pairs`'s plan-defined signature (`players_df, team_styles_df, role_scores_wide, club_context, player_impact`) omits `transfers_df`, which the source's Financial Score baseline (avg_age/avg_mv from transfer-arrivals history via `club_transfer_profile`) depends on. Resolved by baselining against the target club's current squad (from `players_df`) instead -- a documented adaptation (APPLIED_FIXES), not a silent substitution; `financial_score()` itself (the pure 2-term average) is an exact port. Similarly, Compatibility Score's `similarity_pct` term (player-to-target-player cosine similarity) and Performance Score's team/target percentile terms both require machinery explicitly out of this plan's `read_first` scope (`calculate_player_to_team_player_similarity` and the `external_target_shortlist_absolute_vectorized` league-wide POSITION_METRICS percentiles, respectively) -- both are wired as NaN-excluded-from-average terms with docstrings explaining exactly what's missing and why, so a later phase can supply them without changing either function's contract.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `role_fit.py` and `deterministic_scores.py` are ready for Plan 06 (`build_transfer_value_dataset` feature recipe) and Plan 07 (correctness-oracle snapshot generator) to import `compute_cs_tp_for_pairs` alongside Plan 04's `impact.compute_rmm_column`
- The CS source-fork (legacy `PlayerClubCompatibility.score` vs. this plan's fresh role-fit computation) remains open for Phase 4 to resolve per 03-RESEARCH.md -- this plan characterizes the script's fresh computation only, as directed
- Flagged for Phase 4/5: the two scope gaps documented above (similarity_pct, performance percentile terms, financial-score baseline source) should be revisited once Plan 06/07 need real similarity/percentile-driven parity against the original script's full shortlist output

---
*Phase: 03-scoring-engine-curation-correctness-oracle*
*Completed: 2026-07-21*

## Self-Check: PASSED

All created files verified present on disk; both task commits (`d6b8b62`, `c586883`) verified present in git history.
