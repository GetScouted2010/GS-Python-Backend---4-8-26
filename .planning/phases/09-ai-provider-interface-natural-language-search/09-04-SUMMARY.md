---
phase: 09-ai-provider-interface-natural-language-search
plan: 04
subsystem: api
tags: [django, drf, anthropic, natural-language-search, recent-activity]

# Dependency graph
requires:
  - phase: 09-ai-provider-interface-natural-language-search
    provides: "Plan 02's get_nl_query_parser() factory (tier 1), Plan 01's NLQueryParserError contract; Plan 03's keyword_extract() (tier 2) and search_players() composition service; Phase 8's RecentActivity model with the 'searched' ActivityType reserved for this producer"
provides:
  - "POST /api/players/search/ — PlayerSearchView orchestrating tier1(LLM)->tier2(keyword)->tier3(unfiltered) natural-language player search, always HTTP 200"
  - "Completed the RecentActivity 'searched' producer contract Phase 8 reserved (activity_type='searched', query_text=<raw>, target_id=None) logged exactly once per search call regardless of tier"
  - "DRF APIClient integration test suite (players/tests/test_search_view.py) proving all 3 tiers, RecentActivity logging, and the auth gate, with the LLM call fully mocked at the caller's own binding"
affects: [10-frontend-integration, any-future-search-consumer]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "3-tier graceful-degradation view: only the tier-1 provider call is wrapped in try/except NLQueryParserError; the deterministic tier-2/tier-3 path and the downstream search_players() call are never swallowed by that except, so a genuine DB error still surfaces as a real 500"
    - "fallback_used semantics: false means 'the LLM's own real answer' (even if filters end up empty/partial); true means the LLM CALL itself failed and tier 2 took over — never conflated"
    - "Test mocking patches the CALLER's own import binding (players.views.get_nl_query_parser), never the definition module — established Phase 6-07/09-RESEARCH.md convention, reused correctly with zero deviation needed"

key-files:
  created:
    - get-scouted-be/players/tests/test_search_view.py
  modified:
    - get-scouted-be/players/views.py
    - get-scouted-be/players/urls.py

key-decisions:
  - "PlayerSearchView wraps ONLY get_nl_query_parser().parse(query) in the tier-1 try/except; search_players() is called outside the try so an unexpected DB error there is a genuine 500, never masked as a fallback"
  - "A successful-but-empty/partial tier-1 LLM parse keeps fallback_used=False (it is still the LLM's real answer); fallback_used only flips true when the LLM call itself raised NLQueryParserError"
  - "No explicit permission_classes set on PlayerSearchView — the project's global IsAuthenticated default already denies anonymous, matching every other players view"
  - "Test 4 renamed from the plan's literal test_search_tier3_unfiltered_when_nothing_extractable to test_search_tier3_fallback_unfiltered_when_nothing_extractable so pytest -k fallback selects both tier-2 and tier-3 tests, per the plan's own acceptance criteria"

patterns-established:
  - "Search view request lifecycle: read raw query -> tier1 try/except -> tier2/tier3 fallback -> search_players(filters, request) -> RecentActivity.objects.create(...) -> Response({query, parsed_filters, fallback_used, results})"

requirements-completed: [AI-01, AI-02]

# Metrics
duration: 14min
completed: 2026-07-25
---

# Phase 09 Plan 04: Natural-Language Search Endpoint (3-Tier Degradation) Summary

**POST /api/players/search/ ties together the LLM parser, deterministic keyword fallback, and unfiltered list into one always-200 endpoint that also completes Phase 8's "searched" RecentActivity contract**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-25T10:07:00Z (approx, per STATE.md session continuity)
- **Completed:** 2026-07-25T10:21:00Z
- **Tasks:** 3 completed
- **Files modified:** 3 (2 modified, 1 created)

