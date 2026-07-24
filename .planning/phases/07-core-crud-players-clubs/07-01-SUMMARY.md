---
phase: 07-core-crud-players-clubs
plan: 01
subsystem: api
tags: [django-filter, drf, pagination, pytest, testing-fixtures]

# Dependency graph
requires:
  - phase: 02-auth-access-control
    provides: "REST_FRAMEWORK deny-by-default posture (JWTAuthentication + IsAuthenticated) that this plan extends additively"
  - phase: 03-scoring-engine-curation-correctness-oracle
    provides: "scoring/tests/conftest.py's real_data_available pattern, mirrored per-app here"
provides:
  - "django-filter installed and wired as the DRF project-wide DEFAULT_FILTER_BACKENDS entry"
  - "core.pagination.StandardResultsPagination (25/page default, 100 max, client-adjustable via page_size) as project-wide DEFAULT_PAGINATION_CLASS"
  - "core.pagination.IdsBypassPagination for CRUD-05's ?ids= multi-fetch bypass"
  - "players/tests/conftest.py and clubs/tests/conftest.py real_data_available fixtures for graceful skip on the empty pytest test DB"
affects: [07-02-players-crud, 07-03-clubs-crud]

# Tech tracking
tech-stack:
  added: ["django-filter>=26.1,<27.0"]
  patterns:
    - "REST_FRAMEWORK settings dict extended additively (new keys only), never replaced wholesale, to preserve the deny-by-default auth posture"
    - "Per-app conftest.py real_data_available fixture (not a shared root conftest) since pytest only auto-discovers fixtures within a conftest's own directory or descendants"

key-files:
  created:
    - get-scouted-be/core/pagination.py
    - get-scouted-be/players/tests/conftest.py
    - get-scouted-be/clubs/tests/conftest.py
  modified:
    - get-scouted-be/requirements/base.txt
    - get-scouted-be/config/settings/base.py

key-decisions:
  - "REST_FRAMEWORK dict extended with DEFAULT_FILTER_BACKENDS/DEFAULT_PAGINATION_CLASS/PAGE_SIZE keys added alongside (not replacing) DEFAULT_AUTHENTICATION_CLASSES/DEFAULT_PERMISSION_CLASSES, preserving Phase 2's deny-by-default posture"
  - "IdsBypassPagination subclasses StandardResultsPagination and returns None from paginate_queryset when ?ids= is present, which is DRF's documented signal to ListModelMixin.list() to skip pagination entirely"

patterns-established:
  - "Capped client-adjustable pagination (25 default / 100 max via page_size query param) as the project-wide DRF default"
  - "real_data_available fixture per app test dir, mirroring scoring/tests/conftest.py, for tests that need real Phase 1 migrated data and must skip cleanly against the empty pytest test DB"

requirements-completed: []

# Metrics
duration: 3min
completed: 2026-07-25
---

# Phase 7 Plan 1: Shared Read-Layer Foundation Summary

**django-filter + capped DRF pagination (25/page, 100 max, ?ids= bypass variant) wired additively into REST_FRAMEWORK, plus per-app real_data_available test fixtures for players and clubs.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-07-24T23:18:03Z
- **Completed:** 2026-07-25 (session date)
- **Tasks:** 3 completed
- **Files modified:** 5 (2 modified, 3 created)

## Accomplishments
- django-filter installed, pinned (`>=26.1,<27.0`), added to `INSTALLED_APPS`, and wired as `DjangoFilterBackend` + `OrderingFilter` in `DEFAULT_FILTER_BACKENDS`
- `core/pagination.py` created with `StandardResultsPagination` (project-wide default: 25/page, 100 max, client-adjustable via `page_size`) and `IdsBypassPagination` (skips pagination when `?ids=` is present, for CRUD-05 multi-fetch)
- REST_FRAMEWORK settings dict extended additively — existing `DEFAULT_AUTHENTICATION_CLASSES`/`DEFAULT_PERMISSION_CLASSES` (JWTAuthentication + IsAuthenticated deny-by-default) preserved untouched
- `players/tests/conftest.py` and `clubs/tests/conftest.py` created with app-scoped `real_data_available` fixtures, mirroring `scoring/tests/conftest.py`, unblocking 07-02 and 07-03's real-data integration tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Add django-filter dependency + wire it and pagination into REST_FRAMEWORK (additive)** - `85eea39` (feat)
2. **Task 2: Create shared pagination classes in core/pagination.py** - `43a9e5b` (feat)
3. **Task 3: Wave-0 test scaffold — real_data_available fixtures for players and clubs test suites** - `bf76e4c` (test)

_No plan-metadata commit yet — this SUMMARY.md and STATE.md/ROADMAP.md updates are captured in the final metadata commit below._

## Files Created/Modified
- `get-scouted-be/requirements/base.txt` - added `django-filter>=26.1,<27.0` pin
- `get-scouted-be/config/settings/base.py` - added `django_filters` to `INSTALLED_APPS`; extended `REST_FRAMEWORK` with `DEFAULT_FILTER_BACKENDS`, `DEFAULT_PAGINATION_CLASS`, `PAGE_SIZE`
- `get-scouted-be/core/pagination.py` - new `StandardResultsPagination` + `IdsBypassPagination` classes
- `get-scouted-be/players/tests/conftest.py` - new `real_data_available` fixture (Player-scoped)
- `get-scouted-be/clubs/tests/conftest.py` - new `real_data_available` fixture (Club-scoped)

## Decisions Made
- REST_FRAMEWORK dict was extended, never replaced — verified via grep that `DEFAULT_PERMISSION_CLASSES` remains intact after the edit
- `IdsBypassPagination` implemented as a `StandardResultsPagination` subclass overriding only `paginate_queryset`, so it inherits the same 25/100 page-size contract when `?ids=` is absent

## Deviations from Plan

None — plan executed exactly as written. One minor procedural note: the plan's literal `python -c "from core.pagination import ..."` verify command required `DJANGO_SETTINGS_MODULE=config.settings.local` to be set explicitly (bare `python -c` doesn't get Django settings auto-configured the way `manage.py` does internally). This is not a deviation in delivered code — it only affected how the verification command was invoked, and the acceptance criteria all passed once the env var was set.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `core.pagination.StandardResultsPagination` and `IdsBypassPagination` are ready for 07-02 (Players CRUD) and 07-03 (Clubs CRUD) to import into their ListAPIView `pagination_class` attributes
- `DjangoFilterBackend` + `OrderingFilter` are now the project-wide default filter backends, ready for 07-02/07-03 to declare `filterset_fields`/`ordering_fields` on their views
- `players/tests/conftest.py` and `clubs/tests/conftest.py` provide `real_data_available` for any real-data integration test in 07-02/07-03
- No blockers for 07-02 or 07-03

---
*Phase: 07-core-crud-players-clubs*
*Completed: 2026-07-25*

## Self-Check: PASSED

All created files confirmed on disk; all 3 task commits confirmed in git log.
