---
phase: 10-ai-grounded-report-generation
plan: 02
subsystem: ai
tags: [anthropic, llm, report-generation, grounding, factory-pattern]

# Dependency graph
requires:
  - phase: 10-ai-grounded-report-generation (Plan 10-01)
    provides: "ReportGenerator/GeneratedReport/ReportGeneratorError interface + validate_grounding() numeric-grounding validator"
provides:
  - "AnthropicReportGenerator: plain (non-tool-use) Anthropic Messages API report generator, section-parsed narrative, grounding-validated with retry-once"
  - "get_report_generator(): provider-agnostic factory dispatching on settings.LLM_PROVIDER"
affects: ["10-03 (player scouting report slice)", "10-04 (club insights slice)", "10-05 (wave-3 wiring/verification)"]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Plain (non-tool-use) client.messages.create() call for free-form narrative generation, distinct from Phase 9's forced tool-use extraction pattern"
    - "Bounded retry-once loop for grounding-validation failure, with corrective feedback appended to the retry prompt naming the specific ungrounded numbers"
    - "Section-delimited markdown parsing via re.split on an exact `## <Header>` alternation anchored per-line"

key-files:
  created:
    - get-scouted-be/players/ai/anthropic_report_generator.py
    - get-scouted-be/players/ai/report_factory.py
    - get-scouted-be/players/tests/test_ai_anthropic_report_generator.py
    - get-scouted-be/players/tests/test_ai_report_factory.py
  modified: []

key-decisions:
  - "Reworded the module docstring to avoid the literal substrings 'tool_choice'/'tools=' anywhere in anthropic_report_generator.py, since the plan's own acceptance-criteria grep for those patterns is meant to prove NO forced tool-use kwargs are used anywhere in the file, including comments"
  - "generate() implements the retry as a bounded 2-iteration for-loop (never unbounded recursion), matching the plan's explicit bounded-retry requirement"

patterns-established:
  - "Header-to-key mapping (_header_to_key): lowercase + replace spaces/hyphens with underscores, applied uniformly to both PLAYER_SECTIONS and CLUB_SECTIONS so future report types need only a new SECTIONS_BY_TYPE entry"

requirements-completed: [AI-03, AI-04]

# Metrics
duration: 12min
completed: 2026-07-26
---

# Phase 10 Plan 02: Anthropic Report Generator + Factory Summary

**Plain-text (non-tool-use) AnthropicReportGenerator with section-parsed narrative, grounding-validated with retry-once, plus get_report_generator() provider-agnostic factory**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-26T05:00:00Z (approx.)
- **Completed:** 2026-07-26T05:07:00Z
- **Tasks:** 2
- **Files modified:** 4 (all created)

## Accomplishments
- `AnthropicReportGenerator.generate()` calls plain `client.messages.create()` (no `tools`/`tool_choice`), extracts narrative from `TextBlock.text`, and parses it into report-type-specific named sections (5 for `player_scouting_report`, 3 for `club_insights`)
- Every generated narrative is validated via `validate_grounding()` before being returned; on failure the generator retries generation exactly once with corrective feedback naming the offending numbers, then raises `ReportGeneratorError` rather than ever returning a partially-fabricated report
- `get_report_generator()` dispatches on `settings.LLM_PROVIDER` with a lazy in-branch import, mirroring Phase 9's `get_nl_query_parser()` exactly, so calling code (Plans 10-03/10-04) never imports a concrete generator class
- 10 new tests, all using an injected fake client (no real Anthropic client ever constructed) -- full `players` suite remains green (65 passed, 16 skipped, 0 failed)

## Task Commits

Each task was committed atomically:

1. **Task 1: AnthropicReportGenerator (plain generation + section parse + grounding + retry-once)** - `91614d6` (feat)
2. **Task 2: get_report_generator() factory** - `f1669f1` (feat)

**Plan metadata:** (this commit) `docs(10-02): complete plan`

## Files Created/Modified
- `get-scouted-be/players/ai/anthropic_report_generator.py` - Concrete `AnthropicReportGenerator`: `PLAYER_SECTIONS`/`CLUB_SECTIONS`/`SECTIONS_BY_TYPE`, `_header_to_key`, lazy-DI `generate()` with bounded retry-once grounding validation
- `get-scouted-be/players/ai/report_factory.py` - `get_report_generator()` provider-agnostic factory (lazy in-branch import, `ValueError` on unknown provider)
- `get-scouted-be/players/tests/test_ai_anthropic_report_generator.py` - 7 tests: player/club happy path, missing-header error, API-error error, grounding-retry-then-raise, grounding-retry-then-recover, DI/no-tool-kwargs assertion
- `get-scouted-be/players/tests/test_ai_report_factory.py` - 3 tests: anthropic dispatch + isinstance checks, unknown-provider ValueError, sole-import-needed assertion

## Decisions Made
- Docstring wording deliberately avoids the literal strings `tool_choice`/`tools=` anywhere in the generator module (including prose) so the plan's acceptance-criteria grep genuinely proves the absence of forced tool-use, not just the absence of the kwargs in code
- Retry loop bounded at `MAX_ATTEMPTS = 2` via a plain `for` loop rather than recursion, avoiding any possibility of unbounded retries

## Deviations from Plan

None - plan executed exactly as written. One self-correction during execution: the initial docstring draft used the words "tools"/"tool_choice" in backticks to describe what was *not* used, which itself satisfied the literal grep pattern the plan's acceptance criteria checks against (`grep -n "tool_choice\|tools="` expecting zero matches) -- reworded before committing, no separate fix-commit needed since it was caught pre-commit.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required. `ANTHROPIC_API_KEY`/`ANTHROPIC_REPORT_MODEL`/`LLM_PROVIDER` settings already exist from Plan 10-01.

## Next Phase Readiness
- Plans 10-03 (player scouting report) and 10-04 (club insights) can now call `get_report_generator().generate(grounding, report_type)` directly, catching only `ReportGeneratorError` -- no grounding/retry logic needs to live in their views
- Full `players` test suite green (65 passed, 16 skipped, 0 failed) -- no regression against Phase 9's AI tests
- The autouse `_block_real_anthropic_calls` guard remains intact; no test in this plan constructs a real Anthropic client

---
*Phase: 10-ai-grounded-report-generation*
*Completed: 2026-07-26*

## Self-Check: PASSED

All created files found on disk; both task commits (91614d6, f1669f1) found in git history.