## Accomplishments
- `PlayerSearchView(APIView)` implements the full 3-tier degradation contract: tier 1 (LLM parser via `get_nl_query_parser()`), tier 2 (deterministic `keyword_extract()` on `NLQueryParserError`), tier 3 (unfiltered list when tier 2 also yields nothing) — always returns HTTP 200 with `query`/`parsed_filters`/`fallback_used`/`results`.
- Route wired at `POST /api/players/search/` (`players/urls.py`), behind the project's default `IsAuthenticated` gate (no explicit `permission_classes` needed).
- Every call — success or fallback — logs exactly one `RecentActivity(activity_type="searched", query_text=<raw query>, target_id=None)`, completing the producer contract Phase 8 reserved for this exact event.
- Full DRF `APIClient` integration test suite (`players/tests/test_search_view.py`) covers the auth gate, all 3 tiers, RecentActivity logging, and the blank-query safety case — all mocking the LLM at the caller's own binding (`players.views.get_nl_query_parser`), never constructing a real Anthropic client.
- All 3 tiers plus RecentActivity logging live-verified end-to-end against the real 41,708-player dev DB via `manage.py shell` (pytest's own test DB is empty, matching the established real-data-test pattern across this codebase): tier-2 keyword fallback correctly extracted `{"position": "FWD", "market_value_max": 5000000}` from "strikers under 5m" (4,504 matching players); tier-3 correctly returned the full unfiltered 41,708-player count for an unparseable query; a mocked tier-1 success correctly returned `fallback_used=False` with 25 real CB-position results and logged exactly one RecentActivity row.
- Full test suite run clean: **174 passed, 315 skipped, 0 failed** — all Phase 9 AI test files (`test_ai_base`, `test_ai_safety_net`, `test_ai_anthropic_parser`, `test_ai_factory`, `test_ai_fallback`, `test_services_search`, `test_search_view`) collected and passing/skipping cleanly; zero regression in Phases 7/8's players/clubs/workspace tests.

## Task Commits

Each task was committed atomically:

1. **Task 1: PlayerSearchView (POST) — 3-tier orchestration + RecentActivity logging + URL route** - `17009e7` (feat)
2. **Task 2: DRF APIClient integration tests — all 3 tiers, RecentActivity, auth gate** - `651c22b` (test)
3. **Task 3: Full-suite regression gate** - no file changes; verification-only task, results recorded below

**Plan metadata:** (this commit) `docs(09-04): complete natural-language search endpoint plan`

## Files Created/Modified
- `get-scouted-be/players/views.py` - Added `PlayerSearchView(APIView)` implementing the 3-tier NL search orchestration + RecentActivity logging
- `get-scouted-be/players/urls.py` - Added `path("search/", PlayerSearchView.as_view(), name="player-search")`
- `get-scouted-be/players/tests/test_search_view.py` - New DRF APIClient integration test suite: auth gate, tier-1 success, tier-2 fallback, tier-3 unfiltered, RecentActivity logging, blank-query safety

## Decisions Made
- Only the tier-1 LLM call is wrapped in the `try/except NLQueryParserError` block; `search_players()` is called outside that block so a genuine DB error there surfaces as a real 500 rather than being mistaken for a fallback case (matches the plan's explicit instruction).
- `fallback_used` semantics kept strict: `False` means "the LLM's real answer" even when its filters are empty/partial; it only flips `True` when the LLM call itself failed and tier 2 took over. This avoids conflating "the LLM legitimately found nothing to filter on" with "the LLM was unreachable."
- Renamed the plan's literal test name `test_search_tier3_unfiltered_when_nothing_extractable` to `test_search_tier3_fallback_unfiltered_when_nothing_extractable` so `pytest -k fallback` actually selects both the tier-2 and tier-3 tests, satisfying the plan's own acceptance criterion (`Test names include ones matched by -k fallback (tiers 2 and 3)`).

## Deviations from Plan

None (other than the test-naming tweak documented above, which is a straightforward mechanical fix to satisfy the plan's own stated acceptance criterion, not a functional change). Plan executed exactly as written otherwise.

## Issues Encountered

None. The autouse `_block_real_anthropic_calls` guard in `players/tests/conftest.py` (built in Plan 01) combined with patching `players.views.get_nl_query_parser` directly meant no test ever attempted a real Anthropic client construction — verified by the clean full-suite run producing no `RuntimeError` from that guard.

## User Setup Required

None - no external service configuration required. (Real Anthropic API key configuration for live tier-1 usage remains an existing Phase 9 concern documented in STATE.md, unrelated to this plan's scope.)

## Next Phase Readiness

- Phase 9 (AI Provider Interface & Natural Language Search) is now feature-complete: factory (09-01/09-02), fallback + search composition (09-03), and this endpoint (09-04) together satisfy AI-01 (structured NL search) and AI-02 (graceful degradation, never an error).
- CRUD-09's "searched" RecentActivity event now has a real producer; `/api/workspace/activity/` (Phase 8) will surface real search history going forward.
- Full suite green (174 passed, 315 skipped, 0 failed) protects Phases 7/8 from any Phase 9 regression.
- Phase 9 goal-backward verification (against 09-CONTEXT.md / 09-VALIDATION.md) is the natural next step before this phase is marked complete in ROADMAP.md.

---
*Phase: 09-ai-provider-interface-natural-language-search*
*Completed: 2026-07-25*

## Self-Check: PASSED

All created files confirmed present on disk; both task commits (17009e7, 651c22b) confirmed present in git history.
