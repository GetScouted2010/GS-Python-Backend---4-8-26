---
phase: 02-auth-access-control
plan: 03
subsystem: auth
tags: [drf, jwt, rbac, permissions, django]

# Dependency graph
requires:
  - phase: 02-auth-access-control (Plans 01-02)
    provides: custom accounts.User model, DRF/simplejwt settings, register/login/refresh/logout/password-reset endpoints, UserFactory + authenticated_client(role) pytest fixtures
provides:
  - "Reusable ROLE_RANK / MinimumRole(role) permission factory encoding the additive role hierarchy in one place (accounts/permissions.py)"
  - "IsSelfOrAdmin object-level permission (available for Phase 7/8 reuse, not yet consumed in this plan)"
  - "/api/auth/me/ self-service profile endpoint (view/edit own display_name, role read-only)"
  - "/api/auth/admin/users/ org-wide user management (director read-only, admin read/write role + soft deactivation, no hard-delete route ever registered)"
affects: [phase-07-core-crud, phase-08-user-workspace-crud]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MinimumRole(role) permission-class factory read from a single ROLE_RANK dict -- import this instead of hand-writing per-app role checks"
    - "get_permissions() override per-action on a GenericViewSet to mix rank requirements within one viewset (director for list/retrieve, admin for update/deactivate)"
    - "Separate ModelSerializer per audience for the same User model (ProfileSerializer: role/email read-only; AdminUserSerializer: role/is_active writable) rather than one serializer with conditional field logic"
    - "Soft-delete-only viewsets: compose GenericViewSet from List/Retrieve/Update mixins, deliberately omitting Create/Destroy mixins rather than overriding destroy() to no-op"

key-files:
  created:
    - get-scouted-be/accounts/permissions.py
  modified:
    - get-scouted-be/accounts/serializers.py
    - get-scouted-be/accounts/views.py
    - get-scouted-be/accounts/urls.py
    - get-scouted-be/accounts/tests/test_permissions.py

key-decisions:
  - "ROLE_RANK/MinimumRole implemented exactly per 02-RESEARCH.md's verified interface (scout=analyst=1 < director=2 < admin=3); no deviation from the researched shape"
  - "AdminUserViewSet composes ListModelMixin+RetrieveModelMixin+UpdateModelMixin+GenericViewSet with no Create/Destroy mixins, so DELETE returns 405 (no destroy route exists) rather than being an overridden no-op -- proven by test_no_hard_delete_route"
  - "Role/deactivation freshness verified end-to-end via a real endpoint (test_role_change_takes_effect_immediately: director demoted via ORM mid-session, same access token denied 403 on next request to /api/auth/admin/users/, no re-login) -- confirms JWTAuthentication's per-request DB refetch + DB-fresh permission reads work together as researched, not just in isolation"

requirements-completed: [AUTH-02]

# Metrics
duration: 18min
completed: 2026-07-21
---

# Phase 2 Plan 3: Role-Based Permission Enforcement Summary

**MinimumRole(role) rank-factory permission primitive plus two concrete role-gated endpoints — self-service `/api/auth/me/` (role self-escalation blocked) and org-wide `/api/auth/admin/users/` (director read-only, admin read/write, soft-deactivate only, no hard delete) — proving DB-fresh role/deactivation enforcement takes effect on the very next request with no re-login.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-21T12:01:00Z (approx.)
- **Completed:** 2026-07-21T12:19:00Z
- **Tasks:** 2 completed
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- Single reusable `ROLE_RANK`/`MinimumRole(role)` factory + `IsSelfOrAdmin` in `accounts/permissions.py` — the one role-gating primitive Phase 7/8 will import for Watchlist/Shortlist/SquadPlan
- `/api/auth/me/` lets any authenticated user view/edit their own `display_name` but never their own `role` (self-escalation structurally impossible via `read_only_fields`, not just app-logic denial)
- `/api/auth/admin/users/` gives director+ org-wide read visibility and admin-only write access (role change, soft `is_active=False` deactivation) with zero destroy route registered — accounts are never hard-deleted at the API layer at all
- Integration-tested proof that role/deactivation changes apply on the very next request without re-login, exercising a real endpoint end-to-end (not just the permission class in isolation)
- Full `accounts` test suite green (29 tests) and full repo suite green (47 tests); `manage.py check` clean

