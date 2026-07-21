---
phase: 02-auth-access-control
plan: 02
subsystem: auth
tags: [django, drf, simplejwt, jwt, password-reset]

# Dependency graph
requires:
  - phase: 02-auth-access-control (Plan 01)
    provides: "accounts.User custom model (UUID PK, email login, role field) as AUTH_USER_MODEL; DRF+simplejwt deny-by-default settings; UserFactory/authenticated_client test fixtures"
provides:
  - "Public /api/auth/register/ endpoint (role-restricted to scout/analyst/director; admin excluded)"
  - "Public /api/auth/login/ endpoint issuing JWT access+refresh with a role claim embedded in the access token"
  - "Refresh rotation + blacklisting via TokenRefreshView (BLACKLIST_AFTER_ROTATION)"
  - "Real server-side logout via TokenBlacklistView"
  - "Console-email password reset request + confirm flow using Django's default_token_generator"
  - "AUTH_PASSWORD_VALIDATORS now actually configured (was previously unset, making validate_password a no-op)"
affects: [phase-7-user-workspace-crud, phase-8-recent-activity, any-future-phase-calling-auth-endpoints]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Public DRF views explicitly set permission_classes = [AllowAny] to relax the global IsAuthenticated deny-by-default"
    - "TokenRefreshView/TokenBlacklistView used directly from rest_framework_simplejwt.views (no custom subclass) — simplejwt's built-ins already do the right thing"
    - "Password-reset uses Django's built-in default_token_generator (self-invalidating on password change) instead of a custom token/model"
    - "TDD RED->GREEN per task: tests written and confirmed failing before implementation"

key-files:
  created:
    - get-scouted-be/accounts/serializers.py
    - get-scouted-be/accounts/views.py
    - get-scouted-be/accounts/urls.py
    - get-scouted-be/accounts/tests/test_registration.py
    - get-scouted-be/accounts/tests/test_auth_flow.py
    - get-scouted-be/accounts/tests/test_password_reset.py
  modified:
    - get-scouted-be/config/urls.py
    - get-scouted-be/config/settings/base.py

key-decisions:
  - "Added AUTH_PASSWORD_VALIDATORS (Django's 4 standard validators) to config/settings/base.py — this from-scratch settings module never set it, so validate_password() silently allowed any password including '123' prior to this fix"
  - "PasswordResetRequestView/PasswordResetConfirmView were stubbed with 501 placeholders during Task 1 (needed so accounts/urls.py's full route set — per the plan's <interfaces> block — could import successfully) and given real logic in Task 2, matching each task's TDD RED/GREEN cycle"

patterns-established:
  - "Rank-free public/private split: every public auth view sets permission_classes = [AllowAny] explicitly rather than relying on any implicit DRF default"

requirements-completed: [AUTH-01, AUTH-03]

# Metrics
duration: 20min
completed: 2026-07-21
---

# Phase 2 Plan 2: Account Lifecycle Endpoints Summary

**Registration, JWT login with an embedded role claim, refresh rotation+blacklisting, real server-side logout, and a console-email password-reset flow, all live under /api/auth/.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-21T12:01:27Z
- **Completed:** 2026-07-21T12:10:06Z
- **Tasks:** 2 completed
- **Files modified:** 8 (6 created, 2 modified)

## Accomplishments
- Public registration endpoint restricts self-service role choice to scout/analyst/director (admin rejected with 400); weak passwords now genuinely rejected by Django's validators
- Login returns access+refresh JWTs with a `role` (and `email`) claim embedded in the access token payload, decodable client-side without an extra `/me` call, while the generic simplejwt "No active account..." message prevents user/password enumeration
- Refresh rotation is live: each `/api/auth/token/refresh/` call issues a new refresh token and blacklists the one just used, confirmed by a second refresh with the old token returning 401
- Logout (`TokenBlacklistView`) performs real server-side revocation — a blacklisted refresh token can no longer be refreshed
- Password reset request/confirm flow built on Django's built-in `default_token_generator` (no new schema): request always returns a generic 200 regardless of whether the email exists (no enumeration); confirm validates uid+token, enforces password validators, and is single-use because changing the password invalidates the token hash
- `test_single_auth_backend` asserts `JWTAuthentication` is the sole configured DRF auth class — confirms AUTH-03's "one system of record" requirement

## Task Commits

Each task was committed atomically (TDD RED then GREEN):

