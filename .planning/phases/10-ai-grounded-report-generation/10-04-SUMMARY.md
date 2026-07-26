---
phase: 10-ai-grounded-report-generation
plan: 04
subsystem: api
tags: [django, drf, anthropic, orm-aggregation, club-insights, ai]

# Dependency graph
requires:
  - phase: 10-ai-grounded-report-generation (plan 02)
    provides: "players/ai/report_generator.py (ReportGenerator/GeneratedReport/ReportGeneratorError) + players/ai/report_factory.py (get_report_generator())"
provides:
  - "clubs/services.py: position_needs_aggregate(club) + generate_club_insights(club_id)"
  - "POST /api/clubs/{id}/insights/ (ClubInsightsView)"
  - "clubs/tests/conftest.py autouse _block_real_anthropic_calls guard (closes cross-app safety-net gap)"
affects: [phase-11-position-needs, phase-11-squad-simulation]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Per-app duplicated autouse pytest safety-net fixture (clubs/tests/ mirrors players/tests/, since conftest fixtures are directory-scoped, not inherited across sibling app test dirs)"
    - "Bounded single-entity ORM .values().annotate() group-by for internal-only grounding aggregates (never pandas), matching Phase 6 SCORE-07 precedent"
    - "Cross-app AI orchestration: clubs/services.py imports players.ai.report_factory.get_report_generator(), mirroring clubs/serializers.py's existing players.serializers import precedent"

key-files:
  created:
    - get-scouted-be/clubs/tests/test_ai_safety_net.py
    - get-scouted-be/clubs/services.py
    - get-scouted-be/clubs/tests/test_services_club_insights.py
    - get-scouted-be/clubs/tests/test_ai_club_insights.py
  modified:
    - get-scouted-be/clubs/tests/conftest.py
    - get-scouted-be/clubs/views.py
    - get-scouted-be/clubs/urls.py

key-decisions:
  - "position_needs_aggregate is a single bounded ORM .values('position').annotate() query scoped to club.players (related_name), never pandas -- matches 10-RESEARCH.md Pattern 4 and Phase 6 SCORE-07's no-full-dataset-op precedent"
  - "generate_club_insights calls ClubDetailSerializer().get_transfer_aggregates(club) directly on a bare instance to avoid triggering the heavy get_squad serialization"
  - "ReportGeneratorError is deliberately NOT caught in clubs/services.py -- ClubInsightsView.post is the single catch point, mapping it to a clean 503 (locked decision #6, never a fabricated report)"

patterns-established:
  - "AI-04 grounding dict shape: {club: {name, league}, position_needs: {...}, transfer_aggregates: {...}}"

requirements-completed: [AI-04]

duration: 12min
completed: 2026-07-26
---

# Phase 10 Plan 04: Club Insights (AI-04) Summary

**POST /api/clubs/{id}/insights/ generates AI narrative (recruitment_gaps/over_aged_positions/financial_constraints) grounded in a bounded single-club ORM position-needs aggregation plus reused transfer-behaviour aggregates, with a clean 503 on generation failure and its own ported Anthropic-blocking test safety net.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-26T05:07:00Z (approx)
- **Completed:** 2026-07-26T05:17:00Z
- **Tasks:** 3
- **Files modified:** 7 (3 created new modules/tests, 1 new test file, 3 existing files extended)

## Accomplishments
- Closed the confirmed cross-app safety-net gap: `clubs/tests/conftest.py` now has its own autouse `_block_real_anthropic_calls` fixture (ported verbatim from `players/tests/conftest.py`), proven by a dedicated test, sequenced and committed FIRST before any club-insights test ran.
- `clubs/services.py::position_needs_aggregate(club)` -- a single bounded ORM `.values("position").annotate(...)` group-by (squad_depth/avg_age/contracts_expiring_within_12mo per position), scoped to one club's squad, never pandas.
- `clubs/services.py::generate_club_insights(club_id)` -- combines position needs with `ClubDetailSerializer.get_transfer_aggregates` (reused, not re-derived) into a grounding dict, generates narrative via the cross-app `players.ai.report_factory.get_report_generator()`, and propagates `ReportGeneratorError` unswallowed.
- `ClubInsightsView` (POST `/api/clubs/{id}/insights/`) -- returns `{narrative, grounding}` on success, a clean 503 on `ReportGeneratorError`, and a natural 404 for an unknown club.
- AI-04 is now complete end-to-end and marked `[x]` in REQUIREMENTS.md (via `requirements mark-complete`).

## Task Commits

Each task was committed atomically:

