# GetScouted Backend

A Django/DRF backend for GetScouted, an AI-powered football recruitment and scouting platform
(built for World In Motion Ltd). Serves real player/club/transfer data and computes the
platform's core scores (RMM, Compatibility, Financial Fit, Transfer Probability), natural-language
search, AI-grounded scouting reports, squad planning, and bidirectional player/club matching.

This backend is designed to serve the `pixel-perfect-clone-60729` frontend prototype, replacing
its current Supabase layer. It is backend-only — wiring up the frontend is a separate effort.

---

## Requirements

- Python 3.12
- PostgreSQL (14+ recommended)
- `make` (optional but recommended — see [Makefile](#makefile-reference))

---

## 1. Launch — first-time setup

```bash
cd get-scouted-be

# 1. Create a venv and install dependencies (runtime + test tooling)
make install-dev

# 2. Configure environment
cp .env.example .env
# edit .env: at minimum set SECRET_KEY and DATABASE_URL (see Configuration below)

# 3. Make sure Postgres is running and the database in DATABASE_URL exists, e.g.:
createdb getscouted

# 4. Apply migrations
make migrate

# 5. (Optional but recommended) Load the real dataset
#    See docs/IMPORT_RUNBOOK.md for full details — this powers every score/search/report
#    endpoint with real data instead of an empty DB.
make import-data

# 6. Create an admin user (role=admin is not self-service — only createsuperuser grants it)
make superuser

# 7. Run the dev server
make run
```

The API is now live at `http://localhost:8000/api/v1/`, with interactive docs at
`http://localhost:8000/api/docs/` (see [API Docs](#api-docs--swagger--redoc) below).

Without step 5 (`make import-data`), the server runs fine but most endpoints will return
empty results — the dataset is what makes scores/search/reports meaningful.

---

## 2. Configuration

Copy `.env.example` to `.env` and fill in as needed. Key variables:

| Variable | Default | Notes |
|---|---|---|
| `SECRET_KEY` | `dev-insecure-change-me` | **Must** be set to a real secret outside local dev |
| `DEBUG` | `True` (local settings) | Never `True` in production |
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/getscouted` | Standard `django-environ` DB URL |
| `DATASET_DIR` | `../API-Updated-/dataset` | Where the source CSVs live for `import_all` |
| `LLM_PROVIDER` | `anthropic` | Selects the NL-search/report-generation provider |
| `ANTHROPIC_API_KEY` | *(blank)* | Leave blank to force NL search onto its deterministic keyword fallback (never errors) and to make AI report/insight endpoints return a clean error |
| `ANTHROPIC_MODEL` | verified default | Cheap/fast model, used for search-query parsing |

Settings are split `config/settings/{base,local,production}.py`; `manage.py`/`Makefile` both
default to `config.settings.local` for development.

---

## 3. Authentication

Every endpoint is deny-by-default (`IsAuthenticated`) except registration, login, token refresh,
and password reset. Auth is JWT (access + refresh) via `djangorestframework-simplejwt`.

**Register** (role is self-service-limited to `scout` / `analyst` / `director` — `admin` is
granted only via `make superuser` or by an existing admin):

```bash
curl -X POST http://localhost:8000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email": "scout@example.com", "password": "a-strong-password123", "display_name": "Jane Scout", "role": "scout"}'
```

**Log in** (returns `access` + `refresh` tokens):

```bash
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "scout@example.com", "password": "a-strong-password123"}'
```

**Use the access token** on every subsequent request:

```bash
curl http://localhost:8000/api/v1/players/ \
  -H "Authorization: Bearer <access_token>"
```

**Refresh** when the access token (15 min lifetime) expires:

```bash
curl -X POST http://localhost:8000/api/v1/auth/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "<refresh_token>"}'
```

Other auth routes: `POST /api/v1/auth/logout/` (blacklists a refresh token),
`POST /api/v1/auth/password-reset/` + `POST /api/v1/auth/password-reset/confirm/`,
`GET/PATCH /api/v1/auth/me/` (self profile), `GET /api/v1/auth/admin/users/` (admin/director only).

---

## 4. API overview

All routes are versioned under `/api/v1/`. Full interactive reference: [API Docs](#api-docs--swagger--redoc).

| Area | Base path | Highlights |
|---|---|---|
| Auth | `/api/v1/auth/` | Register, login, refresh, logout, password reset, profile, admin user management |
| Scoring | `/api/v1/scoring/` | Per-player/club RMM, Compatibility, Financial Fit, Transfer Probability, combined Profile summary |
| Players | `/api/v1/players/` | Browse/filter/compare, detail, natural-language search, AI scouting reports, club-fit matching |
| Clubs | `/api/v1/clubs/` | Browse/filter/compare, detail + CSV export, AI insights, position-needs analysis, replacement-player suggestions |
| Workspace | `/api/v1/workspace/` | Per-user Watchlist, Shortlists (+ CSV export), Squad Plans (+ change simulation), Recent Activity |

A few notable endpoints:
- `POST /api/v1/players/search/` — natural-language player search (e.g. *"young left-backs under €5M at possession-based clubs"*); always returns `200`, degrading gracefully if no `ANTHROPIC_API_KEY` is configured.
- `POST /api/v1/players/{id}/scouting-report/` and `POST /api/v1/clubs/{id}/insights/` — AI-generated narrative, every number grounded against real computed scores.
- `GET /api/v1/clubs/{id}/position-needs/` — weak/at-risk/strong classification per position.
- `POST /api/v1/workspace/squad-plans/{id}/simulate/` — in-memory squad-change simulation, never persisted until explicitly committed.
- `GET /api/v1/clubs/{id}/replacements/?position=<POS>` and `GET /api/v1/players/{id}/club-matches/` — bidirectional ranked matching. Both are genuinely slow (tens of seconds to ~2 minutes), live-computed against the full dataset by design — not a bug, don't be alarmed by the wait.

---

## 5. API docs — Swagger & Redoc

Once the server is running:

| URL | What it is |
|---|---|
| `http://localhost:8000/api/docs/` | Swagger UI — interactive, supports "Authorize" with a Bearer token |
| `http://localhost:8000/api/redoc/` | ReDoc — clean read-only reference |
| `http://localhost:8000/api/schema/` | Raw OpenAPI 3 schema (YAML) |

To authorize in Swagger UI: log in via `curl` (or the "Try it out" panel on
`POST /api/v1/auth/login/`), copy the `access` token, click **Authorize** top-right, and enter
`Bearer <access_token>`.

To export the schema to a file instead: `make schema` (writes `schema.yaml`, gitignored).

---

## 6. Running tests

```bash
make test         # full suite
make test-fast     # stop at first failure
```

Most tests use `factory_boy` fixtures and don't need real data. A subset of tests
(scoring parity, live-performance, some integration paths) require the real dataset to be
imported first (`make import-data`) and skip cleanly otherwise — a skip there is expected, not a
failure, if you haven't imported the dataset yet.

---

## 7. Makefile reference

Run `make help` for the full list. Common ones:

| Command | What it does |
|---|---|
| `make install-dev` | Create `.venv`, install runtime + dev/test deps |
| `make migrate` / `make makemigrations` | Apply / generate DB migrations |
| `make import-data` | Run the full CSV → Postgres data migration |
| `make run` | Start the dev server |
| `make shell` | Open a Django shell |
| `make superuser` | Create an admin user |
| `make test` / `make test-fast` | Run the pytest suite |
| `make lint` / `make format` | Ruff check / auto-format |
| `make check` | Django system check |
| `make schema` | Write the OpenAPI schema to `schema.yaml` |
| `make clean` | Remove `__pycache__`, `.pytest_cache`, `.ruff_cache` |

---

## 8. Project layout

```
get-scouted-be/
├── accounts/     # Custom User model, auth (register/login/reset), roles, admin user mgmt
├── clubs/        # Club browse/detail/export, AI insights, position needs, replacements
├── players/      # Player browse/detail, NL search, AI scouting reports, club matching
├── scoring/      # RMM / Compatibility / Financial Fit / Transfer Probability engine + API
├── workspace/    # Per-user Watchlist, Shortlists, Squad Plans (+ simulation), Recent Activity
├── transfers/    # Transfer history data
├── core/         # Shared utilities (pagination, import helpers)
├── config/       # Django project settings, root urls.py
└── docs/         # FIELD_MAPPING.md, IMPORT_RUNBOOK.md
```

Each app owns its own `models.py` / `views.py` / `serializers.py` / `urls.py` / `tests/`.

---

## 9. Deeper references

- `docs/IMPORT_RUNBOOK.md` — full data-migration operator guide
- `docs/FIELD_MAPPING.md` — CSV → Django field mapping
- `.planning/PROJECT.md` (repo root) — requirements, decisions, and what's been built and why
