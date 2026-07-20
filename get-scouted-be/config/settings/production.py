# Hosting target deferred per PROJECT.md — placeholder only.

from .base import *  # noqa: F401,F403

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])  # noqa: F405
