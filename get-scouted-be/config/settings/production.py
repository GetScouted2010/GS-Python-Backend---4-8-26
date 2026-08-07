# Hosting target: Docker on a single EC2 instance behind Nginx (docs/deploy-docker-ec2.md).

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])  # noqa: F405

# Collected static files land here; nginx serves this directory directly.
STATIC_ROOT = BASE_DIR / "staticfiles"  # noqa: F405

# Nginx terminates TLS and forwards this header, so Django's security
# middleware can tell an HTTPS request from a plain HTTP one.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

HTTPS_ENABLED = env.bool("HTTPS_ENABLED", default=False)  # noqa: F405

if HTTPS_ENABLED:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
