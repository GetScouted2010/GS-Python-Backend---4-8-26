---
phase: 08-user-workspace-crud
verified: 2026-07-25T06:09:41Z
status: passed
score: 25/25 must-haves verified (across 6 plans)
---

# Phase 8: User Workspace CRUD Verification Report

**Phase Goal:** Authenticated users can build and manage their own scouting workspace on top of real player/club data — save/remove players on a Watchlist, create/name/manage Shortlists tied to a club, create/manage Squad Plans (formation, live current squad, proposed changes), have Recent Activity auto-recorded and retrievable, and export a Shortlist or Club report as CSV.
**Verified:** 2026-07-25T06:09:41Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can save/remove a player on a personal Watchlist (CRUD-06) | VERIFIED | `workspace/views.py::WatchlistViewSet` (list/create/destroy mixins), `get_queryset` filters by `request.user`, `permission_classes=[IsAuthenticated, IsOwner]`. Live-tested: POST → 201, duplicate POST → 400 (`non_field_errors`, unique constraint), unauth GET → 401. |
| 2 | Duplicate watchlist save returns clean 400, not 500 | VERIFIED | `WatchlistSerializer.user = HiddenField(CurrentUserDefault())` participates in DRF's auto unique-together validator sourced from the model's `UniqueConstraint(["user","player"])`. Live-tested: second POST of same player → `400 {'non_field_errors': [...'must make a unique set'...]}`. |
| 3 | User can create/name/manage Shortlists tied to a club, with player entries + notes (CRUD-07) | VERIFIED | `ShortlistViewSet` (full ModelViewSet) + `entries`/`delete_entry` `@action`s using `self.get_object()` to inherit IsOwner from the parent. Live-tested: create shortlist, POST entry → 201, ownership isolation confirmed (see #9). |
| 4 | User can create/manage Squad Plans with formation + live current_squad + proposed_changes (CRUD-08) | VERIFIED | `SquadPlanViewSet` with `get_serializer_class` list/detail split. `SquadPlanDetailSerializer.get_current_squad` computes `PlayerListSerializer(obj.club.players.all(), many=True).data` live (no stored field). Live-tested: detail response's `current_squad` had exactly 1 entry matching the 1 player attached to the club; list response items had no `current_squad` key. |
| 5 | proposed_changes validated at write time (list of dicts, action in add/remove/swap, swap needs incoming_player_id) | VERIFIED | `validate_proposed_changes` in `SquadPlanDetailSerializer`; unit tests `test_proposed_changes_must_be_list`, `test_proposed_changes_bad_action_rejected`, `test_swap_requires_incoming_player_id` all pass. |
| 6 | Recent Activity is auto-recorded on player/club view and retrievable (CRUD-09) | VERIFIED | `PlayerDetailView.get()` (existing method extended, not replaced) writes `RecentActivity.objects.create(...)` immediately after `get_object_or_404`; `ClubDetailView.retrieve()` (new override) wraps `super().retrieve()` and writes after. `RecentActivityListView` (`GET /api/workspace/activity/`) scoped + `order_by("-created_at")`. Live-tested: viewing a player and a club each produced exactly one matching RecentActivity row; response shapes (`"scores" in profile`, club=None fallback) unchanged from Phase 7. |
| 7 | User can export a Shortlist as CSV (CRUD-10) | VERIFIED | `ShortlistViewSet.export` `@action`, IsOwner-gated via `self.get_object()`. Live-tested: `GET /api/workspace/shortlists/{id}/export/` → 200, `Content-Type: text/csv`, `Content-Disposition: attachment; filename=...`, header row = `PLAYER_EXPORT_COLUMNS`, one data row per entry. |
| 8 | User can export a Club report as CSV (CRUD-10) | VERIFIED | `ClubExportView` (new `APIView` in `clubs/views.py`), reuses `ClubDetailSerializer(club).data["transfer_aggregates"]`. Live-tested: `GET /api/clubs/{id}/export/` → 200, `text/csv`, header includes club profile fields + `total_transfers`/`avg_market_value_at_transfer`/etc., exactly 1 data row. Wired at `clubs/urls.py: path("<uuid:pk>/export/", ...)`, registered before the `<uuid:pk>/` detail route so it doesn't get swallowed. |
| 9 | Ownership/scoping is enforced everywhere (no cross-user leakage) | VERIFIED | All 4 workspace list/create surfaces (`WatchlistViewSet`, `ShortlistViewSet`, `SquadPlanViewSet`, `RecentActivityListView`) explicitly filter `get_queryset()` by `request.user` — confirmed IsOwner's `has_object_permission` does NOT run for list/create, so this filtering is load-bearing, not redundant. Live-tested: user B's shortlist export attempted by user A → 404. Test suite covers scoping/ownership for all 4 resources (`grep scoping/ownership` across all 5 test files). |

**Score:** 9/9 truths verified (mapping to the 5 requirement IDs CRUD-06..10)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `workspace/models.py` | 5 models, UUID PKs, UniqueConstraint/Index convention | VERIFIED | Watchlist, Shortlist, ShortlistEntry, SquadPlan, RecentActivity all present; `target_id` confirmed a bare `UUIDField(null=True, blank=True)`, not a ForeignKey; no `unique_together` usage anywhere; no frozen current-squad field on SquadPlan. |
| `workspace/permissions.py::IsOwner` | polymorphic owner resolution | VERIFIED | `obj.user` with fallback to `obj.shortlist.user` for ShortlistEntry. |
| `workspace/views.py` | 4 viewsets/views, all queryset-scoped | VERIFIED | WatchlistViewSet, ShortlistViewSet, SquadPlanViewSet, RecentActivityListView — every one has an explicit `.filter(user=self.request.user)` (or equivalent) in `get_queryset`. |
| `workspace/serializers.py` | Watchlist/Shortlist/ShortlistEntry/SquadPlan(x2)/RecentActivity serializers | VERIFIED | All present; `CurrentUserDefault` hidden-field pattern used consistently; `get_current_squad` derives live from `obj.club.players.all()`. |
| `workspace/urls.py` | router + explicit activity path | VERIFIED | `watchlist`, `shortlists`, `squad-plans` registered on `DefaultRouter`; `activity/` explicit path composed via `[path(...)] + router.urls` (accounts/urls.py precedent). |
| `config/urls.py` | `api/workspace/` include | VERIFIED | `path("api/workspace/", include("workspace.urls"))` present. |
| `config/settings/base.py` | `workspace` in INSTALLED_APPS | VERIFIED | `"workspace",` present. |
| `players/views.py::PlayerDetailView.get` | RecentActivity write, response unchanged | VERIFIED | Write inserted immediately after `get_object_or_404`; method is the same one from Phase 7 (extended, not replaced); `Response({**profile, "scores": scores})` shape intact; club=None fallback branch (RMM + null_with_reason) untouched. |
| `clubs/views.py::ClubDetailView` | `retrieve()` override writing RecentActivity | VERIFIED | `def retrieve(self, request, *args, **kwargs): response = super().retrieve(...); RecentActivity.objects.create(...); return response` — genuine override wrapping the mixin's retrieve, not just a docstring. |
| `clubs/views.py::ClubExportView` + `clubs/urls.py` | CSV export view + wired route | VERIFIED | Class exists, route registered and reachable (live 200 response with correct headers/content). |
| `workspace/views.py::Echo` + shortlist export `@action` | StreamingHttpResponse CSV | VERIFIED | `class Echo` present; `export` `@action(detail=True, url_path="export")` uses `StreamingHttpResponse` + `csv.writer(Echo())`; reachable and returns real CSV content live. |
| `workspace/tests/*.py` (5 files) | integration test coverage | VERIFIED | test_watchlist.py, test_shortlists.py, test_squad_plans.py, test_recent_activity.py, test_csv_export.py — 32 tests total, all passing. |
| `get-scouted-be/pyproject.toml` testpaths | workspace included | VERIFIED | `testpaths = ["clubs", "players", "transfers", "core", "accounts", "scoring", "workspace"]` — confirmed `workspace` is present; full-suite run collects and executes all 32 workspace tests (not silently excluded). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `WatchlistViewSet.get_queryset` | `Watchlist.objects.filter(user=...)` | explicit filter | WIRED | Confirmed in source; IsOwner alone does not cover list/create per DRF semantics — this filter is the actual enforcement mechanism. |
| `ShortlistViewSet.get_queryset` | `Shortlist.objects.filter(user=...)` | explicit filter | WIRED | Confirmed in source. |
| `SquadPlanViewSet.get_queryset` | `SquadPlan.objects.filter(user=...)` | explicit filter | WIRED | Confirmed in source. |
| `RecentActivityListView.get_queryset` | `RecentActivity.objects.filter(user=...).order_by("-created_at")` | explicit filter | WIRED | Confirmed in source; relies on global `IsAuthenticated` default (no IsOwner needed since it's list-only, and filtering already scopes it). |
| `ShortlistViewSet.entries`/`delete_entry` | `self.get_object()` (parent ownership) | `@action(detail=True)` | WIRED | `get_object()` runs `check_object_permissions` (IsOwner) against the parent Shortlist before any entry mutation; cross-user access to `{other's shortlist}/entries/` returns 404 (queryset-scoped `get_object` never finds another user's row). Live-verified for export (same mechanism). |
| `SquadPlanDetailSerializer.get_current_squad` | `players.serializers.PlayerListSerializer` | `obj.club.players.all()` | WIRED | Live-verified: detail response's `current_squad` contained exactly the players attached to the club at request time (no snapshot). |
| `players/views.py PlayerDetailView.get` | `RecentActivity.objects.create(...)` | inline write | WIRED | Live-verified row created on GET; response shape unchanged. |
| `clubs/views.py ClubDetailView.retrieve` | `RecentActivity.objects.create(...)` | `retrieve()` override wrapping `super().retrieve()` | WIRED | Live-verified row created on GET. |
| `config/urls.py` | `workspace.urls` | `include()` | WIRED | `/api/workspace/*` routes all live-tested successfully. |
| `clubs/urls.py` | `ClubExportView` | `path("<uuid:pk>/export/", ...)` registered before `<uuid:pk>/` | WIRED | Live-tested: `GET /api/clubs/{id}/export/` returns CSV, not swallowed by the detail route. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| CRUD-06 | 08-02 (declared also in 08-01 foundation) | Watchlist save/remove | SATISFIED | Truths #1, #2; live-tested end to end. |
| CRUD-07 | 08-03 | Shortlists tied to a club, entries + notes | SATISFIED | Truth #3; live-tested create + entry + ownership isolation. |
| CRUD-08 | 08-04 | Squad Plans, formation, live current_squad, proposed_changes | SATISFIED | Truths #4, #5; live-tested current_squad computed live, list/detail split confirmed, validation unit-tested. |
| CRUD-09 | 08-05 | Recent Activity auto-recorded + retrievable | SATISFIED | Truth #6; live-tested auto-write on player and club view, Phase 7 response contract preserved. |
| CRUD-10 | 08-06 | CSV export of Shortlist or Club report | SATISFIED | Truths #7, #8; live-tested both export endpoints return real streaming CSV with correct headers. |

No orphaned requirements — REQUIREMENTS.md lists exactly CRUD-06..CRUD-10 for Phase 8, and all 5 appear in plan frontmatter `requirements:` fields.

### Anti-Patterns Found

None. Scanned `workspace/*.py`, `workspace/tests/*.py`, `players/views.py`, `clubs/views.py`, `clubs/urls.py` for TODO/FIXME/XXX/HACK/PLACEHOLDER/"not implemented"/empty-body patterns — no matches.

### Specifically Re-Checked Claims (per verification brief)

1. **IsOwner does not cover list/create — every viewset explicitly filters `get_queryset()`.** CONFIRMED true for all 4: `WatchlistViewSet`, `ShortlistViewSet`, `SquadPlanViewSet` all have `permission_classes = [IsAuthenticated, IsOwner]` plus an explicit `.filter(user=self.request.user)` in `get_queryset`; `RecentActivityListView` (no IsOwner needed, list-only) also filters by `user=self.request.user`. Live cross-user test (shortlist export) returned 404 as expected, and pytest scoping/ownership tests pass for all 4 resources.

2. **SquadPlan has no frozen current-squad snapshot field.** CONFIRMED — `workspace/models.py::SquadPlan` has only `id, user, club, name, formation, proposed_changes, created_at, updated_at`; no squad/snapshot field exists. `current_squad` only appears in the serializer as a `SerializerMethodField` computing `PlayerListSerializer(obj.club.players.all(), many=True).data` live. Live-tested: adding a second player to the club produced `current_squad` with matching live count on the next GET (no caching/freezing observed).

3. **pyproject.toml testpaths now includes workspace, and the full suite actually runs+passes workspace's tests.** CONFIRMED — `testpaths` includes `"workspace"`; `pytest --collect-only -q` shows 32 workspace tests collected; full-suite run (`pytest -q`) shows `144 passed, 305 skipped` with `pytest --collect-only -q | grep -c "workspace/tests"` = 32, i.e. workspace's tests are part of the 144 passing, not silently excluded.

4. **ClubDetailView has a real `retrieve()` override; PlayerDetailView.get() was extended, not replaced; club=None fallback unchanged.** CONFIRMED — `ClubDetailView.retrieve()` wraps `super().retrieve()` and is genuine code (not a docstring). `PlayerDetailView.get()` is the same method signature as Phase 7 with only the `RecentActivity.objects.create(...)` line inserted after `get_object_or_404`; the `club_id is None` branch (RMM + `null_with_reason` for the other 3 scores) is byte-for-byte the Phase 7 logic. Phase 7's own test suites (`players/tests/`, `clubs/tests/`) still pass (19 passed / 12 skipped, skips being the pre-existing "no real CSV data" pattern, unrelated to Phase 8).

5. **CSV export endpoints are real, reachable URLs.** CONFIRMED live: `GET /api/workspace/shortlists/{id}/export/` and `GET /api/clubs/{id}/export/` both returned HTTP 200 with `Content-Type: text/csv` and correct `Content-Disposition` headers and parseable CSV bodies in a live Django shell session (not just unit-mocked).

### Human Verification Required

None. All must-haves were verifiable programmatically (model inspection, source grep, automated pytest suite, and live end-to-end requests through Django's test client against a real Postgres test database).

### Gaps Summary

No gaps. All 5 requirement IDs (CRUD-06 through CRUD-10) are implemented, wired, tested, and independently reproduced via live request/response cycles against a real database — including the specific concerns flagged in the verification brief (queryset scoping on all 4 viewsets, no frozen SquadPlan snapshot, workspace tests genuinely included in the full-suite count, genuine `retrieve()`/`get()` overrides preserving Phase 7 contracts, and CSV export routes being real and reachable).

---

_Verified: 2026-07-25T06:09:41Z_
_Verifier: Claude (gsd-verifier)_
