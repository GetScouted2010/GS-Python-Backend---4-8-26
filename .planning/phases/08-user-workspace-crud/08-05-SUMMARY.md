---
phase: 08-user-workspace-crud
plan: 05
subsystem: workspace-recent-activity
tags: [recent-activity, crud-09, players-views, clubs-views, workspace]
dependency_graph:
  requires:
    - 08-01 (RecentActivity model, IsOwner permission)
    - Phase 7 (PlayerDetailView, ClubDetailView)
  provides:
    - RecentActivity auto-logging on player/club detail GET
    - GET /api/workspace/activity/ (owner-scoped, newest-first)
  affects:
    - players/views.py::PlayerDetailView.get (additive write, no response change)
    - clubs/views.py::ClubDetailView (new retrieve() override, no response change)
tech_stack:
  added: []
  patterns:
    - "Explicit RecentActivity.objects.create() write inside the existing view method (no signals), matching the codebase's explicit-over-implicit convention"
    - "generics.RetrieveAPIView needs a retrieve() override (not a bare method insertion) to hook post-response side effects, since RetrieveModelMixin has no other extension point"
key_files:
  created:
    - get-scouted-be/workspace/tests/test_recent_activity.py
  modified:
    - get-scouted-be/workspace/serializers.py
    - get-scouted-be/workspace/views.py
    - get-scouted-be/workspace/urls.py
    - get-scouted-be/players/views.py
    - get-scouted-be/clubs/views.py
decisions:
  - "RecentActivityListView left with no explicit permission_classes override (unlike Watchlist/Shortlist/SquadPlan viewsets) -- it only needs get_queryset() scoping since there is no per-object action, so the global IsAuthenticated default already denies anonymous requests with a clean 401"
  - "workspace/tests/test_recent_activity.py monkeypatches players.views.rmm.get_rmm (autouse fixture) because a bare PlayerFactory() has no club, and PlayerDetailView's club=None branch calls rmm.get_rmm() directly -- which would otherwise attempt a full scoring-engine population reconstruction against the empty pytest test DB (mirrors players/tests/test_views.py's established club=None test pattern)"
  - "Regression protection went beyond the plan's own pytest-based verification: also live-verified via manage.py shell against the real 41,708-player/1,060-club dev DB (pytest's own test DB is empty, per the project's established pattern) to confirm the real club!=None scoring path (get_summary) and ClubDetailSerializer's squad/transfer_aggregates are byte-identical post-change"
metrics:
  duration_minutes: 8
  tasks_completed: 3
  files_changed: 6
  completed_date: "2026-07-25"
---

# Phase 8 Plan 5: Recent Activity Auto-Logging Summary

Backend-only "viewed players/clubs" tracking: every authenticated GET to `/api/players/{id}/` or `/api/clubs/{id}/` now writes an owner-scoped `RecentActivity` row (no signals, no frontend cooperation required), retrievable via a new newest-first `/api/workspace/activity/` endpoint.

## What Was Built

**RecentActivitySerializer + RecentActivityListView + URL (Task 1).** A read-only `ModelSerializer` over `RecentActivity` (id, activity_type, target_id, query_text, created_at) and a `generics.ListAPIView` whose `get_queryset()` filters to `request.user` and orders `-created_at`. Wired at `GET /api/workspace/activity/`, composed alongside the existing router (`watchlist/`, `shortlists/`, `squad-plans/`) using the same `[path(...)] + router.urls` pattern already established in `accounts/urls.py`.

**RecentActivity writes in Phase 7's detail views (Task 2).** `PlayerDetailView.get()` now creates a `viewed_player` row immediately after `get_object_or_404` confirms the player exists -- before any scoring/serialization work, and without touching the `Response({**profile, "scores": scores})` return. `ClubDetailView` (a plain `RetrieveAPIView` with no prior method override) gained a `retrieve()` override that wraps `super().retrieve()`, writing a `viewed_club` row using `kwargs["pk"]` after the parent call succeeds (so a 404 on an unknown club never gets logged). Both writes use `target_id` as a bare UUID (no FK), matching `RecentActivity.target_id`'s no-cascade-risk design from 08-01.

**test_recent_activity.py (Task 3).** Six tests: auto-logging on player view, auto-logging on club view, newest-first ordering, owner scoping (another user's view never leaks into A's activity feed), Phase 7 response-shape preservation (`scores` + `player` keys still present), and 401 on unauthenticated access to the activity endpoint.

## Deviations from Plan

### Auto-fixed Issues

None -- the plan's literal code for all three tasks was implemented as written (serializer/view/URL shapes, insertion points in `players/views.py` and `clubs/views.py`, and the test list) with no bugs, missing functionality, or blockers encountered.

One addition beyond the plan's literal verification commands: because `PlayerFactory()` (used across the test suite) creates players with `club=None`, and `PlayerDetailView`'s `club=None` branch calls `rmm.get_rmm()` directly, hitting `/api/players/{id}/` in a test against the empty pytest test DB would otherwise crash with a `ValueError` from a real scoring-engine population reconstruction (no migrated club/team playing-style data exists in the test DB). This is not a bug introduced by this plan -- it is the same constraint `players/tests/test_views.py::test_detail_club_none_returns_null_with_reason` already works around. `workspace/tests/test_recent_activity.py` follows that exact established pattern: an autouse `monkeypatch` fixture stubs `players.views.rmm.get_rmm` for every test in the file. This is test-infrastructure scaffolding, not a change to application code, and required no user decision.

## Verification Performed

- `cd get-scouted-be && python manage.py check` -- 0 issues (via the project's `.venv`; the ambient pyenv interpreter lacks `sklearn`, matching prior phases' documented constraint)
- `pytest players/tests/ clubs/tests/ -x` -- 19 passed, 12 skipped (real-data-gated tests skip cleanly against the empty pytest test DB, per established project pattern) -- confirms zero regression in Phase 7's already-shipped detail-view tests
- `pytest workspace/tests/test_recent_activity.py -x` -- 6 passed
- `pytest` (full suite) -- **112 passed, 305 skipped, 0 failed** -- confirms the RecentActivity insertion caused no regressions anywhere in the codebase, satisfying the plan's per-wave full-suite rule
- Live-verified against the real dev DB (41,708 players / 1,060 clubs) via `manage.py shell`, exercising the actual `club != None` production path (unlike the monkeypatched pytest tests):
  - `GET /api/players/{real-player-with-club}/` -> 200, `scores` dict still has all 4 keys (`rmm`, `compatibility`, `financial_fit`, `transfer_probability`)
  - `GET /api/clubs/{real-club}/` -> 200, `squad` key still present
  - Both calls produced exactly 2 new `RecentActivity` rows for the test user, `GET /api/workspace/activity/` returned them newest-first (`viewed_club` then `viewed_player`)
  - Test data cleaned up (`RecentActivity` rows + test user deleted) after verification

## Self-Check: PASSED

- FOUND: get-scouted-be/workspace/tests/test_recent_activity.py
- FOUND: get-scouted-be/workspace/serializers.py (RecentActivitySerializer)
- FOUND: get-scouted-be/workspace/views.py (RecentActivityListView)
- FOUND: get-scouted-be/workspace/urls.py ("activity/" path)
- FOUND: get-scouted-be/players/views.py (activity_type="viewed_player")
- FOUND: get-scouted-be/clubs/views.py (def retrieve, activity_type="viewed_club")
- FOUND commit 508fb5d (Task 1)
- FOUND commit d5857d4 (Task 2)
- FOUND commit 576e8e7 (Task 3)
