---
phase: 02-auth-access-control
verified: 2026-07-21T00:00:00Z
status: passed
score: 4/4 success criteria verified (29/29 must-have truths across 3 plans verified)
---

# Phase 2: Auth & Access Control Verification Report

**Phase Goal:** A single Django system of record for identity and permissions replaces the 3 conflicting legacy auth models, gating every write endpoint by role.
**Verified:** 2026-07-21
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A user can register and log in and is assigned a role of scout, analyst, director, or admin | ✓ VERIFIED | `accounts/models.py` `User.Role` TextChoices (scout/analyst/director/admin, default scout); `RegisterSerializer` restricts self-service to scout/analyst/director (admin 400); `RoleTokenObtainPairSerializer` embeds `role` claim in JWT. `test_register_allowed_role_creates_active_account`, `test_register_admin_role_rejected`, `test_login_flow` all pass (live pytest run, 47/47 project-wide). |
| 2 | Attempting a write (watchlist, shortlist, squad plan, profile) without the correct role returns a permission-denied response, not a silent success | ✓ VERIFIED (scoped to endpoints that exist) | Watchlist/Shortlist/SquadPlan models don't exist yet (Phase 7/8, per 02-CONTEXT.md's explicit phase boundary) — verified no such app/model exists in the codebase. The reusable primitive is proven on the endpoints that DO exist: `/api/auth/me/` (unauthenticated PATCH/GET → 401, `test_write_requires_auth`), self-role-escalation structurally blocked (`read_only_fields` on `ProfileSerializer`, `test_profile_role_read_only`), and `/api/auth/admin/users/` (scout/analyst → 403 `test_role_gated_403`; director write → 403 `test_director_read_only_visibility`). |
| 3 | No write endpoint defaults to allow-by-default; every write path has an explicit, testable permission check | ✓ VERIFIED | `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = ["IsAuthenticated"]` (deny-by-default global), only 3 views explicitly relax to `AllowAny` (register/login/password-reset — all public-by-design, not writes to protected resources). `MinimumRole(role)` factory (`accounts/permissions.py`) is the single reusable rank-check primitive; `AdminUserViewSet.get_permissions()` applies it per-action. `test_single_auth_backend` asserts exactly one auth class configured. |
| 4 | Legacy Supabase-authenticated users are not carried forward — new registration under Django auth is the only path in | ✓ VERIFIED | `grep -rn "Supabase\|supabase" get-scouted-be/ --include="*.py"` returns zero hits — no legacy auth code exists in the Django project. Dev DB was fully reset (dropdb/createdb) and `accounts_user` (not stock `auth_user`) is the origin user table (`SELECT to_regclass('public.auth_user')` returns empty; `accounts_user` exists). Registration is the only account-creation path (no import/migration command for legacy users exists). |

**Score:** 4/4 success criteria verified

