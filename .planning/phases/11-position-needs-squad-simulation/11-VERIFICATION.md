---
phase: 11-position-needs-squad-simulation
verified: 2026-07-26T00:00:00Z
status: passed
score: 16/16 must-haves verified
---

# Phase 11: Position Needs & Squad Simulation Verification Report

**Phase Goal:** Users can see where a club's squad is weak (per-position strong/weak/at-risk classification based on depth, contract expiry, age) and simulate a squad change (add/remove/swap) to see recalculated aggregate metrics (avg age, avg score, budget impact), entirely without persisting anything until the user separately commits via Phase 8's existing SquadPlan update endpoint.
**Verified:** 2026-07-26
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (11-01 / PLAN-01)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | GET /api/clubs/{id}/position-needs/ returns per-position classification | ✓ VERIFIED | `clubs/urls.py:11` routes to `PositionNeedsView`; `clubs/views.py:122-131` calls `services.classify_position_needs(club)`; integration test `test_position_needs_endpoint_returns_classified_payload` passes live |
| 2 | Position with squad_depth < 2 → "weak" | ✓ VERIFIED | `clubs/services.py:73-74` `if depth < 2: label = "weak"`; unit test `test_classify_weak_when_depth_below_2` passes |
| 3 | Depth ≥ 2 and avg_age > 30 → "at-risk" | ✓ VERIFIED | `clubs/services.py:75` `(avg_age is not None and avg_age > 30)`; unit test `test_classify_at_risk_by_age` passes |
| 4 | Depth ≥ 2 and expiring ≥ depth/2 → "at-risk" | ✓ VERIFIED | `clubs/services.py:75` `... or expiring >= depth / 2`; unit test `test_classify_at_risk_by_contract_expiry` passes |
| 5 | Adequate depth, not aging, no mass expiry → "strong" | ✓ VERIFIED | `clubs/services.py:76-78` else branch; unit test `test_classify_strong` passes |
| 6 | Raw numbers (squad_depth/avg_age/contracts_expiring_within_12mo) returned alongside label | ✓ VERIFIED | `clubs/services.py:79` `{**stats, "classification": label}` spreads raw stats |
| 7 | Route not swallowed by `<uuid:pk>/` catch-all | ✓ VERIFIED | `clubs/urls.py` line 11 (`position-needs/`) precedes line 12 (`<uuid:pk>/`); test `test_position_needs_route_not_swallowed_by_catchall` passes |
| 8 | Nonexistent club id → 404 | ✓ VERIFIED | `get_object_or_404(Club, pk=pk)` in view; test `test_position_needs_unknown_club_404` passes |

### Observable Truths (11-02 / PLAN-03)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 9 | POST /api/workspace/squad-plans/{id}/simulate/ returns baseline/simulated/delta | ✓ VERIFIED | `workspace/views.py:121-131` `simulate` action calls `simulate_squad_change`; test `test_simulate_response_shape` passes, asserting all keys present |
| 10 | add/remove/swap applied correctly (player_id for add/remove/outgoing, incoming_player_id only on swap) | ✓ VERIFIED | `workspace/services.py:58-68` implements exactly this; cross-checked against `workspace/serializers.py:59-68` `validate_proposed_changes` (swap requires `incoming_player_id`, add/remove use `player_id`) — schemas agree; test `test_apply_add_remove_swap` passes |
| 11 | Simulation never writes to DB | ✓ VERIFIED | `grep -c ".save(\|.update(\|bulk_update\|bulk_create" workspace/services.py` = 0; manual read of `workspace/services.py` and the `simulate` action in `workspace/views.py` confirms no persistence call anywhere in the code path; `test_simulate_does_not_persist` re-fetches `SquadPlan` from DB and asserts `proposed_changes` unchanged AND `club.players.count()` unchanged — passes live |
| 12 | Unknown player_id/incoming_player_id → clean 400 | ✓ VERIFIED | `workspace/services.py:51-53` raises `InvalidPlayerReference`; `workspace/views.py:126-128` catches it → `Response(..., status=400)`; test `test_invalid_player_id_400` passes |
| 13 | Optional proposed_changes override honored | ✓ VERIFIED | `workspace/services.py:45` `changes = proposed_changes if proposed_changes is not None else squad_plan.proposed_changes`; test `test_simulate_uses_override_when_provided` and `test_uses_stored_proposed_changes_when_no_override` both pass |
| 14 | avg score uses impact_score only | ✓ VERIFIED | `workspace/services.py:33` `scores = [p.impact_score for p in players ...]`; `grep -n "compatibility_score\|financial_fit_score\|transfer_probability_score" workspace/services.py` returns no matches |
| 15 | Null market_value/age/impact_score excluded from averages, never coerced to 0 | ✓ VERIFIED | `workspace/services.py:32-40` filters `is not None` before building lists, returns `None` (not 0) when list empty; test `test_null_values_excluded_not_zero_filled` passes with explicit assertions |
| 16 | Another user's SquadPlan → 404 on /simulate/ | ✓ VERIFIED | `workspace/views.py:123` `self.get_object()` runs `check_object_permissions` (IsOwner); test `test_simulate_ownership_denied` passes |

