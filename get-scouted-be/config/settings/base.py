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
    "clubs",
    "players",
    "transfers",
    "core",
    "accounts",
    "scoring",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
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
