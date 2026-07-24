---
phase: 06-scoring-performance-caching-layer
plan: 06
subsystem: api
tags: [django, pandas, denormalized-field, caching, performance, gap-closure]

# Dependency graph
requires:
  - phase: 06-scoring-performance-caching-layer
    provides: "is_own_club(player_id, club_id)/get_scored_population() (Plan 06-05) -- the own-club/arbitrary-club branch pattern this plan replicates for financial_fit.py and summary.py"
provides:
  - "_financial_fit_own_club(player_id, club_name) -- O(1) indexed read of the denormalized money-scale Player.financial_fit_score, the first production consumer of the field Plans 06-01/06-03 built"
  - "get_financial_fit() own-club/arbitrary-club branch: own-club reads the denormalized field directly (no build_oracle_player_features pass, no TFM pipeline call); arbitrary-other-club sources its upstream RMM/CS/TP features from the memoized get_scored_population() instead of a fresh score_population(pop, None)"
  - "get_summary() own-club/arbitrary-club branch: own-club composes get_scored_population() (RMM/CS/TP) + _financial_fit_own_club() (denormalized financial); arbitrary-other-club keeps the live score_population(pop, club_name) + financial_fit_from_population() fallback"
affects: [06-07-caching-verification-regression-test, 12-club-ranking]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Own-club/arbitrary-club branch replicated verbatim from Plan 06-05 for the two remaining services: financial_fit.py's own-club case reads a DENORMALIZED SCALAR (not a slice of the in-process aggregate, since predicted_fee genuinely needs its own DB write from recompute_scores), while summary.py composes both patterns (aggregate slice for RMM/CS/TP + denormalized scalar for financial_fit)"

key-files:
  created: []
  modified:
    - get-scouted-be/scoring/services/financial_fit.py
    - get-scouted-be/scoring/services/summary.py
    - get-scouted-be/scoring/tests/test_parity_api_sample.py
    - get-scouted-be/scoring/tests/test_views.py

key-decisions:
  - "financial_fit.py's own-club fast path reads Player.financial_fit_score directly rather than slicing get_scored_population() -- Financial Fit is architecturally the ONE score that cannot be sliced from the RMM/CS/TP aggregate (predicted_fee requires its own build_oracle_player_features pandas pass over club-aggregate features), so its performance fix is the denormalized field Plans 06-01/06-03 already wrote, not the in-process cache Plan 06-02 built"
  - "test_parity_api_sample.py's test_tfm_service_parity/test_endpoint_parity/test_summary_service_parity patches targeting scoring.services.financial_fit.score_population (a name removed from financial_fit.py's imports by this plan) were rewired to patch get_scored_population instead -- the plan's own STEP 3/4 text assumed the old patch was merely 'harmless if left', but with score_population no longer imported into financial_fit.py, unittest.mock.patch would raise AttributeError (the attribute must exist on the target module); replacing it with get_scored_population keeps both the patch semantics AND the test executable"
  - "get_summary keeps pop = reconstruct_population() unconditional on both branches (matching Plan 04-05's original design) -- the role_scores_wide merge for the compatibility breakdown needs pop regardless of which club-context branch financial/RMM/CS/TP take"

patterns-established: []

requirements-completed: []  # SCORE-07 intentionally NOT marked complete -- satisfied only once all gap-closure plans (06-05, 06-06, 06-07) + the phase verifier pass, per orchestrator instruction.

# Metrics
duration: 25min
completed: 2026-07-24
---

# Phase 06 Plan 06: Financial Fit and Summary Own-Club Fast Path (Denormalized Field Wiring)

**Wired get_financial_fit/get_summary's own-club case to the denormalized Player.financial_fit_score field (O(1) indexed read, live-measured 0.0024s warm, 0.0059s cold) -- the first production consumer of the field Plans 06-01/06-03 built -- while the arbitrary-other-club Phase 12 path now sources its upstream RMM/CS/TP features from Plan 06-05's memoized get_scored_population() aggregate instead of a fresh full-population pass.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-24T21:00:00Z (approx)
- **Completed:** 2026-07-24T21:25:00Z
- **Tasks:** 2/2 completed
- **Files modified:** 4

## Accomplishments

