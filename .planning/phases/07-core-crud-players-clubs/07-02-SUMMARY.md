---
phase: 07-core-crud-players-clubs
plan: 02
subsystem: api
tags: [drf, django-filter, players, crud]

# Dependency graph
requires:
  - phase: 07-core-crud-players-clubs
    plan: 01
    provides: "core.pagination.StandardResultsPagination/IdsBypassPagination, DjangoFilterBackend+OrderingFilter wired project-wide, players/tests/conftest.py real_data_available fixture"
  - phase: 04-scoring-engine-port
    provides: "scoring.services.summary.get_summary, scoring.services.rmm.get_rmm, scoring.exceptions.null_with_reason"
provides:
  - "players.serializers.PlayerListSerializer -- the lightweight list/squad shape 07-03's Club detail squad-overview component reuses directly"
  - "players.serializers.PlayerDetailSerializer -- full-profile shape"
  - "players.filters.PlayerFilter -- position/league/age/market_value/score-threshold + ids filters, bound to Player.position (not main_position)"
  - "GET /api/players/ (list, filter/sort/paginate + ?ids= bypass) and GET /api/players/{id}/ (full profile + score breakdowns) endpoints"
affects: [07-03-clubs-crud]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PlayerFilter.filter_queryset overridden to enforce a discretionary 100-id cap on ?ids= before django-filter's own filtering runs"
    - "PlayerDetailView branches explicitly on club_id is None BEFORE calling get_summary() (which raises Http404 on an unresolvable club) -- never a try/except that would mask other real 404s"
    - "Module-scope django_db_blocker.unblock() pre-warm fixture (mirrors scoring/tests/test_parity_bulk.py) so the one real get_summary() integration test hits get_scored_population()'s warm ~0.2s own-club path"

key-files:
  created:
    - get-scouted-be/players/serializers.py
    - get-scouted-be/players/filters.py
    - get-scouted-be/players/views.py
    - get-scouted-be/players/urls.py
    - get-scouted-be/players/tests/test_views.py
    - get-scouted-be/players/tests/test_filters.py
  modified:
    - get-scouted-be/config/urls.py

key-decisions:
  - "position filter binds to Player.position (the clean 10-value group), never Player.main_position (22 fine-grained values + a garbage '0' row) -- the highest-risk correctness pivot the plan-checker re-verified"
  - "PlayerDetailView's club_id defaults to the player's own current club (player.club_id) when no ?club_id= query param is given, matching the Phase-6 own-club fast path"
  - "club_id is None branch computes RMM via rmm.get_rmm(pk) (context-free) and returns null_with_reason(...) for compatibility/financial_fit/transfer_probability with reason 'player_has_no_club' -- get_summary() is never called on this path"
  - "?ids= multi-fetch capped at 100 ids (discretionary, per 07-CONTEXT.md's open item), enforced in PlayerFilter.filter_queryset before django-filter's own filtering, raising a 400 ValidationError over the cap"

requirements-completed: []

# Metrics
duration: 7min
completed: 2026-07-25
---

# Phase 7 Plan 2: Players CRUD (List + Detail + Multi-fetch) Summary

**Player list (filter/sort/paginate) and detail (full profile + 4 score breakdowns) endpoints under /api/players/, with position filtering strictly bound to the clean Player.position group and an explicit club=None defensive branch that never fabricates a 404.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-07-25T00:24Z
- **Completed:** 2026-07-25T00:31Z
- **Tasks:** 3 completed
- **Files modified:** 7 (1 modified, 6 created)

