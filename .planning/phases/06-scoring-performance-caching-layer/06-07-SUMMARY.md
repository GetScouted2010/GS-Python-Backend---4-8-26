---
phase: 06-scoring-performance-caching-layer
plan: 07
subsystem: api
tags: [django, pytest, unittest-mock, regression-testing, performance, gap-closure]

# Dependency graph
requires:
  - phase: 06-scoring-performance-caching-layer
    provides: "get_rmm/get_compatibility/get_transfer_probability/get_financial_fit/get_summary own-club fast paths (Plans 06-05, 06-06) -- the wiring this plan's regression test proves and durably guards"
provides:
  - "test_live_scoring_performance.py -- a warm-process regression test that drives the REAL 5 live scoring services and structurally asserts the full-population pandas entry points never run per own-club request, not just a wall-clock threshold"
  - "06-live-wiring-DECISIONS.md -- the own-club/arbitrary-club design decision + explicit 'Yes' answer to 06-VERIFICATION.md's flagged scope question, so it is a recorded decision, not an unstated assumption"
affects: [06-verification-reverification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Mock patch-target discipline for regression guards: unittest.mock.patch must target the NAME BINDING the caller actually resolves at call time (the caller's own `from X import name`), never the origin/definition module -- patching the definition module leaves the caller's separately-bound reference untouched and the mock is silently never invoked, producing a trivially-passing but non-protective assert_not_called()"

key-files:
  created:
    - get-scouted-be/scoring/tests/test_live_scoring_performance.py
    - .planning/phases/06-scoring-performance-caching-layer/06-live-wiring-DECISIONS.md
  modified:
    - get-scouted-be/scoring/tests/test_services_summary.py

key-decisions:
  - "add_player_impact is patched at scoring.services.population.add_player_impact (the caller's own imported name), not scoring.characterization.impact.add_player_impact (the definition module the plan's literal text suggested) -- the latter is a no-op mock that never intercepts population.py's call, verified live via object-identity checks and simulated-regression runs against the real dev DB"
  - "build_oracle_player_features is patched at scoring.services.financial_fit.build_oracle_player_features for the same reason -- financial_fit.py imports it via its own `from ... import` binding"
  - "test_services_summary.py's synthetic get_summary test now mocks is_own_club=False -- Plan 06-06 added a real is_own_club() DB lookup to get_summary that this test's non-UUID synthetic ids ('p1'/'club-uuid') can't satisfy; False correctly routes through the arbitrary-club path the test's other mocks (score_population/financial_fit_from_population) already assumed"

patterns-established:
  - "Regression-test patch-target verification: before trusting an assert_not_called() guard, confirm (object identity or a simulated-regression run with side_effect=Exception) that the patched name is actually the one the code path under test resolves at call time"

requirements-completed: []  # SCORE-07 intentionally NOT marked complete -- that is the phase verifier's call, not this plan's, per orchestrator instruction.

# Metrics
duration: 25min
completed: 2026-07-24
---

# Phase 06 Plan 07: Live-Serving Regression Test + Wiring Decisions Doc (Gap Closure)

**Built a warm-process regression test that drives the real get_rmm/get_compatibility/get_transfer_probability/get_financial_fit/get_summary functions and structurally proves add_player_impact/score_population/build_oracle_player_features never run per own-club request -- catching and correcting a mock patch-target bug in the plan's own verbatim code that would otherwise have made the structural guard a silent no-op, verified via live simulated-regression runs against the real 41,708-player dev DB.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-24T21:28:24Z (approx, immediately after 06-06)
- **Completed:** 2026-07-24T21:45:14Z
- **Tasks:** 2/2 completed
- **Files modified:** 3 (2 created, 1 fixed as a Rule-3 deviation)

## Accomplishments

- `test_live_scoring_performance.py` created: 5 tests, one per live service, each warming `get_scored_population()` once then asserting the real own-club call is sub-second (`WARM_CALL_CEILING_S = 1.0`) AND that the full-population pandas entry points are structurally never invoked.
- **Caught and fixed a real bug in the plan's own verbatim code before trusting it**: the plan text said to patch `add_player_impact`/`build_oracle_player_features` at their DEFINITION modules (`scoring.characterization.impact`/`scoring.characterization.tfm_model`). Read `population.py` and `financial_fit.py` directly and confirmed both import those functions via `from X import name` into their OWN module namespace and call them by that local name -- meaning `unittest.mock.patch` on the definition module would modify an attribute nobody actually looks up at call time, so `assert_not_called()` would pass trivially regardless of whether a regression occurred (zero protective value, a false sense of security).
- Corrected both patch targets to `scoring.services.population.add_player_impact` and `scoring.services.financial_fit.build_oracle_player_features` -- the actual name bindings `score_population()`/`financial_fit_from_population()` resolve at call time.
- **Verified the fix empirically against the real dev DB** (`.venv/bin/python manage.py shell`), not just by inspection:
  - Object-identity check: confirmed the definition-module patch does NOT replace the caller's bound name (`population_mod.add_player_impact is m_wrong` → `False`), while the corrected target does (`... is m_right` → `True`). Same for `build_oracle_player_features`/`financial_fit`.
  - Simulated-regression run 1: force-cleared `get_scored_population`'s cache (simulating a broken/bypassed memoization layer) and confirmed the corrected patch DOES intercept the resulting real `add_player_impact` call (`RuntimeError` raised via `side_effect`, mock `.called == True`) -- proving `assert_not_called()` would correctly fail in this regression class.
  - Simulated-regression run 2: monkeypatched `is_own_club` to always return `False` (simulating the own-club branch being reverted/removed from `get_financial_fit`) and confirmed the corrected patch intercepts the resulting `build_oracle_player_features` call the same way.
  - Positive-path run: confirmed all 5 services are genuinely sub-second warm against the real 41,708-player dev DB with the CORRECT (non-regressed) wiring, and that none of the mocks fire in that case -- `get_rmm` 0.060s, `get_compatibility` 0.149s, `get_transfer_probability` 0.047s, `get_financial_fit` 0.005s, `get_summary` 0.200s.
- Ran the full `scoring/tests/` suite (`-m "not integration"`) and found `test_services_summary.py`'s synthetic `get_summary` test failing with a `ValidationError` (`"p1" is not a valid UUID`) -- a latent regression from Plan 06-06's `is_own_club()` DB-lookup addition to `get_summary` that this specific test (not in 06-06's read_first/modified-files list) was never updated for. Fixed under Rule 3 (blocking issue in-scope for the plan's own "full sweep green" verification requirement): mocked `scoring.services.summary.is_own_club` to `return_value=False`, routing through the arbitrary-club path the test's existing mocks (`score_population`/`financial_fit_from_population`) already assumed.
- `06-live-wiring-DECISIONS.md` created, answering 06-VERIFICATION.md's flagged scope question explicitly ("Yes", SCORE-01..05 remain live/user-facing), documenting the per-service own-club/arbitrary-club design table, the Financial-Fit-uses-denormalized-field rationale, the breakdown decision, the accepted one-time cold-start trade-off, and the mock patch-target gotcha discovered while building the test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Warm-process sub-second + no-full-population-pandas regression test** - `05dadbc` (test)
2. **Task 2: Document the live-wiring design decision + accepted cold-start trade-off** - `6c00179` (docs)

**Plan metadata:** (pending — final docs commit below)

## Files Created/Modified

- `get-scouted-be/scoring/tests/test_live_scoring_performance.py` (created) -- 5 regression tests (`test_get_rmm_warm_is_fast_and_runs_no_full_population_pass`, `test_get_compatibility_own_club_warm_is_fast`, `test_get_transfer_probability_own_club_warm_is_fast`, `test_get_financial_fit_own_club_is_o1_denormalized_read`, `test_get_summary_own_club_warm_is_fast`), each warming the process then asserting sub-second timing + `assert_not_called()` on the correct full-population entry point/orchestrator for that service
- `get-scouted-be/scoring/tests/test_services_summary.py` (modified) -- added `patch("scoring.services.summary.is_own_club", return_value=False)` to the synthetic `test_get_summary_composes_four_helpers_from_single_reconstruction_synthetic` test's mock stack
- `.planning/phases/06-scoring-performance-caching-layer/06-live-wiring-DECISIONS.md` (created) -- the design-decision record

## Decisions Made

- Patch targets for `add_player_impact`/`build_oracle_player_features` corrected from the plan's literal text (patch at definition module) to the caller's own import binding (patch at usage module) -- the only location `unittest.mock.patch` can actually intercept, per Python's name-binding-not-object-identity semantics. The three `score_population` patches (`compatibility.py`/`transfer_probability.py`/`summary.py`) were already correct in the plan's verbatim text, since each of those services calls `score_population` via its own locally-imported name (confirmed by reading each service module).
- `test_services_summary.py`'s synthetic test mocks `is_own_club=False` rather than switching to real UUIDs -- keeps the test's existing arbitrary-club-path mock design (`score_population`/`financial_fit_from_population`) intact and DB-independent, matching its own docstring's "Synthetic, DB-independent guard" intent.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Plan's literal mock patch targets for `add_player_impact`/`build_oracle_player_features` would have been silent no-ops**
- **Found during:** Task 1, writing the test per the plan's verbatim code block
- **Issue:** The plan's `<action>` text specified patching `scoring.characterization.impact.add_player_impact` and (implicitly, via the verbatim code) `scoring.characterization.tfm_model.build_oracle_player_features` -- the DEFINITION modules. Both functions are imported into their CALLING modules (`population.py`, `financial_fit.py`) via `from X import name`, which binds a separate reference in the caller's own module `__dict__`. Patching the definition module's attribute does not affect that already-bound caller-side reference, so the mock would never be invoked and `m.assert_not_called()` would pass trivially regardless of whether a regression actually occurred -- providing zero real protection for the exact scenario this plan exists to guard against.
- **Fix:** Patched at the caller's own binding instead: `scoring.services.population.add_player_impact` and `scoring.services.financial_fit.build_oracle_player_features`. Verified the fix (and the original bug) empirically against the real dev DB via object-identity checks and two simulated-regression runs (broken-cache scenario, own-club-branch-removed scenario) -- both confirmed the corrected patches intercept the real call while the original literal targets do not.
- **Files modified:** `get-scouted-be/scoring/tests/test_live_scoring_performance.py`
- **Commit:** `05dadbc`

**2. [Rule 3 - Blocking issue] `test_services_summary.py`'s synthetic `get_summary` test broken by 06-06's `is_own_club()` addition**
- **Found during:** Task 1's full-sweep verification (`pytest scoring/tests/ -q`)
- **Issue:** Plan 06-06 added a real `is_own_club(player_id, club_id)` ORM lookup to `get_summary`. This synthetic, DB-independent test calls `get_summary("p1", "club-uuid")` with non-UUID placeholder ids, which now raises `django.core.exceptions.ValidationError: "p1" is not a valid UUID` before reaching any of the test's mocked logic. Not caught by 06-06 since this test file wasn't in 06-06's read_first/modified-files list, and 06-06's own full-suite verification run didn't include it.
- **Fix:** Added `patch("scoring.services.summary.is_own_club", return_value=False)` to the test's existing mock stack, routing through the arbitrary-club path the test's other mocks (`score_population`/`financial_fit_from_population`) already assumed. Verified: test passes in isolation and the full `scoring/tests/` sweep (`-m "not integration"`) is now green (56 passed, 290 skipped, 3 deselected, 0 failed).
- **Files modified:** `get-scouted-be/scoring/tests/test_services_summary.py`
- **Commit:** `05dadbc`

**Total deviations:** 2 auto-fixed (1 bug in the plan's own verbatim code, corrected before trusting it; 1 blocking pre-existing test regression inherited from 06-06, fixed to satisfy this plan's own "full sweep green" verification requirement); 0 architectural; 0 out-of-scope items left untouched this plan (the pre-existing unrelated `clubs/models.py` docstring diff noted by 06-05 remains untouched, consistent with prior plans).
**Impact on plan:** None on scope -- both fixes are corrections to test-only code that make the plan's own stated regression-guarding purpose actually true, not scope expansions.

## Issues Encountered

None beyond the two deviations above, both resolved within the fix-attempt budget.

## User Setup Required

None -- no external service configuration required.

## Verification Evidence

Live-verified against the real 41,708-player dev DB (`get-scouted-be/.venv/bin/python manage.py shell`, since the ambient interpreter lacks scikit-learn):

```
player/club: 00032014-830c-41df-90b2-07746ceee1d0 89e28386-3245-4449-953e-f5d7ca6fe2f8

=== POSITIVE CHECKS (current correct code, warm) ===
get_rmm elapsed 0.0598s   mock called: False   rmm: 74.93
get_compatibility elapsed 0.1489s   mock called: False
get_transfer_probability elapsed 0.0467s   mock called: False
get_financial_fit elapsed 0.0049s   mock called: False   predicted_fee present: True
get_summary elapsed 0.2001s   mock called: False   keys: {compatibility, transfer_probability, rmm, financial_fit}

=== Patch-target object-identity proof ===
WRONG target (definition module) intercepts population.py's call-site name? False
CORRECT target (usage module) intercepts population.py's call-site name? True
WRONG target (tfm_model definition) intercepts financial_fit.py's call-site name? False
CORRECT target (financial_fit usage) intercepts financial_fit.py's call-site name? True

=== SIMULATED REGRESSION 1: caching layer broken (cache cleared before request) ===
PASS: add_player_impact WAS invoked (mock called: True) -- corrected patch target
      catches a broken-cache regression; assert_not_called() would correctly fail here

=== SIMULATED REGRESSION 2: get_financial_fit's own-club branch removed (always live) ===
PASS: build_oracle_player_features WAS invoked (mock called: True) -- corrected patch
      target catches an own-club-branch-removed regression; assert_not_called()
      would correctly fail here
```

Test suite (empty pytest test DB, standard project convention): `python -m pytest scoring/tests/test_live_scoring_performance.py -q` → 5 skipped (clean skip, project's real-data-test convention -- pytest-django's own test DB has no Player rows). Full sweep: `python -m pytest scoring/tests/ -q -m "not integration"` → **56 passed, 290 skipped, 3 deselected, 0 failed**.

## Next Phase Readiness

- All 3 gap-closure plans (06-05, 06-06, 06-07) are complete. `test_live_scoring_performance.py` now provides the durable, empirically-verified regression guard 06-VERIFICATION.md's Gap 1 explicitly required.
- `06-live-wiring-DECISIONS.md` gives the phase re-verifier an explicit, documented answer to the scope question flagged in `human_verification` -- no longer an unstated assumption.
- SCORE-07 remains NOT marked complete in REQUIREMENTS.md, per orchestrator instruction -- that determination belongs to the phase verifier's re-verification pass against `06-VERIFICATION.md`'s original gaps, not to this plan.

---
*Phase: 06-scoring-performance-caching-layer*
*Completed: 2026-07-24*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/tests/test_live_scoring_performance.py
- FOUND: .planning/phases/06-scoring-performance-caching-layer/06-live-wiring-DECISIONS.md
- FOUND: get-scouted-be/scoring/tests/test_services_summary.py (modified)
- FOUND: 05dadbc (Task 1 commit)
- FOUND: 6c00179 (Task 2 commit)
