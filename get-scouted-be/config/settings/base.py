"""
Shared Django settings for the GetScouted backend.

Split-settings layout: base.py (shared) -> local.py (dev) / production.py (deploy).
"""

from datetime import timedelta
from pathlib import Path

import environ

env = environ.Env()

# get-scouted-be/config/settings/base.py -> parents: settings/ -> config/ -> get-scouted-be/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")

DEBUG = False

ALLOWED_HOSTS: list[str] = []

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
    "django_filters",
    "drf_spectacular",
    "corsheaders",
    "clubs",
    "players",
    "transfers",
    "core",
    "accounts",
    "scoring",
    "workspace",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
# django-environ parses DATABASE_URL per STACK.md's 12-factor recommendation.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgresql://postgres:postgres@localhost:5432/getscouted",
    )
}
DATABASES["default"]["CONN_MAX_AGE"] = 60

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "static/"

# Dataset location — outside the Django project, at repo-root API-Updated-/dataset/.
# get-scouted-be/ is one level below the repo root, so BASE_DIR.parent is the repo root.
DATASET_DIR = env(
    "DATASET_DIR",
    default=str(BASE_DIR.parent / "API-Updated-" / "dataset"),
)

# Password validators — Django's four standard validators (min length 8, not too
# similar to user attributes, not entirely numeric, not a common password). Not set
# by default outside the startproject template, so this project's from-scratch
# settings must declare it explicitly to satisfy the "Django default validators, no
# custom rules" locked decision (registration/password-reset both call validate_password).
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# CORS: JWT auth reads the token from the Authorization header (not cookies), so
# credentials are not needed cross-origin. Comma-separated list of exact scheme+host
# (+port) origins allowed to call this API, e.g. "http://localhost:3000,https://app.example.com".
# Empty by default here; local.py/production.py set an environment-appropriate value.
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = False

