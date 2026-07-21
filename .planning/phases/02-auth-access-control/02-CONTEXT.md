# Phase 2: Auth & Access Control - Context

**Gathered:** 2026-07-21
**Status:** Ready for planning

<domain>
## Phase Boundary

A single Django system of record for identity and permissions replaces the 3 conflicting legacy auth models (JWT, disabled API-key middleware, Supabase Auth), gating every write endpoint by role. Covers registration, login/logout, token lifecycle, password reset, and the role permission matrix (scout, analyst, director, admin). Scoring, CRUD business logic, and the API layer for Players/Clubs/Transfers themselves are separate phases — this phase only establishes identity and permission enforcement.

</domain>

<decisions>
## Implementation Decisions

### Role Permission Matrix

- **scout** and **analyst** are functionally identical for v1 — full contributors: browse/search Players & Clubs, view scores/reports, manage their own Watchlist/Shortlists/Squad Plans, request AI reports. The distinction between the two is informational/job-title only; no permission check should differentiate them. (Explicitly deferred: splitting them apart later if a real need emerges.)
- **director** = scout/analyst permissions **+ org-wide visibility**: can view (read-only) all users' watchlists/shortlists/squad plans/recent activity across the org, not just their own.
- **admin** = director **+ user management**: can view/manage all user accounts, change any user's role, deactivate accounts. Nothing is off-limits to admin.
- This is an **additive hierarchy** (each higher role's permission set is a superset of the one below), not 4 disjoint permission sets.
- **Core scouting data (Player, Club, Transfer, PlayerRoleScore, PlayerClubCompatibility) is read-only for every non-admin role.** These are populated only by the Phase 1 import pipeline (or admin); no role can edit/correct this data via the API in v1.
- Director/admin's "org-wide visibility" is **view-only oversight** — editing or deleting another user's watchlist/shortlist/squad plan is restricted to its owner, even for director/admin. No cross-user write access at all in v1.

### Registration & Provisioning

- **Open self-service signup** — a public register endpoint accepting email, password, display name, and a role selection. Chosen deliberately over invite-only/admin-provisioned given the 4-day soft deadline; acceptable because the product is still prototype/demo stage with no live user base (consistent with the earlier "Supabase users not migrated" decision).
- **Role choices at signup are limited to scout, analyst, director — admin is excluded from self-service.** The first admin account is created via a Django management command / seed script (createsuperuser-style, one-time setup). Further admins are promoted only by an existing admin.
- **No email verification for v1** — an account is active immediately on registration. Deferred alongside real email-provider selection.
- **Email is the unique login identifier** — no separate username field. Standard swappable-user-model pattern with email as `USERNAME_FIELD`.
- **Role changes after signup are admin-only.** A user cannot self-change their own role once registered (prevents self-escalation), even between the functionally-identical scout/analyst roles.
- **Password-reset (forgot password) IS in scope for v1**, via a basic email-based reset-link flow — but ships using **Django's console/dev email backend** for now (reset link logged/returned, not actually emailed via SMTP/a provider). No concrete email provider has been chosen; this mirrors the project's existing LLM-provider-abstraction pattern (build the flow now, pick the concrete provider later without touching the flow).

### Session & Token Policy

- **djangorestframework-simplejwt** is the auth mechanism (already recommended in `.planning/research/STACK.md`) — short-lived access token + longer-lived refresh token. Exact lifetime values are Claude's discretion (simplejwt's defaults are a reasonable starting point).
- **Multi-device/multi-session login is unrestricted** — a user can be logged in on multiple devices simultaneously; no single-active-session enforcement, no session-tracking table needed.
- **Logout performs real server-side revocation**: the refresh token is submitted to be blacklisted (simplejwt's token-blacklist app), not just discarded client-side.
- **Refresh tokens rotate** (`ROTATE_REFRESH_TOKENS=True`): each refresh issues a new refresh token and blacklists the one just used.
- **Role changes and account deactivation are accepted to take effect starting next login/token refresh, not necessarily instantly mid-session** — a deliberate v1 simplicity choice, not a hard requirement to avoid real-time revocation. (Note for planner/researcher: standard simplejwt/DRF authentication already re-fetches the User row per request in the non-stateless configuration, so immediate `is_active` enforcement may fall out "for free" — get this technically right rather than over-building a separate revocation mechanism.)

### Auth Failure & Security Posture

- **Permission-denied returns 403 Forbidden** with a standard DRF detail message (not 404) — appropriate because core scouting data is readable by all authenticated roles anyway; there's nothing whose existence needs hiding.
- **No login lockout or rate-limiting for v1** — repeated failed logins simply return 401 each time, no attempt counting. Explicitly deferred hardening.
- **Password requirements use Django's default `AUTH_PASSWORD_VALIDATORS`** (min length 8, not too similar to user attributes, not entirely numeric, not a common password) — no custom rules.
- **Login failure message is generic** ("Invalid email or password") regardless of whether the email or the password was wrong — prevents user enumeration.
- **Admin can deactivate a user account (soft — `is_active=False`); accounts are never hard-deleted.** Preserves referential integrity for anything the user created (shortlists, squad plans, activity history) that later CRUD phases (7, 8) build on top of.

### Claude's Discretion

- Exact simplejwt token lifetime values (access/refresh minute/day counts)
- Exact DRF permission-class architecture (custom `BasePermission` classes vs. per-view `permission_classes`) implementing the additive role hierarchy
- Whether role is a `CharField` + choices directly on a custom User model, or a separate Role/Profile model
- Whether the custom User model extends `AbstractUser` (with a manager override for email-as-username) or `AbstractBaseUser` fully custom
- Exact password-reset token/endpoint mechanics (Django's built-in `PasswordResetTokenGenerator` vs. a custom equivalent)
- Whether `is_active`/role checks are enforced with full immediacy per-request as a natural side effect of the chosen simplejwt authentication configuration (see note above) — get the real behavior right, don't just take the "next login" framing as license to under-build

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements this phase satisfies
- `.planning/REQUIREMENTS.md` §"Authentication & Access" — AUTH-01 (register/login with role-based access), AUTH-02 (write endpoints gated by role permissions), AUTH-03 (reconcile 3 legacy auth models; existing Supabase users NOT migrated)

### Project-level decisions this phase must honor
- `.planning/PROJECT.md` §"Key Decisions" — "Existing Supabase-authenticated users in `pixel-perfect-clone-60729` are not migrated" (locked; clean re-registration only)
- `.planning/PROJECT.md` §"Key Decisions" — UUID primary keys across all models (the new User model should follow this same precedent for schema consistency)

### Auth mechanism research (already decided at project level)
- `.planning/research/STACK.md` §"Django REST Framework" and §"djangorestframework-simplejwt" — locks in DRF + simplejwt as the auth stack, including embedding role in custom JWT claims (still validate server-side, never trust the claim alone)
- `.planning/research/STACK.md` §"Trade-off table" (supporting legacy JWT/Supabase long-term) — recommends picking simplejwt as the *sole* model; **its suggested "re-issue Django tokens on first login" migration step is SUPERSEDED** by the locked no-migration decision above — there is no legacy user data to carry forward at all, just clean signup

### Historical context (superseded parts noted)
- `.planning/codebase/CONCERNS.md` §"Auth Model Reconciliation" and §"Auth Model Mismatch with API-Updated-" — documents the 3 legacy auth models this phase replaces. Its phased "Phase 1: accept legacy JWT / Phase 2: Supabase adapter / Phase 3: migrate users" plan is **superseded** — no legacy token acceptance or user migration is in scope; Django auth is the only path in from day one.

### Product context for roles
- `GetScouted PRD.docx` — defines the 4 user-facing roles (scout, analyst, director, admin) this phase's permission matrix implements

### Prior phase precedent
- `.planning/phases/01-data-foundation/01-CONTEXT.md` — establishes the "surface issues, never silently drop/halt" data-quality philosophy and the UUID PK precedent this phase's User model follows

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None yet specific to auth — `django.contrib.auth` is installed (`config/settings/base.py`) but unconfigured beyond the default; no custom User model exists yet.
- `djangorestframework` is a listed dependency (`requirements/base.txt`) but **not yet added to `INSTALLED_APPS`** and has no `REST_FRAMEWORK` settings block — this phase is the first to actually wire up DRF.

### Established Patterns
- All 5 existing models (Club, Player, PlayerRoleScore, PlayerClubCompatibility, Transfer) use UUID primary keys (`models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`) — follow the same pattern for the new User model.
- Django apps are organized by domain (`clubs/`, `players/`, `transfers/`, `core/`) with management commands under `<app>/management/commands/`. A new `accounts/` (or similarly named) app is the natural home for the User model and auth views, following this convention.
- Settings are split `base.py` / `local.py` / `production.py` with `django-environ` reading `.env` — any new auth-related settings (JWT lifetimes, email backend) should follow this same pattern, not be hardcoded.

### Integration Points
- Phase 7/8 (Core CRUD, User Workspace CRUD) will attach `owner`/`user` FKs to Watchlist, Shortlist, Squad Plan models — this phase's User model is what those FKs point to.
- Phase 8's "Recent Activity" (CRUD-09) will need the same User model as its FK target.
- No existing auth code in `get-scouted-be/` to migrate from — this is greenfield within the Django project (the "3 legacy models" being replaced live in the separate `API-Updated-`/`pixel-perfect-clone-60729` codebases, not in `get-scouted-be/`).

</code_context>

<specifics>
## Specific Ideas

No specific product references or "I want it like X" moments — this phase was entirely policy decisions (role scope, provisioning flow, token behavior, failure handling).

</specifics>

<deferred>
## Deferred Ideas

- Splitting scout and analyst into functionally distinct roles — currently identical; revisit if a real need emerges
- Email verification at signup — v2, alongside real email-provider selection
- Login rate-limiting / lockout on repeated failures — v2 security hardening
- Real-time (instant, mid-session) permission/deactivation revocation beyond whatever simplejwt's default per-request user fetch already provides — v2 hardening if ever needed
- Cross-user editing/deletion by director/admin (currently view-only oversight) — not planned, noted in case product needs change
- Concrete email provider selection for password-reset delivery (SendGrid, SES, etc.) — deferred like the LLM provider decision

</deferred>

---

*Phase: 02-auth-access-control*
*Context gathered: 2026-07-21*
