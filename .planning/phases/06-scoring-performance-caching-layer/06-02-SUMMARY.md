---
phase: 06-scoring-performance-caching-layer
plan: 02
subsystem: api
tags: [django, pandas, functools-lru_cache, caching, performance]

# Dependency graph
requires:
  - phase: 04-scoring-engine-port
    provides: "reconstruct_population/score_population/get_tfm_pipeline in scoring/services/population.py, the memoized-lru_cache precedent this plan extends"
provides:
  - "reconstruct_population() memoized with @lru_cache(maxsize=1) -- the ~3.5-4s ORM-to-DataFrame rebuild runs once per process, not per request"
  - "get_scored_population() -- new memoized own-club (club_context=None) whole-population scoring aggregate (the ~74-115s pass), computed once per process"
  - "clear_scoring_caches() -- single invalidator resetting both new caches for the recompute command (Plan 03) to call after a data refresh"
affects: [06-03-recompute-command, 06-04-live-caching-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "In-process @lru_cache(maxsize=1) memoization for zero-argument expensive aggregate builders, matching the existing get_tfm_pipeline precedent; invalidated via an explicit .cache_clear() call from a single clear_scoring_caches() function rather than TTL/signals"

key-files:
  created: []
  modified:
    - get-scouted-be/scoring/services/population.py
    - get-scouted-be/scoring/tests/test_services_population.py

key-decisions:
  - "get_scored_population() memoizes score_population(reconstruct_population(), None) as a NEW wrapper function rather than adding lru_cache directly to score_population, since score_population takes an unhashable Population(DataFrames...) argument that lru_cache cannot hash"
  - "clear_scoring_caches() intentionally does NOT clear get_tfm_pipeline's cache -- the TFM joblib artifact only changes via train_tfm_model, not a data refresh, so conflating the two invalidation triggers would be incorrect"

patterns-established:
  - "Mock-backed cache-mechanics tests (patch the 4 build_* functions, assert call_count) prove memoization/invalidation without needing real DB data or the DB-touching real_data_available fixture -- fast and DB-independent, unlike the plan's own real-data manual verification"

requirements-completed: []  # SCORE-07 intentionally NOT marked complete here -- satisfied only once all 4 plans of Phase 6 + the phase verifier pass, per orchestrator instruction.

# Metrics
duration: 15min
completed: 2026-07-24
---

# Phase 06 Plan 02: In-Process Memoization of reconstruct_population + get_scored_population Summary

**Extended the codebase's existing `@lru_cache(maxsize=1)` precedent (previously only on `get_tfm_pipeline`) onto `reconstruct_population()` and a new `get_scored_population()` own-club aggregate, plus a single `clear_scoring_caches()` invalidator — cutting a live arbitrary-club request's DB rebuild from ~4s per-request to a one-time per-process cost.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-24T19:33:10Z (session start per STATE.md)
- **Completed:** 2026-07-24T19:41:14Z
- **Tasks:** 2/2 completed
- **Files modified:** 2

## Accomplishments

- `reconstruct_population()` is now `@lru_cache(maxsize=1)`-memoized — verified against the real dev DB: first call 4.048s (cold), second call 0.0s (cache hit, `pop1 is pop2 == True`, `cache_info=CacheInfo(hits=1, misses=1, maxsize=1, currsize=1)`)
- New `get_scored_population()` memoizes the own-club (`club_context=None`) whole-population scoring pass — the ~74-115s aggregate SCORE-07's Success Criterion 2 requires be rebuilt on data change, not per request
- New `clear_scoring_caches()` resets both caches in one call, ready for Plan 03's recompute command to invoke after a data refresh
- Two new fast, DB-independent, mock-backed tests prove memoization (build_* called once across two `reconstruct_population()` calls) and invalidation (`clear_scoring_caches()` doubles the call count on the next call; `cache_info().currsize` drops to 0)
- `score_population`'s internal RMM-first ordering and scoring math are byte-for-byte unchanged (confirmed via `git diff` of its body across both commits — empty diff)

## Task Commits

Each task was committed atomically:

1. **Task 1: Memoize reconstruct_population + add get_scored_population aggregate + clear_scoring_caches** - `d9abb73` (feat)
2. **Task 2: Add cache-behavior tests (memoization proven + invalidation proven)** - `ed8efb3` (test)

**Plan metadata:** (pending — final docs commit below)

## Files Created/Modified

- `get-scouted-be/scoring/services/population.py` — added `@lru_cache(maxsize=1)` to `reconstruct_population`; added new `get_scored_population()` and `clear_scoring_caches()` functions
- `get-scouted-be/scoring/tests/test_services_population.py` — added `test_reconstruct_population_is_memoized_and_clear_scoring_caches_invalidates` and `test_clear_scoring_caches_resets_cache_info_currsize`; imported `clear_scoring_caches`/`get_scored_population`

## Decisions Made

- `get_scored_population()` is a new wrapper (not `@lru_cache` directly on `score_population`) because `score_population`'s `pop` argument is a `Population` tuple of unhashable DataFrames — `lru_cache` would raise `TypeError` if applied directly. The plan's `<action>` block specified this design explicitly.
- `clear_scoring_caches()` deliberately excludes `get_tfm_pipeline` from invalidation — that cache's lifecycle (joblib artifact reload) is tied to `train_tfm_model`, not a Phase 1 data refresh, so mixing the two invalidation triggers would be a correctness bug, not a convenience.

## Deviations from Plan

None in the two tasks themselves — both executed exactly as specified, including using `@lru_cache(maxsize=1)`, the verbatim docstrings/function bodies from the plan's `<action>` block, and the plan's exact test structure (mock the 4 `build_*` functions, assert `call_count`, check `cache_info().currsize`).

### Out-of-scope discoveries (logged, not fixed)

Two pre-existing, unrelated uncommitted changes were present in the working tree before this plan started (left in `.planning/phases/06-scoring-performance-caching-layer/deferred-items.md`, not committed as part of 06-02 per the SCOPE BOUNDARY rule):

1. An untracked migration `get-scouted-be/players/migrations/0002_denormalized_scores.py` was initially flagged as a possible gap left by Plan 06-01. **RESOLVED** — this was actually 06-01's own Task 2 migration, temporarily knocked untracked by a git index race between the two parallel wave-1 executors (06-01 and 06-02 both staging/committing in the same working directory at once). Content and applied-DB state were unaffected throughout; the concurrently-running 06-01 agent committed it cleanly as `5d71090 feat(06-01): generate and apply migration for denormalized score columns`. See `deferred-items.md` for the full resolution note.
2. A pre-existing unstaged docstring reformat in `get-scouted-be/clubs/models.py`, unrelated to any 06-02 task -- still unstaged, left as-is.

Note: this repo has parallel plan execution active (config `parallelization: true`); a `test(06-01)` commit (`762ba10`) landed in the middle of this plan's two commits from a concurrently-running 06-01/06-03 agent. Verified via `git log` that it did not touch `scoring/services/population.py` or `scoring/tests/test_services_population.py` — no interference with this plan's files.

**Total deviations:** 0 auto-fixed; 2 out-of-scope items logged to deferred-items.md.
**Impact on plan:** None — both tasks executed exactly as written.

## Issues Encountered

- The first `git commit` for Task 1 unexpectedly picked up the untracked `players/migrations/0002_denormalized_scores.py` file alongside the staged `population.py` (cause not fully determined — possibly a stale index entry from concurrent parallel-plan activity in the same working tree). Caught immediately via post-commit `git show --stat`; fixed with `git reset --soft HEAD~1`, `git restore --staged` on the migration file, and a clean re-commit of `population.py` alone. No functional impact — the migration file remains untracked and un-committed, as logged in deferred-items.md.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `reconstruct_population()` and `get_scored_population()` are ready for Plan 03's recompute command to call `clear_scoring_caches()` after writing fresh data, and for Plan 04's live-path verification to confirm request-time reuse.
- `score_population`'s math/ordering is untouched — Phase 5's parity oracle guarantees remain valid; no re-verification of RMM/CS/TP/TFM values is needed as a result of this plan.

---
*Phase: 06-scoring-performance-caching-layer*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/services/population.py
- FOUND: get-scouted-be/scoring/tests/test_services_population.py
- FOUND: .planning/phases/06-scoring-performance-caching-layer/06-02-SUMMARY.md
- FOUND: d9abb73 (Task 1 commit)
- FOUND: ed8efb3 (Task 2 commit)
