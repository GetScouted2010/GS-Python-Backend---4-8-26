---
phase: 02-auth-access-control
plan: 01
subsystem: auth
tags: [django, drf, simplejwt, jwt, postgres, custom-user-model, factory_boy, pytest]

# Dependency graph
requires:
  - phase: 01-data-foundation
    provides: Player/Club/Transfer/PlayerRoleScore/PlayerClubCompatibility models + import_all re-import pipeline (idempotent, used to repopulate the dev DB after the AUTH_USER_MODEL reset)
provides:
  - Custom accounts.User model (AbstractBaseUser + PermissionsMixin, UUID PK, email login, role scout/analyst/director/admin) as the project's AUTH_USER_MODEL
  - Deny-by-default DRF posture (JWTAuthentication only, IsAuthenticated only)
  - simplejwt 5.5.1 wired with rotation + blacklist app, console EMAIL_BACKEND
  - accounts.0001_initial as the origin migration for accounts_user (dev DB reset + full Phase 1 dataset re-import)
  - UserFactory + authenticated_client(role) pytest fixtures for all downstream auth tests
affects: [02-02, 02-03, 07-watchlist-shortlist, 08-squad-plans]

# Tech tracking
tech-stack:
  added: [djangorestframework-simplejwt>=5.5,<5.6, rest_framework, rest_framework_simplejwt.token_blacklist]
  patterns:
    - "Custom AbstractBaseUser + PermissionsMixin User model with UUID PK, email USERNAME_FIELD, role TextChoices"
    - "Deny-by-default DRF: DEFAULT_AUTHENTICATION_CLASSES=[JWTAuthentication], DEFAULT_PERMISSION_CLASSES=[IsAuthenticated]"
    - "factory_boy UserFactory + authenticated_client(role) fixture building a real RefreshToken.for_user() JWT for tests"

key-files:
  created:
    - get-scouted-be/accounts/models.py
    - get-scouted-be/accounts/admin.py
    - get-scouted-be/accounts/migrations/0001_initial.py
    - get-scouted-be/accounts/tests/conftest.py
    - get-scouted-be/accounts/tests/test_user_model.py
  modified:
    - get-scouted-be/config/settings/base.py
    - get-scouted-be/requirements/base.txt
    - get-scouted-be/pyproject.toml

key-decisions:
  - "Fully custom AbstractBaseUser + PermissionsMixin User (not AbstractUser subclass) to match the project's existing UUID-PK precedent and single display_name field, per 02-RESEARCH.md"
  - "One-time dev-DB reset (dropdb/createdb + fresh migrate) was required because Phase 1's migrate had already applied django.contrib.auth's own migrations, creating a stock auth_user table incompatible with AUTH_USER_MODEL being the origin of the user table"
  - "SIMPLE_JWT lifetimes bumped to 15min access / 7day refresh (discretionary, deliberate departure from simplejwt's 5min/1day defaults) for a demo SPA"
  - "factory_boy UserFactory sets skip_postgeneration_save=True to avoid a double-save deprecation warning from the password post_generation hook"

patterns-established:
  - "authenticated_client(role='scout', **kwargs) -> (APIClient, user) fixture is the shared entrypoint every Plan 02/03/07/08 permission test should reuse"

requirements-completed: [AUTH-01, AUTH-03]

# Metrics
duration: 25min
completed: 2026-07-21
---

# Phase 2 Plan 1: Identity Foundation Summary

**Custom accounts.User model (UUID PK, email login, 4-tier role field) replaces Django's stock auth_user as AUTH_USER_MODEL, with deny-by-default DRF/JWT settings and a freshly re-imported full Phase 1 dataset (41708 players, 1060 clubs, 47201 transfers, 230139 role scores, 8188712 compatibility rows).**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-21T11:20:00Z (approx)
- **Completed:** 2026-07-21T11:54:09Z
- **Tasks:** 3
- **Files modified:** 12 (9 created, 3 modified)