1. **Task 1 RED: registration + auth-flow tests** - `0e1d227` (test)
2. **Task 1 GREEN: registration/login/refresh/logout implementation** - `284403e` (feat)
3. **Task 2 RED: password-reset tests** - `e0ca110` (test)
4. **Task 2 GREEN: password-reset implementation** - `eef6a79` (feat)

## Files Created/Modified
- `get-scouted-be/accounts/serializers.py` - `RegisterSerializer` (admin-excluded role choices) + `RoleTokenObtainPairSerializer` (role/email claims)
- `get-scouted-be/accounts/views.py` - `RegisterView`, `LoginView`, `PasswordResetRequestView`, `PasswordResetConfirmView`
- `get-scouted-be/accounts/urls.py` - register/login/token-refresh/logout/password-reset routes
- `get-scouted-be/config/urls.py` - mounts `accounts.urls` under `api/auth/`
- `get-scouted-be/config/settings/base.py` - added `AUTH_PASSWORD_VALIDATORS`
- `get-scouted-be/accounts/tests/test_registration.py` - registration behaviors (AUTH-01)
- `get-scouted-be/accounts/tests/test_auth_flow.py` - login/refresh/logout/single-auth-backend (AUTH-01, AUTH-03)
- `get-scouted-be/accounts/tests/test_password_reset.py` - reset request/confirm behaviors

## Decisions Made
- Django's `AUTH_PASSWORD_VALIDATORS` setting was missing entirely from this project's from-scratch `base.py` (not auto-provided outside the `startproject` template); added the standard 4-validator list so `validate_password()` in both registration and password-reset-confirm actually enforces something instead of being a silent no-op.
- Password reset used Django's built-in `PasswordResetTokenGenerator` + `send_mail` (console backend), not a custom reset-token model, per the plan's explicit "don't hand-roll" guidance — zero new schema, self-invalidating on password change.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added AUTH_PASSWORD_VALIDATORS to settings**
- **Found during:** Task 1 (registration weak-password test)
- **Issue:** `test_register_weak_password_rejected` expected a 400 for password `"123"`, but got 201 — Django's `validate_password()` had nothing to validate against because `AUTH_PASSWORD_VALIDATORS` was never set in `config/settings/base.py` (this project's settings are hand-written, not generated by `startproject`, which normally seeds this list by default).
- **Fix:** Added the standard 4-entry `AUTH_PASSWORD_VALIDATORS` list (`UserAttributeSimilarityValidator`, `MinimumLengthValidator`, `CommonPasswordValidator`, `NumericPasswordValidator`) matching CONTEXT.md's locked "Django defaults, no custom rules" decision.
- **Files modified:** `get-scouted-be/config/settings/base.py`
- **Verification:** `test_register_weak_password_rejected` and `test_password_reset_confirm_weak_password_rejected` both pass; full `accounts` suite green (20/20).
- **Committed in:** `284403e` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 2 - missing critical functionality)
**Impact on plan:** Necessary correctness fix for a locked security requirement (password strength enforcement); no scope creep — no new endpoints or architecture added beyond the plan.

## Issues Encountered
- The plan's Task 1 `<interfaces>` block specifies a complete `accounts/urls.py` including the two password-reset routes, but `PasswordResetRequestView`/`PasswordResetConfirmView` aren't implemented until Task 2. Resolved by adding minimal `501 Not Implemented` placeholder views in Task 1 (enough for `urls.py` to import and for Task 1's own tests, which don't touch these routes, to pass), then replacing them with full logic in Task 2's RED/GREEN cycle. No plan deviation — just a sequencing detail within the plan's own file list.

## Next Phase Readiness
- All Plan 02 tests green (20/20 in `accounts`); full project suite green (38/38).
- `/api/auth/*` is now a working public surface: register, login (role-claim JWT), refresh (rotate+blacklist), logout (revoke), password-reset request/confirm.
- Ready for Plan 03 (role-based permission matrix / write-endpoint gating, AUTH-02) to build `MinimumRole` permission classes on top of this auth surface per 02-RESEARCH.md's Pattern 2.
- No blockers.

## Self-Check: PASSED

All created/modified files confirmed present on disk; all 4 task commits (`0e1d227`, `284403e`, `e0ca110`, `eef6a79`) confirmed in git history.

---
*Phase: 02-auth-access-control*
*Completed: 2026-07-21*
