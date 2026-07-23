---
phase: 04-scoring-engine-port
plan: 05
subsystem: api
tags: [django, drf, pandas, service-layer, scoring, summary, serializers]

# Dependency graph
requires:
  - phase: 04-scoring-engine-port
    plan: 01
    provides: "reconstruct_population/score_population (RMM-first)/resolve_club_name substrate"
  - phase: 04-scoring-engine-port
    plan: 02
    provides: "rmm_breakdown_from_scored"
  - phase: 04-scoring-engine-port
    plan: 03
    provides: "cs_breakdown_from_row (+ its role_scores_wide merge pattern), tp_breakdown_from_row"
  - phase: 04-scoring-engine-port
    plan: 04
    provides: "financial_fit_from_population"
provides:
  - "get_summary(player_id, club_id): all 4 scores + breakdowns in one response, off exactly ONE population reconstruction, for the PRD Player Profile page"
  - "scoring/serializers.py: RMMSerializer, CompatibilitySerializer, FinancialFitSerializer, TransferProbabilitySerializer, SummarySerializer — output contract for all 5 endpoints"
affects: [04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single-reconstruction orchestration: get_summary calls reconstruct_population()/score_population() exactly once, then slices/reuses results across all 4 sub-score helpers -- verified by a mocked call_count==1 test"
    - "financial_fit reuses the summary's own already-computed scored/cs_tp via financial_fit_from_population rather than calling the high-level get_financial_fit (which would reconstruct+re-score again) -- an accepted efficiency reuse scoped to this endpoint"
    - "Replicates Plan 03's role_scores_wide merge exactly (pop.players_df.merge(pop.role_scores_wide, on='player_id', how='left')) before slicing player_row for cs_breakdown_from_row, so the summary's compatibility breakdown stays internally consistent with its own compatibility_score"
    - "Serializers are thin DictField/JSONField pass-through shapes, not strict nested schemas -- component keys are data-dependent (e.g. RMM's components keys are position-specific), so the service layer stays the single source of truth for response shape"

key-files:
  created:
    - get-scouted-be/scoring/services/summary.py
    - get-scouted-be/scoring/serializers.py
    - get-scouted-be/scoring/tests/test_services_summary.py
  modified: []

key-decisions:
  - "financial_fit's 4 upstream TFM features (player_impact/compatibility_score/performance_score/role_pct) are computed in the summary's single-club context (club_name), not each player's own club as the standalone Financial Fit endpoint does -- an accepted within-scope efficiency tradeoff, documented in the module docstring, not a silent inconsistency"
  - "get_summary does NOT wrap the 4 sub-score calls in a broad try/except -- each helper already returns its own null+reason envelope for missing data, so a genuine reconstruction ValueError should propagate, not be silently swallowed"
  - "Verified end-to-end against real data (not just mocked): for one real player/club pair, the compatibility breakdown mathematically reconstructed its own score ((87.23+70.0)/2=78.615→78.62, matching compatibility_score exactly), and Transfer Probability's 4 contributions summed exactly to the reported transfer_probability (23.59+17.91+16.0+30.0=87.5)"

requirements-completed: []

# Metrics
duration: ~40min
completed: 2026-07-23
---

# Phase 4 Plan 05: Combined Summary + Serializers Summary

**`get_summary(player_id, club_id)` returns all four scores with full breakdowns in one response off exactly one population reconstruction, for the PRD Player Profile page; `serializers.py` documents the output contract for all 5 endpoints.**

## Performance

- **Duration:** ~40 min
- **Tasks:** 3
- **Files created:** 3

## Accomplishments

- `summary.py`: `get_summary` reconstructs the population and runs the RMM-first `score_population` sequence exactly once (proven by a mocked `call_count == 1` test), then composes `rmm_breakdown_from_scored` + `cs_breakdown_from_row` + `financial_fit_from_population` + `tp_breakdown_from_row` from that single pass — never re-reconstructing per sub-score.
- Replicates Plan 03's `role_scores_wide` merge fix exactly, so the summary's compatibility breakdown doesn't regress into the same bug the plan-checker caught in Plan 03 (`role_fit_score`/`bonus` silently disagreeing with the real `compatibility_score`).
- `serializers.py`: 5 DRF serializers (`RMMSerializer`, `CompatibilitySerializer`, `FinancialFitSerializer`, `TransferProbabilitySerializer`, `SummarySerializer`) — thin pass-through shapes over the service layer's already-well-formed dicts, every score field nullable with an optional `reason` field for the shared null+reason envelope.
- **Verified end-to-end against real data** (single real player/club pair, not synthetic): the compatibility breakdown's `role_fit_score`/`bonus` reconstructed the exact `compatibility_score` returned ((87.23+70.0)/2 = 78.615 → 78.62, matching exactly); Transfer Probability's 4 individual contributions (23.59+17.91+16.0+30.0) summed exactly to the reported `87.5`; `predicted_fee` (~€894K) confirmed money-scale, not the log-scale bug range.
- Full `scoring` test suite green: 48 passed, 30 skipped (standard `real_data_available` skip pattern against the isolated pytest-django test DB), 0 failures.

## Task Commits

1. **Task 1: Write failing tests for the summary orchestrator (RED)** — `c4f845d` (test)
2. **Task 2: Implement the summary orchestrator (GREEN)** — `8b1e54a` (feat)
3. **Task 3: Define serializers.py output contract for all 5 endpoints** — `d6fa1f7` (feat)

## Files Created

- `get-scouted-be/scoring/services/summary.py` — `get_summary`
- `get-scouted-be/scoring/serializers.py` — 5 serializers
- `get-scouted-be/scoring/tests/test_services_summary.py` — including the single-reconstruction (`call_count==1`) and compatibility-consistency assertions

## Decisions Made

See `key-decisions` in frontmatter. Most consequential: the summary's `financial_fit` sub-object computes its 4 upstream features in the summary's shared club context rather than each player's own club (the standalone `/financial-fit/` endpoint's convention) — a documented, accepted efficiency tradeoff flagged by the plan-checker as a warning (not a blocker) during planning.

## Deviations from Plan

None. The plan's own text already specified the role_scores_wide merge replication and the single-reconstruction requirement (added during the plan-checker revision cycle before execution); this plan executed both as specified.

## Issues Encountered

The original execution session was cut off mid-stream (API connection error, not a task failure) after committing Task 1 (RED tests) and implementing but not committing Task 2 (`summary.py`). This wrap-up session reviewed the uncommitted implementation, ran the test suite to confirm GREEN, performed one additional real-data end-to-end verification (a single `get_summary` call, not a loop, given the ~80s-per-reconstruction cost), committed Task 2, then implemented and committed Task 3 (`serializers.py`) following the plan spec directly.

## User Setup Required

None.

## Next Phase Readiness

- `get_summary` is ready for Plan 06's `GET /players/{id}/summary/?club_id={club_id}` endpoint
- `serializers.py`'s 5 serializers are ready for Plan 06's DRF views to use for browsable-API rendering

---
*Phase: 04-scoring-engine-port*
*Completed: 2026-07-23*

## Self-Check: PASSED

All 3 created files verified present on disk; all 3 task commits (`c4f845d`, `8b1e54a`, `d6fa1f7`) verified present in git history. Full scoring suite green (48 passed, 30 skipped). Additionally verified end-to-end against real data: compatibility breakdown mathematically reconstructs its own score; Transfer Probability's 4 contributions sum exactly to the reported value; predicted_fee confirmed money-scale.
