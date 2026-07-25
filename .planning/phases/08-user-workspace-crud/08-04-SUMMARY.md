---
phase: 08-user-workspace-crud
plan: 04
subsystem: api
tags: [django, drf, workspace, squad-plans, jsonfield-validation]

# Dependency graph
requires:
  - phase: 08-user-workspace-crud
    provides: "SquadPlan model (08-01), IsOwner permission, workspace app router (08-02/08-03)"
provides:
  - "SquadPlanViewSet (ModelViewSet) at /api/workspace/squad-plans/ -- full CRUD scoped to request.user"
  - "SquadPlanListSerializer (lightweight) vs SquadPlanDetailSerializer (live current_squad) list/detail split"
  - "write-time proposed_changes structural validation (action in {add,remove,swap}, swap requires incoming_player_id)"
affects: [phase-11-simulation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "list/detail serializer split via get_serializer_class branching on self.action == 'list'"
    - "live (never frozen) derived data via SerializerMethodField reusing PlayerListSerializer over club.players.all()"
    - "JSONField write-time structural validation via validate_<field_name> on ModelSerializer"

key-files:
  created:
    - get-scouted-be/workspace/tests/test_squad_plans.py
  modified:
    - get-scouted-be/workspace/serializers.py
    - get-scouted-be/workspace/views.py
    - get-scouted-be/workspace/urls.py

key-decisions:
  - "SquadPlanViewSet.permission_classes = [IsAuthenticated, IsOwner], not the plan's literal [IsOwner] -- matches the established 08-02/08-03 pattern (overriding permission_classes drops the global IsAuthenticated default and crashes get_queryset() on AnonymousUser instead of returning a clean 401)"
  - "proposed_changes validation runs on create because SquadPlanViewSet's create action uses the detail serializer (self.action == 'create' != 'list'), so write-time structural checks apply to every POST as intended"

patterns-established:
  - "current_squad is always derived live via PlayerListSerializer(obj.club.players.all(), many=True).data -- never stored/frozen on the SquadPlan row, so Phase 11's simulation reads the same live shape"

requirements-completed: [CRUD-08]

# Metrics
duration: 6min
completed: 2026-07-25
---

# Phase 8 Plan 4: Squad Plan CRUD Summary

**Squad Plans CRUD under /api/workspace/squad-plans/ with a lightweight list serializer, a detail serializer that derives current_squad live from the club's players (never frozen), and write-time proposed_changes structural validation.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-25T05:36:20Z
- **Completed:** 2026-07-25T05:41:51Z
- **Tasks:** 2 completed
- **Files modified:** 4 (3 modified, 1 created)

## Accomplishments
- SquadPlanViewSet delivers full CRUD (create/list/retrieve/update/delete) scoped to request.user via get_queryset filtering
- List/detail serializer split: list stays lightweight (no current_squad computation per row), detail computes current_squad live via PlayerListSerializer over club.players.all()
- proposed_changes JSONField validated at write time: must be a list of dicts, each with action in {add, remove, swap}; swap entries require incoming_player_id — malformed input returns 400
- squad-plans registered on the existing workspace router alongside watchlist and shortlists

## Task Commits

Each task was committed atomically:

1. **Task 1: SquadPlan list/detail serializers + SquadPlanViewSet** - `5ef8cd5` (feat)
2. **Task 2: test_squad_plans.py — create/live-squad/validation/scoping/ownership** - `adec083` (test)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/workspace/serializers.py` - Added SquadPlanListSerializer, SquadPlanDetailSerializer (get_current_squad, validate_proposed_changes)
- `get-scouted-be/workspace/views.py` - Added SquadPlanViewSet (ModelViewSet, get_queryset scoped to user, get_serializer_class list/detail split)
- `get-scouted-be/workspace/urls.py` - Registered squad-plans router entry
- `get-scouted-be/workspace/tests/test_squad_plans.py` - 8 integration tests: create, live current_squad, lightweight list, 3 validation-failure cases, scoping, ownership

## Decisions Made
- Applied the established `permission_classes = [IsAuthenticated, IsOwner]` pattern from 08-02/08-03 instead of the plan's literal `[IsOwner]`, since overriding permission_classes drops DRF's global default and would let AnonymousUser crash `get_queryset()` rather than return a clean 401.
- No architectural changes; SquadPlan model, IsOwner permission, and router already existed from 08-01.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Used [IsAuthenticated, IsOwner] instead of plan's literal [IsOwner]**
- **Found during:** Task 1 (SquadPlanViewSet)
- **Issue:** The plan's action block specified `permission_classes = [IsOwner]`, which would silently drop DRF's global `IsAuthenticated` default and crash `get_queryset()` on an anonymous request instead of returning 401 — the exact bug documented and fixed in 08-02 and applied proactively in 08-03.
- **Fix:** Set `permission_classes = [IsAuthenticated, IsOwner]`, matching WatchlistViewSet/ShortlistViewSet.
- **Files modified:** get-scouted-be/workspace/views.py
- **Verification:** `python manage.py check` passes; full workspace test suite (21 tests) green, including authenticated_client-only paths (no explicit anon-401 test was required by this plan, but the pattern matches the codebase-wide convention read in `files_to_read`).
- **Committed in:** 5ef8cd5 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug-class permission fix)
**Impact on plan:** Necessary for correctness/security consistency with the rest of the workspace app. No scope creep.

## Issues Encountered
- Ambient `python` interpreter lacks `sklearn`, which `scoring/urls.py` imports transitively — same pre-existing environment characteristic documented in Phase 5/6 STATE.md entries. Resolved by running `manage.py check` / `pytest` via the project's `.venv/bin/python`, not by modifying any project code.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CRUD-08 complete: Squad Plans are fully functional (create/list/retrieve/update/delete), scoped per-user, with live current_squad and validated proposed_changes — exactly the shape Phase 11's simulation will consume.
- Full workspace/tests/ suite (watchlist + shortlists + squad-plans) green: 21/21 passing.
- Plan 08-05 (or whichever plan is next in wave 4+) can proceed; no blockers introduced by this plan.

---
*Phase: 08-user-workspace-crud*
*Completed: 2026-07-25*

## Self-Check: PASSED

- FOUND: get-scouted-be/workspace/tests/test_squad_plans.py
- FOUND: .planning/phases/08-user-workspace-crud/08-04-SUMMARY.md
- FOUND: commit 5ef8cd5
- FOUND: commit adec083