## Task Commits

Each task followed RED -> GREEN (TDD):

1. **Task 1: MinimumRole/IsSelfOrAdmin + /api/auth/me/**
   - `72ebf95` test(02-03): add failing tests for MinimumRole/profile endpoint (Task 1 RED)
   - `eeb542d` feat(02-03): add MinimumRole/IsSelfOrAdmin + self-service /api/auth/me/ (Task 1 GREEN)
2. **Task 2: AdminUserViewSet — director read-only, admin read/write**
   - `79201f6` test(02-03): add failing tests for AdminUserViewSet (Task 2 RED)
   - `b34d8b9` feat(02-03): add AdminUserViewSet -- director read-only, admin read/write user mgmt (Task 2 GREEN)

**Plan metadata:** (this commit, added after SUMMARY.md/STATE.md/ROADMAP.md updates)

_Note: this plan's tasks were TDD (RED test commit, then GREEN implementation commit per task); no separate refactor commits were needed._

## Files Created/Modified
- `get-scouted-be/accounts/permissions.py` - ROLE_RANK table, MinimumRole(role) factory, IsSelfOrAdmin object permission
- `get-scouted-be/accounts/serializers.py` - ProfileSerializer (role/email/id read-only), AdminUserSerializer (role/is_active writable)
- `get-scouted-be/accounts/views.py` - ProfileView (RetrieveUpdateAPIView targeting request.user), AdminUserViewSet (List/Retrieve/Update mixins + deactivate action, per-action get_permissions())
- `get-scouted-be/accounts/urls.py` - `me/` path; DefaultRouter registering `admin/users` -> AdminUserViewSet
- `get-scouted-be/accounts/tests/test_permissions.py` - 9 tests covering both tasks (auth-required, self-edit, role-read-only, immediacy, role-gated 403, director read-only, admin role-change, admin soft-deactivate, no-hard-delete-route)

## Decisions Made
- Encoded the additive hierarchy in exactly one dict (`ROLE_RANK`) and one factory (`MinimumRole`), per 02-RESEARCH.md Pattern 2 — no bespoke per-role permission classes were written
- `AdminUserViewSet.get_permissions()` differentiates by `self.action` (director rank for `list`/`retrieve`, admin rank for `update`/`partial_update`/`deactivate`) rather than splitting into two viewsets, keeping the single "director read-only, admin read/write" shape Phase 7/8 will replicate visible in one place
- Verified role/deactivation immediacy against a real endpoint, not only the permission class in isolation, per the plan's explicit requirement that the primary assertion "MUST exercise a real endpoint"

## Deviations from Plan

None - plan executed exactly as written. One micro-adjustment during Task 2 implementation: the initial `AdminUserViewSet` docstring mentioned the literal string "DestroyModelMixin" in prose (to explain its intentional absence), which tripped the acceptance criteria's literal `grep` check for that string; reworded the docstring to describe the same intent ("hard-delete mixin") without using the literal class name. No code/behavior change, no separate commit needed (folded into the Task 2 GREEN commit before it was made).

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 (auth-access-control) is now fully implemented across all 3 plans: custom User model + DRF/JWT settings (01), account lifecycle endpoints (02), role-based permission enforcement (03)
- `MinimumRole(role)` and `IsSelfOrAdmin` in `accounts/permissions.py` are ready for direct import by Phase 7 (Core CRUD) and Phase 8 (User Workspace CRUD) for Watchlist/Shortlist/SquadPlan role gating (director read-only org-wide visibility + owner-only writes, same shape as this plan's AdminUserViewSet)
- Full `accounts` suite (29 tests) and full repo suite (47 tests) green; `manage.py check` clean
- This is the last plan in Phase 2 — phase now proceeds to `/gsd:verify-phase` (or equivalent verification step) rather than another execute-plan cycle
- No blockers identified for downstream phases

---
*Phase: 02-auth-access-control*
*Completed: 2026-07-21*

## Self-Check: PASSED

All created/modified files verified present on disk; all 4 task commits (72ebf95, eeb542d, 79201f6, b34d8b9) verified present in git log.
