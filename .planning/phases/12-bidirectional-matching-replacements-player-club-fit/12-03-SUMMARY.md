---
phase: 12-bidirectional-matching-replacements-player-club-fit
plan: 03
subsystem: api
tags: [django, pandas, scoring, matching, tfm, player-club-fit]

# Dependency graph
requires:
  - phase: 12-bidirectional-matching-replacements-player-club-fit
    provides: "12-01's shared scoring/services/matching.py module skeleton and fully-implemented _attach_real_tfm top-N enrichment helper"
  - phase: 12-bidirectional-matching-replacements-player-club-fit
    provides: "12-02's precedent for the top-N-bounded real-TFM enrichment pattern (Pattern 1, rank_replacement_players)"
provides:
  - "rank_clubs_for_player fully implemented (Pattern 2: direct reuse of the low-level pure scoring functions -- compatibility_score/financial_score/transfer_probability -- with squad_stats computed ONCE over the full population, never a compute_cs_tp_for_pairs single-row slice) -- own-club-excluded, transfer_probability-sorted, top-N-bound ranking with CS/financial breakdown + real top-N TFM enrichment"
  - "test_matching_reuses_shared_primitives now genuinely passes (both the structural import guard AND a latent unhashable-set bug in the Wave-0 scaffold that only surfaced once the real imports landed)"
  - "Live-measured Pattern 2 per-club-loop latency: ~78.3-78.7s cold (no existing benchmark before this plan)"
