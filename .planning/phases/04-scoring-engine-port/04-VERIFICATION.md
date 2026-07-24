---
phase: 04-scoring-engine-port
verified: 2026-07-24T11:15:00Z
status: passed
score: 10/10 must-haves verified
---

# Phase 4: Scoring Engine Port Verification Report

**Phase Goal:** The curated, authoritative calculators for all four scores run as real Django/Python services and are reachable via API with full component breakdowns.
**Verified:** 2026-07-24
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Player Score (RMM) via API returns a real computed value, not an approximation | ✓ VERIFIED | Direct call to `get_rmm` against real DB (41,708 players) returned `{'rmm': 74.93, 'positive': 64.35, 'negative': 47.38, 'components': {...5 position-specific keys...}, 'reliability': 'Very Low'}`. Confirmed via `scoring/services/rmm.py` reading `add_player_impact`'s output, never `compute_rmm_column`. |
| 2 | Compatibility Score (CS) via API returns a real computed value | ✓ VERIFIED | `get_compatibility` against real club "AGF" (has style data) returned `compatibility_score=86.62` with full breakdown. Repeated for 30,938 real player/club pairs with non-null CS. |
| 3 | The plan-checker-caught role_scores_wide merge bug fix is genuinely present and functioning | ✓ VERIFIED | Code inspection of `compatibility.py` and `summary.py` confirms `pop.players_df.merge(pop.role_scores_wide, on="player_id", how="left", ...)` runs BEFORE player_row is sliced. Mathematically confirmed against 3 real players: `round((clip(role_fit_score,0,100)+bonus)/2,2)` reconstructed `compatibility_score` EXACTLY (86.62==86.62, 77.42==77.42, 74.44==74.44) — this is the exact regression the plan-checker flagged, and it is fixed, not just claimed. |
| 4 | Financial Fit (TFM) via API returns a real money-scale value, not the raw log-scale model output | ✓ VERIFIED | Real prediction returned `predicted_fee=1,291,198.37` (money-scale, matches `np.expm1(pipeline.predict(X))` in code) — never in the 13-17 log range the raw pipeline output would produce. |
| 5 | Financial Fit's buying-club override genuinely changes the prediction context, not just a label | ✓ VERIFIED | `financial_fit.py`'s `players_df.loc[mask, "Team"] = club_name` runs BEFORE `build_oracle_player_features`; the returned `buying_club` field reflects the requested club ("Burnley U21"), and this Team value feeds the club-aggregate features. |
| 6 | Transfer Probability via API returns the real value plus all 4 weighted terms | ✓ VERIFIED | Real call returned `{'transfer_probability': 86.9, 'components': {'compatibility': {'raw': 86.62,'weight':0.3,'contribution':25.99}, 'performance': {...0.2...}, 'financial': {...0.2...}, 'contract_fit': {...0.3...}}}` — weights and contributions matched the WEIGHTS dict exactly and summed to the reported transfer_probability. |
| 7 | Every score response includes a component breakdown, not just a final number | ✓ VERIFIED | All 4 real responses above carry `components`/breakdown structures (RMM: positive/negative/components/reliability; CS: role_fit_score/similarity_pct/bonus; TFM: value_comparison/value_verdict; TP: 4-term raw/weight/contribution). |
| 8 | Summary endpoint reconstructs the population once and combines all 4 scores | ✓ VERIFIED | `get_summary` calls `reconstruct_population()` and `score_population()` exactly once (single call sites in `summary.py`), then reuses `rmm_breakdown_from_scored`/`cs_breakdown_from_row`/`tp_breakdown_from_row`/`financial_fit_from_population`. Real call returned all 4 top-level keys with populated/null-enveloped values, each degrading independently. |
| 9 | All 5 endpoints are reachable under /api/scoring/ and require authentication | ✓ VERIFIED | `reverse()` resolved all 5 URL names. Live HTTP test via Django's test `Client` against the real DB: unauthenticated GET → 401; JWT-authenticated GET → 200 with real computed data, for `/impact/`, `/financial-fit/`, and `/summary/`. `test_endpoints_require_authentication` (parametrized over all 5 URLs) passed in the automated suite without needing real data. |
| 10 | Full scoring test suite passes with no regressions | ✓ VERIFIED (with note) | `pytest scoring -q` → 53 passed, 36 skipped, 0 failed. Skips are all `real_data_available`-gated tests skipping against the empty pytest-django ephemeral test DB (same pre-existing Phase 3 pattern, not new to Phase 4) — separately confirmed correct by manually exercising the exact same service functions against the real 41,708-player dev DB (see truths 1-9 above). |

