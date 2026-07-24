---
phase: 05-scoring-parity-testing
verified: 2026-07-24T16:10:00Z
status: passed
score: 3/3 must-haves verified
---

# Phase 5: Scoring Parity Testing Verification Report

**Phase Goal:** The Django port is proven numerically faithful to the original script, not just "runs without crashing."
**Verified:** 2026-07-24T16:10:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP.md Success Criteria, used as must-haves per Option B)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | An automated parity test suite runs the Django port against the Phase 3 oracle snapshot for every position group and reports pass/fail within an agreed numerical tolerance. | VERIFIED | `scoring/tests/test_parity_bulk.py` (185 lines) parametrizes `test_rmm_parity_per_group`/`test_cs_parity_per_group`/`test_tp_parity_per_group` over `POSITION_GROUPS` (all 10 real groups: GK, CB, LB, RB, CM, DMF, AMF, LW, RW, CF) plus `test_tfm_parity_bulk`. Tolerances (`RMM_CS_TP_ATOL=0.01`, `TFM_RTOL=0.001`) and the both-null-aware comparator live in one shared module `scoring/tests/_parity_helpers.py` (186 lines), imported by all three parity test files. |
| 2 | The full parity suite passes for all position groups before the port is considered done. | VERIFIED | 05-02-SUMMARY.md documents a live run against the real 41,708-player dev DB: **31/31 tests passed** (10 RMM + 10 CS + 10 TP + 1 TFM). Independently re-confirmed: (a) `pytest scoring/tests/test_parity_bulk.py scoring/tests/test_parity_api_sample.py scoring/tests/test_parity_edge_cases.py scoring/tests/test_oracle_snapshot.py -q` skips cleanly (2 passed, 245 skipped) against pytest-django's empty test DB, as expected by project convention; (b) spot-checked 4 individual real-data claims directly via `manage.py shell` against the live dev DB (41,708 players confirmed present) — zero-minutes RMM (oracle 37.26 == port 37.26), invalid-position RMM both-null (oracle NaN, port None, pass), missing-market-value TFM (oracle-money 669266.82 == port 669266.82), CB CS (oracle 88.47 == port 88.47) — all matched exactly, corroborating the SUMMARY.md figures rather than merely trusting the text. |
| 3 | Edge cases (missing stats, boundary ages, zero-appearance players) are covered by the parity suite and pass. | VERIFIED | `scoring/tests/test_parity_edge_cases.py` (278 lines) contains 7 dynamically-mined named tests: zero-minutes (`Minutes_played=0`), missing `market_value`, missing `club`, youngest/oldest age boundaries (`exclude(age=0)` for genuine youngest), `age==0` placeholder, invalid `main_position=="0"`. 05-04-SUMMARY.md documents all 7 live-verified exact-match against the real dev DB. Independently re-confirmed 2 of these (zero-minutes, invalid-position) directly, matching the documented values exactly. |

**Score:** 3/3 truths verified

### Additional Tier-2 Coverage (per-request wiring — the class of bug SCORE-06 exists to catch)

