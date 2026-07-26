---
phase: 12-bidirectional-matching-replacements-player-club-fit
plan: 04
subsystem: api
tags: [django, drf, scoring, matching, tfm, player-club-fit, phase-gate]

# Dependency graph
requires:
  - phase: 12-bidirectional-matching-replacements-player-club-fit
    provides: "12-03's fully-implemented rank_clubs_for_player (Pattern 2)"
  - phase: 12-bidirectional-matching-replacements-player-club-fit
    provides: "12-02's fully-implemented rank_replacement_players (Pattern 1) + ReplacementsView, needed for this plan's dual-endpoint phase-gate spike"
provides:
  - "GET /api/players/{id}/club-matches/ live -- ClubMatchesView, registered above the <uuid:pk>/ catch-all"
  - "build_team_styles_df empty-Club-table guard (Rule 1 bug fix, mirrors build_role_scores_wide/build_transfers_df's existing empty-table convention)"
  - "rank_clubs_for_player empty-candidates guard (Rule 1 bug fix, mirrors rank_replacement_players' own `if candidates.empty` guard)"
  - "Full backend suite green (241 passed, 321 skipped, 0 failed) -- confirms the previously-known accounts/tests/test_permissions.py::test_director_read_only_visibility failure no longer reproduces"
  - "Live dual-endpoint phase-gate spike against the real 41,708-player/1,060-club dev DB: both rank_replacement_players and rank_clubs_for_player verified end-to-end"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ClubMatchesView (GET APIView) mirrors PositionNeedsView's thin-view shape: get_object_or_404 for a fast 404, then Response(service_function(pk)) with no try/except (Http404 from the service itself propagates naturally to a 404, matching PLAN-02's ReplacementsView convention)"

key-files:
  created: []
  modified:
    - get-scouted-be/players/views.py
    - get-scouted-be/players/urls.py
    - get-scouted-be/scoring/characterization/reconstruct.py
    - get-scouted-be/scoring/services/matching.py
    - get-scouted-be/players/tests/test_club_matches_view.py

key-decisions:
  - "build_team_styles_df needed the same empty-table guard 12-02 already added to build_transfers_df -- a genuinely empty Club table (not just missing coverage on existing rows) previously crashed reconstruction with a bare ValueError; this plan's own endpoint test scaffold is what first exercised that exact edge case"
  - "rank_clubs_for_player now returns {'results': []} when team_styles_df yields zero candidate club rows, instead of crashing pd.DataFrame([]).sort_values() with a KeyError -- mirrors rank_replacement_players' existing `if candidates.empty` early-return"
  - "reconstruct_population()/get_scored_population() are intentionally process-level lru_cache'd (Phase 6 SCORE-07 design) -- correct for the real dev DB but stale across this test file's per-test isolated Player fixtures under pytest-django's per-test DB rollback; added a local autouse _clear_scoring_caches fixture scoped to test_club_matches_view.py rather than touching the caching design itself"
  - "PLAN-02 and PLAN-04 are functionally complete as of this plan; per every prior phase's established convention, marking REQUIREMENTS.md PLAN-02/PLAN-04 as complete is left to the goal-backward verifier, not run here"

patterns-established:
  - "Both bidirectional-matching endpoints (POST-free, GET-only, deterministic, no LLM/503 path) are now live under their respective owning resource: /api/clubs/{id}/replacements/?position=<POS> (PLAN-02) and /api/players/{id}/club-matches/ (PLAN-04), both registered above their app's <uuid:pk>/ catch-all"

requirements-completed: []

# Metrics
duration: ~20min
completed: 2026-07-26
---

# Phase 12 Plan 04: Club Matches Endpoint + Phase Gate Summary

**`GET /api/players/{id}/club-matches/` exposes PLAN-04's `rank_clubs_for_player`, closing out the final plan of the final v1 phase with a full-suite-green + live dual-endpoint (replacements + club-matches) correctness/perf spike against the real dev DB.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-26T18:05:00Z (approx)
- **Completed:** 2026-07-26T18:25:19Z
- **Tasks:** 2
- **Files modified:** 5 (2 planned + 3 deviation fixes)

## Accomplishments

