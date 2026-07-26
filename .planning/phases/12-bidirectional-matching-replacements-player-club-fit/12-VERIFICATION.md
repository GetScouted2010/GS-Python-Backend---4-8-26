---
phase: 12-bidirectional-matching-replacements-player-club-fit
verified: 2026-07-26T18:38:29Z
status: passed
score: 8/8 must-haves verified
---

# Phase 12: Bidirectional Matching - Replacements & Player-Club Fit Verification Report

**Phase Goal:** Users can get ranked matches in both directions — replacement players for a weak position, and clubs that fit a given player.
**Verified:** 2026-07-26T18:38:29Z
**Status:** passed
**Re-verification:** No — initial verification

This is the final phase of the v1 roadmap. Verification independently re-derived and re-ran every claim in the four plans' SUMMARYs rather than trusting them — full suite re-run, both live `manage.py shell` correctness/perf spikes re-run against the real 41,708-player/1,060-club dev DB, source code read directly, and the 12-02 stalled-executor housekeeping commit diffed to confirm it touched zero source files.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can get a ranked list of suggested replacement players for a weak position, ordered by RMM/CS/TFM fit | ✓ VERIFIED | `rank_replacement_players` + `GET /api/clubs/{id}/replacements/?position=<POS>` live-verified: independently re-ran, 118.62s, 5 results, all position=CB, `excl_own=True`, top entry carries real `financial_fit.predicted_fee=€3.81M` |
| 2 | User can get a ranked list of clubs that fit a given player (Player→Club), scored by CS/TFM | ✓ VERIFIED | `rank_clubs_for_player` + `GET /api/players/{id}/club-matches/` live-verified: independently re-ran, 87.48s, 10 results, own club excluded, `financial_fit.predicted_fee=€559K`/`value_verdict=Bargain` on top entry |
| 3 | Both ranking directions reuse one shared underlying service, not duplicated logic (success criterion 3) | ✓ VERIFIED | Single `scoring/services/matching.py` module; both functions import the same low-level primitives (`compatibility_score`, `financial_score`, `transfer_probability`); `test_matching_reuses_shared_primitives` (AST-based structural check, no DB needed) PASSES; one shared `_attach_real_tfm` helper used by both (`grep -c "_attach_real_tfm("` = 2, once per direction) |
| 4 | Real TFM (predicted_fee/value_verdict) attached only to bounded top-N, never the full candidate set, for both directions | ✓ VERIFIED | `_attach_real_tfm` is the only call-site of `get_financial_fit` in the module; `test_real_tfm_called_only_for_top_n` mocks it and asserts `call_count == top_n`, PASSES; live spikes show real (non-fabricated) predicted_fee/value_verdict values, confirming the real ML pipeline (not the cheap `financial_score` label) is what's attached |
| 5 | Both endpoints exclude the "already there" case (current squad / player's own club) | ✓ VERIFIED | Code-level `scored["Team"] != club_name` / `if club_name == own_club_name: continue`; live-confirmed `excl_own True` in both independent re-runs above; `test_rank_replacement_players_excludes_current_squad`/`test_rank_clubs_for_player_excludes_own_club` present and correct |
| 6 | Pattern 2's squad_stats correctness fix holds — financial_score is NOT systematically null for non-own candidate clubs | ✓ VERIFIED | `squad_stats` computed once via `pop.players_df.groupby("Team")` over the FULL population (not a single-row slice); `compute_cs_tp_for_pairs` never called (0 call-sites, only 3 explanatory comment references); live re-run shows `financial_score` non-null for all 10 of 10 top clubs, not just the player's own |
| 7 | Both endpoints resolve above their app's `<uuid:pk>/` catch-all, with correct auth/404/400 behavior | ✓ VERIFIED | `clubs/urls.py`: `replacements/` (line 13) precedes `<uuid:pk>/` (line 14); `players/urls.py`: `club-matches/` (line 15) precedes `<uuid:pk>/` (line 16); integration tests (`test_replacements_view.py`, `test_club_matches_view.py`) exercise real isolated DB fixtures (not skipped) and pass: 200+results, route-not-swallowed, 404 unknown id, 401 unauthenticated — 8/8 passed |
| 8 | Full backend test suite is green before the phase is marked complete | ✓ VERIFIED | Independently re-run: `241 passed, 321 skipped, 0 failed` (skips are the established "no real data in pytest's empty test DB" convention, gated by `real_data_available`) |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/scoring/services/matching.py` | Shared module: both ranking functions + `_attach_real_tfm` + `DEFAULT_TOP_N` | ✓ VERIFIED | 277 lines; both functions fully implemented (no `NotImplementedError` remaining); `_attach_real_tfm` implemented once, called from both directions |
| `get-scouted-be/clubs/views.py::ReplacementsView` | GET APIView, position query param, 400/404 | ✓ VERIFIED | Present at line 136; correct `get_object_or_404` fast-404, 400 on missing `position`, calls `rank_replacement_players` |
| `get-scouted-be/clubs/urls.py` | `replacements/` route above `<uuid:pk>/` | ✓ VERIFIED | Line 13, before catch-all at line 14 |
| `get-scouted-be/players/views.py::ClubMatchesView` | GET APIView, 404 on unknown player | ✓ VERIFIED | Present at line 110; thin wrapper, correct `get_object_or_404` then `rank_clubs_for_player` |
| `get-scouted-be/players/urls.py` | `club-matches/` route above `<uuid:pk>/` | ✓ VERIFIED | Line 15, before catch-all at line 16 |
| `get-scouted-be/scoring/tests/test_services_matching.py` | 8 named unit/structural tests | ✓ VERIFIED | All 8 present; 2 non-DB structural tests pass unconditionally, 6 DB tests gate on `real_data_available` |
| `get-scouted-be/clubs/tests/test_replacements_view.py` | 4 integration tests | ✓ VERIFIED | All 4 present, use real (isolated) DB fixtures, all 4 pass (not skipped) |
| `get-scouted-be/players/tests/test_club_matches_view.py` | 4 integration tests | ✓ VERIFIED | All 4 present, use real (isolated) DB fixtures, all 4 pass (not skipped) |
| `get-scouted-be/scoring/characterization/reconstruct.py` | Empty-table guards (Rule-1 deviation fixes) | ✓ VERIFIED | `build_transfers_df` and `build_team_styles_df` both have the documented empty-table early-return guard, mirroring the pre-existing `build_role_scores_wide` pattern |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `ReplacementsView.get` | `rank_replacement_players` | direct call | ✓ WIRED | `return Response(rank_replacement_players(pk, position))` |
| `rank_replacement_players` | `score_population` | full-population single pass | ✓ WIRED | Called once per invocation; live-confirmed |
| `rank_replacement_players` | `_attach_real_tfm` | top-N enrichment call | ✓ WIRED | `pairs` built strictly from the already-sliced `results` (top-N), never the full candidate frame |
| `ClubMatchesView.get` | `rank_clubs_for_player` | direct call | ✓ WIRED | `return Response(rank_clubs_for_player(pk))` |
| `rank_clubs_for_player` | `calculate_subjective_role_fit_for_player_to_team` | per-club loop over `team_styles_df` | ✓ WIRED | Real import + call inside the ~1,060-row loop |
| `rank_clubs_for_player` | `financial_score`/`transfer_probability` (deterministic_scores) | squad_stats-baselined, computed once over full population | ✓ WIRED | `squad_stats = pop.players_df.groupby("Team")...` — never a single-row slice |
| `rank_clubs_for_player` | `_attach_real_tfm` | top-N enrichment call, name→id resolved first | ✓ WIRED | Bounded `Club.objects.filter(name__in=top_names)` query; unresolved entries null-filled, not raised |
| `_attach_real_tfm` | `get_financial_fit` (real ML TFM pipeline) | per-entry call, top-N only | ✓ WIRED | Sole call-site in the module; `test_real_tfm_called_only_for_top_n` passes; live spikes show genuine, non-fabricated `predicted_fee`/`value_verdict` values |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| PLAN-02 | 12-01, 12-02 | User can get AI-suggested replacement players for a weak position, ranked by RMM/CS/TFM fit | ✓ SATISFIED | `GET /api/clubs/{id}/replacements/?position=<POS>` live and correct. "AI-suggested" is deliberately read as "algorithmically ranked" per 12-CONTEXT.md's documented, well-reasoned decision (ROADMAP's own success criteria and REQUIREMENTS.md's Out-of-Scope table — "LLM directly computing scores" — both confirm zero LLM involvement is intended for this phase). REQUIREMENTS.md's traceability table currently still shows PLAN-02 as "Pending" — this is the expected, documented state per this project's convention (marking it complete is explicitly left to this verifier's call, per every plan's SUMMARY) |
| PLAN-04 | 12-01, 12-03, 12-04 | User can get a ranked list of clubs that fit a given player (Player→Club Matching), scored by CS/TFM | ✓ SATISFIED | `GET /api/players/{id}/club-matches/` live and correct; Pattern 2's squad_stats correctness fix independently re-verified live (financial_score non-null 10/10 in top-N) |

**No orphaned requirements found** — PLAN-02 and PLAN-04 are the only two requirement IDs mapped to Phase 12 in REQUIREMENTS.md, and both are declared across the four plans' `requirements` frontmatter (12-01: both; 12-02: PLAN-02; 12-03/12-04: PLAN-04).

### Anti-Patterns Found

None. Scanned `scoring/services/matching.py`, `clubs/views.py`, `clubs/urls.py`, `players/views.py`, `players/urls.py`, `scoring/characterization/reconstruct.py` for TODO/FIXME/placeholder/empty-return/console-log-only patterns — zero matches.

### Independent Scrutiny of the Two Flagged Concerns

**1. 12-02's stalled-executor recovery (commit `155a072`) — confirmed cosmetic-only, not just claimed.**
Diffed `155a072` directly: `git show 155a072 -- scoring/services/matching.py clubs/views.py clubs/urls.py` returns an empty diff — the housekeeping commit touched **zero source files**. Its only changes were to `.planning/ROADMAP.md`, `.planning/STATE.md`, `12-02-PLAN.md`/`12-03-PLAN.md` (adding clarifying prose/acceptance-criteria notes that document decisions the executor had already made in code, plus stripping a stray `</content></invoke>` tool-call fragment), and creating `12-02-SUMMARY.md`. The three actual functional commits (`91036f3`, `f9541b7`, `fa02405`) were committed by the (stalled) 12-02 executor itself, before the stall, and are independently confirmed correct: the full backend suite passes, the 8 unit/structural tests for `rank_replacement_players` pass or skip cleanly, the 4 integration tests against isolated real DB fixtures pass, and an independent live re-run against the real dev DB (118.62s, 5 CB candidates, `excl_own=True`, real `financial_fit`) confirms the endpoint works end-to-end. The recovery was documentation/housekeeping-only, exactly as claimed.

**2. Pattern 2's 78.3-78.7s cold latency (exceeding the plan's own ~60s flag) — reasoning holds, not a corner cut.**
Independently re-measured: 87.48s on a fresh independent run (in the same ballpark as 12-03's own 78.3-78.7s two-run measurement — cold full-population reconstruction cost dominates, consistent with run-to-run variance already documented elsewhere in this project, e.g. 12-04's 120.1s single-run for Pattern 1 vs. Phase 6's 44.6s). Cross-checked against Phase 6's actual documented precedent in `.planning/STATE.md` (Phase 06-05 entry): `get_scored_population()` cold = 92.04s, arbitrary-other-club live `score_population` = 44.6s — both directly comparable full-population-reconstruction-plus-scoring costs. Pattern 2's ~78-87s sits within/near this already-accepted range, not a new order of magnitude. No caching code was added anywhere in the phase's diff (confirmed via source read — the only caching present is Phase 6's pre-existing `lru_cache` on `reconstruct_population`/`get_scored_population`, not new infrastructure built for this phase), matching 12-CONTEXT.md's explicit Deferred Ideas entry ("Caching/precomputing replacement-player rankings per club — not built... matches this project's consistent 'don't add infra without a forcing reason' pattern"). The reasoning is internally consistent and was carried into the phase gate as a documented, deliberate decision rather than a silently-cut corner.

**3. TFM-meaning resolution — implemented, not just documented.**
Read `_attach_real_tfm`'s source directly: it is the sole call-site of `get_financial_fit` (the real trained ML pipeline from `scoring/services/financial_fit.py`) anywhere in `matching.py`, called exactly once per top-N entry in both directions (`grep -c "_attach_real_tfm("` = 2). Both independent live spikes returned genuine, varying, non-fabricated `predicted_fee` (€3.81M and €559K) and `value_verdict` (`None`/`'Bargain'`) values — not the cheap `financial_score` label-average column, which is kept under a separate key on every result (`financial_score` vs `financial_fit`) exactly as the locked design specifies. The cheap `financial_score` (used only for ranking/sorting, never presented as TFM) and the real `financial_fit` (real ML pipeline, top-N only) are never conflated in the returned payload — confirmed by inspecting both result dicts directly.

### Human Verification Required

None. This phase is a backend-only API surface (no UI of its own, by explicit design per 12-CONTEXT.md) and every claim was verified programmatically and re-confirmed live against the real dev DB by this verifier, independent of the SUMMARYs' own reported figures.

### Gaps Summary

No gaps found. All 8 observable truths verified, all artifacts substantive and wired, all key links confirmed, requirements PLAN-02/PLAN-04 both satisfied, full backend suite independently re-run green (241 passed, 0 failed, 321 skipped — expected empty-test-DB skips), both endpoints independently live-re-verified against the real 41,708-player/1,060-club dev DB with correct exclusions and genuine real-TFM enrichment. The two concerns flagged for extra scrutiny (12-02's stalled-executor recovery, and Pattern 2's latency-vs-threshold decision) both independently confirmed sound under direct inspection, not just trusted from the SUMMARYs.

One informational note (not a gap): `REQUIREMENTS.md`'s traceability table still shows `PLAN-02 | Phase 12 | Pending` as of this verification — per this project's established convention (documented explicitly in 12-02-SUMMARY.md and 12-04-SUMMARY.md), marking it "Complete" is this verifier's call, made here: **PLAN-02 is verified complete and satisfied**, alongside PLAN-04. Whoever runs the phase-completion step should update that table row accordingly.

---

*Verified: 2026-07-26T18:38:29Z*
*Verifier: Claude (gsd-verifier)*
