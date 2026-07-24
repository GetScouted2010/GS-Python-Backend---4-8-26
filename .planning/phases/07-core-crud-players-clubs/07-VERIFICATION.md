---
phase: 07-core-crud-players-clubs
verified: 2026-07-24T23:55:02Z
status: passed
score: 6/6 must-haves verified
---

# Phase 7: Core CRUD - Players & Clubs Verification Report

**Phase Goal:** Users can browse, filter, and inspect real player and club data, including their scores, through a full API surface.
**Verified:** 2026-07-24T23:55:02Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can list/filter/sort/paginate Players by position, age, market value, league, score thresholds | ✓ VERIFIED | Live `manage.py shell` call against real dev DB (41,708 players): `GET /api/players/?position=FWD&ordering=-impact_score&page_size=5` → 200, `count: 6391`, all results `position=="FWD"`. Combined `impact_score_min=80&age_min=18&age_max=23&market_value_min=100000` → 200, `count: 1389`. `PlayerFilter.base_filters["position"].field_name == "position"` (unit test, guards against regression to `main_position`). Real DB confirms `Player.position` has exactly 10 clean values + null — never the 22-value `main_position` group. |
| 2 | User can list/filter Clubs by league, country, and playing style | ✓ VERIFIED (see note) | `ClubFilter` has correct `league`/`country`/8 `*_min` playing-style filters; live call `GET /api/clubs/` with league filter returns real, correctly-scoped results. **Note:** live dev-DB inspection (`SELECT COUNT(*) FROM clubs_club WHERE country IS NOT NULL` = 0) shows all 1,060 real clubs have `country = NULL` — a Phase-1-locked, already-documented data limitation (Phase 1's own VERIFICATION.md: "manager/formation/country are 0/1,060 populated... locked, documented Phase-1 CONTEXT.md decision, not a migration defect"). The `country` filter mechanism is implemented correctly and would work the instant real country data exists, but is currently unexercisable against real data. `clubs/tests/test_views.py::test_list_filters_by_country`'s precondition (`assert country, "expected at least one real Club.country value"`) would fail if actually run against the real dev DB — I reproduced this directly via `manage.py shell` and confirmed the `AssertionError`. This means 07-03-SUMMARY.md's blanket claim that all real-data tests were "live-verified against the real dev DB" is not accurate for this one assertion. Not a Phase 7 code defect — a data-availability gap inherited from Phase 1 — but flagged for correction (see Gaps Summary). |
| 3 | User can retrieve a single Player's full profile, season-by-season stats, and score breakdowns | ✓ VERIFIED | Live call `GET /api/players/{real_id}/` → 200, returns full profile (`"__all__"` fields), `season: "2023-2024"` (real value), `scores: {rmm, compatibility, financial_fit, transfer_probability}` all populated dicts. "Season-by-season" deliberately scoped to the single real `season` value per 07-CONTEXT.md's documented, data-reality-driven decision (every one of 41,708 players has exactly one row) — correctly not fabricated. First call after cold process start took ~77s (Phase 6's known `get_scored_population()` cold-build cost); second call in the same process: 0.171s, matching Phase 6's documented ~0.2s warm own-club path. This is expected, pre-existing Phase 6 caching behavior, not a Phase 7 regression. |
| 4 | User can retrieve a single Club's full profile, squad overview, and transfer behaviour aggregates | ✓ VERIFIED | Live call `GET /api/clubs/{club_with_transfers}/` → 200. `squad` is a list (reuses `PlayerListSerializer`, confirmed 1 item for a 1-player club). `transfer_aggregates` for a club with 258 real transfers: `{total_transfers: 258, arrivals: 125, departures: 133, avg_market_value_at_transfer: 267248.0620155039, total_market_value_at_transfer: 68950000, by_window: [...]}` — exact match to 07-03-SUMMARY.md's independently-claimed figure (`267248.06...`). Grep confirms no `Sum("fee")`/`Avg("fee")` anywhere in `clubs/serializers.py`; only `market_value_at_transfer` is aggregated. A club with 0 transfers correctly returns `None` averages (verified live), not fabricated zeros. |
| 5 | User can fetch multiple players or clubs by ID in one request for side-by-side comparison | ✓ VERIFIED | Live calls: `GET /api/players/?ids=<3 real uuids>` → 200, unpaginated list of exactly 3. `GET /api/clubs/?ids=<3 real uuids>` → 200, unpaginated list of exactly 3. 101-id request → 400 `{"ids": "A maximum of 100 ids may be requested at once."}` on both endpoints (live-verified for players; unit-tested for clubs). `IdsBypassPagination.paginate_queryset` returns `None` when `?ids=` present, which is DRF's documented "skip pagination" signal. |
| 6 | Cross-phase regression (global pagination breaking Phase 2's admin endpoint) is fixed and the full suite is green | ✓ VERIFIED | `pytest -q` from `get-scouted-be/`: **112 passed, 0 failed, 305 skipped** (skips are all `real_data_available`-gated, expected against pytest's own empty test DB). `accounts/tests/test_permissions.py::test_director_read_only_visibility` passes individually. `config/settings/base.py`'s `REST_FRAMEWORK` dict confirmed to no longer contain `DEFAULT_PAGINATION_CLASS`/`PAGE_SIZE` keys (commit `c04c705`, inspected directly). `players/views.py`/`clubs/views.py` confirmed to each explicitly set `pagination_class = IdsBypassPagination` on their list views — live-verified both `/api/players/` and `/api/clubs/` still return proper `{count,next,previous,results}` envelopes with `page_size=25` default. Re-ran the full suite independently (not just trusting the reported count) — same 112/0/305 result, no other regressions introduced by the fix. |

**Score:** 6/6 truths verified (5 ROADMAP success criteria + 1 cross-cutting regression-fix truth)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/core/pagination.py` | `StandardResultsPagination` + `IdsBypassPagination` | ✓ VERIFIED | 33 lines. Both classes present, correctly implemented, not wired as global default (post-fix), imported by both `players/views.py` and `clubs/views.py`. |
| `get-scouted-be/players/serializers.py` | `PlayerListSerializer` (lightweight+scores), `PlayerDetailSerializer` (full profile) | ✓ VERIFIED | 52 lines. Both classes present; `PlayerListSerializer` reused verbatim by `clubs/serializers.py`'s squad overview. |
| `get-scouted-be/players/filters.py` | `PlayerFilter`: position/league/age/market_value/score-threshold + ids | ✓ VERIFIED | 55 lines. `field_name="position"` confirmed (never `main_position`). 100-id cap enforced in `filter_queryset`. |
| `get-scouted-be/players/views.py` | `PlayerListView`, `PlayerDetailView` (get_summary + club=None branch) | ✓ VERIFIED | 64 lines. `club_id is None` branch structurally precedes `get_summary()` call — confirmed never invoked on that path (both by code reading and by `mock_get_summary.assert_not_called()` in tests). |
| `get-scouted-be/players/urls.py` | list + detail routes | ✓ VERIFIED | `player-list`, `player-detail` registered, UUID pk. |
| `get-scouted-be/clubs/serializers.py` | `ClubListSerializer` + `ClubDetailSerializer` (squad + transfer_aggregates) | ✓ VERIFIED | 77 lines. `market_value_at_transfer` used exclusively for aggregates; `fee` never referenced. |
| `get-scouted-be/clubs/filters.py` | `ClubFilter`: league/country/playing-style + ids | ✓ VERIFIED | 44 lines. |
| `get-scouted-be/clubs/views.py` | `ClubListView`, `ClubDetailView` | ✓ VERIFIED | 38 lines. `ClubDetailView` correctly a plain `RetrieveAPIView` (no scoring dependency). |
| `get-scouted-be/clubs/urls.py` | list + detail routes | ✓ VERIFIED | `club-list`, `club-detail` registered. |
| `get-scouted-be/config/urls.py` | `api/players/` + `api/clubs/` includes | ✓ VERIFIED | Both present, additive (auth/scoring includes untouched). |
| `get-scouted-be/players/tests/test_views.py`, `test_filters.py` | integration + unit tests | ✓ VERIFIED | 171 + 17 lines. Auth gate, filter/sort/paginate, detail+breakdowns, club=None branch (mocked), ids multi-fetch, cap — all present and pass. |
| `get-scouted-be/clubs/tests/test_views.py` | integration tests | ✓ VERIFIED | 141 lines. Auth gate, filter, pagination, detail+squad+aggregates, market-value-not-fee guarantee, ids multi-fetch, cap. One test's real-data precondition (`test_list_filters_by_country`) does not hold against the actual dev DB — see Truth #2 note. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `config/urls.py` | `players.urls` / `clubs.urls` | `include()` | ✓ WIRED | Both includes present and additive. |
| `players/views.py` | `scoring.services.summary.get_summary` / `scoring.services.rmm.get_rmm` | direct import + call | ✓ WIRED | Live-verified: real player detail call returns populated 4-key `scores` dict; club=None path calls `rmm.get_rmm` only, never `summary.get_summary` (asserted in test + code structure). |
| `clubs/serializers.py` | `players.serializers.PlayerListSerializer` | direct import, `get_squad` | ✓ WIRED | Live-verified: club detail's `squad` field returns a real, populated list via the reused serializer. |
| `players/views.py`, `clubs/views.py` | `core.pagination.IdsBypassPagination` | `pagination_class` attribute | ✓ WIRED | Live-verified: both endpoints paginate normally (25/page) without `?ids=`, and bypass pagination (return a plain list) with `?ids=`. |
| `REST_FRAMEWORK` settings | `players`/`clubs` filterset views | `DEFAULT_FILTER_BACKENDS` | ✓ WIRED | `DjangoFilterBackend` + `OrderingFilter` project-wide; both list views declare `filterset_class`/`ordering_fields` and filters demonstrably narrow real results. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CRUD-01 | 07-01, 07-02 | List/filter/sort/paginate Players by position, age, market value, league, score thresholds | ✓ SATISFIED | `PlayerFilter` + `PlayerListView` live-verified against real data (Truth #1). |
| CRUD-02 | 07-03 | List/filter Clubs by league, country, playing style | ✓ SATISFIED (with data-coverage caveat) | `ClubFilter` + `ClubListView` correctly implemented for all 3 dimensions; league/playing-style live-verified functional, country mechanically correct but currently 0% real-data coverage (Phase-1-inherited, see Truth #2). |
| CRUD-03 | 07-02 | Retrieve a single Player's full profile, season-by-season stats, and score breakdowns | ✓ SATISFIED | `PlayerDetailView` live-verified (Truth #3); season scope deliberately matches real data model per 07-CONTEXT.md. |
| CRUD-04 | 07-03 | Retrieve a single Club's full profile, squad overview, and transfer behaviour aggregates | ✓ SATISFIED | `ClubDetailView` live-verified (Truth #4); aggregates correctly source `market_value_at_transfer`, never `fee`. |
| CRUD-05 | 07-01, 07-02, 07-03 | Fetch multiple players/clubs by ID in one request for comparison | ✓ SATISFIED | `?ids=` on both list endpoints, live-verified unpaginated exact-set return + 100-id cap (Truth #5). |

No orphaned requirements — REQUIREMENTS.md's traceability table maps only CRUD-01 through CRUD-05 to Phase 7, and all 5 are claimed across the 3 plans' `requirements` frontmatter.

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, no empty handlers, no static/fabricated return values in any of the 9 created/modified source files reviewed (`core/pagination.py`, `players/{serializers,filters,views,urls}.py`, `clubs/{serializers,filters,views,urls}.py`).

### Human Verification Required

None. This phase delivers a read-only API surface with no UI of its own (explicitly out of scope per 07-CONTEXT.md), so all success criteria are programmatically verifiable via live HTTP calls against the real dev database, which was done for every truth above.

### Gaps Summary

No blocking gaps. Phase 7 achieves its goal: all 5 ROADMAP success criteria are implemented, wired, and independently live-verified against the real 41,708-player / 1,060-club dev database, and the cross-phase pagination regression the orchestrator found and fixed (commit `c04c705`) is confirmed resolved with a fully green test suite (112 passed, 0 failed, 305 skipped) and no new regressions introduced by the fix.

One non-blocking follow-up worth tracking (does not affect CRUD-01 through CRUD-05 completion, and is not a Phase 7 code defect):

- **`clubs/tests/test_views.py::test_list_filters_by_country`'s real-data precondition does not hold.** All 1,060 real `Club` rows have `country = NULL` (confirmed via raw SQL and ORM query against the dev DB) — a data limitation locked and documented back in Phase 1 (`manager`/`formation`/`country` were never populated; "no legacy source exists," per Phase 1's own VERIFICATION.md). The `country` filter is implemented correctly in `ClubFilter` and would work the moment real country data exists, but currently the test's `assert country, "expected at least one real Club.country value"` would raise `AssertionError` if actually exercised against the real dev DB (reproduced directly). 07-03-SUMMARY.md's claim that this test was "live-verified against the real dev DB" is therefore not accurate as stated for this specific assertion. Recommended follow-up (not blocking): update the test to `pytest.skip(...)` gracefully when no club has a `country` value (mirroring the `real_data_available` pattern already used elsewhere), and/or add an explicit note to PROJECT.md alongside the existing season-by-season scoping precedent that `Club.country` filtering is code-complete but currently has zero real-data coverage.

`deferred-items.md`'s tracked item (the `test_director_read_only_visibility` pagination regression) is fully resolved — confirmed via a clean full-suite run and direct inspection of `config/settings/base.py`.

---

*Verified: 2026-07-24T23:55:02Z*
*Verifier: Claude (gsd-verifier)*
