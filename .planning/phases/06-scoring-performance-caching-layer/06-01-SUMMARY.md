---
phase: 06-scoring-performance-caching-layer
plan: 01
subsystem: database
tags: [django, postgres, migrations, pandas, denormalization]

# Dependency graph
requires:
  - phase: 05-scoring-parity-testing
    provides: verified-correct RMM/CS/TFM/TP scoring pipeline (service functions + oracle-parity tests)
provides:
  - "Player model with 4 nullable, indexed FloatFields: impact_score, compatibility_score, financial_fit_score, transfer_probability_score"
  - "Applied migration 0002_denormalized_scores adding the 4 columns + 3 descending-score indexes to players_player"
  - "build_players_df() hardened against the column-name collision the new fields introduce, with regression tests proving the fix"
affects: [06-02, 06-03, 06-04, 07-crud]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Denormalized-output-field exclusion set (_DENORMALIZED_SCORE_FIELDS) guarding dynamic Player._meta.fields enumeration in reconstruct.py"

key-files:
  created:
    - get-scouted-be/players/migrations/0002_denormalized_scores.py
  modified:
    - get-scouted-be/players/models.py
    - get-scouted-be/scoring/characterization/reconstruct.py
    - get-scouted-be/scoring/tests/test_reconstruct.py

key-decisions:
  - "transfer_probability_score left unindexed (display/grounding value, not a Phase 7 CRUD-01 sort/filter key; avoids slowing Plan 03's bulk_update write path)"
  - "No RunPython backfill in migration 0002 -- all 41,708 rows get NULL; Plan 03's recompute_scores command is the sole writer of real values"
  - "_DENORMALIZED_SCORE_FIELDS frozenset excludes the 4 new Player fields from build_players_df()'s dynamic field_names enumeration, since they are pipeline OUTPUTS never scoring INPUTS"

patterns-established:
  - "When denormalizing a scoring-pipeline OUTPUT onto a model that reconstruction code dynamically re-reads via Model._meta.fields, add an explicit exclusion set rather than relying on downstream merge/rename logic to paper over the collision"

requirements-completed: []  # SCORE-07 not marked complete here -- only satisfied once the full phase (all 4 plans + verifier) passes

# Metrics
duration: 7min
completed: 2026-07-24
---

# Phase 6 Plan 1: Denormalized Score Fields + Reconstruction Collision Fix Summary

**Added impact_score/compatibility_score/financial_fit_score/transfer_probability_score as nullable, indexed FloatFields on Player, applied the migration, and hardened build_players_df() against the compatibility_score column-name collision this introduces into the live scoring pipeline.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-24T19:33:45Z
- **Completed:** 2026-07-24T19:40:46Z
- **Tasks:** 3 completed
- **Files modified:** 4

## Accomplishments
- `Player.objects.filter(impact_score__gte=80).order_by('-impact_score')` is now a valid, index-backed ORM query (verified live against the real 41,708-player dev DB; all values still NULL until Plan 03 populates them)
- Migration 0002 applied cleanly: 4 nullable columns + 3 descending-score indexes physically exist in Postgres `players_player`, no RunPython backfill
- `build_players_df()` no longer leaks any of the 4 new output fields into the reconstructed DataFrame; the `cs_tp["compatibility_score"]` re-merge used by `generate_scoring_oracle.py`, `train_tfm_model.py`, and the live `/api/scoring/financial-fit` endpoint (`financial_fit.py::_merge_tfm_feature_columns`) stays a single clean column post-migration, proven both by two new pytest regression tests and a live shell run against real data

## Task Commits

Each task was committed atomically:

1. **Task 1: Add 4 denormalized score FloatFields + indexes to the Player model** - `9fefee4` (feat)
2. **Task 2: Generate and apply the 0002 migration, verify columns exist in Postgres** - `5d71090` (feat)
3. **Task 3: Exclude the 4 denormalized output fields from build_players_df() + regression tests** - `762ba10` (test)

**Plan metadata:** (final commit below)

## Files Created/Modified
- `get-scouted-be/players/models.py` - 4 new nullable FloatFields + 3 descending-score indexes on Player
- `get-scouted-be/players/migrations/0002_denormalized_scores.py` - AddField x4 + AddIndex x3, applied to dev Postgres
- `get-scouted-be/scoring/characterization/reconstruct.py` - `_DENORMALIZED_SCORE_FIELDS` frozenset excludes the 4 output fields from `build_players_df()`'s dynamic `Player._meta.fields` enumeration
- `get-scouted-be/scoring/tests/test_reconstruct.py` - 2 new regression tests: no-leak assertion + single-column cs_tp merge assertion (reproducing the oracle/TFM/financial_fit merge sites)

## Decisions Made
- transfer_probability_score intentionally left unindexed (display value, not a primary Phase 7 sort/filter key; keeps Plan 03's bulk_update write path fast)
- No backfill in the migration — fields stay NULL until Plan 03's `recompute_scores` command runs
- Exclusion-set pattern chosen over renaming/reordering the merge call sites, since the 4 new fields are provably pipeline outputs, never scoring inputs

## Deviations from Plan

### Auto-fixed Issues

None — Rules 1-3 were not triggered; the plan's Task 3 (adding `_DENORMALIZED_SCORE_FIELDS`) was executed exactly as specified, since the plan-checker had already identified and pre-solved this as a real bug during planning.

### Process Note (not a Rule 1-4 deviation)

**Concurrent-execution git race on Task 2.** Plan 06-02 was executing in parallel in the same git working directory (both plans are wave 1, `depends_on: []`, per the orchestrator's parallelization config). After this agent staged `players/migrations/0002_denormalized_scores.py` for Task 2's commit, plan 06-02's executor's `git commit` ran first and swept the already-staged migration file into its own commit alongside `population.py` (`4640cfe`). That agent then self-corrected by running `git reset` and recommitting only its own file as `d9abb73`, which left the migration file untracked again in the working directory rather than lost. This agent detected the untracked file during the self-check step, re-verified its content and applied-migration state were unaffected (`grep` counts on AddField/AddIndex/RunPython unchanged; `manage.py showmigrations` showed `[X] 0002_denormalized_scores` still applied), and re-committed it cleanly as `5d71090`. No code or data was lost or altered at any point; only the commit history shows the extra back-and-forth from the race.

---

**Total deviations:** 0 auto-fixed. 1 process note (shared-working-directory git race between two parallel wave-1 plans, self-corrected; no functional impact).

## Issues Encountered
None beyond the commit-interleaving process note above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The 4 denormalized score columns exist on Player, nullable and indexed, ready for Plan 03's `recompute_scores` command to populate real values via bulk_update
- `build_players_df()` is hardened against the collision these fields introduce, so Plan 03's own use of the scoring pipeline (and any future re-run of oracle generation / TFM training / the live Financial Fit endpoint) stays correct
- Plan 04's timing test can now assert list/browse/sort endpoints query these plain indexed columns with no scoring math in the request cycle
- No blockers for Plan 02/03/04

---
*Phase: 06-scoring-performance-caching-layer*
*Completed: 2026-07-24*

## Self-Check: PASSED

All 4 modified/created files confirmed present on disk; all 3 task commits (`9fefee4`, `5d71090`, `762ba10`) confirmed present in git history.
