# Phase 6 — Live-Serving Wiring Decisions (gap closure, Plans 06-05..06-07)

## Scope question the verifier flagged (06-VERIFICATION.md human_verification)
Are Phase 4's SCORE-01..05 detail endpoints still live/user-facing and therefore
expected to be fast? **Yes.** 06-CONTEXT.md's own language ("those stay live-computed,
but faster") and REQUIREMENTS.md marking SCORE-01..05 Complete both mean these are the
production scoring surface. Plans 06-05/06-06 make them fast rather than deferring them
to a future Phase 7 endpoint. This is now an explicit decision, not an assumption.

## Per-service design
| Service | Own-club (common case) | Arbitrary other club (Phase 12 path) |
|---|---|---|
| RMM (context-free) | slice memoized get_scored_population().scored | n/a (no club context) |
| Compatibility | slice memoized get_scored_population().cs_tp | live score_population(pop, club_name) |
| Transfer Probability | slice memoized get_scored_population().cs_tp | live score_population(pop, club_name) |
| Financial Fit | read denormalized Player.financial_fit_score (O(1) DB) | live get_scored_population() upstream + club-override TFM build |
| Summary | aggregate reads + denormalized financial | live score_population + financial_fit_from_population |

## Why Financial Fit uses the denormalized field, not the aggregate
RMM/CS/TP breakdowns can be sliced from the cached (scored, cs_tp) frames, so those
services stay O(1)-warm WITH full breakdowns. Financial Fit's predicted_fee, however,
requires a full-population build_oracle_player_features pass (club-aggregate features)
that cannot be sliced from cs_tp — so the own-club fee is read from the denormalized
Player.financial_fit_score instead (money-scale, np.expm1 applied at write time). This
is the first production consumer of the field Plans 06-01/06-03 built.

## Breakdown decision
SCORE-05 breakdowns are preserved for every service. RMM/CS/TP breakdowns come from the
cached aggregate rows. Financial Fit's "breakdown" (value_comparison + value_verdict) is
re-derived from the denormalized fee + Player.market_value via the same add_value_labels
logic — no full-population data needed.

## Accepted trade-off: one-time cold start
The RMM/CS/TP/summary own-club paths depend on get_scored_population()'s in-process
lru_cache. The FIRST request in a fresh process pays the ~92s cold build once, then every
subsequent request is O(1). This is the same in-process-cache trade-off 06-CONTEXT.md
already accepted (each server process warms its own copy once; Redis/shared-cache is a
documented Deferred Idea). Financial Fit's own-club path has NO cold cost — it is a plain
indexed DB read. SCORE-07's Criterion 4 ("stays flat as dataset size grows") is about
per-entity retrieval scaling, which the warm path satisfies (proven by
test_live_scoring_performance.py).

## Non-changes
No scoring math changed. RMM/CS/TFM/TP correctness (Phases 3-5) and the parity suite are
untouched — the aggregate/denormalized values are byte-identical to the prior live
computation for the own-club case. Endpoint contracts and response shapes are unchanged;
views.py/urls.py were not modified.

## Regression-test patch-target note (found during Plan 06-07)
`test_live_scoring_performance.py`'s structural `assert_not_called()` checks must patch
the full-population functions (`add_player_impact`, `build_oracle_player_features`) at
the NAME BINDING each caller actually resolves at call time (`scoring.services.
population.add_player_impact`, `scoring.services.financial_fit.
build_oracle_player_features`), not at their origin/definition module
(`scoring.characterization.impact`/`tfm_model`). Patching the definition module leaves
the caller's own already-imported reference untouched (`from X import name` binds a
separate name in the caller's module dict), so the mock would never be invoked and
`assert_not_called()` would pass trivially with zero regression-catching power —
verified directly against the real dev DB during this plan's execution (object-identity
check confirmed the wrong target does NOT intercept the caller's bound name, the
corrected target does). The `score_population` patches for compatibility/
transfer_probability/summary were already correct, since each of those services calls
`score_population` via its own locally-imported module name.