**Score:** 16/16 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/clubs/services.py::classify_position_needs` | Classification layered on `position_needs_aggregate` | ✓ VERIFIED | Present (line 62), calls `position_needs_aggregate(club)` (line 67), single real `.annotate(` occurrence in file (2nd grep hit is inside a docstring, not code) |
| `get-scouted-be/clubs/views.py::PositionNeedsView` | GET endpoint | ✓ VERIFIED | Present (line 122), plain APIView style matching ClubInsightsView precedent |
| `get-scouted-be/clubs/urls.py` | route above catch-all | ✓ VERIFIED | `position-needs/` (line 11) precedes `<uuid:pk>/` (line 12) |
| `get-scouted-be/clubs/tests/test_position_needs.py` | 4 unit tests | ✓ VERIFIED | All 4 present and passing |
| `get-scouted-be/clubs/tests/test_views_position_needs.py` | 4 integration tests | ✓ VERIFIED | All 4 present and passing |
| `get-scouted-be/workspace/services.py` | NEW file: simulate_squad_change, InvalidPlayerReference, _squad_metrics, _referenced_ids | ✓ VERIFIED | All 4 definitions present; zero `.save()/.update()/bulk_*` calls |
| `get-scouted-be/workspace/views.py::SquadPlanViewSet.simulate` | @action | ✓ VERIFIED | Present (line 121), uses `self.get_object()`, maps `InvalidPlayerReference` to 400 |
| `get-scouted-be/workspace/tests/test_squad_simulation.py` | unit + integration tests | ✓ VERIFIED | 4 unit + 5 integration = 9 tests, all present and passing |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `clubs/views.py::PositionNeedsView` | `clubs.services.classify_position_needs` | direct call | ✓ WIRED | `services.classify_position_needs(club)` in `get()` |
| `clubs/services.py::classify_position_needs` | `clubs.services.position_needs_aggregate` | reuse | ✓ WIRED | `needs = position_needs_aggregate(club)`, no second query |
| `clubs/urls.py` | `PositionNeedsView` | path ordering | ✓ WIRED | Verified route order above; live test proves non-swallowing |
| `workspace/views.py::SquadPlanViewSet.simulate` | `workspace.services.simulate_squad_change` | @action call | ✓ WIRED | Direct call with try/except mapping to 400 |
| `workspace/services.py::simulate_squad_change` | `players.models.Player` | bulk `id__in` fetch | ✓ WIRED | Single `Player.objects.filter(id__in=ref_ids)` call, no per-entry loop query |
| `workspace/services.py::_squad_metrics` | `Player.impact_score/market_value/age` | None-filtered sum/avg | ✓ WIRED | Confirmed only `impact_score` used for scoring, None-filtered lists |
| `workspace/views.py::SquadPlanViewSet.simulate` | `IsOwner` | `self.get_object()` | ✓ WIRED | Confirmed 404 on cross-user access via live test |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| PLAN-01 | 11-01-PLAN.md | User can view Position Needs analysis (strong/weak/at-risk) for a club's squad | ✓ SATISFIED | Endpoint live, tested, matches REQUIREMENTS.md checkbox marked `[x]` and Phase 11 mapping row `Complete` |
| PLAN-03 | 11-02-PLAN.md | User can simulate a squad change (add/remove/swap) and get recalculated aggregate squad metrics without persisting until committed | ✓ SATISFIED | Simulate endpoint live, tested (including a real DB-unchanged assertion), matches REQUIREMENTS.md `[x]` and mapping row `Complete` |

No orphaned requirements: REQUIREMENTS.md's Phase 11 mapping table lists only PLAN-01 and PLAN-03 against Phase 11; PLAN-02 and PLAN-04 are explicitly mapped to Phase 12, matching both plans' frontmatter (`requirements: [PLAN-01]` / `requirements: [PLAN-03]`) exactly — nothing declared but unimplemented, nothing implemented but undeclared.

### Anti-Patterns Found

None. Grep for TODO/FIXME/XXX/HACK/PLACEHOLDER/"coming soon"/"not implemented" across all 5 touched files (`clubs/services.py`, `clubs/views.py`, `clubs/urls.py`, `workspace/services.py`, `workspace/views.py`) returned zero matches.

### Live Pytest Results

Full backend suite run independently (`.venv/bin/python -m pytest`):

```
231 passed, 315 skipped, 0 failed
```

Phase-11-specific subset run independently:

```
clubs/tests/test_position_needs.py — 4 passed
clubs/tests/test_views_position_needs.py — 4 passed
workspace/tests/test_squad_simulation.py — 9 passed
```

All 315 skips are pre-existing "No real Player data in the dev DB" guards unrelated to this phase (same skip reasons documented in prior phases' SUMMARYs). Zero regressions.

### Timing / "Premature Completion" Assessment (requested cross-check)

**Question:** Was ROADMAP.md's Phase 11 "2/2 Complete" marking (committed by 11-01 in `6a32670` at 07:23:26) premature, given 11-02's own docs/SUMMARY commit (`198a016`) didn't land until 07:25:03 — two minutes later?

**Finding: Benign timing artifact, NOT the Phase 10 class of problem.**

Git history for this phase is strictly linear (single branch, no merges — confirmed via `git log --oneline --graph`):

```
fe165d4  07:19:32  test(11-01): add classify_position_needs service + unit tests
c353a48  07:19:56  test(11-02): add simulate_squad_change service with unit tests
7a9011b  07:21:00  feat(11-01): add PositionNeedsView endpoint + route
5aaae5c  07:22:22  feat(11-02): add simulate action on SquadPlanViewSet
6a32670  07:23:26  docs(11-01): complete position-needs plan  <- marks ROADMAP "2/2 Complete"
198a016  07:25:03  docs(11-02): complete squad-simulation plan
```

Because history is linear, `6a32670` (the commit that marked Phase 11 "2/2 Complete") is a direct descendant of `5aaae5c` — the actual `simulate` action feature commit. By the time the "Complete" marker was written to disk, **both** feature commits (`7a9011b` for 11-01, `5aaae5c` for 11-02) were already present in the working tree and git history. Independently re-running the full test suite today confirms both features are real, wired, and tested.

This differs materially from the prior Phase 10 incident, where REQUIREMENTS.md was marked complete while the actual endpoint code did not exist anywhere in the repository at that timestamp. Here, the code existed; only the second plan's own *documentation* commit (SUMMARY.md creation, STATE.md update) was still pending. The "2/2 Complete" claim in ROADMAP.md was accurate at the moment it was written — it just preceded 11-02's self-documentation by two minutes, which is a metadata-ordering artifact (two parallel-wave agents racing to write their own docs commits), not a case of marking work "done" before the work existed.

### Human Verification Required

None. All must-haves are backend API behaviors fully verifiable via code inspection and live pytest execution; no UI, real-time, or external-service behavior is in scope for this phase.

### Gaps Summary

No gaps found. All 16 derived observable truths verified against live code and passing tests; all artifacts exist, are substantive, and are wired; both requirement IDs (PLAN-01, PLAN-03) cross-referenced cleanly against REQUIREMENTS.md with no orphans; the reported "premature completion" concern was independently investigated and found to be a benign commit-ordering artifact rather than a substantive gap — the underlying code was genuinely present and functional at the time ROADMAP.md was updated.

---

*Verified: 2026-07-26*
*Verifier: Claude (gsd-verifier)*
