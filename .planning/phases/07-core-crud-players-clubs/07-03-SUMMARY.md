---
phase: 07-core-crud-players-clubs
plan: 03
subsystem: api
tags: [drf, django-filter, clubs, crud]

# Dependency graph
requires:
  - phase: 07-core-crud-players-clubs
    plan: 01
    provides: "core.pagination.StandardResultsPagination/IdsBypassPagination, DjangoFilterBackend+OrderingFilter wired project-wide, clubs/tests/conftest.py real_data_available fixture"
  - phase: 07-core-crud-players-clubs
    plan: 02
    provides: "players.serializers.PlayerListSerializer -- the lightweight shape this plan's Club detail squad-overview component reuses directly"
provides:
  - "clubs.serializers.ClubListSerializer -- lightweight list/multi-fetch shape (identity + league/country/manager/formation + 8 playing-style floats)"
  - "clubs.serializers.ClubDetailSerializer -- full club profile + squad overview (reuses players.serializers.PlayerListSerializer) + transfer_aggregates (from Transfer.market_value_at_transfer only)"
  - "clubs.filters.ClubFilter -- league/country + 8 playing-style _min threshold filters + ids CSV multi-fetch capped at 100"
  - "GET /api/clubs/ (list, filter/paginate + ?ids= bypass) and GET /api/clubs/{id}/ (full profile + squad + transfer aggregates) endpoints"
