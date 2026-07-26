---
phase: 10-ai-grounded-report-generation
plan: 03
subsystem: api
tags: [django, drf, llm-orchestration, grounding, scouting-report]

# Dependency graph
requires:
  - phase: 10-ai-grounded-report-generation (10-01/10-02)
    provides: "ReportGenerator/GeneratedReport/ReportGeneratorError contract, grounding validation with bounded retry, get_report_generator() provider-agnostic factory"
  - phase: 04-scoring-engine-port (04-05)
    provides: "scoring.services.summary.get_summary(player_id, club_id) -- the exact grounding-data source this plan's service assembles into the report prompt"
provides:
  - "generate_scouting_report(player_id, club_id) service: get_summary grounding -> get_report_generator().generate -> {narrative, grounding}"
  - "POST /api/players/{id}/scouting-report/ endpoint (PlayerScoutingReportView)"
  - "Clean 503 on ReportGeneratorError (never a fabricated report); clean 400 when no club context resolvable"
affects: [11-club-insights-report-generation, ai-report-generation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Thin view / fat-nothing service: the view resolves club_id and maps ReportGeneratorError -> 503; ALL grounding/retry/validation logic stays inside the 10-02 generator, never re-implemented at the orchestration layer"
    - "Module-top factory import (from players.ai.report_factory import get_report_generator) so tests patch the caller's own binding (players.services.get_report_generator), matching the test_search_view.py / STATE.md Phase-6/9 established convention"

key-files:
  created:
    - get-scouted-be/players/tests/test_scouting_report_view.py
  modified:
    - get-scouted-be/players/services.py
    - get-scouted-be/players/views.py
    - get-scouted-be/players/urls.py

key-decisions:
  - "generate_scouting_report does NOT catch ReportGeneratorError -- it propagates untouched to the view, which is the only place that maps it to a clean 503. This makes a fabricated/template report structurally impossible at the service layer."
  - "club_id resolution (request.data club_id or player.club_id) happens in the VIEW before calling the service, mirroring PlayerDetailView's existing club_id-branch pattern -- get_summary is never called with club_id=None, avoiding its misleading Http404 for a genuinely club-less player (surfaced instead as a clean 400)."
  - "Unknown/unresolvable club_id (a real but nonexistent UUID) is deliberately left to surface as get_summary's natural Http404 -> DRF's standard 404, matching PlayerDetailView's posture -- not caught or converted."

requirements-completed: [AI-03]

duration: 12min
completed: 2026-07-26
---

# Phase 10 Plan 03: Player Scouting-Report Endpoint Summary

**POST /api/players/{id}/scouting-report/ composes get_summary's grounding with the Wave-2 provider-agnostic ReportGenerator into a structured {narrative, grounding} response, returning a clean 503/400 instead of ever fabricating a report.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2
- **Files modified:** 4 (3 existing files edited, 1 test file created)

## Accomplishments

- `generate_scouting_report(player_id, club_id)` service in `players/services.py`: assembles grounding from the already-tested `get_summary()`, runs it through `get_report_generator().generate(grounding, "player_scouting_report")`, returns `{"narrative": ..., "grounding": ...}`, and deliberately lets `ReportGeneratorError` propagate uncaught.
- `PlayerScoutingReportView` (`players/views.py`) wired at `POST /api/players/{id}/scouting-report/`: resolves `club_id` from the request body or the player's own club, returns a clean 400 if neither is available, calls the service, and maps `ReportGeneratorError` to a clean 503 — never a fabricated/template report reaches the response body.
- 7 tests in `players/tests/test_scouting_report_view.py` covering the service in isolation (happy path, error propagation, grounding-passed-unchanged) and the endpoint end-to-end (auth gate, success, clean 503 on generator failure with an explicit no-narrative-leakage assertion, clean 400 on missing club context with the generator/summary calls asserted never invoked).

## Task Commits

Each task was committed atomically:

1. **Task 1: generate_scouting_report() service (grounding assembly + generation orchestration)** - `b2c6811` (feat)
2. **Task 2: PlayerScoutingReportView + route + endpoint integration tests** - `ff709e1` (feat)

**Plan metadata:** (this commit) `docs(10-03): complete player scouting-report plan`

## Files Created/Modified

- `get-scouted-be/players/services.py` - Added `generate_scouting_report(player_id, club_id)`, module-top imports of `get_report_generator` and `get_summary`
- `get-scouted-be/players/views.py` - Added `PlayerScoutingReportView(APIView)` with the club_id-resolution + `ReportGeneratorError` -> 503 mapping
- `get-scouted-be/players/urls.py` - Added the `<uuid:pk>/scouting-report/` route (placed before the bare detail route)
- `get-scouted-be/players/tests/test_scouting_report_view.py` - 3 service-level tests + 4 endpoint-level tests (auth gate, success, failure/503, missing-club/400)

## Decisions Made

- `generate_scouting_report` never wraps the generator call in try/except -- `ReportGeneratorError` propagates to the view by design, so a fabricated report is structurally impossible at the service layer (only the view decides the HTTP mapping).
- club_id resolution happens in the view (request body `club_id` or the player's own `club_id`), mirroring `PlayerDetailView`'s existing pattern, so `get_summary` is never invoked with `club_id=None` (which would otherwise raise a misleading `Http404` for a genuinely club-less player instead of a clean 400).
- An unresolvable-but-present `club_id` (nonexistent UUID) is left to surface as `get_summary`'s natural `Http404` -> standard DRF 404, matching `PlayerDetailView`'s existing posture -- not intercepted.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. (Uses the same `LLM_PROVIDER`/`ANTHROPIC_REPORT_MODEL` settings already configured in 10-01/10-02; all tests here use an injected fake generator, never a real Anthropic call.)

## Next Phase Readiness

- AI-03 is now complete end-to-end: real grounding -> real (mockable-in-tests) LLM narrative -> clean error handling, all proven by integration tests hitting the real DRF endpoint with `force_authenticate`.
- `players/services.py`'s `generate_scouting_report` establishes the exact orchestration shape (grounding source -> factory -> propagate-error) that Phase 11's club-insights report generation (AI-04, `report_type="club_insights"`) can mirror directly against the same `ReportGenerator` interface.
- Full backend suite verified green: 204 passed, 315 skipped (real-data/oracle tests skip cleanly against the empty pytest test DB, matching every prior phase's pattern), 0 failed -- no regression to Phases 1-9 or 10-01/10-02.

---
*Phase: 10-ai-grounded-report-generation*
*Completed: 2026-07-26*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commit hashes (b2c6811, ff709e1) verified present in git log.