## Accomplishments
- `PlayerListSerializer` (lightweight: identity + position/league/club + market value + 4 denormalized scores) and `PlayerDetailSerializer` (full profile, all model fields) created in `players/serializers.py`
- `PlayerFilter` created with position/league exact-match filters, age/market_value/score-threshold range filters, and an `IdsInFilter` CSV multi-fetch filter capped at 100 ids -- `position` verified bound to `field_name="position"`, never `main_position`
- `PlayerListView` (ListAPIView) wired with `filterset_class=PlayerFilter`, `pagination_class=IdsBypassPagination`, `ordering_fields` on age/market_value/the 4 scores, default `ordering=["-impact_score"]`
- `PlayerDetailView` (APIView) returns full profile + `{"rmm", "compatibility", "financial_fit", "transfer_probability"}` score breakdowns, branching explicitly on `club_id is None` before calling `summary.get_summary()` -- the club-less fallback calls `rmm.get_rmm(pk)` and returns `null_with_reason(..., "player_has_no_club")` for the 3 club-dependent scores
- `api/players/` wired into `config/urls.py`; `players/urls.py` registers `player-list` (`/api/players/`) and `player-detail` (`/api/players/{id}/`)
- Integration tests (auth gate, list filter/order/pagination, detail + breakdowns, club=None branch via mocks, ids multi-fetch, 101-id cap) and filter unit tests (position field binding, gte lookup) all pass; real-data tests skip cleanly on the empty pytest test DB and were live-verified against the real dev DB

## Task Commits

Each task was committed atomically:

1. **Task 1: PlayerListSerializer + PlayerDetailSerializer + PlayerFilter** - `7d6ffe0` (feat)
2. **Task 2: PlayerListView + PlayerDetailView + url wiring** - `1bdcbb3` (feat)
3. **Task 3: Player list/detail/ids/auth tests** - `6b903c1` (test)

## Files Created/Modified
- `get-scouted-be/players/serializers.py` - `PlayerListSerializer` (lightweight) + `PlayerDetailSerializer` (full profile)
- `get-scouted-be/players/filters.py` - `PlayerFilter` (position/league/age/market_value/score-threshold + ids CSV filter, 100-id cap enforced in `filter_queryset`)
- `get-scouted-be/players/views.py` - `PlayerListView`, `PlayerDetailView`
- `get-scouted-be/players/urls.py` - `player-list` / `player-detail` routes
- `get-scouted-be/config/urls.py` - added `path("api/players/", include("players.urls"))`
- `get-scouted-be/players/tests/test_views.py` - integration tests
- `get-scouted-be/players/tests/test_filters.py` - filter unit tests

## Decisions Made
- Position filtering strictly binds to `Player.position` (clean 10-value group), verified by both a unit test and a live dev-DB spot check
- Detail view's club=None branch is a structural `if/else` on `club_id is None`, not a try/except around `get_summary()`, so other genuine 404s (unknown player) still propagate normally via `get_object_or_404`
- ids cap set to 100 (matches `IdsBypassPagination`'s bypass semantics: a bounded, named set, not an unbounded browse)
- `PlayerListSerializer` confirmed as the shape 07-03's Club detail squad-overview component will import directly (no separate squad serializer needed)

## Deviations from Plan

None - plan executed exactly as written. One adjustment during test authoring (Rule 1 - Bug, self-contained within Task 3, no separate commit needed since it was fixed before the task's single commit): the plan's `mock_get_rmm.assert_called_once_with(str(player.id))` example assumed a string pk; the actual URL-resolved `pk` DRF passes to the view is a `uuid.UUID` object, so the test asserts `mock_get_rmm.assert_called_once_with(player.id)` (no `str()`) to match the real call signature. Caught immediately during the task's own local test run, no separate fix-then-verify cycle needed.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `players.serializers.PlayerListSerializer` is ready for 07-03's Club detail squad-overview component to import directly
- `players.filters.PlayerFilter`, `players.views.PlayerListView`/`PlayerDetailView` patterns (filterset_class/pagination_class/ordering_fields, explicit club_id-is-None branching before a Http404-raising service call) are the established convention 07-03's Clubs CRUD should mirror
- No blockers for 07-03

---
*Phase: 07-core-crud-players-clubs*
*Completed: 2026-07-25*

## Self-Check: PASSED

All 6 created files confirmed on disk; all 3 task commits (7d6ffe0, 1bdcbb3, 6b903c1) confirmed in git log.
