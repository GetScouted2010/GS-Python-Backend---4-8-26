from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Dev convenience: allow the common local frontend dev-server origins out of the box.
# Override via CORS_ALLOWED_ORIGINS in .env if the frontend runs elsewhere.
if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    CORS_ALLOWED_ORIGINS = [  # noqa: F405
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
