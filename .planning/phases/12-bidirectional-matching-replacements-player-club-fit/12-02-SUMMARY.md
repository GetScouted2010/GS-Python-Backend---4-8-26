---
phase: 12-bidirectional-matching-replacements-player-club-fit
plan: 02
subsystem: api
tags: [django, pandas, scoring, matching, tfm, replacements]

# Dependency graph
requires:
  - phase: 12-bidirectional-matching-replacements-player-club-fit
    provides: "12-01's shared scoring/services/matching.py module skeleton and fully-implemented _attach_real_tfm top-N enrichment helper"
  - phase: 06-scoring-performance-caching-layer
    provides: "score_population(pop, arbitrary_club_name) arbitrary-other-club live scoring path, explicitly deferred to this phase"
provides:
  - "rank_replacement_players fully implemented (Pattern 1: direct score_population(pop, club_name) reuse) -- position-filtered, current-squad-excluded, transfer_probability-sorted, top-N-bound ranking with RMM/CS breakdown + real top-N TFM enrichment"
  - "GET /api/clubs/{id}/replacements/?position=<POS> live, registered above the <uuid:pk>/ catch-all"
  - "build_transfers_df empty-Transfer-table guard (Rule 1 bug fix), matching build_role_scores_wide's existing convention"
affects: [12-03-PLAN.md, 12-04 (phase verification)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern 1 (arbitrary-other-club full-population reuse): rank_replacement_players calls score_population(pop, club_name) once, filters/sorts/bounds the returned DataFrame in pandas -- zero new scoring math, zero re-derived CS/TFM/TP formula"
    - "Real TFM (predicted_fee/value_verdict) enrichment stays a deliberately separate step (pairs built from the already-sliced top-N results list, passed to the shared _attach_real_tfm helper) so the expensive ML pipeline is called exactly top_n times, never once per position candidate"

key-files:
  created: []
  modified:
    - get-scouted-be/scoring/services/matching.py
    - get-scouted-be/clubs/views.py
    - get-scouted-be/clubs/urls.py
    - get-scouted-be/scoring/characterization/reconstruct.py

key-decisions:
  - "build_transfers_df now mirrors build_role_scores_wide's empty-table guard (logs a warning, returns an empty DataFrame with the required literal columns) instead of crashing with ValueError -- an isolated/fresh DB with zero Transfer rows is a legitimate state reconstruct_population must survive, not just a full-scale-import assumption"

patterns-established:
  - "Live endpoint docstrings for a full-population arbitrary-club scoring pass must state the measured latency (~40-50s+, uncached, by design) so no future plan mistakes it for a bug or adds surprise caching (12-CONTEXT.md Deferred Ideas)"

requirements-completed: [PLAN-02]

# Metrics
duration: 20min
completed: 2026-07-26
---

# Phase 12 Plan 02: Ranked Replacement Players Summary

**`GET /api/clubs/{id}/replacements/?position=<POS>` returns a top-N, transfer-probability-sorted, current-squad-excluded replacement candidate list with RMM/CS breakdown plus real top-N-only TFM pricing, implemented via a single `score_population(pop, club_name)` reuse pass (Pattern 1) -- zero new scoring math.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-26T17:07:00Z (approx)
- **Completed:** 2026-07-26T17:27:31Z
- **Tasks:** 3
- **Files modified:** 4 (3 planned + 1 deviation fix)

## Accomplishments
- `rank_replacement_players(club_id, position, top_n)` implemented in `scoring/services/matching.py`: resolves the target club, runs `score_population(pop, club_name)` exactly once, filters to the requested `position` and excludes the target club's own squad, sorts by `transfer_probability` (primary) with `Player Impact`/`compatibility_score` as visible tiebreak/breakdown fields, and bounds to `top_n`.
- Real TFM (`predicted_fee`/`value_verdict`) attached to exactly the bounded top-N via the shared `_attach_real_tfm` helper -- verified by `test_real_tfm_called_only_for_top_n` (call_count == top_n).
- `ReplacementsView` (GET APIView) wired at `/api/clubs/{id}/replacements/?position=<POS>`, registered above the `<uuid:pk>/` catch-all; missing `position` -> 400, unknown club -> 404 (fast, before the multi-minute scoring pass), unauthenticated -> 401.
- Live-verified end-to-end against the real 41,708-player/1,060-club dev DB: `rank_replacement_players(club.id, "CB", top_n=3)` returned 3 real CB candidates, all excluded from the target club, each carrying a real `financial_fit` (predicted_fee/value_verdict); `compatibility_score`/`transfer_probability` correctly surfaced as `null` (not fabricated) for the sampled club, which has no Playstyles.csv coverage -- matching the project's documented never-zero-fill null-propagation convention.

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement rank_replacement_players (Pattern 1 ranking, no TFM yet)** - `91036f3` (feat)
2. **Task 2: Attach real TFM to the top-N replacement candidates** - `f9541b7` (feat)
3. **Task 3: Wire ReplacementsView (GET) + route above the catch-all** - `fa02405` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/scoring/services/matching.py` - `rank_replacement_players` fully implemented (Pattern 1); `_none_if_nan` helper added; top-N `_attach_real_tfm` enrichment call
- `get-scouted-be/clubs/views.py` - `ReplacementsView` (GET APIView) added
- `get-scouted-be/clubs/urls.py` - `replacements/` route registered above `<uuid:pk>/`
- `get-scouted-be/scoring/characterization/reconstruct.py` - `build_transfers_df` empty-Transfer-table guard (deviation fix)

## Decisions Made
- `build_transfers_df` now returns an empty DataFrame with the required literal columns (logging a warning) when the `Transfer` table has zero rows, mirroring `build_role_scores_wide`'s existing empty-table convention, instead of raising `ValueError` on the zero-column `pd.DataFrame.from_records([])` result.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] build_transfers_df crashed on a legitimately empty Transfer table**
- **Found during:** Task 3 (`clubs/tests/test_replacements_view.py::test_replacements_endpoint_returns_ranked_list`, which creates an isolated club + 2 players fixture with zero `Transfer` rows)
- **Issue:** `pd.DataFrame.from_records([])` on an empty queryset produces a DataFrame with zero columns; the subsequent `.rename()` never populates the required literal columns, so `assert_columns_present` always raised `ValueError: build_transfers_df missing columns: [...]`, surfacing as a 500 from the new endpoint on any DB with no transfer history yet
- **Fix:** Added an early-return guard (log a warning, return `pd.DataFrame(columns=_TRANSFERS_REQUIRED_COLUMNS)`) before the rename/assert, exactly matching `build_role_scores_wide`'s existing pattern for an empty `PlayerRoleScore` table just above it in the same file
- **Files modified:** `get-scouted-be/scoring/characterization/reconstruct.py`
- **Verification:** `clubs/tests/test_replacements_view.py` (4/4 passed); full `scoring/` + `clubs/` suite re-run (86 passed, 1 expected-red, 305 skipped, no new failures)
- **Committed in:** `fa02405` (Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for the new endpoint to function against any DB state with no transfer history yet (a realistic, not merely hypothetical, empty-table case); no scope creep -- fix is scoped to the exact function this plan's own endpoint call path exercises.

## Issues Encountered
- Per the plan's explicit instruction (and the important_note in this task's brief), `test_matching_reuses_shared_primitives` was left failing/red -- Pattern 1 legitimately reuses `score_population` wholesale and does not import the low-level `compatibility_score`/`financial_score`/`transfer_probability` primitives directly; that structural guard only becomes true in 12-03 (Pattern 2). Confirmed via a full `scoring/`+`clubs/` suite run: exactly 1 failure (`test_matching_reuses_shared_primitives`), 86 passed, 305 skipped -- no other regression.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `scoring/services/matching.py` now has one implemented direction (`rank_replacement_players`) and one remaining stub (`rank_clubs_for_player`, `raise NotImplementedError`) for 12-03-PLAN.md (Pattern 2) to implement against the same shared `_attach_real_tfm` helper.
- `test_matching_reuses_shared_primitives` remains the expected next-plan target: 12-03 Task 1 must add real `from ...role_fit import compatibility_score` / `from ...deterministic_scores import financial_score, transfer_probability` import statements to turn it green.
- The `build_transfers_df` empty-table fix is a general reconstruction hardening (benefits any future empty-Transfer-table scenario, e.g. 12-03's own tests), not scoped only to this endpoint.

---
*Phase: 12-bidirectional-matching-replacements-player-club-fit*
*Completed: 2026-07-26*

## Self-Check: PASSED

All 4 created/modified files exist on disk; all 3 task commits (`91036f3`, `f9541b7`, `fa02405`) found in git history.