# DRF: deny-by-default posture (AUTH-02/AUTH-03) — JWTAuthentication is the only
# configured auth class, IsAuthenticated is the only default permission. Views that
# must be public (register/login/refresh/password-reset) explicitly set
# permission_classes = [AllowAny].
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    # Every response is wrapped in a {data, meta} envelope (core/envelope.py),
    # mirroring the sibling giri-cart project's response contract. This is a
    # rendering-layer change only (JSONRenderer subclass) -- it does NOT alter
    # `response.data` in tests using DRF's APIClient (that attribute reflects
    # the view's pre-render return value, not the rendered bytes), so it's
    # safe alongside the exception-handler/pagination changes below without
    # touching most existing test assertions.
    "DEFAULT_RENDERER_CLASSES": ["core.envelope.EnvelopeRenderer"],
    # Every error response is normalised to {error: {code, detail, fields?}}
    # via core/exceptions.py, replacing this project's previously-inconsistent
    # mix of bare {"error": "..."} / {"detail": "..."} manual Response(...)
    # bodies with one typed shape everywhere (see API_ERROR_MAP for the code
    # list). Unlike the renderer above, this DOES change `response.data` for
    # any response that goes through DRF's exception handling (raised
    # exceptions, serializer validation, Http404) -- views that previously
    # built such Response(...) bodies manually were converted to raise the
    # matching exception instead (ValidationError / ServiceUnavailableError)
    # so they flow through this same handler.
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    # Wired project-wide (previously deliberately NOT set, since it would have
    # retroactively paginated /api/v1/auth/admin/users/ into DRF's default
    # {count,next,previous,results} shape, which callers weren't written to
    # expect). Now that every response is envelope-wrapped either way, a
    # paginated response is just {data, meta, pagination} and a non-paginated
    # one is {data, meta} -- applying real, bounded pagination everywhere is a
    # pure improvement over an unbounded plain list, not a breaking change in
    # kind. See core/pagination.py for the {items, pagination} -> envelope
    # promotion. players/clubs list views keep their own `pagination_class =
    # core.pagination.IdsBypassPagination` override for the ?ids= bypass.
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsPagination",
    # API versioning: every route lives under the literal /api/v1/ URL prefix
    # (config/urls.py). URLPathVersioning is enabled so `request.version` is
    # populated ("v1") without requiring every urlpattern to declare a captured
    # <version> group -- it falls back to DEFAULT_VERSION when the URLconf
    # doesn't supply one, which is exactly this project's literal-prefix setup.
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# OpenAPI schema / Swagger UI (drf-spectacular). Docs live outside the /api/v1/
# prefix (/api/schema/, /api/docs/, /api/redoc/) since the schema/docs surface
# itself isn't versioned data — only the API it describes is. SimpleJWT's Bearer
# scheme is picked up automatically (drf-spectacular ships a built-in
# `rest_framework_simplejwt` auth extension), so the Swagger UI "Authorize"
# button works out of the box.
SPECTACULAR_SETTINGS = {
    "TITLE": "GetScouted API",
    "DESCRIPTION": (
        "AI-powered football recruitment and scouting platform backend "
        "(World In Motion Ltd). All responses are wrapped in `{data, meta}`.\n\n"
        "## Response envelope\n\n"
        "Every successful response:\n"
        "```json\n"
        '{ "data": <payload>, "meta": { "request_id": "<uuid>" } }\n'
        "```\n"
        "Paginated list responses include a `pagination` key alongside "
        "`data` and `meta`:\n"
        "```json\n"
        "{\n"
        '  "data": [ "...items..." ],\n'
        '  "meta": { "request_id": "<uuid>" },\n'
        '  "pagination": {\n'
        '    "page": 1, "page_size": 25, "total_items": 143,\n'
        '    "has_next_page": true, "next_page": 2\n'
        "  }\n"
        "}\n"
        "```\n\n"
        "## Error handling\n\n"
        "Every error response uses this envelope — `error.detail` is "
        "**always a string**:\n"
        "```json\n"
        "{\n"
        '  "error": {\n'
        '    "code": "VALIDATION_ERROR",\n'
        '    "detail": "Validation failed.",\n'
        '    "fields": [ { "field": "email", "message": "Enter a valid email address." } ]\n'
        "  },\n"
        '  "meta": { "request_id": "<uuid>" }\n'
        "}\n"
        "```\n"
        "`error.fields` is present **only on `VALIDATION_ERROR`** when "
        "field-level attribution is available. All other error types "
        "return `{code, detail}` with no `fields` key.\n\n"
        "| Code | HTTP | When |\n"
        "|---|---|---|\n"
        "| `VALIDATION_ERROR` | 400 | Invalid request body or query params |\n"
        "| `NOT_AUTHENTICATED` | 401 | Missing or expired `Authorization` header |\n"
        "| `AUTHENTICATION_FAILED` | 401 | Invalid credentials or token |\n"
        "| `PERMISSION_DENIED` | 403 | Authenticated but not authorised for this resource |\n"
        "| `NOT_FOUND` | 404 | Resource does not exist |\n"
        "| `RATE_LIMITED` | 429 | Too many requests |\n"
        "| `METHOD_NOT_ALLOWED` | 405 | HTTP method not supported on this endpoint |\n"
        "| `SERVICE_UNAVAILABLE` | 503 | AI generation failed (report/insights) — never a fabricated response |\n"
        "| `INTERNAL_ERROR` | 500 | Unexpected server error |\n\n"
        "See the **`ErrorEnvelope`**, **`ApiError`**, and **`FieldError`** "
        "schemas in the Schemas section for full type definitions.\n\n"
        "## Typical flow\n\n"
        "1. **Auth** — `POST /auth/register/` (role: scout/analyst/director — "
        "admin is granted separately, never self-service), then "
        "`POST /auth/login/` for an access + refresh token pair. Send the "
        "access token as `Authorization: Bearer <token>` on every other call; "
        "refresh it via `POST /auth/token/refresh/` when it expires (15 min).\n"
        "2. **Discover players/clubs** — browse/filter `GET /players/` and "
        "`GET /clubs/`, or skip straight to `POST /players/search/` with a "
        "plain-English query (e.g. *\"young left-backs under €5M at "
        "possession-based clubs\"*) — it always returns 200, degrading "
        "through an LLM parse -> deterministic keyword fallback -> "
        "unfiltered list.\n"
        "3. **Inspect a player or club** — `GET /players/{id}/` and "
        "`GET /clubs/{id}/` return full profiles plus real computed scores "
        "(RMM, Compatibility, Financial Fit, Transfer Probability); the "
        "`scoring/` endpoints expose each score individually with its "
        "breakdown if you only need one.\n"
        "4. **Go deeper with AI** (optional) — `POST /players/{id}/"
        "scouting-report/` and `POST /clubs/{id}/insights/` turn those same "
        "computed scores into a narrative. Every number in the narrative is "
        "validated against the real scores before being returned — a 503 "
        "means generation failed, never a fabricated report.\n"
        "5. **Save work** — `workspace/` endpoints hold a user's Watchlist, "
        "Shortlists, and Squad Plans. All are private to the requesting user.\n"
        "6. **Plan a squad** — `GET /clubs/{id}/position-needs/` flags which "
        "positions are weak/at-risk, `GET /clubs/{id}/replacements/"
        "?position=<POS>` ranks real replacement candidates for a weak "
        "position, and `POST /workspace/squad-plans/{id}/simulate/` previews "
        "an add/remove/swap change in memory (never persisted until you "
        "explicitly save the Squad Plan itself).\n"
        "7. **Match the other direction** — `GET /players/{id}/club-matches/` "
        "ranks clubs that fit a given player, the mirror image of step 6's "
        "replacement search.\n\n"
        "Endpoints under `scoring/`, `players/{id}/club-matches/`, and "
        "`clubs/{id}/replacements/` compute against the real ~41,708-player "
        "dataset live — most respond in well under a second (Phase 6 "
        "caching), but the two arbitrary-other-club matching endpoints are "
        "intentionally uncached and can take 40s-2min. That's expected, not "
        "a bug."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "core.spectacular.add_error_schemas",
    ],
    "TAGS": [
        {
            "name": "auth",
            "description": (
                "Registration, login/refresh/logout, password reset, and "
                "user management. Everything else in the API requires a "
                "Bearer token obtained here."
            ),
        },
        {
            "name": "players",
            "description": (
                "Browse, filter, search, and inspect players — including "
                "natural-language search, AI scouting reports, and "
                "Player -> Club fit matching."
            ),
        },
        {
            "name": "clubs",
            "description": (
                "Browse, filter, and inspect clubs — including AI insights, "
                "position-needs analysis, CSV export, and replacement-player "
                "suggestions."
            ),
        },
        {
            "name": "scoring",
            "description": (
                "The four core scores (RMM, Compatibility, Financial Fit, "
                "Transfer Probability) exposed individually with full "
                "breakdowns, plus a combined summary. Every number shown "
                "elsewhere in the API (player/club detail, reports, "
                "matching) is computed by this same layer."
            ),
        },
        {
            "name": "workspace",
            "description": (
                "A user's private workspace: Watchlist, Shortlists (with "
                "CSV export), Squad Plans (with in-memory simulation), and "
                "an auto-logged Recent Activity feed. Every row here is "
                "scoped to the authenticated user."
            ),
        },
    ],
}