1. **Task 1: Port the autouse Anthropic-block safety net into clubs/tests/** - `4d2222f` (test)
2. **Task 2: clubs/services.py -- position_needs_aggregate() + generate_club_insights()** - `7dd62b1` (feat)
3. **Task 3: ClubInsightsView + route + endpoint integration tests** - `651758c` (feat, see Deviations -- swept into a concurrent 10-03 executor's completion commit due to a parallel-execution git race)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/clubs/tests/conftest.py` - Appended the ported autouse `_block_real_anthropic_calls` guard (real_data_available preserved)
- `get-scouted-be/clubs/tests/test_ai_safety_net.py` - Proves the guard is active in clubs/tests/
- `get-scouted-be/clubs/services.py` - New module: position_needs_aggregate + generate_club_insights
- `get-scouted-be/clubs/tests/test_services_club_insights.py` - 6 tests: aggregation shape, single-club scope, contract null-safety/cutoff boundary, generate happy path, error propagation
- `get-scouted-be/clubs/views.py` - Added ClubInsightsView (POST, catches ReportGeneratorError -> 503)
- `get-scouted-be/clubs/urls.py` - Added `<uuid:pk>/insights/` route
- `get-scouted-be/clubs/tests/test_ai_club_insights.py` - 4 endpoint integration tests: success, failure->503, unknown club->404, auth gate

## Decisions Made
- position_needs_aggregate implemented exactly per 10-RESEARCH.md Pattern 4 (single bounded ORM query, cutoff = today + 365 days, contract_expires__isnull=False guard).
- generate_club_insights calls `ClubDetailSerializer().get_transfer_aggregates(club)` directly on a bare instance (no queryset/context needed) to avoid triggering the heavier `get_squad` serialization path.
- ClubInsightsView carries no explicit permission_classes (global IsAuthenticated default), matching ClubExportView's precedent since club data is not user-owned.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Formatted position_needs_aggregate's ORM chain to keep `.values("position").annotate(` on one line**
- **Found during:** Task 2
- **Issue:** Initial multi-line formatting split `.values("position")` and `.annotate(` across lines, which would have failed the plan's literal grep-based acceptance check for the bounded-query pattern.
- **Fix:** Reformatted to match the plan's exact code shape (single-line `.values("position").annotate(`), matching 10-RESEARCH.md Pattern 4's example verbatim.
- **Files modified:** get-scouted-be/clubs/services.py
- **Verification:** `grep -n '\.values("position")\.annotate('` matches; full test suite still green.
- **Committed in:** 7dd62b1 (Task 2 commit)

### Notable Non-Code Deviation (informational, not a Rule 1-4 fix)

**Parallel execution git race:** A concurrent executor was running plan 10-03 (player scouting-report) in the same working tree at the same time as this plan. Task 3's `git add` staged `clubs/views.py`, `clubs/urls.py`, and `clubs/tests/test_ai_club_insights.py`, but before this agent's own commit ran, the 10-03 executor's `docs(10-03): complete player scouting-report plan` commit (`651758c`) captured those already-staged files alongside its own `.planning/*` updates. The content is verified correct and fully authored by this plan (confirmed via `git show 651758c -- get-scouted-be/clubs/views.py`), and `git diff` confirms zero uncommitted changes remain -- so no functional impact, only a commit-message/attribution artifact. No further action taken; documented here for traceability.

---

**Total deviations:** 1 auto-fixed (Rule 3 - blocking/acceptance-criteria formatting) + 1 informational (concurrent-execution commit attribution, no functional impact)
**Impact on plan:** Zero scope creep; all three tasks' code and tests are fully present, correct, and verified.

## Issues Encountered
None beyond the documented deviations above.

## User Setup Required

None - no external service configuration required. `ANTHROPIC_API_KEY`/`ANTHROPIC_REPORT_MODEL` were already configured in Phase 9/10-01.

## Next Phase Readiness
- AI-04 (club insights) is complete end-to-end: bounded ORM grounding + cross-app LLM generation + clean-error contract, matching AI-03's (10-03) sibling pattern exactly.
- Phase 11's full canonical Position Needs feature (strong/weak/at-risk labels, public endpoint) can build on top of this plan's narrower internal aggregation without conflict -- different scope, same underlying `Player.position/age/contract_expires` fields.
- 10-05 (the remaining Phase 10 plan) can proceed independently.

---
*Phase: 10-ai-grounded-report-generation*
*Completed: 2026-07-26*

## Self-Check: PASSED

All 7 created/modified source files confirmed present on disk; all 3 task commit hashes (4d2222f, 7dd62b1, 651758c) confirmed present in git history.
