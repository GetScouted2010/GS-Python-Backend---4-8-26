---
phase: 04-scoring-engine-port
plan: 03
subsystem: api
tags: [django, pandas, service-layer, scoring, compatibility, transfer-probability]

# Dependency graph
requires:
  - phase: 04-scoring-engine-port
    plan: 01
    provides: "reconstruct_population/score_population (RMM-first)/resolve_club_name substrate (scoring/services/population.py); null_with_reason envelope"
provides:
  - "get_compatibility(player_id, club_id): real Compatibility Score + role_fit_score/similarity_pct(null)/bonus breakdown that reconstructs the returned score; club_style_data_unavailable null envelope"
  - "cs_breakdown_from_row(cs_tp_row, player_row, club_name, team_styles_df): low-level breakdown builder, reusable by the summary endpoint (Plan 05) with no extra reconstruction"
  - "get_transfer_probability(player_id, club_id): real deterministic Transfer Probability + all 4 weighted terms (raw/weight/contribution)"
  - "tp_breakdown_from_row(cs_tp_row): low-level breakdown builder, reusable by the summary endpoint (Plan 05)"
affects: [04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Role-aware player_row: pop.players_df merged with pop.role_scores_wide (on='player_id', how='left') BEFORE slicing the single player row, replicating compute_cs_tp_for_pairs' own internal merge (deterministic_scores.py:354) -- required because calculate_subjective_role_fit_for_player_to_team and get_player_own_best_role both read role-score columns off the row itself (role in player_row.index), which a bare pop.players_df row doesn't carry"
    - "Breakdown-reconstructs-score regression test: round((clip(role_fit_score,0,100)+bonus)/2,2) == round(compatibility_score,2) -- a hard arithmetic check that fails if the role-column merge is ever dropped, not just a type/range check"
    - "TP breakdown re-exposes compute_cs_tp_for_pairs' already-computed weighted terms rather than reimplementing the formula -- contract_fit scaled *100 for 0-100 display parity with the other 3 terms, documented inline"

key-files:
  created:
    - get-scouted-be/scoring/services/compatibility.py
    - get-scouted-be/scoring/services/transfer_probability.py
    - get-scouted-be/scoring/tests/test_services_compatibility.py
    - get-scouted-be/scoring/tests/test_services_transfer_probability.py
  modified: []

key-decisions:
  - "This plan implements a fix the plan-checker required during planning (not discovered during execution): get_compatibility's player_row is built from players_df.merge(role_scores_wide, on='player_id', how='left', suffixes=('','_role')) before slicing, rather than slicing pop.players_df directly -- without this, role_fit_score/bonus would silently disagree with the real compatibility_score on every request"
  - "similarity_pct is always None in the CS breakdown -- Phase 3 explicitly left this term's target-player-comparison-pool machinery out of scope; documented as a known gap, not silently omitted from the breakdown shape"
  - "Both services go through compute_cs_tp_for_pairs via score_population, never call role_fit.compatibility_score directly -- preserves compute_cs_tp_for_pairs' NaN-role-fit guard (forces compatibility_score to NaN when Role Fit Score is NaN, no bonus-only fallback)"

requirements-completed: []

# Metrics
duration: ~35min
completed: 2026-07-23
---

# Phase 4 Plan 03: Compatibility Score + Transfer Probability Services Summary

**`get_compatibility` returns a real Compatibility Score with a breakdown that mathematically reconstructs the score (role_fit_score + bonus, both re-derived from a role-column-merged player row); `get_transfer_probability` returns the real deterministic Transfer Probability with all 4 weighted terms individually.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 3
- **Files created:** 4 (2 services, 2 test files)

## Accomplishments

- `compatibility.py`: `get_compatibility(player_id, club_id)` resolves the club UUID, runs the RMM-first `score_population` sequence, and returns the real `compatibility_score`. The breakdown (`role_fit_score`, `similarity_pct`, `bonus`) is re-derived via a second call to `calculate_subjective_role_fit_for_player_to_team`/`get_player_own_best_role` — critically, on a `player_row` sliced from `players_df` merged with `role_scores_wide` first, so those functions can actually read the player's role-score columns instead of degenerating to `role_fit_score=None`/`bonus=70.0` regardless of the real score.
- `transfer_probability.py`: `get_transfer_probability(player_id, club_id)` reads the already-computed deterministic `transfer_probability` value off `compute_cs_tp_for_pairs`' output and re-exposes its 4 weighted terms (compatibility 0.30, performance 0.20, financial 0.20, contract_fit 0.30), each with raw value, weight, and contribution.
- Both services return the shared null+reason envelope when their score can't be computed (`club_style_data_unavailable` for CS; `insufficient_data` for TP when an upstream term like `performance_score` is NaN) — never a fabricated fallback.
- Full `scoring` test suite green: `test_services_compatibility.py` (3 passed, 5 skipped) and `test_services_transfer_probability.py` (4 passed, 3 skipped) — skips are the standard `real_data_available` pattern against pytest-django's isolated empty test DB, not failures.

## Task Commits

1. **Task 1: Write failing tests for CS and TP services (RED)** — `5dfd609` (test)
2. **Task 2: Implement the Compatibility Score service (GREEN)** — `2bd77c4` (feat)
3. **Task 3: Implement the Transfer Probability service (GREEN)** — `de545b9` (feat)

## Files Created

- `get-scouted-be/scoring/services/compatibility.py` — `get_compatibility`, `cs_breakdown_from_row`
- `get-scouted-be/scoring/services/transfer_probability.py` — `get_transfer_probability`, `tp_breakdown_from_row`
- `get-scouted-be/scoring/tests/test_services_compatibility.py` — including the breakdown-reconstructs-score consistency assertion
- `get-scouted-be/scoring/tests/test_services_transfer_probability.py` — including the sum-of-contributions-reconstructs-tp assertion

## Decisions Made

See `key-decisions` in frontmatter. Most consequential: the role-column merge fix, which was a plan-checker-mandated correction applied during planning (not an execution-time deviation) — the plan text itself already specified the exact merge to replicate before this plan was executed.

## Deviations from Plan

None. The plan's own text already contained the role-scores-wide merge fix (added during the plan-checker revision cycle before execution began); this plan executed it as specified.

## Issues Encountered

The original execution session stalled (infrastructure watchdog timeout, not a task failure) after committing Tasks 1 and 2 (tests + Compatibility Score service) but before committing Task 3 (Transfer Probability service) or this SUMMARY.md. This wrap-up session verified the committed work, reviewed and committed the already-written (uncommitted) `transfer_probability.py`, confirmed both test files pass, and completed the plan record.

## User Setup Required

None.

## Next Phase Readiness

- `cs_breakdown_from_row` and `tp_breakdown_from_row` are the exact low-level helpers Plan 05's summary endpoint imports directly, avoiding any extra population reconstruction
- Both services are ready for Plan 06's DRF endpoint wiring (`/players/{id}/clubs/{club_id}/compatibility/` and `.../transfer-probability/`)

---
*Phase: 04-scoring-engine-port*
*Completed: 2026-07-23*

## Self-Check: PASSED

All 4 created files verified present on disk; all 3 task commits (`5dfd609`, `2bd77c4`, `de545b9`) verified present in git history. Both test files pass (7 passed, 8 skipped — standard real-data skip pattern).
