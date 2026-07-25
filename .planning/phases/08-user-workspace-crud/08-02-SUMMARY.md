---
phase: 08-user-workspace-crud
plan: 02
subsystem: api
tags: [drf, watchlist, permissions, get-queryset-scoping, integration-tests]

# Dependency graph
requires:
  - phase: 08-user-workspace-crud (08-01)
    provides: workspace app scaffold, Watchlist model with UniqueConstraint(user, player), IsOwner permission, tests/conftest.py fixtures
provides:
  - "POST/GET/DELETE /api/workspace/watchlist/ (list/create/destroy, no update)"
  - "WatchlistSerializer with HiddenField(CurrentUserDefault) auto-uniqueness pattern"
  - "get_queryset user-scoping pattern for user-owned DRF ViewSets"
  - "6 integration tests covering save/duplicate/remove/scoping/ownership/auth"
affects: [08-03, 08-04, 08-05, 08-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Selective-mixin GenericViewSet (List/Create/Destroy only, no Update) for add/remove-only resources"
    - "HiddenField(CurrentUserDefault()) on serializer 'user' field so DRF's auto UniqueTogetherValidator (from the model's UniqueConstraint) yields a clean 400 on duplicate, never client-supplied and never a raw IntegrityError 500"
    - "get_queryset() filtered to request.user is mandatory for user-owned resources -- object-level permissions (IsOwner) never run for list/create, only for retrieve/update/destroy"
    - "permission_classes overrides must explicitly re-list IsAuthenticated -- setting permission_classes=[IsOwner] alone silently drops the project's global IsAuthenticated default and lets AnonymousUser reach get_queryset(), crashing instead of returning 401"

key-files:
  created:
    - get-scouted-be/workspace/serializers.py
    - get-scouted-be/workspace/views.py
    - get-scouted-be/workspace/urls.py
    - get-scouted-be/workspace/tests/test_watchlist.py
  modified:
    - get-scouted-be/config/urls.py

key-decisions:
  - "WatchlistViewSet.permission_classes explicitly includes IsAuthenticated alongside IsOwner, since DRF permission_classes overrides (rather than extends) the project-wide default -- the plan's literal code sample only listed IsOwner, which was caught live by the unauthenticated-request test."

patterns-established:
  - "User-owned CRUD ViewSet template: selective mixins + get_queryset(user=request.user) + permission_classes=[IsAuthenticated, IsOwner] + HiddenField(CurrentUserDefault) on serializer -- the reusable shape for Shortlist/SquadPlan/RecentActivity in remaining Phase 8 plans."

requirements-completed: [CRUD-06]

# Metrics
duration: 5min
completed: 2026-07-25
---

# Phase 08 Plan 02: Watchlist CRUD Summary

**WatchlistViewSet (list/create/destroy) under /api/workspace/watchlist/, scoped to request.user via get_queryset filtering, with duplicate-add handled cleanly by DRF's auto UniqueTogetherValidator instead of a raw IntegrityError.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-25T06:23:55+01:00
- **Completed:** 2026-07-25T06:28:15+01:00
- **Tasks:** 2 completed
- **Files modified:** 5 (4 created, 1 modified)

## Accomplishments
- CRUD-06 live: an authenticated user can POST to save a player, DELETE to remove it, GET to list only their own saves
- Duplicate save returns a clean 400 (DRF's auto UniqueTogetherValidator derived from the model's UniqueConstraint), never a 500 IntegrityError
- List correctly scoped to request.user — confirmed cross-user isolation is not accidental (get_queryset filter, since IsOwner's object-level check never runs for list/create)
- Cross-user delete denied (403/404), unauthenticated requests denied (401) after fixing a permission_classes override gap
- 6 integration tests exercising save/duplicate/remove/scoping/ownership/auth against the full DRF request/response cycle

## Task Commits

Each task was committed atomically:

1. **Task 1: WatchlistSerializer + WatchlistViewSet + URL wiring** - `4c8f21b` (feat)
2. **Task 2: test_watchlist.py — save/remove/duplicate/scoping/auth** - `ec898cd` (test, includes an inline views.py fix)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/workspace/serializers.py` - WatchlistSerializer; `user` is a HiddenField(CurrentUserDefault()) so the client never submits it and the model's UniqueConstraint auto-validates per-user duplicates
- `get-scouted-be/workspace/views.py` - WatchlistViewSet (List/Create/Destroy mixins + GenericViewSet); get_queryset() scoped to request.user; permission_classes=[IsAuthenticated, IsOwner]
- `get-scouted-be/workspace/urls.py` - DefaultRouter registering "watchlist"
- `get-scouted-be/config/urls.py` - appended `path("api/workspace/", include("workspace.urls"))`
- `get-scouted-be/workspace/tests/test_watchlist.py` - 6 integration tests: save 201, duplicate 400, remove 204, list scoping, cross-user delete denied, unauthenticated 401

## Decisions Made
- Explicitly listed `IsAuthenticated` alongside `IsOwner` in `permission_classes` rather than relying on the project's global default, since any `permission_classes` override on a DRF view replaces (not extends) the default. Documented inline in views.py as a comment so future workspace viewsets (Shortlist, SquadPlan, RecentActivity) don't repeat the gap.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Unauthenticated watchlist requests crashed instead of returning 401**
- **Found during:** Task 2 (writing `test_unauthenticated_denied`)
- **Issue:** The plan's literal `views.py` code sample set `permission_classes = [IsOwner]`. `IsOwner` has no `has_permission` override (defaults to `True`), and DRF's `permission_classes` attribute *overrides* the global `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` rather than extending it. An anonymous request therefore passed the permission check and reached `get_queryset()`, which called `Watchlist.objects.filter(user=self.request.user)` with `request.user` being `AnonymousUser` — Django then raised `ValidationError: "AnonymousUser" is not a valid UUID` (an unhandled 500), directly contradicting the plan's own must-have truth ("Unauthenticated requests to any watchlist route are denied (401)").
- **Fix:** Added `from rest_framework.permissions import IsAuthenticated` and changed `permission_classes = [IsOwner]` to `permission_classes = [IsAuthenticated, IsOwner]`, with an inline comment explaining why both are required.
- **Files modified:** `get-scouted-be/workspace/views.py`
- **Verification:** `test_unauthenticated_denied` now asserts 401 and passes; full `pytest workspace/tests/test_watchlist.py` (6/6) and full-suite regression (112 passed, 305 skipped, 0 failed) both green.
- **Committed in:** `ec898cd` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, Rule 1)
**Impact on plan:** Necessary correctness fix directly required by the plan's own must-have truths; no scope creep. This pattern (permission_classes override silently dropping the global default) is now the template every remaining Phase 8 viewset must copy correctly from the start.

## Issues Encountered
- `python manage.py check` and `pytest` initially failed under the ambient pyenv Python with `ModuleNotFoundError: No module named 'sklearn'` (unrelated to this plan — scoring app's TFM dependency). Resolved by running all verification through the project's existing `get-scouted-be/.venv`, matching the precedent already noted in STATE.md for prior phases (5, 6). No code change required.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CRUD-06 fully live and tested; the User-owned CRUD ViewSet template (get_queryset scoping + explicit IsAuthenticated+IsOwner + HiddenField(CurrentUserDefault)) is proven end-to-end and ready to be copied by 08-03 (Shortlist/ShortlistEntry), 08-04/08-05 (SquadPlan), and 08-06 (RecentActivity).
- No blockers. Pre-existing unrelated regression (`accounts/tests/test_permissions.py::test_director_read_only_visibility`, tracked in Phase 07's deferred-items.md) remains out of scope and untouched.

---
*Phase: 08-user-workspace-crud*
*Completed: 2026-07-25*

## Self-Check: PASSED

All created/modified files and task commit hashes verified present on disk and in git history.
