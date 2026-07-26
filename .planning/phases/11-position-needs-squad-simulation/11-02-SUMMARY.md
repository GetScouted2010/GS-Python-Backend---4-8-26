---
phase: 11-position-needs-squad-simulation
plan: 02
subsystem: api
tags: [django, drf, workspace, squad-simulation, in-memory, rmm]

requires:
  - phase: 08-user-workspace-crud
    provides: SquadPlan model, SquadPlanViewSet (IsOwner + get_queryset), proposed_changes validation with add/remove/swap field semantics
  - phase: 06-scoring-performance-caching-layer
    provides: Player.impact_score denormalized field (club-independent RMM)
provides:
  - "POST /api/workspace/squad-plans/{id}/simulate/ -- applies proposed_changes (stored or ad-hoc override) to a club's live squad entirely in memory and returns baseline/simulated/delta metrics"
  - "workspace/services.py: simulate_squad_change, InvalidPlayerReference, _squad_metrics, _referenced_ids"
affects: [phase-11-plan-01-position-needs, future-squad-plan-commit-ui]

tech-stack:
  added: []
  patterns:
    - "Per-app services.py convention (clubs/services.py precedent) for business logic outside serializers/views"
    - "In-memory simulation: never .save()/.update(), single bulk id__in fetch, null-safe averages (never zero-filled)"
    - "@action(detail=True) on an existing ModelViewSet, self.get_object() for IsOwner-via-404, DefaultRouter auto-routing (no urls.py edit)"

key-files:
  created:
    - get-scouted-be/workspace/services.py
    - get-scouted-be/workspace/tests/test_squad_simulation.py
  modified:
    - get-scouted-be/workspace/views.py

key-decisions:
  - "avg score uses Player.impact_score exclusively (club-independent RMM); the three own-club-context score fields (compatibility_score/financial_fit_score/transfer_probability_score) are never used since they would be meaningless for an incoming player from a different club"
  - "Null age/impact_score/market_value values are excluded from averages/sums rather than coerced to 0, with missing_market_value_count surfacing the excluded count"
  - "Simulation is a pure read-side computation -- no new commit endpoint; committing a plan continues to reuse Phase 8's existing PATCH /api/workspace/squad-plans/{id}/"

requirements-completed: [PLAN-03]

duration: 12min
completed: 2026-07-26
---

# Phase 11 Plan 02: Squad Simulation Summary

**POST /api/workspace/squad-plans/{id}/simulate/ applies add/remove/swap proposed_changes to a club's live squad entirely in memory, returning baseline/simulated/delta avg age, avg RMM score, and budget impact -- never persisting to the database.**

## Performance

- **Duration:** ~12 min
- **Completed:** 2026-07-26
- **Tasks:** 2/2 completed
- **Files modified:** 3 (1 created service, 1 created test file, 1 modified view)

## Accomplishments

- New `workspace/services.py::simulate_squad_change` correctly applies add (player_id), remove (player_id), and swap (player_id outgoing + incoming_player_id incoming) against an in-memory copy of `club.players.all()`, matching `SquadPlanDetailSerializer.validate_proposed_changes`'s authoritative field semantics exactly.
- Null-safe aggregate metrics (`_squad_metrics`): avg_age, avg_score (impact_score only), total_market_value, missing_market_value_count -- all null values excluded from sums/averages, never coerced to 0.
- Single bulk `Player.objects.filter(id__in=...)` query resolves every referenced player id up front (no N+1), raising `InvalidPlayerReference` on any unknown id.
- New `simulate` `@action` on `SquadPlanViewSet` wired to the service: 200 with baseline/simulated/delta/simulated_squad on success, 400 (not 500) on an invalid player reference, 404 on a non-owned plan via `self.get_object()`, optional `proposed_changes` body override falling back to the stored value.
- 9 tests (4 unit + 5 integration) all green; no manual `urls.py` edit needed (DefaultRouter auto-routes the `@action`); full backend suite (231 passed, 315 skipped, 0 failed) confirms zero regression.

## Task Commits

Each task was committed atomically:

1. **Task 1: NEW workspace/services.py -- simulate_squad_change + unit tests (RED->GREEN)** - `c353a48` (test)
2. **Task 2: simulate @action on SquadPlanViewSet + integration tests (RED->GREEN)** - `5aaae5c` (feat)

_Note: Task 1's single commit intentionally bundles the RED test file and the GREEN service implementation together (tests were confirmed failing pre-implementation via a standalone pytest run, not via a separate git commit) since both files land in the same review-friendly change; Task 2 added only `views.py` as a follow-on commit since the integration tests were already authored in Task 1's test file and independently re-confirmed RED before the `@action` was added._

## Files Created/Modified

- `get-scouted-be/workspace/services.py` - NEW. `simulate_squad_change(squad_plan, proposed_changes=None)`, `InvalidPlayerReference`, `_squad_metrics`, `_referenced_ids`. Pure in-memory computation, zero `.save()`/`.update()`/`bulk_*` calls.
- `get-scouted-be/workspace/tests/test_squad_simulation.py` - NEW. 4 unit tests (add/remove/swap, null-exclusion, invalid reference, stored-vs-override) + 5 integration tests (response shape, invalid id 400, non-persistence, override honored, ownership 404).
- `get-scouted-be/workspace/views.py` - Added `from workspace import services as workspace_services` import and `SquadPlanViewSet.simulate` `@action(detail=True, methods=["post"], url_path="simulate")`.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' code (services.py, the view action) match the plan's literal `<action>` code blocks verbatim; only the test file's exact prose/assertion wording was authored fresh per the `<behavior>` spec (functionally identical to the plan's described test cases).

## Verification Evidence

- `cd get-scouted-be && pytest workspace/tests/test_squad_simulation.py::test_apply_add_remove_swap ... ` (Task 1's 4 unit tests): confirmed RED (ImportError: no `services` module) before implementation, then 4 passed after.
- `.venv/bin/python -m pytest workspace/tests/test_squad_simulation.py`: confirmed RED (404 on `/simulate/`, ambient interpreter's missing `sklearn` required switching to the project's `.venv` for the app-loading path -- matches Phase 5/6's documented "ambient pyenv Python lacks scikit-learn" constraint) before the `@action`, then all 9 passed after.
- `.venv/bin/python -m pytest workspace`: 41 passed, 0 failed (full workspace app suite, no regression).
- `.venv/bin/python -m pytest` (full backend suite): 231 passed, 315 skipped, 0 failed.
- All plan-specified acceptance-criteria greps (file existence, function/class definitions, single bulk `id__in` fetch, zero `.save()/.update()/bulk_*` occurrences, zero own-club-context score field references, None-filtering, zero manual `urls.py` edits) independently re-run and confirmed passing.

## Self-Check: PASSED

- FOUND: get-scouted-be/workspace/services.py
- FOUND: get-scouted-be/workspace/tests/test_squad_simulation.py
- FOUND: get-scouted-be/workspace/views.py (simulate action present)
- FOUND commit c353a48
- FOUND commit 5aaae5c