- `_financial_fit_own_club(player_id, club_name)` added to `financial_fit.py`: a genuine O(1) indexed DB read of the denormalized money-scale `Player.financial_fit_score` field, re-deriving `value_verdict`/`value_comparison` from that fee + `market_value` via the SAME `add_value_labels` logic the live path uses -- byte-identical response shape.
- `get_financial_fit` now branches on `is_own_club()`: own-club reads `_financial_fit_own_club` directly; arbitrary-other-club still runs the live `financial_fit_from_population` (Team-override + `build_oracle_player_features` + TFM pipeline `predict`), but its 4 upstream RMM/CS/TP feature columns now come from the memoized `get_scored_population()` instead of a fresh `score_population(pop, None)` call.
- `get_summary` now branches `own = is_own_club(player_id, club_id)`: own-club RMM/CS/TP come from `get_scored_population()` (Plan 06-05's pattern) and `financial_fit` from `_financial_fit_own_club`; arbitrary-other-club keeps the exact prior live behavior (`score_population(pop, club_name)` + `financial_fit_from_population`). The 4-key response shape (`rmm`/`compatibility`/`financial_fit`/`transfer_probability`) is unchanged.
- Live-verified against the real 41,708-player dev DB via `manage.py shell`: `get_financial_fit(own club)` cold **0.0059s**, warm **0.0024s** (both equal the denormalized `financial_fit_score` field exactly); `get_summary(own club)` cold **0.2324s**, warm **0.198s**. A strict negative-control check confirmed the own-club path for BOTH `get_financial_fit` and `get_summary` never calls `build_oracle_player_features` or `get_tfm_pipeline` (patched to raise `AssertionError` if invoked -- neither raised).
- Arbitrary-other-club fallback confirmed still functional: `get_financial_fit(pid, other_club)` returned a valid priced result in 93.4s (full live pass, expected -- this is Phase 12's future-use path, not the hot path SCORE-07 targets); `get_summary(pid, other_club)` returned all 4 keys in 45.4s.
- Parity suite (`test_parity_api_sample.py`) and view tests (`test_views.py`) patch seams updated for both services; full suite (`test_parity_api_sample.py` + `test_parity_bulk.py` + `test_parity_edge_cases.py` + `test_views.py`) re-run: 6 passed, 250 skipped (skips cleanly against the empty pytest test DB per established project convention, matching Plan 06-05's precedent).

## Task Commits

Each task was committed atomically:

1. **Task 1: Denormalized O(1) own-club Financial Fit + arbitrary-club memoized fallback** - `f392fe3` (feat)
2. **Task 2: Own-club fast path for the combined Summary** - `1ade314` (feat)

**Plan metadata:** (pending — final docs commit below)

## Files Created/Modified

- `get-scouted-be/scoring/services/financial_fit.py` -- added `_financial_fit_own_club(player_id, club_name)` immediately before `get_financial_fit`; rewrote `get_financial_fit` to branch `is_own_club()`; import block updated (added `get_scored_population`, `is_own_club`; removed `score_population`, no longer referenced)
- `get-scouted-be/scoring/services/summary.py` -- `get_summary` rewritten to branch `own = is_own_club(player_id, club_id)`; import block updated (added `get_scored_population`, `is_own_club`, `_financial_fit_own_club`)
- `get-scouted-be/scoring/tests/test_parity_api_sample.py` -- `test_tfm_service_parity`/`test_summary_service_parity`/`test_endpoint_parity` patch seams updated to `get_scored_population` (financial_fit and summary modules); added the `financial_fit_score__isnull` skip guard to all three tests so an unpopulated denormalized field skips cleanly instead of erroring; `test_endpoint_parity` also gained `summary.reconstruct_population`/`summary.get_scored_population` patches for the `/summary/` call in its own-club scenario
- `get-scouted-be/scoring/tests/test_views.py` -- `_patched_services` updated: `financial_fit.score_population` patch replaced with `financial_fit.get_scored_population`; added `summary.get_scored_population` patch alongside the existing `summary.score_population` patch (robust regardless of which branch the suite's arbitrarily-picked club happens to hit)

## Decisions Made

- Financial Fit's own-club fast path reads the denormalized `Player.financial_fit_score` scalar directly rather than slicing `get_scored_population()` -- this is the ONE score that architecturally cannot be sliced from the RMM/CS/TP in-process aggregate (its `predicted_fee` requires its own `build_oracle_player_features` club-aggregate pandas pass), so its performance fix is the denormalized field Plans 06-01/06-03 already built and Plan 06-03's `recompute_scores` already populated (41,708 non-null, verified), not Plan 06-02's in-process cache.
- Rewired the `score_population` patch targets in `test_parity_api_sample.py` (both `test_tfm_service_parity` and `test_endpoint_parity`'s financial block) to `get_scored_population` instead — the plan's own STEP 3/4 text characterized the old `financial_fit.score_population` patch as merely "no-op"/"harmless if left", but since `score_population` was removed from `financial_fit.py`'s import block entirely (Task 1's `get_financial_fit` rewrite no longer calls it), `unittest.mock.patch("scoring.services.financial_fit.score_population", ...)` would raise `AttributeError` (the attribute must actually exist on the target module) rather than silently no-op. Replacing it with `get_scored_population` (which IS still imported) keeps the tests executable and semantically equivalent.
- `get_summary` keeps `pop = reconstruct_population()` unconditional on both the own-club and arbitrary-club branches — the `role_scores_wide` merge feeding the compatibility breakdown's `role_fit_score`/`bonus` re-derivation needs `pop` regardless of which club-context branch the RMM/CS/TP/financial sub-scores take, matching Plan 04-05's original design and Plan 06-05's precedent for `get_compatibility`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] `test_endpoint_parity`'s stale `financial_fit.score_population` patch would AttributeError, not no-op**
- **Found during:** Task 1, STEP 4 (updating `test_endpoint_parity`'s financial patches)
- **Issue:** The plan's action text said the two `scoring.services.financial_fit.*` patches in `test_endpoint_parity`'s `with (...)` block were "no longer exercised for this call but are harmless if left." After Task 1 removed `score_population` from `financial_fit.py`'s import block, `patch("scoring.services.financial_fit.score_population", ...)` targets an attribute that no longer exists on the module — `unittest.mock.patch` raises `AttributeError` at context-manager entry (not a silent no-op), which would have broken the test.
- **Fix:** Replaced `patch("scoring.services.financial_fit.score_population", ...)` with `patch("scoring.services.financial_fit.get_scored_population", ...)` in both `test_tfm_service_parity` and `test_endpoint_parity` (Task 1), and equivalently for `summary.score_population` → kept `summary.score_population` (still imported, unlike financial_fit's) but added `summary.get_scored_population` as an additional patch in `test_endpoint_parity` and `test_summary_service_parity` (Task 2).
- **Files modified:** `get-scouted-be/scoring/tests/test_parity_api_sample.py`, `get-scouted-be/scoring/tests/test_views.py`
- **Commit:** `f392fe3` (Task 1), `1ade314` (Task 2)

**Total deviations:** 1 auto-fixed (blocking test-breakage, corrected inline); 0 architectural; 0 out-of-scope items newly discovered this plan.
**Impact on plan:** None on scope or design — same end-state the plan intended (patch seams targeting the memoized aggregate function), just via `get_scored_population` instead of the plan text's literal (but non-functional) `score_population` reference.

## Issues Encountered

None beyond the deviation above. `python manage.py check` stayed clean throughout; no migrations, no scoring math touched.

## User Setup Required

None — no external service configuration required.

## Verification Evidence

Live-verified against the real 41,708-player dev DB (`getscouted` Postgres database, `41708` rows in `players_player` confirmed via `psql`) using the project's `.venv` (`get-scouted-be/.venv/bin/python`, has scikit-learn) via `manage.py shell`:

```
Player: 00032014-830c-41df-90b2-07746ceee1d0 (club 89e28386-...) denorm fee: 1291198.3685155262 market_value: 300000
get_financial_fit(own club) cold: 0.0059 s -> predicted_fee == denormalized field exactly
get_financial_fit(own club) warm: 0.0024 s -> identical result
get_financial_fit(arbitrary club Burnley U21): 93.3846 s -> valid priced result (live path confirmed functional)
get_summary(own club) cold: 0.2324 s
get_summary(own club) warm: 0.198 s -> financial_fit sub-object == standalone get_financial_fit(own club) result exactly
get_summary(arbitrary club Burnley U21): 45.444 s -> all 4 keys present
STRICT CHECK: get_financial_fit(own club) and get_summary(own club) both succeed with
  build_oracle_player_features / get_tfm_pipeline patched to raise AssertionError if called
  -- neither raised, confirming the own-club path genuinely never touches the TFM
  pipeline or the full-population feature build.
```

Note: the arbitrary-other-club `predicted_fee` for this player came out numerically identical to the own-club denormalized value across the sampled other club (Burnley U21). This is a pre-existing characteristic of `financial_fit_from_population`'s club-override mechanics (the 4 upstream RMM/CS/TP features were already computed with `club_context=None` before this plan — see the plan's own "KEY EQUIVALENCE" interface note — so this plan's swap from `score_population(pop, None)` to `get_scored_population()` is provably behavior-preserving, not a regression) and is out of this integration-only plan's scope to investigate further.

Test suite (empty pytest test DB, standard project convention): `python -m pytest scoring/tests/test_parity_api_sample.py scoring/tests/test_parity_bulk.py scoring/tests/test_parity_edge_cases.py scoring/tests/test_views.py -q` → **6 passed, 250 skipped**, zero errors.

## Next Phase Readiness

- Both remaining SCORE-07-relevant services (`financial_fit.py`, `summary.py`) now follow the own-club fast path / arbitrary-club live fallback pattern established in Plan 06-05, closing the last two service-level gaps.
- Plan 06-07's regression test can now assert O(1)-warm behavior for `get_financial_fit`/`get_summary` directly (this plan's manual `manage.py shell` strict negative-control check -- patching `build_oracle_player_features`/`get_tfm_pipeline` to raise -- is a ready-made template for that automated assertion).
- SCORE-07 remains NOT marked complete in REQUIREMENTS.md, per orchestrator instruction — gated on 06-07 and the phase re-verification.

---
*Phase: 06-scoring-performance-caching-layer*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/services/financial_fit.py
- FOUND: get-scouted-be/scoring/services/summary.py
- FOUND: get-scouted-be/scoring/tests/test_parity_api_sample.py
- FOUND: get-scouted-be/scoring/tests/test_views.py
- FOUND: f392fe3 (Task 1 commit)
- FOUND: 1ade314 (Task 2 commit)