- `ClubMatchesView` (GET APIView) added to `players/views.py`, thinly wrapping `rank_clubs_for_player(pk)` after a fast `get_object_or_404` 404 check -- no explicit `permission_classes` (global `IsAuthenticated` default), matching `PositionNeedsView`'s posture.
- `players/urls.py` registers `<uuid:pk>/club-matches/` ABOVE the `<uuid:pk>/` catch-all, alongside the existing `scouting-report/` specific route.
- All 4 tests in `players/tests/test_club_matches_view.py` now pass (previously 3 RED from 12-01's Wave-0 scaffold; `test_unknown_player_404` was incidentally already green pre-wiring since an unmatched multi-segment path never resolved to any view): 200 + ranked `results` list, route not swallowed by the `<uuid:pk>/` catch-all, unknown player -> 404, unauthenticated -> 401.
- Full backend suite: **241 passed, 321 skipped, 0 failed**. The previously-known `accounts/tests/test_permissions.py::test_director_read_only_visibility` failure (tracked since Phase 7, `.planning/phases/07-core-crud-players-clubs/deferred-items.md`) no longer reproduces -- re-confirmed passing in isolation.
- Live dual-endpoint phase-gate spike against the real 41,708-player/1,060-club dev DB (verbatim output below): both `rank_replacement_players` and `rank_clubs_for_player` return bounded, correctly-enriched results.

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire ClubMatchesView (GET) + route above the catch-all** - `7f3d2a7` (feat) -- includes 3 Rule-1 deviation fixes required to make the endpoint's own test scaffold pass (see Deviations below)
2. **Task 2: Phase gate -- full suite green + live real-data correctness/perf spike for BOTH endpoints** - no commit (data-only verification per the plan's own file spec: "no source file modified")

**Plan metadata:** (this commit)

## Files Created/Modified

- `get-scouted-be/players/views.py` -- `ClubMatchesView` (GET APIView) added
- `get-scouted-be/players/urls.py` -- `club-matches/` route registered above `<uuid:pk>/`
- `get-scouted-be/scoring/characterization/reconstruct.py` -- `build_team_styles_df` empty-Club-table guard (deviation fix)
- `get-scouted-be/scoring/services/matching.py` -- `rank_clubs_for_player` empty-candidates guard (deviation fix)
- `get-scouted-be/players/tests/test_club_matches_view.py` -- autouse `_clear_scoring_caches` fixture (deviation fix)

## Live Phase-Gate Spike (verbatim, real dev DB)

```
REPLACEMENTS sec 120.1 n 10 excl_own True tfm {'predicted_fee': 3808411.2057689056, 'value_verdict': None}
CLUB-MATCHES sec 4.5 n 10 tfm {'predicted_fee': 559065.2400943147, 'value_verdict': 'Bargain'}
```

**Measured latencies:**
- `rank_replacement_players` (Pattern 1): **120.1s** in this run (single fresh process, first call -- reconstructs the population AND runs the full `add_player_impact` RMM pass cold). Consistent with the ~44.6-92s precedent range already accepted in Phase 6/12-02 for this arbitrary-other-club full-population pass; this particular run landed at the higher end.
- `rank_clubs_for_player` (Pattern 2): **4.5s** in this run -- NOT a true independent cold measurement. This spike script (as specified by the plan) calls both functions back-to-back in the SAME process; `rank_replacement_players` ran first and populated `reconstruct_population()`'s process-level `lru_cache`, so `rank_clubs_for_player`'s own `pop = reconstruct_population()` call was served from cache (0s) and only its `get_scored_population()` first-call (RMM pass on an already-reconstructed population) plus the ~1,060-row per-club loop ran fresh. The genuine independent cold latency for Pattern 2 is 12-03-SUMMARY.md's own measurement: **~78.3-78.7s** (two isolated cold runs, no prior cache in the process). Both figures are recorded here for completeness; the 78.3-78.7s figure is the one that should inform any future timeout/caching decision, not the 4.5s warm-reuse figure.
- Both exceed the plan's own "~60s = surprisingly slow" flag threshold on a cold/isolated run (Pattern 1: up to ~120s observed here; Pattern 2: ~78s per 12-03). Per 12-CONTEXT.md's explicit Deferred Ideas (no surprise caching), no caching infrastructure was added in this phase -- both are accepted, documented, uncached, real-data-scoring passes.

**Correctness checks (both PASS):**
- `REPLACEMENTS ... excl_own True` -- target club correctly excluded from its own replacement candidates.
- `REPLACEMENTS` top entry carries a non-`None` `financial_fit` dict (`predicted_fee=€3.81M`; `value_verdict=None` is a legitimate null-propagation outcome, not a bug -- mirrors 12-02-SUMMARY.md's documented null-verdict precedent for TFM's ambiguous-bucket case).
- `CLUB-MATCHES ... n <= 10` (n=10) -- correctly bounded to `top_n`.
- `CLUB-MATCHES` top entry carries a fully-populated `financial_fit` (`predicted_fee=€559K`, `value_verdict='Bargain'`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `build_team_styles_df` crashed on a genuinely empty Club table**
- **Found during:** Task 1 verification (`players/tests/test_club_matches_view.py::test_club_matches_endpoint_returns_ranked_list`, whose fixture creates ONLY a `Player` row with no `Club` at all)
- **Issue:** `Club.objects.values(...)` on a zero-row table produces `pd.DataFrame.from_records([])` with zero columns; the subsequent `.rename()` never populates the 9 required literal columns (`Team`, `Control Possession`, etc.), so `assert_columns_present` always raised `ValueError: build_team_styles_df missing columns: [...]`, surfacing as a 500 from the new endpoint on any DB with zero clubs
- **Fix:** Added an early-return guard (log a warning, return `pd.DataFrame(columns=_TEAM_STYLES_REQUIRED_COLUMNS)`) before the rename/assert -- exact structural mirror of 12-02's `build_transfers_df` fix and the pre-existing `build_role_scores_wide` guard in the same file
- **Files modified:** `get-scouted-be/scoring/characterization/reconstruct.py`
- **Verification:** `players/tests/test_club_matches_view.py` progressed past this failure; full suite re-run confirms no regression
- **Committed in:** `7f3d2a7` (Task 1 commit)

**2. [Rule 1 - Bug] `rank_clubs_for_player` crashed with `KeyError: 'transfer_probability'` when zero candidate clubs exist**
- **Found during:** Task 1 verification, immediately after fixing deviation 1 above -- with zero `Club` rows, `pop.team_styles_df` is empty, so the per-club loop's `rows` list stays empty and `pd.DataFrame([]).sort_values(["transfer_probability", ...])` raised `KeyError` (no columns exist on a fully empty DataFrame)
- **Fix:** Added an `if not rows: return {"player_id": ..., "results": []}` early return, mirroring `rank_replacement_players`' own existing `if candidates.empty: return {...}` guard directly above it in the same module
- **Files modified:** `get-scouted-be/scoring/services/matching.py`
- **Verification:** `players/tests/test_club_matches_view.py` progressed past this failure
- **Committed in:** `7f3d2a7` (Task 1 commit)

**3. [Rule 1 - Bug] `reconstruct_population()`'s process-level cache went stale across this test file's per-test Player fixtures**
- **Found during:** Task 1 verification -- running the full `test_club_matches_view.py` file (not just a single test in isolation) surfaced a spurious 404 (`test_club_matches_route_not_swallowed_by_catchall`, expected 200) because `reconstruct_population()`/`get_scored_population()` (both `@lru_cache(maxsize=1)`, process-scoped, Phase 6 SCORE-07 design) retained the FIRST test's population snapshot; the second test's freshly-created `Player` row (a new UUID under pytest-django's per-test-rolled-back DB) was invisible to the stale cached population, so `rank_clubs_for_player`'s own internal `Http404("Player {id} not found")` fired
- **Fix:** Added a local `autouse=True` `_clear_scoring_caches` fixture to `test_club_matches_view.py` that calls `clear_scoring_caches()` before and after each test in the file -- scoped narrowly to this file (not the caching design itself, which is correct-by-design for the real dev DB where data doesn't mutate per-request)
- **Files modified:** `get-scouted-be/players/tests/test_club_matches_view.py`
- **Verification:** `players/tests/test_club_matches_view.py` -- 4/4 passed, in file-order and standalone
- **Committed in:** `7f3d2a7` (Task 1 commit)

---

**Total deviations:** 3 auto-fixed (3 bugs, all Rule 1)
**Impact on plan:** All three were necessary for this plan's own stated acceptance criterion ("players/tests/test_club_matches_view.py auth + 404 + route tests pass") to be satisfiable at all -- no scope creep beyond the exact code paths this plan's endpoint wiring and its own Wave-0 test scaffold exercise. Deviations 1 and 2 also directly harden `rank_clubs_for_player`/`build_team_styles_df` for any future genuinely-empty-Club-table state (a realistic scenario, not merely a test artifact), matching 12-02's precedent for `build_transfers_df`.

## Issues Encountered

None beyond the three deviations above, which were resolved inline during Task 1.

## User Setup Required

None -- no external service configuration required.

## Next Phase Readiness

- Both bidirectional-matching directions are now fully live end-to-end: `GET /api/clubs/{id}/replacements/?position=<POS>` (PLAN-02, 12-02) and `GET /api/players/{id}/club-matches/` (PLAN-04, this plan), sharing the single `scoring/services/matching.py` module and its `_attach_real_tfm` top-N enrichment helper.
- Full backend suite green: 241 passed, 321 skipped, 0 failed. The previously-tracked `accounts/tests/test_permissions.py::test_director_read_only_visibility` failure (`.planning/phases/07-core-crud-players-clubs/deferred-items.md`) no longer reproduces as of this run.
- **PLAN-02 and PLAN-04 are functionally complete.** Marking them (and REQUIREMENTS.md's traceability table) complete is the goal-backward verifier's call, matching every prior phase's established convention in this project (07-03, 10-05, etc.) -- not done in this plan.
- **Phase 12 (bidirectional-matching-replacements-player-club-fit) is functionally complete** -- this is the final plan of the final phase of the v1 roadmap. Phase-level and milestone-level goal-backward verification is the remaining step before v1 can be declared done.

---
*Phase: 12-bidirectional-matching-replacements-player-club-fit*
*Completed: 2026-07-26*

## Self-Check: PASSED

Both modified core files (`get-scouted-be/players/views.py`, `get-scouted-be/players/urls.py`) exist on disk; Task 1 commit (`7f3d2a7`) found in git history; Task 2 correctly has no commit (data-only phase-gate spike per the plan's own file spec).
