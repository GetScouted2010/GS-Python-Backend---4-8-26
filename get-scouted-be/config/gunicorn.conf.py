"""Gunicorn server hooks -- warms the in-process scoring caches at worker
startup instead of on the first user request.

`scoring.services.population.get_scored_population(group)` / `get_tfm_pipeline()`
are `functools.lru_cache`d -- memoized once PER WORKER PROCESS (one entry per
scoring group: the legacy pool of older seasons, and 2025-2026 on its own).
Without this hook, the ~60k-player (two populations) pandas + sklearn reconstruction they do
runs on whichever request happens to hit a cold worker first (always true
right after every deploy, since `docker compose ... up -d --force-recreate
web` starts fresh worker processes). That reconstruction has been observed
to run past gunicorn's own request --timeout on this instance size, killing
the worker and failing the user's request outright (see incident: player
detail endpoint 500s + WORKER TIMEOUT, 2026-08-21).

Warming here, in `post_worker_init`, moves that cost to worker boot -- off
the request path entirely -- so it's free to take as long as it needs
without any user-facing timeout. `--timeout` (docker-compose.prod.yml) is
still raised as a belt-and-braces fallback for genuinely slow arbitrary-club
requests that can't hit this warmed cache (see get_summary's `own` branch
in scoring/services/summary.py -- only the own-club path is covered here).
"""

from __future__ import annotations


def post_worker_init(worker):
    from scoring.services.population import warm_scoring_caches

    worker.log.info("Warming scoring population caches (every group: RMM/CS/TP + TFM pipeline)...")
    warm_scoring_caches()
    worker.log.info("Scoring population caches warmed -- worker ready.")