affects: [08-watchlist-shortlist, 09-ai-layer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ClubDetailSerializer.get_transfer_aggregates computes total_transfers/arrivals/departures/avg+total market_value_at_transfer/by_window entirely from Transfer.market_value_at_transfer (BigIntegerField, 0 nulls) -- Transfer.fee (free-text CharField) is never aggregated; an empty Transfer queryset correctly yields None averages via Django's Avg/Sum, not a fabricated zero"
    - "ClubDetailSerializer.get_squad delegates to players.serializers.PlayerListSerializer(club.players.all(), many=True) -- confirms the squad-overview reuse Plan 02 flagged as ready"
    - "ClubFilter mirrors PlayerFilter's filter_queryset override pattern: a discretionary 100-id cap enforced on ?ids= before django-filter's own filtering runs"

key-files:
  created:
    - get-scouted-be/clubs/serializers.py
    - get-scouted-be/clubs/filters.py
    - get-scouted-be/clubs/views.py
    - get-scouted-be/clubs/urls.py
    - get-scouted-be/clubs/tests/test_views.py
  modified:
    - get-scouted-be/config/urls.py

key-decisions:
  - "Transfer-behaviour aggregates strictly source Transfer.market_value_at_transfer, never Transfer.fee (free-text 'Free'/'loan'/currency strings) -- the plan-checker's highest-priority correctness pivot for this plan, verified with a live dev-DB call that returned real numeric averages without raising"
  - "ClubDetailView is a plain generics.RetrieveAPIView (no scoring service call, no APIView subclass needed) since all aggregation is bounded ORM work scoped to a single club"
  - "config/urls.py edit was strictly additive -- api/players/ (07-02) preserved, api/clubs/ appended after it"

requirements-completed: [CRUD-02, CRUD-04, CRUD-05]

# Metrics
duration: 5min
completed: 2026-07-25
---

# Phase 7 Plan 3: Clubs CRUD (List + Detail + Squad + Transfer Aggregates) Summary

**Club list (filter by league/country/playing-style, paginated) and detail (full profile + squad overview reusing PlayerListSerializer + transfer-behaviour aggregates sourced exclusively from Transfer.market_value_at_transfer) endpoints under /api/clubs/, completing Phase 7's read surface.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-25T00:36Z
- **Completed:** 2026-07-25T00:40Z
- **Tasks:** 3 completed
- **Files modified:** 6 (1 modified, 5 created)

## Accomplishments
- `ClubListSerializer` (lightweight: identity + league/country/manager/formation + 8 playing-style floats, nullable) and `ClubDetailSerializer` (full profile + `squad` SerializerMethodField delegating to `PlayerListSerializer(club.players.all(), many=True)` + `transfer_aggregates` SerializerMethodField) created in `clubs/serializers.py`
- `ClubFilter` created with `league`/`country` exact-match, 8 playing-style `*_min` gte threshold filters, and an `IdsInFilter` CSV multi-fetch filter capped at 100 ids
- `ClubListView` (ListAPIView) wired with `filterset_class=ClubFilter`, `pagination_class=IdsBypassPagination`, default `ordering=["name"]`
- `ClubDetailView` (RetrieveAPIView) returns full profile + squad + transfer aggregates; no scoring service dependency
- `api/clubs/` wired into `config/urls.py` alongside (not replacing) 07-02's `api/players/` include
- Integration tests (auth gate, list filter by league/country, pagination shape, detail + squad + transfer_aggregates, market-value-not-fee guarantee, ids multi-fetch, 101-id cap) all pass; real-data tests skip cleanly on the empty pytest test DB and were live-verified against the real dev DB via `manage.py shell`

## Task Commits

Each task was committed atomically:

1. **Task 1: ClubListSerializer + ClubDetailSerializer + ClubFilter** - `dc24b72` (feat)
2. **Task 2: ClubListView + ClubDetailView + url wiring** - `7b17993` (feat)
3. **Task 3: Club list/detail/ids/auth tests** - `7e30be0` (test)

## Files Created/Modified
- `get-scouted-be/clubs/serializers.py` - `ClubListSerializer` (lightweight) + `ClubDetailSerializer` (full profile + squad + transfer_aggregates)
- `get-scouted-be/clubs/filters.py` - `ClubFilter` (league/country/playing-style thresholds + ids CSV filter, 100-id cap in `filter_queryset`)
- `get-scouted-be/clubs/views.py` - `ClubListView`, `ClubDetailView`
- `get-scouted-be/clubs/urls.py` - `club-list` / `club-detail` routes
- `get-scouted-be/config/urls.py` - added `path("api/clubs/", include("clubs.urls"))` after the existing `api/players/` include
- `get-scouted-be/clubs/tests/test_views.py` - integration tests

## Decisions Made
- Transfer aggregates read `Transfer.market_value_at_transfer` (clean BigInteger) exclusively; `Transfer.fee` (free-text) is never passed to `Sum`/`Avg` -- verified both via `grep` (no `Sum("fee")`/`Avg("fee")` present) and a live dev-DB call returning real numeric averages (`avg_market_value_at_transfer: 267248.06...`) without raising
- `get_squad` reuses `players.serializers.PlayerListSerializer` verbatim over `club.players.all()`, confirming 07-02's flagged reuse point
- `ClubDetailView` kept as a plain `RetrieveAPIView` (not a custom `APIView`) since its aggregation is pure bounded ORM work, unlike Players' detail view which needs the scoring service
- `config/urls.py`'s edit was purely additive: `api/players/` line untouched, `api/clubs/` appended immediately after it

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**Pre-existing unrelated test failure discovered during full-suite verification (`pytest -q`):** `accounts/tests/test_permissions.py::test_director_read_only_visibility` fails with `TypeError: string indices must be integers, not 'str'` because `GET /api/auth/admin/users/` now returns a paginated dict (`{"results": [...], "count": ...}`) rather than a plain list, a side effect of 07-01's project-wide `DEFAULT_PAGINATION_CLASS` wiring. Confirmed via `git checkout e970a28 -- get-scouted-be` (the commit immediately after 07-02 completed, before any 07-03 work) that this failure already existed prior to this plan's changes -- out of scope per the deviation rules' scope boundary (pre-existing failure in an unrelated app, not caused by clubs/players CRUD code). Logged to `.planning/phases/07-core-crud-players-clubs/deferred-items.md`, not fixed here. All `clubs/tests/test_views.py` tests and the rest of the suite are green.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 7's full read surface (Players + Clubs list/detail/ids) is now live under `/api/players/` and `/api/clubs/`
- `accounts/tests/test_permissions.py::test_director_read_only_visibility` needs a follow-up fix (update assertion to read `response.data["results"]`, or exempt that admin endpoint from pagination) -- tracked in deferred-items.md, not blocking Phase 7
- CRUD-02/04/05 requirements are functionally complete per this plan's must_haves, but marking them complete in REQUIREMENTS.md is deferred to the phase verifier's call, not this plan's

---
*Phase: 07-core-crud-players-clubs*
*Completed: 2026-07-25*

## Self-Check: PASSED

All 6 created files (serializers.py, filters.py, views.py, urls.py, tests/test_views.py, deferred-items.md) confirmed on disk; all 3 task commits (dc24b72, 7b17993, 7e30be0) confirmed in git log.
