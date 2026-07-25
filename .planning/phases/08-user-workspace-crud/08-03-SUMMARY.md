---
phase: 08-user-workspace-crud
plan: 03
subsystem: api
tags: [drf, shortlist, nested-action-routes, get-object-ownership, permissions, integration-tests]

# Dependency graph
requires:
  - phase: 08-user-workspace-crud (08-01)
    provides: workspace app scaffold, Shortlist/ShortlistEntry models, IsOwner permission (shortlist.user fallback for entries), tests/conftest.py fixtures
  - phase: 08-user-workspace-crud (08-02)
    provides: "permission_classes=[IsAuthenticated, IsOwner] template, get_queryset user-scoping pattern, HiddenField(CurrentUserDefault) template"
provides:
  - "Full ModelViewSet CRUD for /api/workspace/shortlists/ (create/list/retrieve/update/delete), scoped to request.user"
  - "GET/POST /api/workspace/shortlists/{id}/entries/ nested @action route (list + add player with optional note)"
  - "DELETE /api/workspace/shortlists/{id}/entries/{entry_id}/ nested @action route"
  - "Nested-resource-via-@action pattern: parent ownership propagates to children through self.get_object() without drf-nested-routers"
  - "7 integration tests covering create/name/club, entry add/list/delete, cross-user list scoping, cross-user entry-ownership denial, auth gate"
affects: [08-04, 08-05, 08-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Nested sub-resource via @action(detail=True): self.get_object() on the parent re-runs check_object_permissions, so child operations (entries list/create/delete) inherit IsOwner for free without a second router/viewset"
    - "url_path=r'entries/(?P<entry_id>[^/.]+)' on a second @action gives a two-segment nested delete route (shortlists/{id}/entries/{entry_id}/) without drf-nested-routers"
    - "Full ModelViewSet (not selective mixins) used here since Shortlist supports update (rename) unlike Watchlist's add/remove-only shape"

key-files:
  created:
    - get-scouted-be/workspace/tests/test_shortlists.py
  modified:
    - get-scouted-be/workspace/serializers.py
    - get-scouted-be/workspace/views.py
    - get-scouted-be/workspace/urls.py

key-decisions:
  - "Applied the 08-02-established permission_classes=[IsAuthenticated, IsOwner] pattern directly in Task 1's implementation (rather than discovering the gap via a failing test), since the fix was already a documented decision from the prior plan -- no deviation needed this time."

patterns-established:
  - "Nested-resource-via-@action: any future workspace resource needing a parent-scoped child collection (e.g. SquadPlan proposed_changes if ever split out) can route through self.get_object() the same way instead of adding drf-nested-routers."

requirements-completed: [CRUD-07]

# Metrics
duration: 4min
completed: 2026-07-25
---

# Phase 08 Plan 03: Shortlist CRUD + Nested Entries Summary

**ShortlistViewSet (full ModelViewSet) under /api/workspace/shortlists/ with nested entries/delete_entry @action routes whose ownership checks propagate from the parent shortlist via self.get_object(), avoiding drf-nested-routers.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-25T06:31:05+01:00
- **Completed:** 2026-07-25T06:34:26+01:00
- **Tasks:** 2 completed
- **Files modified:** 4 (1 created, 3 modified)

## Accomplishments
- CRUD-07 live: authenticated user can POST {name, club} to create a named, club-scoped shortlist and full GET/PATCH/DELETE it
- Nested entry sub-routes (GET/POST list+create, DELETE remove) live under /shortlists/{id}/entries/ and /shortlists/{id}/entries/{entry_id}/
- Ownership propagates from parent Shortlist to entry operations purely through self.get_object() -- no separate permission wiring needed for the nested routes
- Cross-user list correctly scoped (get_queryset filter); cross-user entry POST against another user's shortlist returns 404 (object not in that user's queryset), never leaking existence
- 7 integration tests: create/name/club, add-entry-with-note, list-entries, delete-entry, cross-user scoping, cross-user ownership denial, unauthenticated 401
- Full workspace/tests/ suite: 13/13 passing (6 watchlist + 7 shortlist), no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Shortlist + ShortlistEntry serializers and ShortlistViewSet with nested entry actions** - `24666af` (feat)
2. **Task 2: test_shortlists.py — create/name/club/entries/scoping/ownership** - `c9a85c8` (test)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/workspace/serializers.py` - ShortlistSerializer (user HiddenField) + ShortlistEntrySerializer (shortlist field read_only, injected by the view) appended; WatchlistSerializer preserved
- `get-scouted-be/workspace/views.py` - ShortlistViewSet (ModelViewSet) with get_queryset scoped to request.user, permission_classes=[IsAuthenticated, IsOwner], entries @action (GET/POST) and delete_entry @action (DELETE via regex sub-path); WatchlistViewSet preserved
- `get-scouted-be/workspace/urls.py` - router now registers both "watchlist" and "shortlists"
- `get-scouted-be/workspace/tests/test_shortlists.py` - 7 integration tests exercising create/name/club, entries add/list/delete, cross-user scoping, cross-user ownership denial, unauthenticated 401

## Decisions Made
- Reused the exact `permission_classes=[IsAuthenticated, IsOwner]` pattern documented as a decision in 08-02's SUMMARY.md directly in Task 1's code, rather than writing `[IsOwner]` per the plan's literal sample and re-discovering the AnonymousUser crash via the auth test. No deviation was logged since the fix was applied proactively per the files_to_read instruction, not found reactively.
- Consolidated the plan's two separate `from workspace.models import Shortlist, ShortlistEntry` import lines (one per file, appended after existing imports in the literal plan text) into each file's single existing top-of-file import statement, avoiding duplicate/shadowed imports. No behavioral difference from the plan's intent.

## Deviations from Plan

None - plan executed exactly as written (the only departure from the plan's literal code sample -- consolidating import lines and pre-applying the known permission_classes fix -- are non-behavioral cleanups covered under "Decisions Made" above, not corrective deviations).

## Issues Encountered
- `python manage.py check` and `pytest` both require the project's `.venv` (ambient pyenv Python lacks scikit-learn, needed transitively by `scoring.urls` which `config/urls.py` imports) -- same environment quirk noted in prior phase summaries (05, 06). Activated `.venv` for all verification commands; no code change required.

## Next Phase Readiness
- Shortlist CRUD + nested entries fully live and tested; CRUD-07 satisfied
- Nested-@action pattern now has two working precedents (accounts AdminUserViewSet.deactivate, workspace ShortlistViewSet.entries/delete_entry) available for 08-04/08-05 (SquadPlan, RecentActivity) if either needs a similar sub-resource shape
- No blockers for remaining Phase 8 plans

---
*Phase: 08-user-workspace-crud*
*Completed: 2026-07-25*

## Self-Check: PASSED

- FOUND: get-scouted-be/workspace/tests/test_shortlists.py
- FOUND: .planning/phases/08-user-workspace-crud/08-03-SUMMARY.md
- FOUND commit: 24666af
- FOUND commit: c9a85c8