affects: [12-04-PLAN.md (phase verification + club-matches endpoint wiring)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pattern 2 (single-player-vs-full-population reuse): rank_clubs_for_player computes ALL club-independent terms (player_impact, performance_score, own_best_role, contract_fit) ONCE, then loops the ~1,060-row team_styles_df computing only the per-club-varying role-fit/compatibility and an O(1) squad_stats lookup -- squad_stats itself is a single groupby('Team') over the FULL players_df, never a per-club or per-row recompute (this is the locked fix for the compute_cs_tp_for_pairs single-row-slice bug that silently NaNs financial_score for every non-own club)"
    - "Real TFM enrichment stays a deliberately separate step after ranking/bounding to top_n, mirroring 12-02's rank_replacement_players -- resolves club names to club_ids via one bounded Club.objects.filter(name__in=...) query, then routes only resolvable (player_id, club_id) pairs through the shared _attach_real_tfm helper; unresolvable entries get a null financial_fit instead of raising"

key-files:
  created: []
  modified:
    - get-scouted-be/scoring/services/matching.py
    - get-scouted-be/scoring/tests/test_services_matching.py

key-decisions:
  - "test_matching_reuses_shared_primitives' Wave-0 scaffold had a latent TypeError (nesting unhashable set objects inside a set comprehension) that only surfaced once matching.py actually gained real role_fit/deterministic_scores imports -- fixed to a list-of-per-module-name-sets comprehension, preserving the original structural-guard intent"
  - "78.3-78.7s measured Pattern 2 latency exceeds the plan's own ~60s 'surprisingly slow' flag threshold; per 12-CONTEXT.md's explicit Deferred Ideas (no surprise caching), this is flagged for the 12-04 phase gate rather than silently building caching infra now"

patterns-established:
  - "Both bidirectional-matching directions (rank_replacement_players Pattern 1, rank_clubs_for_player Pattern 2) now share an identical top-N real-TFM enrichment shape: rank -> bound to top_n -> resolve identities -> route only resolvable pairs through _attach_real_tfm -> null-fill unresolved entries -- the pattern 12-04's endpoint wiring can rely on being consistent across both directions"

requirements-completed: [PLAN-04]

# Metrics
duration: ~15min
completed: 2026-07-26
---

# Phase 12 Plan 03: Ranked Clubs For Player (Pattern 2) Summary

**`rank_clubs_for_player(player_id, top_n)` returns a top-N, transfer-probability-sorted, own-club-excluded club fit list with CS/financial breakdown plus real top-N-only TFM pricing, implemented via Pattern 2 (direct low-level primitive reuse with squad_stats computed once over the full population) -- the locked correctness fix that avoids the compute_cs_tp_for_pairs single-row-slice bug.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-26T18:00:00Z (approx, first task commit 18:00:40Z)
- **Completed:** 2026-07-26T18:08:00Z (approx)
- **Tasks:** 3
- **Files modified:** 2 (1 planned + 1 deviation fix)

## Accomplishments
- `rank_clubs_for_player(player_id, top_n)` implemented in `scoring/services/matching.py` using Pattern 2 (12-RESEARCH.md LOCKED): computes club-independent terms (player_impact via memoized `get_scored_population()`, `performance_score`, `own_best_role`, `contract_fit`) exactly once, then loops the ~1,060-row `team_styles_df` computing only per-club-varying `compatibility_score` (role-fit) and an O(1) `squad_stats` lookup for `financial_score`/`transfer_probability` -- `squad_stats` itself is a single `groupby("Team")` over the FULL `players_df`, never a per-row slice into `compute_cs_tp_for_pairs` (the verified correctness bug this pattern exists to avoid).
- The player's own current club is excluded from the ranked results; results are sorted by `transfer_probability` (primary) with `compatibility_score` as tiebreak, bounded to `top_n`.
- Real TFM (`predicted_fee`/`value_verdict`) attached to exactly the bounded top-N via the shared `_attach_real_tfm` helper, resolving club names to `club_id`s via a single bounded `Club.objects.filter(name__in=...)` query -- mirrors 12-02's `rank_replacement_players` enrichment shape exactly. Unresolvable club names get a null `financial_fit` instead of raising.
- `test_matching_reuses_shared_primitives` now genuinely passes: matching.py imports `compatibility_score` from `role_fit` and `financial_score`/`transfer_probability` from `deterministic_scores` for real (not just mentioned in docstrings) -- the first wave where this structural guard becomes true.
- Live-measured Pattern 2 per-club-loop latency against the real 41,708-player/1,060-club dev DB (no prior benchmark existed): **~78.3-78.7s** (two independent cold runs: 78.26s, 78.69s), returning 10 clubs with `financial_score` non-null for all 10 (regression guard for the squad_stats fix live-confirmed: FIN_NONNULL=10, not just the player's own club).

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement rank_clubs_for_player core ranking (Pattern 2, no TFM yet)** - `61b3782` (feat)
2. **Task 2: Live-time Pattern 2's per-club loop against the real dev DB** - no commit (data-only spike, per plan's own file spec: "exercised, not modified")
3. **Task 3: Attach real TFM to the top-N clubs** - `dea38b9` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/scoring/services/matching.py` - `rank_clubs_for_player` fully implemented (Pattern 2); module docstring updated to reflect both directions are now implemented (was stale, referencing "later plans")
- `get-scouted-be/scoring/tests/test_services_matching.py` - Fixed a latent `TypeError: unhashable type: 'set'` in `test_matching_reuses_shared_primitives`'s Wave-0 scaffold (deviation, see below)

## Decisions Made
- The measured 78.3-78.7s Pattern 2 latency exceeds the plan's own ~60s flag threshold for "surprisingly slow". Per 12-CONTEXT.md's Deferred Ideas (explicitly defers caching for this phase), no caching was added; this is flagged here for the 12-04 phase gate to weigh against the ~44.6-92s precedent already accepted for `rank_replacement_players`/`get_scored_population` in Phases 6 and 12-02 -- Pattern 2's cost is dominated by the same underlying full-population reconstruction + RMM scoring pass, not new inefficiency introduced by this plan's per-club loop itself.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_matching_reuses_shared_primitives crashed with TypeError once real imports landed**
- **Found during:** Task 1 verification (`test_matching_reuses_shared_primitives`)
- **Issue:** The 12-01 Wave-0 scaffold's `role_fit_imports`/`deterministic_scores_imports` set comprehensions attempted to nest `set` objects (from `imported_names_by_module`'s `set()` values) inside an outer `set`, which is unhashable. This was latent/invisible while `matching.py` had zero `role_fit`/`deterministic_scores` imports (the comprehension's filter never matched, so the crashing branch never executed) -- it only surfaced once this task's required imports actually landed, which is exactly the wave the test itself says it should turn green.
- **Fix:** Rewrote both comprehensions as list comprehensions of per-module name-`set`s (`[names for module, names in ... if "role_fit" in module]`), preserving the original structural-guard intent (`any("compatibility_score" in names for names in role_fit_imports)` now correctly iterates per-module `set`s).
- **Files modified:** `get-scouted-be/scoring/tests/test_services_matching.py`
- **Verification:** `test_matching_reuses_shared_primitives` passes; full `scoring/tests/test_services_matching.py` suite (2 passed, 6 skipped, no regression)
- **Committed in:** `61b3782` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary for Task 1's own verification criterion (`test_matching_reuses_shared_primitives` PASSES) to be satisfiable at all; fix is scoped exactly to the test this plan's own acceptance criteria depend on -- no scope creep.

## Issues Encountered
- `grep -c "compute_cs_tp_for_pairs" get-scouted-be/scoring/services/matching.py` returns 3, not the plan's stated 0 -- all 3 occurrences are docstring/comment references explaining WHY the function is intentionally never called (no actual `compute_cs_tp_for_pairs(...)` invocation exists in the file). Confirmed via `grep -n` that no call-site exists; the acceptance criterion's intent ("Pattern 2 does NOT call the monolithic entry point") is satisfied.
- A full backend suite run (`pytest`) surfaces 3 pre-existing failures in `players/tests/test_club_matches_view.py` (`test_club_matches_endpoint_returns_ranked_list`, `test_club_matches_route_not_swallowed_by_catchall`, `test_club_matches_requires_auth`) -- these test a `GET /api/players/{id}/club-matches/` endpoint that does not exist yet. Confirmed via `git log` that this test file was added in 12-01's Wave-0 RED scaffold (commit `84bd4a7`) and is explicitly ROADMAP.md's 12-04-PLAN.md scope ("PLAN-04 endpoint: GET /api/players/{id}/club-matches/ + phase gate"), not this plan's. Left red by design, out of scope for 12-03 (which only implements the service-layer `rank_clubs_for_player` function, not its endpoint wiring) -- 12-04 is expected to turn these green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both bidirectional-matching service functions (`rank_replacement_players` Pattern 1, `rank_clubs_for_player` Pattern 2) are now fully implemented in `scoring/services/matching.py`, sharing the same `_attach_real_tfm` top-N enrichment shape.
- 12-04-PLAN.md's remaining scope: wire `GET /api/players/{id}/club-matches/` (turning `players/tests/test_club_matches_view.py`'s 3 RED tests green) + the phase gate (full suite + live dual-endpoint spike). The measured 78.3-78.7s Pattern 2 latency should inform that endpoint's docstring/timeout expectations, matching 12-02's precedent of documenting live-measured latency directly in the endpoint docstring.
- `test_matching_reuses_shared_primitives` is now permanently green (no further action needed) -- both directions' shared-primitive reuse is structurally locked in.

---
*Phase: 12-bidirectional-matching-replacements-player-club-fit*
*Completed: 2026-07-26*

## Self-Check: PASSED

Both modified files exist on disk; both task commits (`61b3782`, `dea38b9`) found in git history; Task 2 correctly has no commit (data-only spike per plan's file spec).