### Plan-Level Must-Haves (aggregated across 02-01/02/03)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Custom `accounts.User` model with role field, email login, UUID PK | ✓ VERIFIED | `accounts/models.py`: `AbstractBaseUser`+`PermissionsMixin`, `id = UUIDField`, `USERNAME_FIELD = "email"`, `Role` TextChoices |
| 2 | `AUTH_USER_MODEL` → `accounts.User`; dev DB reset so `accounts_user` is origin table | ✓ VERIFIED | `config/settings/base.py: AUTH_USER_MODEL = "accounts.User"`; psql confirms `accounts_user` exists, `auth_user` does not |
| 3 | Full Phase 1 dataset repopulated after reset | ✓ VERIFIED | Live psql counts: `players_player`=41708, `clubs_club`=1060, `transfers_transfer`=47201 (match plan targets exactly) |
| 4 | Only JWTAuthentication configured; IsAuthenticated global default (deny-by-default) | ✓ VERIFIED | `REST_FRAMEWORK` dict in `base.py`; `test_single_auth_backend` passes |
| 5 | UserFactory + `authenticated_client(role)` fixture | ✓ VERIFIED | `accounts/tests/conftest.py`; used across all test files |
| 6 | Register (role-restricted) + login (role-claim JWT) | ✓ VERIFIED | `test_registration.py`, `test_auth_flow.py::test_login_flow` pass |
| 7 | Wrong-credential login → generic 401 (no enumeration) | ✓ VERIFIED | `test_login_wrong_password_generic_401` passes |
| 8 | Refresh rotates + blacklists prior token; logout blacklists | ✓ VERIFIED | `test_refresh_rotation`, `test_logout_blacklist` pass |
| 9 | Password reset (console email, no enumeration, single-use token) | ✓ VERIFIED | `test_password_reset.py` (6 tests) all pass |
| 10 | `MinimumRole(role)` factory + `ROLE_RANK` single source of truth | ✓ VERIFIED | `accounts/permissions.py`; scout=analyst=1 < director=2 < admin=3 |
| 11 | `/api/auth/me/` self-service, role self-escalation blocked | ✓ VERIFIED | `ProfileSerializer.read_only_fields=["id","email","role"]`; `test_profile_role_read_only` |
| 12 | Unauthenticated write → 401/403 never 200 | ✓ VERIFIED | `test_write_requires_auth` |
| 13 | Scout/analyst → 403 on admin-rank endpoint | ✓ VERIFIED | `test_role_gated_403` |
| 14 | Director: read-only org-wide visibility, no write | ✓ VERIFIED | `test_director_read_only_visibility` (GET 200, PATCH 403, deactivate 403) |
| 15 | Admin: role change + soft deactivation, never hard delete | ✓ VERIFIED | `test_admin_can_change_role`, `test_admin_can_deactivate_soft`, `test_no_hard_delete_route` (DELETE → 405; no `DestroyModelMixin`) |
| 16 | Role/deactivation change takes effect on very next request, no re-login | ✓ VERIFIED | `test_role_change_takes_effect_immediately` — director demoted via ORM mid-session, same access token denied 403 on next request against a real endpoint |

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/accounts/models.py` | `User(AbstractBaseUser, PermissionsMixin)` + `UserManager` | ✓ VERIFIED | 48 lines; contains `class User`, `USERNAME_FIELD = "email"`, `Role` TextChoices |
| `get-scouted-be/config/settings/base.py` | `AUTH_USER_MODEL`, `REST_FRAMEWORK`, `SIMPLE_JWT`, `EMAIL_BACKEND`, `AUTH_PASSWORD_VALIDATORS` | ✓ VERIFIED | All settings present and correctly valued; `manage.py check` passes |
| `get-scouted-be/accounts/migrations/0001_initial.py` | Origin migration creating `accounts_user` | ✓ VERIFIED | `migrations.CreateModel` present; applied (`showmigrations` shows `[X] 0001_initial`) |
| `get-scouted-be/accounts/tests/conftest.py` | `UserFactory` + `authenticated_client(role)` | ✓ VERIFIED | Both present, used across 5 test files |
| `get-scouted-be/accounts/serializers.py` | `RegisterSerializer`, `RoleTokenObtainPairSerializer`, `ProfileSerializer`, `AdminUserSerializer` | ✓ VERIFIED | All 4 classes present with correct read_only_fields split |
| `get-scouted-be/accounts/views.py` | `RegisterView`, `LoginView`, `PasswordResetRequestView`, `PasswordResetConfirmView`, `ProfileView`, `AdminUserViewSet` | ✓ VERIFIED | All 6 present; `AdminUserViewSet` composes List/Retrieve/Update mixins only (no Create/Destroy) |
| `get-scouted-be/accounts/urls.py` | register/login/refresh/logout/password-reset/me/admin-users routes | ✓ VERIFIED | All routes present; `DefaultRouter` registers `admin/users` |
| `get-scouted-be/accounts/permissions.py` | `ROLE_RANK`, `MinimumRole(role)`, `IsSelfOrAdmin` | ✓ VERIFIED | All present, matches researched interface exactly |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `config/settings/base.py` | `accounts.User` | `AUTH_USER_MODEL` setting | ✓ WIRED | `AUTH_USER_MODEL = "accounts.User"` confirmed |
| `config/settings/base.py` | `JWTAuthentication` | `DEFAULT_AUTHENTICATION_CLASSES` | ✓ WIRED | Single-entry list, confirmed by `test_single_auth_backend` |
| `config/urls.py` | `accounts.urls` | `include("accounts.urls")` under `api/auth/` | ✓ WIRED | Confirmed in `config/urls.py` |
| `accounts/views.py` | `RoleTokenObtainPairSerializer` | `LoginView.serializer_class` | ✓ WIRED | Confirmed |
| `accounts/views.py` (`AdminUserViewSet`) | `accounts.permissions.MinimumRole` | `get_permissions()` | ✓ WIRED | `get_permissions()` returns `MinimumRole("admin")()` for write actions, `MinimumRole("director")()` otherwise; exercised end-to-end by `test_role_gated_403`, `test_director_read_only_visibility`, `test_admin_can_change_role` |
| `accounts/permissions.py` | `request.user.role` | DB-fresh read (never JWT claim) | ✓ WIRED | `has_permission` reads `request.user.role` directly (no `request.auth` token-claim access anywhere in `permissions.py`); proven live by `test_role_change_takes_effect_immediately` |
| `accounts/urls.py` | `accounts.views.AdminUserViewSet` | `DefaultRouter` under `admin/users/` | ✓ WIRED | Confirmed; live GET/PATCH/POST/DELETE all route correctly per passing tests |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|-------------|--------------|--------|----------|
| AUTH-01 | 02-01, 02-02 | User can register and log in with role-based access | ✓ SATISFIED | Custom User model + role field (02-01); register/login endpoints with role claim (02-02); all tests green |
| AUTH-02 | 02-03 | All write endpoints (watchlist, shortlist, squad plan, profile) gated by role-based permissions | ✓ SATISFIED (scoped) | `MinimumRole` primitive built and proven reusable on `/api/auth/me/` and `/api/auth/admin/users/` — the only write endpoints that exist in Phase 2's scope. Watchlist/Shortlist/SquadPlan don't exist until Phase 7/8 per the explicit phase boundary in 02-CONTEXT.md; REQUIREMENTS.md marking this "Complete" at the Phase-2 level is consistent with that boundary (the primitive, not the future endpoints, is this phase's deliverable) |
| AUTH-03 | 02-01, 02-02 | 3 legacy auth models reconciled into one Django system of record; Supabase users not migrated | ✓ SATISFIED | `AUTH_USER_MODEL` swap is the reconciliation; zero Supabase/legacy-JWT code in `get-scouted-be/`; DB reset confirms `accounts_user` (not `auth_user`) is origin; registration is the only account-creation path |

No orphaned requirements: REQUIREMENTS.md maps only AUTH-01/02/03 to Phase 2, and all three appear in plan frontmatter (`requirements:` fields of 02-01, 02-02, 02-03 collectively cover all three).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | `grep` for TODO/FIXME/XXX/HACK/PLACEHOLDER/"not implemented"/empty-return patterns across all `accounts/*.py` production files returned zero matches |

### Test Suite Verification (live run, not SUMMARY claims)

- `cd get-scouted-be && ./.venv/bin/python manage.py check` → `System check identified no issues (0 silenced)`
- `cd get-scouted-be && ./.venv/bin/pytest accounts -q` → **29 passed**
- `cd get-scouted-be && ./.venv/bin/pytest -q` (full project suite) → **47 passed**
- `showmigrations accounts` → `[X] 0001_initial` (applied)
- `SELECT to_regclass('public.accounts_user')` → `accounts_user` (exists)
- `SELECT to_regclass('public.auth_user')` → empty (does not exist)
- `players_player`=41708, `clubs_club`=1060, `transfers_transfer`=47201 (Phase 1 dataset counts match exactly)

### Human Verification Required

None. All Phase 2 behaviors (registration, login, token refresh/rotation, logout blacklist, password reset, role-gated permissions, immediate role/deactivation effect, single-auth-backend enforcement) have automated test coverage that was executed live during this verification, not merely inferred from SUMMARY.md.

### Gaps Summary

No gaps. All 4 ROADMAP success criteria verified, all 3 requirement IDs (AUTH-01, AUTH-02, AUTH-03) satisfied, all artifacts exist/substantive/wired, all key links wired, no anti-patterns found, full test suite (47/47) green, `manage.py check` clean.

One scoping note (not a gap): Success Criterion 2 references watchlist/shortlist/squad-plan write gating, but those models are intentionally out of scope until Phase 7/8 per 02-CONTEXT.md's explicit phase boundary. Phase 2's job — building and proving the reusable `MinimumRole` role-gating primitive via the write endpoints that DO exist (profile self-service, admin user management) — is fully and verifiably done. Phase 7/8 will need to actually import and apply `MinimumRole`/`IsSelfOrAdmin` to the new Watchlist/Shortlist/SquadPlan endpoints when those are built; that wiring is future work, not a Phase 2 gap.

---

*Verified: 2026-07-21*
*Verifier: Claude (gsd-verifier)*
</content>
