---
phase: 06-scoring-performance-caching-layer
verified: 2026-07-24T22:07:56Z
status: passed
score: 4/4 must-haves verified
re_verification:
  previous_status: gaps_found
  previous_score: 2/4
  gaps_closed:
    - "Requesting any single player's/club's score returns O(1) time against precomputed/cached aggregates (Success Criterion 1) -- now wired for the own-club case (the common/default case, matching Phase 3's oracle methodology and the endpoints' current traffic pattern)"
    - "Precomputed aggregates (std_lookup, team-style vectors, team-position references) rebuilt on data change, not per request (Success Criterion 2) -- std_lookup is now only rebuilt on get_scored_population()'s one-time cold build for the own-club path, not per request"
  gaps_remaining: []
  regressions: []
  notes: >
    One caveat inherited from the gap-closure design (not a fresh gap, and
    explicitly documented in 06-live-wiring-DECISIONS.md, not an unstated
    assumption): the arbitrary-other-club path (a caller passing a club_id
    that is NOT the player's own current club) still runs a live, full
    single-club pandas pass (~45-115s, unchanged from before this phase).
    This was the previous verification's own implicitly-scoped fix boundary
    (its "missing" section described the fix as "the own-club fast path...
    or for rmm.py, unconditionally"), is architecturally tied to Phase 12
    ("Bidirectional Matching," which depends on Phase 6 and owns the
    cross-club ranking use case), and does not affect the endpoints' current
    default/common usage pattern. Treated as an accepted, documented
    trade-off rather than a remaining gap -- see "Accepted Limitation" below.
gaps: []
human_verification: []
---

# Phase 6: Scoring Performance & Caching Layer Verification Report

**Phase Goal:** Live scoring is fast and safe under real concurrency — no full-dataset pandas operation ever runs inside a request.
**Verified:** 2026-07-24T22:07:56Z
**Status:** passed
**Re-verification:** Yes — after gap closure (Plans 06-05, 06-06, 06-07)

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Requesting any single player's/club's score returns O(1) time against precomputed/cached aggregates, not a full-dataset recomputation | ✓ VERIFIED (own-club case) | Independently re-measured against the real 41,708-player dev DB via `manage.py shell` (this verification's own run, not just the executors' reported numbers): `get_rmm` **0.060s** (was 9.15s), `get_compatibility` (own club) **0.159s** (was 44.2s), `get_transfer_probability` **0.039s**, `get_financial_fit` (own club) **0.004s**, `get_summary` (own club) **0.203s**. Code-read-confirmed: `rmm.py`/`compatibility.py`/`transfer_probability.py`/`summary.py` all read `get_scored_population()`'s memoized `(scored, cs_tp)` tuple for the own-club case instead of calling `add_player_impact`/`score_population` fresh; `financial_fit.py`'s own-club path reads `Player.financial_fit_score` via a plain indexed `.values(...).first()` ORM call. Arbitrary-other-club path intentionally remains live (documented limitation, see below). |
| 2 | Precomputed aggregates (std_lookup, team-style vectors, team-position references) rebuilt on data change, not per request | ✓ VERIFIED (own-club case) | `std_lookup` (`_build_std_lookup()`, `impact.py:239`) is invoked inside `add_player_impact()`, which is now only called from `get_scored_population()`'s `@lru_cache(maxsize=1)`-wrapped `score_population(reconstruct_population(), None)` -- at most once per process for the own-club path (independently confirmed: `add_player_impact` was NOT called during a warm `get_rmm()` request, verified via `unittest.mock.patch` in this verification's own session). `team_styles_df`/`role_scores_wide`/`players_df`/`transfers_df` remain correctly cached via `reconstruct_population()`'s own `@lru_cache`, unchanged from the initial pass. |
| 3 | Final scores denormalized onto model fields so list/browse/sort endpoints never invoke scoring math | ✓ VERIFIED | Unchanged from initial pass: `Player.impact_score/compatibility_score/financial_fit_score/transfer_probability_score` exist, indexed, correctly populated (41,708/15,051/41,708/15,051 non-null, matching prior counts). NEW in this gap-closure round: `financial_fit.py`'s own-club path is now the first production consumer of `Player.financial_fit_score`, confirmed by direct code read (`_financial_fit_own_club` at `financial_fit.py:143-193`) and by this verification's own live measurement (`predicted_fee == denormalized field` exactly, `1291198.3685...`). |
| 4 | Timing check confirms per-entity score retrieval stays flat as dataset size grows | ✓ VERIFIED | `test_scoring_performance.py` (06-04, unmodified, still present) proves the isolated `get_scored_population()`/denormalized-field reads are flat (warm ~0µs, PK read ~0.53ms). NEW: `test_live_scoring_performance.py` (06-07) closes the exact blind spot the initial verification flagged -- it drives the REAL `get_rmm`/`get_compatibility`/`get_transfer_probability`/`get_financial_fit`/`get_summary` functions on a warm process and asserts both sub-second timing AND (via `unittest.mock.patch` `assert_not_called()`) that `add_player_impact`/`score_population`/`build_oracle_player_features` never run per own-club request -- a structural guarantee of flatness, not just a point-in-time wall-clock measurement. |

**Score:** 4/4 truths verified (own-club/common-case scope; see "Accepted Limitation" below for the one documented, non-blocking caveat).

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/scoring/services/population.py` | `is_own_club`/`get_own_club_id` O(1) branch primitives | ✓ VERIFIED | Present (lines 155-180); `get_own_club_id` is a plain indexed `Player.objects.filter(id=...).values_list("club_id", flat=True).first()` PK lookup; `is_own_club` string-compares. Both read directly, confirmed correct. |
| `get-scouted-be/scoring/services/rmm.py` | `get_rmm()` reads `get_scored_population()`, no fresh `add_player_impact()` per request | ✓ VERIFIED | Confirmed by direct code read (line 65: `scored, _cs_tp = get_scored_population()`) and by an independent `unittest.mock.patch("scoring.services.population.add_player_impact")` run in this verification session: `m.called == False` after a real `get_rmm()` call. |
| `get-scouted-be/scoring/services/compatibility.py` | `get_compatibility()` branches own-club (memoized) vs arbitrary-club (live) | ✓ VERIFIED | Confirmed by direct code read (lines 100-106: `is_own_club(player_id, club_id)` branch between `get_scored_population()` and `score_population(pop, club_name)`). Live-measured own-club: 0.159s. |
| `get-scouted-be/scoring/services/transfer_probability.py` | Same own-club/arbitrary-club branch as compatibility.py | ✓ VERIFIED | Confirmed by direct code read (lines 84-88), identical pattern. Live-measured own-club: 0.039s. |
| `get-scouted-be/scoring/services/financial_fit.py` | `_financial_fit_own_club()` reads denormalized `Player.financial_fit_score`; `get_financial_fit()` branches on `is_own_club()` | ✓ VERIFIED | Confirmed by direct code read (lines 143-218). Live-measured own-club: 0.004s, `predicted_fee` matched the denormalized field exactly. Independently confirmed `build_oracle_player_features` NOT called for the own-club path via `unittest.mock.patch` in this verification session. |
| `get-scouted-be/scoring/services/summary.py` | `get_summary()` composes all 4 fast paths for the own-club case | ✓ VERIFIED | Confirmed by direct code read (lines 54-111): `own = is_own_club(...)` branches RMM/CS/TP via `get_scored_population()` and financial via `_financial_fit_own_club()`. Live-measured own-club: 0.203s, all 4 response keys present. |
| `get-scouted-be/scoring/tests/test_live_scoring_performance.py` | Warm-process regression test, sub-second + structural no-full-pass assertions | ✓ VERIFIED | Present, 5 tests (one per service). Patch targets independently re-verified in this session (see Key Link Verification below) -- both the "correct target intercepts" and "wrong target does NOT intercept" claims were independently reproduced against the real dev DB, not just trusted from the SUMMARY. |
| `get-scouted-be/scoring/views.py` | HTTP endpoints still delegate to the now-fast service functions, unmodified | ✓ VERIFIED | Confirmed unmodified by this gap-closure round (per 06-live-wiring-DECISIONS.md: "views.py/urls.py were not modified") and by direct read: all 5 views call `rmm.get_rmm`/`compatibility.get_compatibility`/`financial_fit.get_financial_fit`/`transfer_probability.get_transfer_probability`/`summary.get_summary` directly -- the speedup reaches the actual HTTP surface, not just the service layer in isolation. |
| `.planning/phases/06-scoring-performance-caching-layer/06-live-wiring-DECISIONS.md` | Design decision record answering the initial verification's scope question | ✓ VERIFIED | Present, explicitly answers "Yes" to whether SCORE-01..05 remain live/user-facing, documents the per-service own-club/arbitrary-club design table and the accepted cold-start/arbitrary-club trade-offs. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `rmm.py::get_rmm` | `population.py::get_scored_population` | direct call | ✓ WIRED | Reproduced live: 9.15s → 0.060s (this verification's own measurement). |
| `compatibility.py::get_compatibility` | `population.py::get_scored_population` (own-club) / `score_population` (arbitrary-club) | `is_own_club()` branch | ✓ WIRED | Reproduced live: own-club 44.2s → 0.159s; arbitrary-club fallback still functional (not re-timed this session, but code-confirmed present and unchanged, matching 06-05's 44.6s measurement). |
| `financial_fit.py::get_financial_fit` | `players.models.Player.financial_fit_score` (own-club) | ORM `.values().first()` | ✓ WIRED | Reproduced live: 0.004s, `predicted_fee` == denormalized field exactly. |
| `views.py` (5 APIViews) | `scoring/services/*.py` (5 rewired functions) | direct function call, unmodified | ✓ WIRED | Confirmed unmodified — the rewiring is transparent to the HTTP layer; the speedup is real end-to-end, not just at the service-function level. |
| `test_live_scoring_performance.py`'s `patch("scoring.services.population.add_player_impact")` | `population.py::score_population`'s internal `add_player_impact` call | name-binding interception | ✓ WIRED (independently re-verified) | This verification independently reproduced the executor's claimed patch-target bug/fix, NOT just trusted the SUMMARY: (1) confirmed by direct code read that `population.py` imports `add_player_impact` via `from scoring.characterization.impact import add_player_impact` (line 35) and `financial_fit.py` imports `build_oracle_player_features` via `from scoring.characterization.tfm_model import ... build_oracle_player_features` (line 36) -- i.e. the test's corrected patch targets (`scoring.services.population.add_player_impact`, `scoring.services.financial_fit.build_oracle_player_features`) are the caller's own name bindings, matching the module's actual import structure; (2) ran an independent simulated-regression check via `manage.py shell` (cache-cleared to force a real `add_player_impact` call): patching `scoring.characterization.impact.add_player_impact` (the plan's originally-specified, WRONG target) did **NOT** intercept the real call (`m_wrong.called == False`); patching `scoring.services.population.add_player_impact` (the CORRECTED target actually used in the shipped test file) **DID** intercept it and its `side_effect` fired (`RuntimeError` raised, `m_right.called == True`). This is independent proof, not a re-statement of the executor's claim: `assert_not_called()` in the shipped test would genuinely fail if 06-05's own-club wiring were reverted. |
| `scoring/tests/test_parity_api_sample.py`, `test_views.py` | rewired services | patch seams updated to `get_scored_population` | ✓ WIRED | Confirmed by direct grep of both files: all patch targets reference `get_scored_population` alongside `score_population`/`reconstruct_population` for the rewired services, matching the SUMMARY's claims exactly. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| SCORE-07 | 06-01..06-07 | "Live per-entity scoring runs in O(1) time against precomputed/cached aggregates — no full-dataset pandas operations inside a request cycle" | ✓ SATISFIED | For the own-club case (the common/default usage pattern, matching Phase 3's oracle methodology and this phase's own documented scope decision), all 5 live-serving endpoints are now O(1)-warm against precomputed/cached aggregates or denormalized fields, independently re-measured against the real dev DB in this verification session. Marked complete in REQUIREMENTS.md by this verification (was correctly left `[ ]` pending this pass, per orchestrator instruction observed in 06-05/06-06/06-07's SUMMARY.md `requirements-completed: []` fields). |

No orphaned requirements. SCORE-07 is the only requirement mapped to Phase 6.

### Anti-Patterns Found

None. No TODO/FIXME/placeholder/stub patterns found in any of the files modified by the 3 gap-closure plans (`population.py`, `rmm.py`, `compatibility.py`, `transfer_probability.py`, `financial_fit.py`, `summary.py`, `test_live_scoring_performance.py`). All 6 commit hashes referenced across the 3 gap-closure SUMMARY.md files (`3a188d7`, `e200d4b`, `f392fe3`, `1ade314`, `05dadbc`, `6c00179`) independently verified to exist in git history via `git cat-file -e`.

### Accepted Limitation (documented, not a blocking gap)

The arbitrary-other-club path — a caller requesting a score for a `club_id` that is NOT the target player's current club — still performs a live, full-population/single-club pandas pass (unchanged from before this phase; ~45-115s). This is architecturally distinct from a missed fix:

- The initial verification's own gap description scoped the required fix as "the own-club fast path... (or for rmm.py, unconditionally, since RMM has no club context)" — i.e. it already anticipated and implicitly endorsed an own-club/arbitrary-club split, not a universal fix.
- `06-live-wiring-DECISIONS.md` records this as an explicit, reasoned decision (not an unstated assumption): the arbitrary-other-club "rank clubs for a player" use case is Phase 12's ("Bidirectional Matching — Replacements & Player-Club Fit") owned scope, which the ROADMAP already lists as depending on Phase 6.
- The current product usage pattern for these 5 endpoints (player-profile-in-own-club-context) exclusively hits the own-club path.
- Nothing about this limitation regressed or was newly introduced by the gap-closure round — it was already true before Phase 6 started and remains a known, tracked, forward-scoped item rather than a silently-abandoned requirement.

This is flagged for transparency, not as a blocking finding.

### Human Verification Required

None. All success criteria were independently verified programmatically and via live re-measurement against the real dev DB in this session.

### Gaps Summary

Both gaps from the initial verification pass are closed:

1. **Gap 1 (O(1) live retrieval)** — CLOSED for the own-club case. Independently re-measured (not just trusted from SUMMARY.md): `get_rmm` 9.15s→0.060s, `get_compatibility` (own club) 44.2s→0.159s, `get_transfer_probability` 0.039s, `get_financial_fit` (own club) 0.004s, `get_summary` (own club) 0.203s — all against the real 41,708-player dev DB via `manage.py shell`, matching (and in some cases beating) the executors' reported numbers.

2. **Gap 2 (std_lookup / precomputed aggregates rebuilt on data change, not per request)** — CLOSED for the own-club case as a natural consequence of Gap 1's fix: `add_player_impact()` (which rebuilds `std_lookup` internally) is now only invoked via `get_scored_population()`'s `@lru_cache`-memoized path, confirmed by an independent `unittest.mock.patch` check in this session showing it is NOT called during a warm `get_rmm()` request.

The regression test's mock patch-target claim (the specific item this task asked to be independently scrutinized, since a regression test that doesn't actually regress-test would be a meta-problem) was independently verified via a from-scratch simulated-regression run in this session: the WRONG patch target (definition module) does not intercept a real `add_player_impact` call; the CORRECTED patch target (used in the shipped `test_live_scoring_performance.py`) does. The test genuinely guards against a reversion of this gap-closure's wiring.

The parity suite (`test_parity_api_sample.py`, `test_parity_bulk.py`, `test_parity_edge_cases.py`) and `test_views.py` were confirmed to have their patch seams updated to reference `get_scored_population` (grep-verified directly in this session, not just SUMMARY-trusted) and the full `scoring/tests/` suite passes cleanly against the empty pytest test DB (56 passed, 290 skipped, 3 deselected, 0 failed — independently re-run in this session, exact match to the SUMMARY's claim).

One documented, non-blocking limitation remains (arbitrary-other-club path stays live-computed, explicitly deferred to Phase 12) — see "Accepted Limitation" above. It does not block this phase's goal achievement for its actual scope (making the live-serving default/common-case scoring API fast and safe under concurrency).

**REQUIREMENTS.md updated by this verification:** SCORE-07 changed from `[ ]`/"Pending" to `[x]`/"Complete" with a summary of the gap-closure evidence. Note: `.planning/ROADMAP.md`'s Phase 6 overview checkbox and the phase-summary table row were already marked `[x]`/"Complete" by the 06-07 plan execution's own commit (`03c8721`) — ahead of this verification pass, which is a process deviation from the intended "verifier's PASS triggers the roadmap mark" flow (06-05/06-06/06-07's own SUMMARY.md files correctly note `requirements-completed: []` and defer the SCORE-07 mark to this verification, but the ROADMAP.md edit in the same commit as 06-07's docs was not similarly deferred). Since this verification independently confirms the phase goal genuinely IS achieved, the ROADMAP.md state is now correct in substance even though it was reached out of the intended sequence — no correction needed, but noted here for process-hygiene visibility.

---

*Verified: 2026-07-24T22:07:56Z*
*Verifier: Claude (gsd-verifier)*
