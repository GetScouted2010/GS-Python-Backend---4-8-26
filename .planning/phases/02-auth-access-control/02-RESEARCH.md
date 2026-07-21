# Phase 2: Auth & Access Control - Research

**Researched:** 2026-07-21
**Domain:** Django/DRF custom User model, JWT auth (djangorestframework-simplejwt), role-based permissions
**Confidence:** HIGH (custom User model pattern, simplejwt settings/blacklist/claims, DRF permission composition — all verified against official docs and this project's actual dev DB state); MEDIUM (exact token lifetime values — genuinely discretionary, no single "correct" answer); LOW (none — all findings below were verifiable)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Role Permission Matrix**
- **scout** and **analyst** are functionally identical for v1 — full contributors: browse/search Players & Clubs, view scores/reports, manage their own Watchlist/Shortlists/Squad Plans, request AI reports. The distinction between the two is informational/job-title only; no permission check should differentiate them. (Explicitly deferred: splitting them apart later if a real need emerges.)
- **director** = scout/analyst permissions **+ org-wide visibility**: can view (read-only) all users' watchlists/shortlists/squad plans/recent activity across the org, not just their own.
- **admin** = director **+ user management**: can view/manage all user accounts, change any user's role, deactivate accounts. Nothing is off-limits to admin.
- This is an **additive hierarchy** (each higher role's permission set is a superset of the one below), not 4 disjoint permission sets.
- **Core scouting data (Player, Club, Transfer, PlayerRoleScore, PlayerClubCompatibility) is read-only for every non-admin role.** These are populated only by the Phase 1 import pipeline (or admin); no role can edit/correct this data via the API in v1.
- Director/admin's "org-wide visibility" is **view-only oversight** — editing or deleting another user's watchlist/shortlist/squad plan is restricted to its owner, even for director/admin. No cross-user write access at all in v1.

**Registration & Provisioning**
- **Open self-service signup** — a public register endpoint accepting email, password, display name, and a role selection. Chosen deliberately over invite-only/admin-provisioned given the 4-day soft deadline; acceptable because the product is still prototype/demo stage with no live user base.
- **Role choices at signup are limited to scout, analyst, director — admin is excluded from self-service.** The first admin account is created via a Django management command / seed script (createsuperuser-style, one-time setup). Further admins are promoted only by an existing admin.
- **No email verification for v1** — an account is active immediately on registration. Deferred alongside real email-provider selection.
- **Email is the unique login identifier** — no separate username field. Standard swappable-user-model pattern with email as `USERNAME_FIELD`.
- **Role changes after signup are admin-only.** A user cannot self-change their own role once registered (prevents self-escalation), even between the functionally-identical scout/analyst roles.
- **Password-reset (forgot password) IS in scope for v1**, via a basic email-based reset-link flow — but ships using **Django's console/dev email backend** for now (reset link logged/returned, not actually emailed via SMTP/a provider). No concrete email provider has been chosen.

**Session & Token Policy**
- **djangorestframework-simplejwt** is the auth mechanism — short-lived access token + longer-lived refresh token. Exact lifetime values are Claude's discretion (simplejwt's defaults are a reasonable starting point).
- **Multi-device/multi-session login is unrestricted** — no single-active-session enforcement, no session-tracking table needed.
- **Logout performs real server-side revocation**: the refresh token is submitted to be blacklisted (simplejwt's token-blacklist app), not just discarded client-side.
- **Refresh tokens rotate** (`ROTATE_REFRESH_TOKENS=True`): each refresh issues a new refresh token and blacklists the one just used.
- **Role changes and account deactivation are accepted to take effect starting next login/token refresh, not necessarily instantly mid-session** — a deliberate v1 simplicity choice. (Note for planner/researcher: standard simplejwt/DRF authentication already re-fetches the User row per request in the non-stateless configuration, so immediate `is_active` enforcement may fall out "for free" — get this technically right rather than over-building a separate revocation mechanism.)

**Auth Failure & Security Posture**
- **Permission-denied returns 403 Forbidden** with a standard DRF detail message (not 404).
- **No login lockout or rate-limiting for v1** — repeated failed logins simply return 401 each time.
- **Password requirements use Django's default `AUTH_PASSWORD_VALIDATORS`** (min length 8, not too similar to user attributes, not entirely numeric, not a common password) — no custom rules.
- **Login failure message is generic** ("Invalid email or password") regardless of whether the email or the password was wrong.
- **Admin can deactivate a user account (soft — `is_active=False`); accounts are never hard-deleted.**

### Claude's Discretion
- Exact simplejwt token lifetime values (access/refresh minute/day counts)
- Exact DRF permission-class architecture (custom `BasePermission` classes vs. per-view `permission_classes`) implementing the additive role hierarchy
- Whether role is a `CharField` + choices directly on a custom User model, or a separate Role/Profile model
- Whether the custom User model extends `AbstractUser` (with a manager override for email-as-username) or `AbstractBaseUser` fully custom
- Exact password-reset token/endpoint mechanics (Django's built-in `PasswordResetTokenGenerator` vs. a custom equivalent)
- Whether `is_active`/role checks are enforced with full immediacy per-request as a natural side effect of the chosen simplejwt authentication configuration — get the real behavior right, don't just take the "next login" framing as license to under-build

### Deferred Ideas (OUT OF SCOPE)
- Splitting scout and analyst into functionally distinct roles — currently identical; revisit if a real need emerges
- Email verification at signup — v2, alongside real email-provider selection
- Login rate-limiting / lockout on repeated failures — v2 security hardening
- Real-time (instant, mid-session) permission/deactivation revocation beyond whatever simplejwt's default per-request user fetch already provides — v2 hardening if ever needed
- Cross-user editing/deletion by director/admin (currently view-only oversight) — not planned, noted in case product needs change
- Concrete email provider selection for password-reset delivery (SendGrid, SES, etc.) — deferred like the LLM provider decision
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| AUTH-01 | User can register and log in with role-based access (scout, analyst, director, admin) | Custom User model pattern (AbstractBaseUser + PermissionsMixin, UUID PK, email USERNAME_FIELD, `role` CharField+choices); registration serializer/view pattern; `TokenObtainPairView` + custom `get_token()` claim embedding — see Architecture Patterns, Code Examples |
| AUTH-02 | All write endpoints (watchlist, shortlist, squad plan, profile) are gated by role-based permissions | DRF global `DEFAULT_PERMISSION_CLASSES` default-deny pitfall; composable rank-based `BasePermission` factory for the additive hierarchy; concrete Phase-2-owned write endpoints (profile self-edit, admin user management) to prove the pattern before Phase 7/8 reuse it — see Don't Hand-Roll, Common Pitfalls, Architecture Patterns |
| AUTH-03 | The 3 conflicting legacy auth models are reconciled into one Django system of record; existing Supabase users are not migrated | Greenfield custom User model is the *only* auth path (no legacy JWT/Supabase acceptance code written at all); critical `AUTH_USER_MODEL` timing pitfall verified against this project's actual dev DB (see Common Pitfalls #1) — this is the concrete mechanism that "reconciles" the three legacy models by replacing all of them with one |
</phase_requirements>

## Summary

This phase is standard, well-trodden Django/DRF territory — a custom User model, `djangorestframework-simplejwt` for tokens, and DRF `BasePermission` classes for role gating. Nothing here requires inventing new patterns; the risk is entirely in *sequencing* and *not under-building the "free" parts*. Two findings dominate the plan:

1. **The `AUTH_USER_MODEL` swap has a live landmine in this specific codebase.** `python manage.py showmigrations` against the actual dev Postgres DB confirms `auth.0001_initial` through `auth.0012_...` are **already applied** (Phase 1 setup ran `migrate` before this phase existed), which created the stock `auth_user` table. It has 0 rows and `django_admin_log` has 0 rows, so no real data is at risk — but Django's swappable-model machinery requires the custom user app's own migration to be the *origin* of the user table, not a later replacement of one that's already migrated. The safe, standard fix (verified against Django's own docs) is a **full dev-DB reset**: drop and recreate the local Postgres database, set `AUTH_USER_MODEL` before ever running `migrate` again, run `migrate` fresh (so `auth_user` per se is never created), then re-run Phase 1's `import_all` command to repopulate Player/Club/Transfer/etc. — safe because those import commands are confirmed idempotent (STATE.md). This must be an explicit early task in the plan, not an assumed no-op.

2. **`is_active`/role freshness "for free" is real, not aspirational — but only if you use the right authentication class and don't trust the JWT claim.** simplejwt's default `JWTAuthentication` (not `JWTStatelessUserAuthentication`) calls `get_user()` on every single request, which does a fresh DB `SELECT` for the user row and checks `is_active` via `CHECK_USER_IS_ACTIVE` (default `True`). Combined with permission classes that read `request.user.role` (the freshly-fetched DB object) rather than the JWT payload's `role` claim, **both deactivation and role changes take effect on the very next request**, not just "next login" — exceeding the CONTEXT.md's stated minimum bar for free, provided the implementation doesn't accidentally use the stateless variant or read the claim instead of the DB field.

Beyond these two, the rest is standard library usage: `AbstractBaseUser` + `PermissionsMixin` for the User model, `rest_framework_simplejwt.views.TokenBlacklistView` (built-in, no custom logout view needed) for revocation, Django's own `PasswordResetTokenGenerator` for reset tokens (self-invalidating once the password changes, since the hash incorporates the current password hash), and a small rank-based permission factory to avoid a permission-class explosion that Phase 7/8 will otherwise have to repeat.

**Primary recommendation:** Build a fully custom `accounts.User(AbstractBaseUser, PermissionsMixin)` with UUID PK, `email` as `USERNAME_FIELD`, and a `role` `TextChoices` field; wire `djangorestframework-simplejwt` with `ROTATE_REFRESH_TOKENS=True` + `BLACKLIST_AFTER_ROTATION=True` + the blacklist app; embed `role` in the token via a custom `get_token()` override purely for client convenience while every permission check re-reads `request.user.role` from the DB; implement the additive hierarchy as one parameterized `BasePermission` factory (`MinimumRole(role)`), not four hand-written classes — and do the dev-DB reset for the `AUTH_USER_MODEL` swap as the very first task.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| djangorestframework-simplejwt | 5.5.1 (verified current on PyPI, 2026-07-21) | JWT issuance, refresh rotation, blacklist, custom claims | Already locked by `.planning/research/STACK.md`; verified still current and, notably, **5.5.1 is the exact version that patches CVE-2024-22513** (improper privilege management allowing a disabled user's already-issued token to keep working) — versions ≤5.3.1 are vulnerable. This project's dev venv currently has no simplejwt installed at all, so pin `>=5.5.1` explicitly, don't let anything resolve an older cached wheel. |
| Django | 5.2.16 (installed in `get-scouted-be/.venv`) | Web framework / ORM, `django.contrib.auth` primitives | Already installed; this phase is the first to actually configure `django.contrib.auth` beyond defaults. |
| Django REST Framework | 3.17.1 (installed in `get-scouted-be/.venv`) | API layer, `BasePermission`, serializers/views | Installed as a dependency already (per Phase 1); **not yet added to `INSTALLED_APPS`** and has no `REST_FRAMEWORK` settings block — this phase adds both. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `rest_framework_simplejwt.token_blacklist` | bundled with simplejwt 5.5.1 | Server-side refresh-token revocation on logout + rotation blacklisting | Add to `INSTALLED_APPS`, run `migrate` — creates `OutstandingToken`/`BlacklistedToken` tables. Required by the locked "real server-side revocation" decision. |
| factory_boy | 3.3.3 (installed) | Test data factories | `UserFactory` for auth tests, parametrized by role. |
| pytest-django | 4.12.0 (installed) | Test runner integration | Already the project's test stack (per `core/tests/conftest.py` precedent). |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `AbstractBaseUser` + `PermissionsMixin` (fully custom User) | `AbstractUser` with `username = None` and an `id` field override to UUID | `AbstractUser` gives free `first_name`/`last_name`/`is_staff`/`date_joined` and slightly less boilerplate, and *is* a valid, commonly-recommended path for "just remove the username field" cases. Not chosen here because this project wants a single `display_name` field (not first/last name split), a UUID PK from the start (redefining the implicit `id` field on an `AbstractUser` subclass works but is a second point of surprise), and a fully custom manager is needed regardless for email-based `create_user`/`create_superuser` — so there's no boilerplate actually saved by starting from `AbstractUser`. Official Django docs' own "customizing authentication" walkthrough for this exact shape (email login, custom fields) uses `AbstractBaseUser` + `PermissionsMixin`, not `AbstractUser`. |
| Custom `MinimumRole(role)` permission-class factory | Four separate hardcoded `IsScout`/`IsDirector`/`IsAdmin` classes | Four classes is more obvious to read at a glance but doesn't scale — Phase 7/8 will need the same "director-or-above" check on Watchlist/Shortlist/SquadPlan viewsets, and CONTEXT.md explicitly flags avoiding "a permission-class explosion across future CRUD phases." A single rank-comparison factory composes with DRF's `&`/`|` operators cleanly and is the one place the role hierarchy is encoded. |
| Django's `PasswordResetTokenGenerator` (built-in) | A custom random-token + DB table (e.g., a `PasswordResetToken` model with `expires_at`) | The built-in generator needs no new model/table at all — its token is a deterministic hash of `user.pk + timestamp + user.password + is_active` (roughly; exact hash inputs are Django-version-specific), so it is naturally single-use (changing the password invalidates it) and time-limited (`PASSWORD_RESET_TIMEOUT`, default 259200s/3 days) with zero extra schema. A custom table would only be justified if you needed to *list/revoke* outstanding reset requests, which isn't a requirement here. |

**Installation:**
```bash
cd get-scouted-be
./.venv/bin/pip install "djangorestframework-simplejwt>=5.5.1,<5.6"
```
Add to `requirements/base.txt`:
```
djangorestframework-simplejwt>=5.5,<5.6
```

**Version verification:** Confirmed directly against PyPI (2026-07-21):
```
$ pip index versions djangorestframework-simplejwt
djangorestframework-simplejwt (5.5.1)
Available versions: 5.5.1, 5.5.0, 5.4.0, 5.3.1, ...
```
And against the actual project venv:
```
$ get-scouted-be/.venv/bin/pip list | grep -iE "django|jwt"
Django              5.2.16
djangorestframework 3.17.1
```
(simplejwt itself is not yet installed in this venv — this phase installs it for the first time.)

## Architecture Patterns

### Recommended Project Structure
```
get-scouted-be/
├── accounts/                        # new app — this phase's home
│   ├── models.py                    # User(AbstractBaseUser, PermissionsMixin), UserManager
│   ├── managers.py                  # (or keep manager in models.py — small enough either way)
│   ├── serializers.py               # RegisterSerializer, RoleTokenObtainPairSerializer,
│   │                                 #   ProfileSerializer, PasswordResetRequestSerializer,
│   │                                 #   PasswordResetConfirmSerializer, AdminUserSerializer
│   ├── views.py                     # RegisterView, ProfileView, PasswordResetRequestView,
│   │                                 #   PasswordResetConfirmView, AdminUserViewSet
│   ├── permissions.py                # MinimumRole() factory, IsSelfOrAdmin, role rank table
│   ├── urls.py
│   ├── admin.py                     # register User with contrib.admin (UserAdmin subclass)
│   ├── management/commands/         # (optional) seed_admin.py if createsuperuser override isn't enough
│   ├── migrations/0001_initial.py   # MUST be created only after AUTH_USER_MODEL is set + dev DB reset
│   └── tests/
│       ├── conftest.py              # UserFactory, authenticated_client(role) fixture
│       ├── test_registration.py     # AUTH-01
│       ├── test_auth_flow.py        # login/refresh/logout/blacklist — AUTH-01, AUTH-03
│       ├── test_permissions.py      # role-gated write endpoints return 403 — AUTH-02
│       └── test_password_reset.py
├── config/settings/base.py          # INSTALLED_APPS, AUTH_USER_MODEL, REST_FRAMEWORK, SIMPLE_JWT, EMAIL_BACKEND
```

### Pattern 1: Custom User Model (AbstractBaseUser + PermissionsMixin, UUID PK, email login)
**What:** A fully custom User model matching this project's existing UUID-PK precedent, with `role` as a `TextChoices` field directly on the model (not a separate Role model — simplest for 4 fixed, non-user-configurable values).
**When to use:** Exactly this phase, exactly once — `AUTH_USER_MODEL` cannot be changed later without pain.
**Example:**
```python
# Source: pattern verified against docs.djangoproject.com/en/5.2/topics/auth/customizing/
# (official "customizing authentication" walkthrough), adapted for UUID PK + role field
import uuid
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        extra_fields.setdefault("role", User.Role.SCOUT)
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        # createsuperuser-style first-admin path: force admin role + staff/superuser flags.
        extra_fields["role"] = User.Role.ADMIN
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SCOUT = "scout", "Scout"
        ANALYST = "analyst", "Analyst"
        DIRECTOR = "director", "Director"
        ADMIN = "admin", "Admin"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SCOUT)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)  # Django admin access, independent of `role`
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]  # prompted by createsuperuser; role defaults via manager

    def __str__(self):
        return self.email
```
```python
# config/settings/base.py addition
AUTH_USER_MODEL = "accounts.User"
```

### Pattern 2: Additive Role Hierarchy via a Rank Factory (not 4 hardcoded classes)
**What:** One `BasePermission` subclass parameterized by the minimum required role, built from an explicit rank table — matches CONTEXT.md's "additive hierarchy" model and is reusable by Phase 7/8's Watchlist/Shortlist/SquadPlan viewsets without adding new permission classes.
**When to use:** Any write endpoint; also usable for read endpoints that need director+ (org-wide visibility) gating.
**Example:**
```python
# accounts/permissions.py
# Source: pattern verified against DRF official docs (django-rest-framework.org/api-guide/permissions/)
# on custom BasePermission + has_permission/has_object_permission + &/| composition
from rest_framework.permissions import BasePermission

ROLE_RANK = {
    "scout": 1,
    "analyst": 1,   # scout/analyst are functionally identical rank — locked decision
    "director": 2,
    "admin": 3,
}


def MinimumRole(role: str):
    """Factory returning a BasePermission class requiring at least `role`'s rank.

    Usage: permission_classes = [IsAuthenticated, MinimumRole("director")]
    """
    required_rank = ROLE_RANK[role]

    class _MinimumRole(BasePermission):
        message = "You do not have the required role for this action."

        def has_permission(self, request, view):
            user = request.user
            if not user or not user.is_authenticated:
                return False
            # Always re-read from the DB-fetched request.user, never a JWT claim.
            return ROLE_RANK.get(user.role, 0) >= required_rank

    return _MinimumRole


class IsSelfOrAdmin(BasePermission):
    """Object-level: a user may act on their own account; admin may act on any."""

    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.role == "admin"
```
This single factory is what Phase 7/8 reuse for `MinimumRole("director")` (org-wide read visibility) on Watchlist/Shortlist/SquadPlan list endpoints, composed with an owner-only object permission for writes — the exact "view-only oversight, no cross-user write" shape CONTEXT.md locks in.

### Pattern 3: Custom JWT Claims Without Trusting Them Server-Side
**What:** Embed `role` in the access token for client UX (so the SPA can render role-gated UI without an extra `/me` round trip), while every actual permission check re-reads the DB.
**Example:**
```python
# accounts/serializers.py
# Source: django-rest-framework-simplejwt.readthedocs.io/en/latest/customizing_token_claims.html
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token
```
```python
# config/settings/base.py
SIMPLE_JWT = {
    "TOKEN_OBTAIN_SERIALIZER": "accounts.serializers.RoleTokenObtainPairSerializer",
    # ... (see Code Examples for the full dict)
}
```
```python
# accounts/views.py
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import RoleTokenObtainPairSerializer


class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer
```
Login failure message must stay generic per the locked decision — simplejwt's default `TokenObtainPairSerializer` already raises a generic `AuthenticationFailed("No active account found with the given credentials")` on bad email/password, so this requirement is satisfied by *not* overriding the error path, not by adding custom logic.

### Anti-Patterns to Avoid
- **Trusting the JWT `role` claim in permission checks:** the claim is for client convenience only; if an admin demotes a user mid-session, a still-valid access token would carry the stale claim until it expires. Always check `request.user.role` (freshly fetched from DB per request), never `request.auth["role"]`.
- **Using `JWTStatelessUserAuthentication`:** this authentication class explicitly avoids a DB lookup (that's its whole point) which would silently break the "is_active/role freshness for free" property this phase relies on. Use the default `JWTAuthentication`.
- **Writing a bespoke logout view when `TokenBlacklistView` already exists:** `rest_framework_simplejwt.views.TokenBlacklistView` accepts `{"refresh": "<token>"}` and blacklists it out of the box — no custom view needed unless you want a different response shape.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| JWT issuance/refresh/rotation/blacklist | A custom PyJWT-based token service | `djangorestframework-simplejwt` (`TokenObtainPairView`, `TokenRefreshView`, `TokenBlacklistView`) | Already the locked stack choice; handles rotation, blacklist storage, and the CVE-2024-22513-class bugs (patched in 5.5.1) that a hand-rolled version would have to independently discover. |
| Password hashing/validation | Custom hashing or a bespoke strength checker | `user.set_password()` / `check_password()` + `django.contrib.auth.password_validation.validate_password()` against `AUTH_PASSWORD_VALIDATORS` | Django's default validators are exactly what the locked decision specifies ("min length 8, not too similar, not entirely numeric, not common") — this is a settings list, not code to write. |
| Password-reset token generation/expiry | A `PasswordResetToken` model with `expires_at`, manual random-token generation | `django.contrib.auth.tokens.PasswordResetTokenGenerator` (`default_token_generator`) + `urlsafe_base64_encode`/`decode` for the uid | Self-invalidating (hash includes current password hash) and time-limited (`PASSWORD_RESET_TIMEOUT`) with zero new schema. |
| Role-hierarchy permission checks | 4 separate hardcoded permission classes duplicated per app in Phase 7/8 | One rank-based `MinimumRole(role)` factory in `accounts/permissions.py`, imported everywhere | CONTEXT.md explicitly flags avoiding a permission-class explosion; a single source of truth for `ROLE_RANK` also means promoting/adding a role later is a one-line change. |
| First-admin bootstrapping | A bespoke interactive seed script | Django's built-in `createsuperuser` management command, made to work via a `create_superuser()` manager override that forces `role="admin"` | `createsuperuser` already exists, is interactive, and integrates with `USERNAME_FIELD`/`REQUIRED_FIELDS` automatically — overriding the manager method is the only code needed; CONTEXT.md's "createsuperuser-style" wording literally maps to this. |

**Key insight:** Every piece of this phase already has a first-party Django/DRF/simplejwt answer. The only genuinely custom code is the `role` field, the `MinimumRole` rank factory, and the registration/profile/admin-user-management serializers — everything else (hashing, token lifecycle, reset-token security, blacklisting) is configuration, not implementation.

## Common Pitfalls

### Pitfall 1: `AUTH_USER_MODEL` swap conflicts with already-applied `auth` migrations in this exact dev DB
**What goes wrong:** Setting `AUTH_USER_MODEL = "accounts.User"` and running `makemigrations`/`migrate` against the current dev database will hit Django's swappable-model migration graph expecting the custom app to be the *origin* of the user table — but `auth.0001_initial` (which creates the stock `auth_user` table) has already been applied here.
**Why it happens:** Phase 1's setup ran `python manage.py migrate` (to set up `clubs`/`players`/`transfers`/`core`) before this phase existed, which also silently ran all of `django.contrib.auth`'s own migrations (`0001_initial` through `0012_alter_user_first_name_max_length`), creating the default `auth_user` table.
**Verified directly against this project (2026-07-21):**
```
$ get-scouted-be/.venv/bin/python manage.py showmigrations
auth
 [X] 0001_initial
 ...
 [X] 0012_alter_user_first_name_max_length
```
```sql
SELECT count(*) FROM auth_user;        -- 0
SELECT count(*) FROM django_admin_log; -- 0
```
Zero rows in both — no real data at risk, but the migration *state* is already committed.
**How to avoid:** Treat this as a required Wave 0 / first task, not an incidental step:
1. Drop and recreate the local dev Postgres database (or drop just the `getscouted` schema/DB the project's `.env` `DATABASE_URL` points at).
2. Add the `accounts` app to `INSTALLED_APPS`, set `AUTH_USER_MODEL = "accounts.User"` in `config/settings/base.py`.
3. Run `makemigrations accounts` then `migrate` fresh — `auth_user` as a concrete table is never created; `accounts_user` (or whatever the custom model's table name is) is used everywhere from the very first migration.
4. Re-run Phase 1's `import_all` (or equivalent per-model import commands) to repopulate Player/Club/Transfer/PlayerRoleScore/PlayerClubCompatibility — confirmed safe/idempotent per STATE.md ("idempotent upsert... re-run left row count unchanged").
**Warning signs:** `makemigrations` prompting about a conflicting `auth.User` reference, or `migrate` erroring with something like "Cannot alter... foreign key" / inconsistent migration history on `contenttypes`/`admin`/`auth`.

### Pitfall 2: DRF's global default permission is `AllowAny` — the "no allow-by-default" requirement is a settings change, not automatic
**What goes wrong:** Adding `rest_framework` to `INSTALLED_APPS` without an explicit `REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]` means every view defaults to `AllowAny` unless each view manually sets `permission_classes`. AUTH-02/AUTH-03's "no write endpoint defaults to allow-by-default" requirement is violated by DRF's own out-of-the-box default.
**Why it happens:** DRF ships permissive defaults for zero-config quick starts; production projects are expected to override this explicitly.
**How to avoid:** Set a deny-by-default global posture, then explicitly relax it per public view:
```python
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}
```
Then `RegisterView`, `LoginView` (`TokenObtainPairView` subclass), `TokenRefreshView`, and the two password-reset views each explicitly set `permission_classes = [AllowAny]`.
**Warning signs:** A permission test expecting 403/401 instead gets 200 for an unauthenticated or wrong-role request.

### Pitfall 3: simplejwt ≤5.3.1's CVE-2024-22513 (deactivated users' tokens still working)
**What goes wrong:** Versions up to and including 5.3.1 have a documented "Improper Privilege Management" issue (CWE-269) where, under certain manual-token-creation misuse patterns, a deactivated user's previously issued token could keep working.
**Why it happens:** `AccessToken.for_user()`/manual token creation doesn't itself check `is_active`; the protection relies on always authenticating through `JWTAuthentication`, which does check it (`CHECK_USER_IS_ACTIVE`, default `True`).
**How to avoid:** Pin `djangorestframework-simplejwt>=5.5.1` (the patched version, and also the version STACK.md already targets) and never construct tokens manually outside of `TokenObtainPairSerializer.get_token()` / the standard views.
**Warning signs:** N/A if pinned correctly — this is a "pin the version and use the standard views" fix, not a code-level workaround.

### Pitfall 4: Confusing "role changes take effect next login" (the locked minimum) with "role changes require re-login" (over-building)
**What goes wrong:** A team might build a session/token-versioning table to force re-authentication on role change, reading the CONTEXT.md language too literally as "must not be instant."
**Why it happens:** The locked decision's exact wording ("next login/token refresh, not necessarily instantly") is a *ceiling* on required engineering effort, not a floor requiring artificial delay.
**How to avoid:** Use default `JWTAuthentication` (DB lookup per request, confirmed above) and read `request.user.role` fresh in every permission check — this makes role changes and deactivation effective on the *very next request*, which is strictly better than the stated minimum and requires zero extra code. Do not build a token-versioning or session-invalidation table; CONTEXT.md's own note flags this exact over-build risk.
**Warning signs:** Any new model/table whose sole purpose is "track when to force re-auth" — that's a sign the free behavior above was missed.

### Pitfall 5: `django-cors-headers` not yet installed but the SPA will need it soon
**What goes wrong:** Not directly an AUTH-01/02/03 requirement, but this phase is the first to make DRF endpoints actually reachable — a frontend integration attempt will immediately hit CORS failures if `django-cors-headers` (already recommended in STACK.md) isn't wired up.
**How to avoid:** Out of strict scope for this phase's requirements, but worth a one-line settings note/flag for whichever phase first needs the SPA to call these endpoints live. Not treated as a Phase 2 task here since no CRUD/AUTH requirement mandates it yet.

## Code Examples

### Full `SIMPLE_JWT` settings block
```python
# config/settings/base.py
# Source: django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html (verified 2026-07-21)
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "TOKEN_OBTAIN_SERIALIZER": "accounts.serializers.RoleTokenObtainPairSerializer",
}
```
Lifetime rationale (Claude's discretion per CONTEXT.md): simplejwt's own defaults are 5 min access / 1 day refresh. 15 min / 7 days is a common, still-conservative bump that avoids painfully frequent silent-refresh churn for a demo SPA without meaningfully weakening the security posture given there's no rate-limiting/lockout either way in v1. `BLACKLIST_AFTER_ROTATION=True` is required for `ROTATE_REFRESH_TOKENS` to actually blacklist the *previous* refresh token on each rotation (otherwise rotation alone just issues new tokens without revoking old ones).

### `INSTALLED_APPS` additions
```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "clubs",
    "players",
    "transfers",
    "core",
    "accounts",
]

AUTH_USER_MODEL = "accounts.User"
```

### urls.py wiring
```python
# accounts/urls.py
# Source: pattern verified via simplejwt's own "getting started" + blacklist_app docs
from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView, TokenBlacklistView
from .views import RegisterView, LoginView, ProfileView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),               # TokenObtainPairView subclass
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="logout"),     # built-in, no custom view needed
    path("me/", ProfileView.as_view(), name="profile"),
]
```

### Password reset (DRF-friendly, built-in token generator)
```python
# accounts/views.py
# Source: pattern combining django.contrib.auth.tokens.PasswordResetTokenGenerator
# (docs.djangoproject.com/en/5.2/topics/auth/default/) with a DRF APIView instead of Django's HTML forms
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from accounts.models import User


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            # Console backend for now — logs to stdout instead of sending real email.
            send_mail(
                subject="Password reset",
                message=f"Reset link: /reset-password/confirm/{uid}/{token}/",
                from_email=None,
                recipient_list=[user.email],
            )
        # Always 200 regardless of whether the email matched — no user enumeration.
        return Response({"detail": "If that email exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError

        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({"detail": "Invalid reset link."}, status=400)

        if not default_token_generator.check_token(user, token):
            return Response({"detail": "Invalid or expired reset link."}, status=400)

        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return Response({"detail": e.messages}, status=400)

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password has been reset."})
```
```python
# config/settings/base.py — console backend for now (locked decision)
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)
```

### Registration serializer (role restricted, admin excluded)
```python
# accounts/serializers.py
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from accounts.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    role = serializers.ChoiceField(
        choices=[
            (User.Role.SCOUT, User.Role.SCOUT.label),
            (User.Role.ANALYST, User.Role.ANALYST.label),
            (User.Role.DIRECTOR, User.Role.DIRECTOR.label),
        ]  # admin deliberately excluded from self-service choices
    )

    class Meta:
        model = User
        fields = ["email", "password", "display_name", "role"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|--------------------|---------------|--------|
| Django Sessions / cookie auth for a decoupled SPA | Token-based auth (JWT via simplejwt) | Standard for any Django-backend + separately-hosted-SPA architecture (this project's shape since Phase 1) | Already the locked choice; no session/cookie CSRF machinery needed for the API surface. |
| `djangorestframework-simplejwt` <5.5.1 (CVE-2024-22513) | 5.5.1+ | Patched 2024, still current latest as of 2026-07-21 | Pin `>=5.5.1` — see Pitfall 3. |

**Deprecated/outdated:**
- Manually managing `django.contrib.auth.models.User` (the stock model) for any project needing a `role` field or non-username login — Django's own docs have recommended custom user models from project start for years; this project is simply doing it slightly late (Phase 2 instead of Phase 0), which is exactly why the DB-reset pitfall above exists.

## Open Questions

1. **Exact `display_name` validation rules (min/max length, allowed characters)?**
   - What we know: CONTEXT.md specifies `display_name` as a registration field, no further constraints given.
   - What's unclear: whether any length/format validation beyond "required, non-blank" is wanted.
   - Recommendation: Default to `CharField(max_length=150)` (matches Django's own `first_name` convention) with only "non-blank" validation; this is a planning-time detail, not a research blocker.

2. **Should `PASSWORD_RESET_TIMEOUT` be shortened from Django's 3-day default?**
   - What we know: CONTEXT.md doesn't specify a reset-link expiry window.
   - What's unclear: whether 3 days is acceptable for a demo/prototype-stage product with no rate-limiting elsewhere.
   - Recommendation: Leave the 3-day Django default; consistent with the "no login lockout / minimal hardening for v1" posture elsewhere in this phase's locked decisions.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-django 4.12.0 (already installed in `get-scouted-be/.venv`) |
| Config file | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`, `DJANGO_SETTINGS_MODULE = "config.settings.local"`) |
| Quick run command | `cd get-scouted-be && ./.venv/bin/pytest accounts -x -q` |
| Full suite command | `cd get-scouted-be && ./.venv/bin/pytest` |

Note: `pyproject.toml`'s `testpaths` currently lists `["clubs", "players", "transfers", "core"]` — this phase must add `"accounts"` to that list, or the full-suite command will silently skip the new app's tests.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| AUTH-01 | Register creates a user with the selected role (scout/analyst/director); admin role rejected from self-service | unit | `pytest accounts/tests/test_registration.py -x -q` | ❌ Wave 0 |
| AUTH-01 | Login returns access+refresh tokens; access token carries `role` claim; wrong credentials return generic 401 message | unit | `pytest accounts/tests/test_auth_flow.py::test_login_flow -x -q` | ❌ Wave 0 |
| AUTH-01 | Refresh rotates the refresh token and blacklists the prior one | unit | `pytest accounts/tests/test_auth_flow.py::test_refresh_rotation -x -q` | ❌ Wave 0 |
| AUTH-02 | Unauthenticated request to a write endpoint returns 401/403, not 200 | unit | `pytest accounts/tests/test_permissions.py::test_write_requires_auth -x -q` | ❌ Wave 0 |
| AUTH-02 | Scout/analyst attempting an admin-only action (e.g. changing another user's role) returns 403 | unit | `pytest accounts/tests/test_permissions.py::test_role_gated_403 -x -q` | ❌ Wave 0 |
| AUTH-02 | Role/deactivation change takes effect on the very next request (no re-login required) | integration | `pytest accounts/tests/test_permissions.py::test_role_change_takes_effect_immediately -x -q` | ❌ Wave 0 |
| AUTH-03 | Logout blacklists the refresh token; subsequent refresh attempt with it fails | unit | `pytest accounts/tests/test_auth_flow.py::test_logout_blacklist -x -q` | ❌ Wave 0 |
| AUTH-03 | Only `JWTAuthentication` (Django-native) is a configured auth backend — no legacy JWT/Supabase acceptance path exists | unit (settings assertion) | `pytest accounts/tests/test_auth_flow.py::test_single_auth_backend -x -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `cd get-scouted-be && ./.venv/bin/pytest accounts -x -q`
- **Per wave merge:** `cd get-scouted-be && ./.venv/bin/pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] Dev database reset (drop/recreate) + re-run Phase 1's `import_all` — required before `accounts` migrations can be created safely (see Pitfall 1)
- [ ] `accounts/` app scaffold (`models.py`, `serializers.py`, `views.py`, `permissions.py`, `urls.py`, `admin.py`)
- [ ] `accounts/tests/conftest.py` — `UserFactory` (factory_boy) + `authenticated_client(role)` fixture pattern (`RefreshToken.for_user(user)` + `APIClient().credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")`)
- [ ] `pip install djangorestframework-simplejwt>=5.5.1,<5.6` + add to `requirements/base.txt`
- [ ] `INSTALLED_APPS`: add `rest_framework`, `rest_framework_simplejwt.token_blacklist`, `accounts`
- [ ] `REST_FRAMEWORK` + `SIMPLE_JWT` + `AUTH_USER_MODEL` + `EMAIL_BACKEND` settings blocks in `config/settings/base.py`
- [ ] Add `"accounts"` to `pyproject.toml`'s `testpaths`

## Sources

### Primary (HIGH confidence)
- [djangorestframework-simplejwt settings docs](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html) — `SIMPLE_JWT` dict keys/defaults, `CHECK_USER_IS_ACTIVE`
- [djangorestframework-simplejwt customizing token claims](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/customizing_token_claims.html) — `get_token()` override pattern, `TOKEN_OBTAIN_SERIALIZER` setting
- [djangorestframework-simplejwt blacklist app docs](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/blacklist_app.html) — blacklist app setup, `TokenBlacklistView`
- [Django 5.2 customizing authentication docs](https://docs.djangoproject.com/en/5.2/topics/auth/customizing/) — `AbstractBaseUser`/`PermissionsMixin` pattern, `AUTH_USER_MODEL` first-migration requirement, `CircularDependencyError` warning
- [DRF permissions API guide](https://www.django-rest-framework.org/api-guide/permissions/) — `BasePermission`, `has_permission`/`has_object_permission`, `&`/`|`/`~` composition
- PyPI JSON API / `pip index versions` — confirmed `djangorestframework-simplejwt` 5.5.1 current, fetched directly 2026-07-21
- Direct inspection of this project's dev environment — `get-scouted-be/.venv` package versions (Django 5.2.16, DRF 3.17.1), `manage.py showmigrations` output confirming `auth` app already migrated, direct SQL confirming 0 rows in `auth_user`/`django_admin_log`

### Secondary (MEDIUM confidence)
- [GitHub Advisory GHSA-5vcc-86wm-547q / NVD CVE-2024-22513](https://nvd.nist.gov/vuln/detail/CVE-2024-22513) — cross-verified across NVD, Red Hat, and GitHub advisory listings agreeing on "patched in 5.5.1"
- WebSearch-derived pytest fixture pattern (`RefreshToken.for_user()` + `APIClient.credentials()`) — cross-referenced against multiple community sources, consistent with simplejwt's own public API (`RefreshToken.for_user`, `.access_token`)

### Tertiary (LOW confidence)
- None — all findings above were verifiable against official docs, PyPI, or this project's actual environment/DB state.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions verified directly against PyPI and the project's own venv, not training-data recall
- Architecture: HIGH — patterns verified against official Django/DRF/simplejwt docs, not inferred
- Pitfalls: HIGH — Pitfall 1 (the most load-bearing finding) was verified by directly running `showmigrations` and SQL queries against this project's actual dev database, not speculated

**Research date:** 2026-07-21
**Valid until:** 30 days (stable ecosystem — Django/DRF/simplejwt versions here are LTS/mature; re-verify simplejwt version if this phase's implementation slips past mid-August 2026)

---
*Phase: 02-auth-access-control*
*Research completed: 2026-07-21*