`scoring/tests/test_parity_api_sample.py` (427 lines) drives a seeded (`np.random.default_rng(42)`), stratified ~31-player sample through the real `get_rmm`/`get_compatibility`/`get_financial_fit`/`get_transfer_probability`/`get_summary` service functions and 5 real authenticated DRF endpoints (`force_authenticate` present), memoizing `score_population` to avoid the ~90s-per-player naive cost. 05-03-SUMMARY.md documents 6 service-level players (GK/LB/RB/CB×3) and 5 endpoint-level players passing every assertion live against the dev DB, plus a 401 check for unauthenticated requests. Independently re-confirmed one additional CS check (CB player, oracle 88.47 == port 88.47) via the real per-request `get_compatibility` service.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scoring/tests/_parity_helpers.py` | Oracle discovery, load+bucketing, UUID→str normalizer, both-null-aware comparator, mismatch writer | VERIFIED | 186 lines. Contains `find_latest_oracle_csv`, `load_oracle_df`, `to_str_index`, `compare_scalar`, `compare_series`, `compare_tfm_series`, `write_mismatch_report`, `POSITION_GROUPS` (10 groups), `GROUPS_WITH_NULL_CS_TP = {"GK","LB","RB"}`, `RMM_CS_TP_ATOL = 0.01`, `TFM_RTOL = 0.001`. Imports `normalise_position` from `scoring.characterization.impact` (no hand-rolled position dict). |
| `scoring/tests/test_oracle_snapshot.py` | Refactored to consume shared discovery helper | VERIFIED | 87 lines; imports `find_latest_oracle_csv` from `_parity_helpers`; passes/skips cleanly. |
| `scoring/tests/test_parity_bulk.py` | Tier-1 full-population parity, parametrized over 10 groups | VERIFIED | 185 lines. `@pytest.mark.parametrize("group", POSITION_GROUPS)` on 3 tests, `score_population(pop, None)` bulk call, `to_str_index` applied before `.reindex`, GK/LB/RB both-null assertion present, TFM uses raw log-scale `pipeline.predict` reconciled via `compare_tfm_series`. |
| `scoring/tests/test_parity_api_sample.py` | Tier-2 per-request service + DRF endpoint parity | VERIFIED | 427 lines. Seeded stratified sample, `force_authenticate`, all 5 endpoint paths, `compare_scalar`-only comparisons, `oracle.loc[str(...)]` lookups throughout, memoized `score_population`. |
| `scoring/tests/test_parity_edge_cases.py` | Named real-data edge-case parity | VERIFIED | 278 lines. `Minutes_played=0`, `market_value__isnull`, `club__isnull`, `exclude(age=0)`, `age=0` placeholder, `main_position="0"` — all dynamically mined, all via `compare_scalar`. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `_parity_helpers.py` | `scoring.characterization.impact.normalise_position` | import + apply on `main_position` | WIRED | `from scoring.characterization.impact import normalise_position` present; used in `load_oracle_df`. |
| `test_oracle_snapshot.py` | `_parity_helpers.find_latest_oracle_csv` | import replaces local glob | WIRED | Confirmed via grep; local `_find_latest_oracle_csv` removed. |
| `test_parity_bulk.py` | `scoring.services.population.score_population` | one `score_population(pop, None)` module-scope call | WIRED | Confirmed in module-scope `bulk_scored` fixture. |
| `test_parity_bulk.py` | `_parity_helpers` | `load_oracle_df`/`to_str_index`/`compare_series`/`compare_tfm_series`/`POSITION_GROUPS` | WIRED | All imported and used, no re-implementation of tolerance/id-cast logic. |
| `test_parity_api_sample.py` | `scoring.services.{rmm,compatibility,financial_fit,transfer_probability,summary}` | real `get_*` calls with memoized reconstruct/score patched in | WIRED | `get_compatibility(` and siblings called; `patch("scoring.services.` present. |
| `test_parity_api_sample.py` | `_parity_helpers` | `compare_scalar`/`load_oracle_df` | WIRED | Confirmed. |
| `test_parity_edge_cases.py` | `scoring.services.rmm.get_rmm` / `summary.get_summary` / `financial_fit.get_financial_fit` | real per-request service calls on mined edge players | WIRED | Confirmed; also uses `get_financial_fit`/direct `score_population` lookup for the missing-club CS case, a deliberate and documented deviation that still satisfies the plan's key-link pattern (`get_rmm\(` matches 5×). |
| `test_parity_edge_cases.py` | `_parity_helpers` | `compare_scalar`/`load_oracle_df` | WIRED | Confirmed. |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|--------------|--------|----------|
| SCORE-06 | 05-01, 05-02, 05-03, 05-04 | The Django port passes a numerical parity test suite against the original script's real output, within an agreed tolerance, for every position group | SATISFIED | All 3 ROADMAP success criteria verified above (test suite exists, passes for all 10 groups on real data, edge cases covered and pass). No orphaned requirements found for Phase 5 in REQUIREMENTS.md (SCORE-06 is the only ID mapped to this phase). REQUIREMENTS.md line 31 and ROADMAP.md still show SCORE-06 unmarked (`[ ]`), per design — this verifier's PASS status is the trigger for marking it complete via the normal flow. |

### Anti-Patterns Found

None. Grepped all 4 parity files for `TODO|FIXME|XXX|HACK|PLACEHOLDER` (case-insensitive) — the only hits are legitimate in-code documentation of the real `age==0` data-quality placeholder condition being tested (`test_age_zero_placeholder_parity`), not stub/incomplete code. No empty-return stubs, no console-log-only handlers (not applicable — this is a pytest suite, not UI code).

### Human Verification Required

None. This phase is a backend numerical-correctness test suite; every claim is independently verifiable by running pytest and/or querying the dev DB directly, which was done above.

### Minor Bookkeeping Note (non-blocking)

`.planning/ROADMAP.md` line 112 still shows `- [ ] 05-03-PLAN.md` (unchecked) even though `05-03-SUMMARY.md` exists and documents the plan as complete, while 05-01/05-02/05-04 are checked `[x]`. This is a stale checkbox, not a goal/artifact gap — 05-03's deliverable (`test_parity_api_sample.py`) exists, is substantive, and its real-data verification is documented. Flagged for whoever next touches ROADMAP.md bookkeeping; does not block this phase's PASS status.

### Gaps Summary

None. All 3 ROADMAP success criteria are verified against actual code and independently spot-checked against the real 41,708-player dev DB (not just SUMMARY.md text). The phase goal — "the Django port is proven numerically faithful to the original script" — is achieved: a repeatable, oracle-version-agnostic pytest suite exists across 3 tiers (bulk full-population, per-request/API-sample, named edge-cases), all tolerances and null-handling semantics are centralized in one shared, well-tested module, and real-dev-DB execution (documented in each plan's SUMMARY.md and independently re-confirmed here on 4 distinct claims spanning RMM, CS, and TFM) shows exact or within-tolerance matches with zero failures.

---

*Verified: 2026-07-24T16:10:00Z*
*Verifier: Claude (gsd-verifier)*