**Score:** 10/10 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/scoring/services/population.py` | `reconstruct_population`, `score_population` (RMM-first), `resolve_club_name`, `get_tfm_pipeline` | ✓ VERIFIED | All 4 present; `score_population` runs `add_player_impact` then merges `player_impact` BEFORE calling `compute_cs_tp_for_pairs`; `get_tfm_pipeline` is `lru_cache(maxsize=1)`-memoized and reads `feature_cols` from the `.metrics.json` sidecar, never hardcoded. |
| `get-scouted-be/scoring/services/rmm.py` | `get_rmm` reads `add_player_impact`'s breakdown | ✓ VERIFIED | `get_rmm` calls `add_player_impact` directly; `compute_rmm_column` is never imported or called (grep confirms no match). |
| `get-scouted-be/scoring/services/compatibility.py` | `get_compatibility` merges `role_scores_wide` onto `players_df` BEFORE slicing `player_row` | ✓ VERIFIED | Confirmed present in code AND mathematically verified against real data (see truth #3) — the plan-checker-caught bug fix is genuinely implemented, not just claimed. |
| `get-scouted-be/scoring/services/transfer_probability.py` | `get_transfer_probability` exposes all 4 weighted terms | ✓ VERIFIED | `WEIGHTS = {"compatibility": 0.30, "performance": 0.20, "financial": 0.20, "contract_fit": 0.30}`; real response carries all 4 with raw/weight/contribution. |
| `get-scouted-be/scoring/services/financial_fit.py` | `np.expm1()` unwrap + buying-club override | ✓ VERIFIED | Both present in code and confirmed via real prediction (money-scale value, buying_club reflects override). |
| `get-scouted-be/scoring/services/summary.py` | `get_summary` reconstructs population exactly once | ✓ VERIFIED | Single `reconstruct_population()` + single `score_population()` call site; reuses per-score `*_from_row`/`*_from_scored`/`financial_fit_from_population` helpers, no re-reconstruction. |
| `get-scouted-be/scoring/serializers.py` | 5 serializers exist | ✓ VERIFIED | `RMMSerializer`, `CompatibilitySerializer`, `FinancialFitSerializer`, `TransferProbabilitySerializer`, `SummarySerializer` all present, import cleanly, each exposes an optional `reason` field for the null envelope. Note: per 04-06-SUMMARY.md, views return `Response(service_function(...))` directly without instantiating these serializers — they document the contract but aren't wired for validation. This matches the plan's explicit scope (documentation/contract, not enforcement) and is not a gap. |
| `get-scouted-be/scoring/views.py` + `urls.py` + `config/urls.py` | 5 endpoints wired under `/api/scoring/`, authenticated | ✓ VERIFIED | All 5 `path()` patterns present; `config/urls.py` includes `scoring.urls` under `api/scoring/`; views are thin (`get_object_or_404` + delegate to `scoring.services.*` + `Response(...)`); global `IsAuthenticated` + `JWTAuthentication` DRF defaults apply (no bespoke permission class needed). |
| `get-scouted-be/scoring/tests/` | Full suite passes | ✓ VERIFIED | `53 passed, 36 skipped, 0 failed` — skips are environmental (empty ephemeral test DB), independently confirmed correct via direct real-DB verification. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `population.py` | `impact.add_player_impact` + `deterministic_scores.compute_cs_tp_for_pairs` | RMM merged onto players_df before compute_cs_tp_for_pairs | ✓ WIRED | Line order confirmed: `add_player_impact` call precedes `compute_cs_tp_for_pairs` call; `player_impact=rmm_series` passed explicitly. |
| `population.py` | TFM joblib artifact + `.metrics.json` | `lru_cache`-memoized `joblib.load` + json `feature_cols` read | ✓ WIRED | `@lru_cache(maxsize=1)` decorator present; `feature_cols` read from `json.load(open(metrics_path))["feature_cols"]`, never hardcoded. |
| `compatibility.py` | `pop.players_df.merge(pop.role_scores_wide, ...)` before slicing `player_row` | Replicates `deterministic_scores.py:354`'s internal merge | ✓ WIRED | Confirmed in code and mathematically verified with real data (reconstruction check exact match, 3/3 sampled players). |
| `transfer_probability.py` | `population.score_population` | Reads compatibility/performance/financial/contract_fit off `cs_tp` row, reapplies weights | ✓ WIRED | Real response shows raw values matching cs_tp columns and correct weighted contributions. |
| `financial_fit.py` | `population.score_population` (RMM-first) → merge 4 upstream features → `build_oracle_player_features` | `player_impact` + CS/TP columns merged before feature build | ✓ WIRED | `_merge_tfm_feature_columns` runs before `build_oracle_player_features`; confirmed via code + real prediction being sane (not NaN-degraded). |
| `financial_fit.py` | `predicted_fee` money-scale contract | `np.expm1` applied to `pipeline.predict` output | ✓ WIRED | Real predicted_fee = 1,291,198.37 (money-scale, not 13-17 log range). |
| `summary.py` | `rmm`/`compatibility`/`transfer_probability`/`financial_fit` helpers | One reconstruct + one score_population, results sliced per-player | ✓ WIRED | Single call sites confirmed; real summary response populated all 4 keys correctly. |
| `config/urls.py` | `scoring/urls.py` | `path('api/scoring/', include('scoring.urls'))` | ✓ WIRED | Confirmed via grep and live `reverse()` resolution of all 5 URL names. |
| `views.py` | `scoring.services.{rmm,compatibility,financial_fit,transfer_probability,summary}` | Each view calls its service function, returns `Response(result)` | ✓ WIRED | Confirmed via code read and live HTTP round-trip (Django test Client, real DB) returning 200 with real computed data. |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|--------------|--------|----------|
| SCORE-01 | 01, 02, 05, 06 | RMM computed via curated port, exposed via API | ✓ SATISFIED | `get_rmm` + `/impact/` endpoint verified with real data. |
| SCORE-02 | 03, 05, 06 | CS between player and club computed and exposed via API | ✓ SATISFIED | `get_compatibility` + `/compatibility/` endpoint verified with real data, including the role-merge fix. |
| SCORE-03 | 04, 05, 06 | Financial Fit (TFM) computed and exposed via API | ✓ SATISFIED | `get_financial_fit` + `/financial-fit/` endpoint verified with real money-scale prediction. |
| SCORE-04 | 03, 05, 06 | Transfer Probability computed and exposed via API | ✓ SATISFIED | `get_transfer_probability` + `/transfer-probability/` endpoint verified with real 4-term breakdown. |
| SCORE-05 | 01-06 (all) | All 4 scores return a component breakdown, not just a final number | ✓ SATISFIED | Every service returns breakdown structures; confirmed via real API responses. |

No orphaned requirements: every SCORE-01..05 ID declared across the 6 plans' `requirements` frontmatter is accounted for; no additional Phase-4-mapped IDs in REQUIREMENTS.md are missing from a plan.

**Documentation note (not a code gap):** `.planning/REQUIREMENTS.md`'s tracking table still lists SCORE-01 through SCORE-05 as `In progress (Plan 1/6 — substrate only, no API endpoints yet)` with unchecked `[ ]` boxes. This is stale — all 6 plans are complete and the code verification above confirms all 5 requirements are satisfied. This tracking table should be updated as part of phase completion, separate from this verification.

### Anti-Patterns Found

None. Scanned all Phase 4 files under `scoring/services/`, `scoring/serializers.py`, `scoring/views.py`, `scoring/urls.py` for TODO/FIXME/placeholder/stub patterns and empty-return anti-patterns — the only `return null_with_reason(...)`/`return None`-shaped matches found are the intentional, documented shared missing-data envelope, not stubs.

### Human Verification Required

None required for functional correctness — the phase goal (real, non-approximated, breakdown-carrying scores reachable via API) was independently confirmed via direct execution against the real 41,708-player dev database, both at the service layer and through the full HTTP request/response cycle (auth gate + real computed payloads).

Optional follow-up for the team (not blocking phase completion):
1. **Test DB seeding for CI** — the `real_data_available`-gated tests (36 skips) will continue to skip in any CI environment using a fresh ephemeral pytest-django test DB. If full-suite CI confidence (not just this manual verification) is desired going forward, consider seeding the CI test DB from a snapshot of the real dev DB, as 04-04-SUMMARY.md notes was done locally for one session.
2. **Performance** — `score_population` over the full population takes roughly 60-100+ seconds per request (confirmed empirically during this verification). This is explicitly flagged in the plans as "correct-but-slow, ready for Phase 5/6 parity + caching work" — not a Phase 4 scope failure, but worth surfacing since it affects real request latency until a later phase addresses it (SCORE-07).

### Gaps Summary

No gaps found. All 10 derived observable truths, all 9 required artifacts, and all 9 key links verified against the actual codebase and confirmed against real production-scale data (41,708 players), not just plan claims or SUMMARY.md narrative. The specific plan-checker-caught regression (CS breakdown's role_scores_wide merge) was independently re-derived and mathematically confirmed fixed using real player/club pairs, not just re-read from the SUMMARY.

---

_Verified: 2026-07-24T11:15:00Z_
_Verifier: Claude (gsd-verifier)_