## Accomplishments
- Custom `accounts.User(AbstractBaseUser, PermissionsMixin)` is now `AUTH_USER_MODEL`, with UUID PK, email as `USERNAME_FIELD`, and a `role` field (scout/analyst/director/admin, default scout)
- DRF wired deny-by-default: `JWTAuthentication` is the only configured auth class, `IsAuthenticated` the only default permission
- `djangorestframework-simplejwt` 5.5.1 installed (patches CVE-2024-22513), with `ROTATE_REFRESH_TOKENS`/`BLACKLIST_AFTER_ROTATION` and the `token_blacklist` app migrated
- Performed the one-time `AUTH_USER_MODEL` dev-DB reset (drop/recreate Postgres `getscouted`, migrate fresh) and re-ran `import_all`, restoring the exact expected Phase 1 counts with a PASS reconciliation
- `UserFactory` + `authenticated_client(role)` fixtures exist for every downstream Plan 02/03 auth test, backed by a green smoke test suite (4 tests) and the full project suite (22 tests, all green)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install simplejwt, wire DRF/JWT/email settings, scaffold accounts app + User model** - `b8708f4` (feat)
2. **Task 2: Reset dev DB, create+apply accounts migration, re-import full dataset, register User in admin** - `0bbcf70` (feat)
3. **Task 3: Test infrastructure — UserFactory + authenticated_client(role) fixture + User model smoke test** - `8bd4ea3` (test)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `get-scouted-be/accounts/models.py` - `User(AbstractBaseUser, PermissionsMixin)` + `UserManager`
- `get-scouted-be/accounts/admin.py` - `UserAdmin` subclass registering `User`
- `get-scouted-be/accounts/apps.py` - `AccountsConfig`
- `get-scouted-be/accounts/migrations/0001_initial.py` - origin migration creating `accounts_user`
- `get-scouted-be/accounts/tests/conftest.py` - `UserFactory` + `authenticated_client(role)` fixture
- `get-scouted-be/accounts/tests/test_user_model.py` - smoke test (4 tests)
- `get-scouted-be/config/settings/base.py` - `AUTH_USER_MODEL`, `REST_FRAMEWORK`, `SIMPLE_JWT`, `EMAIL_BACKEND`, `INSTALLED_APPS` additions
- `get-scouted-be/requirements/base.txt` - added `djangorestframework-simplejwt>=5.5,<5.6`
- `get-scouted-be/pyproject.toml` - `testpaths` now includes `accounts`

## Decisions Made
- Fully custom `AbstractBaseUser` + `PermissionsMixin` model chosen over `AbstractUser` subclassing, matching the project's UUID-PK precedent (`clubs.Club`) and avoiding a redefined implicit `id` field
- Dev DB reset (dropdb/createdb) executed as a required one-time step, not an assumed no-op — verified `auth_user` does not exist post-reset and `accounts_user` does
- `role` embedded as a `TextChoices` CharField directly on `User` (not a separate Role model) — 4 fixed, non-user-configurable values
- `skip_postgeneration_save=True` added to `UserFactory.Meta` to eliminate a factory_boy deprecation warning from the explicit `set_password()` + `save()` post-generation hook

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed factory_boy double-save deprecation warning**
- **Found during:** Task 3 (test infrastructure)
- **Issue:** `UserFactory`'s `password` `post_generation` hook explicitly calls `obj.save()`, but factory_boy's default behavior also auto-saves after post-generation hooks, triggering a `DeprecationWarning` about redundant saves in the next major factory_boy release
- **Fix:** Added `skip_postgeneration_save = True` to `UserFactory.Meta`, the fix factory_boy's own warning message recommends
- **Files modified:** `get-scouted-be/accounts/tests/conftest.py`
- **Verification:** `pytest accounts/tests/test_user_model.py -x -q` re-run clean, warning gone
- **Committed in:** `8bd4ea3` (part of Task 3 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Minor test-infra cleanliness fix; no scope creep, no behavior change to production code.

## Issues Encountered
None beyond the above.

## User Setup Required
None - no external service configuration required. (Postgres dev DB reset was performed by the executor as a required plan step, not a manual user action.)

## Next Phase Readiness
- `accounts.User`, DRF/simplejwt settings, and the `UserFactory`/`authenticated_client(role)` fixtures are ready for Plan 02 (registration/login/password-reset endpoints) and Plan 03 (permissions/admin user management)
- Full test suite green (22 tests) and `manage.py check` clean before proceeding
- No blockers

---
*Phase: 02-auth-access-control*
*Completed: 2026-07-21*

## Self-Check: PASSED

All created files and task commit hashes verified present.