# simplejwt lifetimes 15min/7days are a deliberate discretionary bump over simplejwt's
# own defaults (5min/1day) for a demo SPA, avoiding painful silent-refresh churn without
# meaningfully weakening security given there's no rate-limiting/lockout either way in v1.
# BLACKLIST_AFTER_ROTATION=True is required for ROTATE_REFRESH_TOKENS to actually revoke
# the prior refresh token on each rotation (otherwise rotation alone issues new tokens
# without blacklisting the old one).
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

# Password-reset (forgot password) uses Django's console/dev email backend for now —
# no concrete email provider chosen yet (locked decision).
EMAIL_BACKEND = env(
    "EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend"
)

# LLM provider abstraction (AI-05). LLM_PROVIDER selects the concrete
# NLQueryParser implementation via players.ai.factory.get_nl_query_parser().
# Swapping providers = one new class + change this one env var, zero
# changes to search-calling code.
LLM_PROVIDER = env("LLM_PROVIDER", default="anthropic")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
# Model id is env-overridable ON PURPOSE: 09-RESEARCH.md Open Question 1 flags
# real uncertainty about the exact current fast/cheap model string, and STATE.md's
# Blockers note "AI layer LLM library/API surface should get a fresh check at build
# time." The default below was verified at build time (see build-time verification
# step) — never trust a stale model string.
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-haiku-4-5")
# Report generation (AI-03/AI-04) uses a separate, independently-configurable,
# stronger/flagship-tier model -- reports are low-volume, on-demand narrative
# generation (quality over cost), unlike ANTHROPIC_MODEL's per-search cheap
# extraction use case. Default verified at build time against the installed
# anthropic SDK's own ModelParam Literal type (no API key available to hit
# the live /v1/models endpoint) -- see 10-01-SUMMARY.md for the exact command
# output. Never trust a stale model string; re-verify if executed much later.
ANTHROPIC_REPORT_MODEL = env("ANTHROPIC_REPORT_MODEL", default="claude-sonnet-5")
