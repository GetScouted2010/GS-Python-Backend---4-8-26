---
phase: 04-scoring-engine-port
plan: 04
subsystem: api
tags: [django, pandas, scikit-learn, service-layer, scoring, tfm]

# Dependency graph
requires:
  - phase: 04-scoring-engine-port
    plan: 01
    provides: "reconstruct_population/score_population (RMM-first)/resolve_club_name/get_tfm_pipeline substrate (scoring/services/population.py); null_with_reason envelope"
provides:
  - "get_financial_fit(player_id, club_id): money-scale TFM predicted_fee priced against a SPECIFIC requested club's buying profile, plus market_value comparison and Bargain/Fair Value/Overpay verdict"
  - "financial_fit_from_population(player_id, club_name, pop, scored, cs_tp): the core computation, reusable by the summary endpoint (Plan 05) with no extra reconstruction"
affects: [04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Buying-club-context override: the requested club's name overwrites the target player's Team column on players_df BEFORE build_oracle_player_features runs, so club-aggregate features (and the prediction) genuinely reflect the requested club, not the player's own club"
    - "Log-scale-to-money-scale unwrap: np.expm1(pipeline.predict(X)) applied at the single point predicted_fee is produced"
    - "Process-level test cache (module dict) for score_population's ~80s full-population RMM+CS/TP pass, with reconstruct_population/score_population monkeypatched per-test so real-data tests still exercise the real get_financial_fit entry point without repaying that cost"

key-files:
  created:
    - get-scouted-be/scoring/services/financial_fit.py
    - get-scouted-be/scoring/tests/test_services_financial_fit.py
  modified: []

key-decisions:
  - "The 4 upstream feature columns (player_impact/compatibility_score/performance_score/role_pct) are computed with club_context=None (each player's OWN club) inside get_financial_fit, matching the oracle/training methodology for those specific features; only the club-AGGREGATE features inside build_oracle_player_features reflect the overridden target club -- the locked buying-club-context decision is scoped to club-aggregates, per 04-RESEARCH.md's resolution"
  - "Real-data tests cache score_population's expensive (~80s) full-41,708-player RMM+CS/TP pass at process level and monkeypatch reconstruct_population/score_population per test, rather than calling get_financial_fit end-to-end repeatedly -- keeps the real-artifact test suite fast (~90s total) while still exercising the real entry point, real DB club lookups, and the real trained pipeline"

requirements-completed: []

# Metrics
duration: 30min
completed: 2026-07-23
---

# Phase 4 Plan 04: Financial Fit (TFM) Service Summary

**`get_financial_fit(player_id, club_id)` prices a player against a SPECIFIC requested club's buying profile using the trained TFM sklearn pipeline, unwraps its log-scale raw output to a real money-scale `predicted_fee` via `np.expm1`, and returns the market-value comparison plus Bargain/Fair Value/Overpay verdict.**

## Performance

- **Duration:** ~30 min
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `financial_fit.py` merges `player_impact`/`compatibility_score`/`performance_score`/`role_pct` onto a `players_df` copy BEFORE calling `build_oracle_player_features` (fact 2) -- that function reads those 4 columns straight off `players_df` (tfm_model.py line ~799) and silently NaNs them if absent.
- The requested `club_id`'s resolved name overwrites the target player's `Team` on `players_df` BEFORE the feature build, so `club_id` genuinely changes the club-aggregate features (`club_pos_avg_in_fee`, `seller_hist_*`, etc.) fed into the pipeline -- verified directly against the real 41,708-player population: the same player priced against 6 different real clubs produced fees ranging from ~€597K to ~€1.29M, not a single repeated value.
- `predicted_fee = float(np.expm1(pipeline.predict(X))[0])` unwraps the confirmed log-scale (`log1p(fee)`) raw prediction to money-scale -- verified: real predictions for real players land in the hundreds-of-thousands-to-millions range, never the [0, 20] log-scale bug range.
- `feature_cols` always comes from `get_tfm_pipeline()`'s `.metrics.json` sidecar (23 entries, exact order) -- a dedicated test captures the actual columns passed to `pipeline.predict` and asserts list equality against the sidecar, including a "does an extra engineered column leak through" guard.
- `add_value_labels` produces `value_verdict` (Bargain/Fair Value/Overpay) + `fee_diff`/`ratio_market_to_predicted` in `value_comparison`; a row with `_has_club_context=False` returns the shared `null_with_reason("predicted_fee", "no_club_context")` envelope instead of a fabricated fee.
- `financial_fit_from_population(player_id, club_name, pop, scored, cs_tp)` is exposed as a separate reusable core so Plan 05's summary endpoint can call it directly with an already-reconstructed/scored population instead of reconstructing again.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Write failing tests including the money-scale regression test (RED)** - `2eda89b` (test)
2. **Task 2: Implement the Financial Fit service with RMM-first merge + Team override + np.expm1 unwrap (GREEN)** - `7c4751c` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `get-scouted-be/scoring/services/financial_fit.py` - `get_financial_fit`, `financial_fit_from_population`, `_merge_tfm_feature_columns`
- `get-scouted-be/scoring/tests/test_services_financial_fit.py` - 8 tests: sidecar feature_cols fidelity, upstream RMM-first merge guard, Team-override mechanism guard, null envelope, money-scale regression, verdict/market-value shape, real-data club-override effect, unknown-club Http404

## Decisions Made

- Scoped the buying-club-context override to the club-AGGREGATE features only (matching 04-RESEARCH.md's documented resolution) -- the 4 upstream RMM/CS/TP-derived features stay computed against each player's own current club, consistent with how the oracle/training pipeline computed them.
- Built a process-level cache for `score_population`'s expensive full-population pass in the real-data tests (verified at ~77s for the whole 41,708-player RMM+CS/TP computation) with `reconstruct_population`/`score_population` monkeypatched per test, so 5 real-data tests share one computation instead of each paying it independently -- kept the real-artifact-backed test suite (real trained pipeline, real DB club/player rows) fast without weakening what's actually being tested.

## Deviations from Plan

None - plan executed exactly as written, including the exact `_merge_tfm_feature_columns`/`financial_fit_from_population`/`get_financial_fit` implementations spelled out in Task 2's action block.

## Issues Encountered

- `score_population` over the real 41,708-player population takes ~77s (RMM's per-position calculators + Compatibility/Transfer-Probability over the whole population), which made the plan's literal "call `get_financial_fit` per player/club combination in a loop" test style prohibitively slow for a real-data test suite. Resolved by caching the reconstructed+scored population at the test-module level (a plain dict, populated once by the first test that needs it) and monkeypatching `reconstruct_population`/`score_population` inside `scoring.services.financial_fit` for the duration of each test -- `get_financial_fit` is still exercised as the real, un-mocked entry point (real `resolve_club_name` DB lookup, real `build_oracle_player_features`, real trained pipeline `predict`), only the expensive population-wide scoring pass is shared across tests. Not a deviation from any locked plan requirement -- an implementation detail of how the real-data tests source their fixture data.
- To exercise the `real_data_available`-gated tests locally (rather than skip, as Plan 01 documented for the standard empty pytest-django test DB), this session's `test_getscouted` database was seeded from a `CREATE DATABASE ... TEMPLATE getscouted` copy of the real dev DB (41,708 players) -- a one-time local environment setup, not a code or plan change. Both money-scale regression numbers and the club-override numbers quoted above (~€597K-€1.29M range) came from this real run, not a synthetic fixture.

## User Setup Required

None - no external service configuration required. (The `test_getscouted` local DB seeding above is a one-time dev-environment convenience for exercising `real_data_available` tests without skipping; it is not required for this plan's code to function, and pytest-django will continue to gracefully skip these tests in any environment where it's absent, per the existing `real_data_available` fixture pattern from Phase 3/04-01.)

## Next Phase Readiness

- Plan 05 (summary endpoint) can call `financial_fit_from_population(player_id, club_name, pop, scored, cs_tp)` directly with its own already-reconstructed/scored `Population`, `scored`, and `cs_tp` -- no extra reconstruction needed.
- No changes were made to any file under `scoring/characterization/` (verified via `git diff --stat` scope of this plan's commits).
- `get_financial_fit`'s Http404 behavior (unknown `club_id`, via `resolve_club_name`) is available for Plan 06's DRF view layer to translate into a 404 response.

---
*Phase: 04-scoring-engine-port*
*Completed: 2026-07-23*

## Self-Check: PASSED

All created files (`get-scouted-be/scoring/services/financial_fit.py`, `get-scouted-be/scoring/tests/test_services_financial_fit.py`) and commit hashes (`2eda89b`, `7c4751c`) verified present.
