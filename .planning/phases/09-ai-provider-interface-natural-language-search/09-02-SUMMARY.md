---
phase: 09-ai-provider-interface-natural-language-search
plan: 02
subsystem: api
tags: [anthropic, llm, tool-use, natural-language-search, factory-pattern]

# Dependency graph
requires:
  - phase: 09-ai-provider-interface-natural-language-search (Plan 01)
    provides: "NLQueryParser ABC, ParsedQuery/NLQueryParserError, LLM_PROVIDER/ANTHROPIC_API_KEY/ANTHROPIC_MODEL settings, autouse _block_real_anthropic_calls test guard"
provides:
  - "AnthropicNLQueryParser(NLQueryParser) -- forced tool-use extraction against the real PlayerFilter/ClubFilter whitelist"
  - "get_nl_query_parser() factory dispatching on settings.LLM_PROVIDER"
  - "Defensive _validate() that drops hallucinated position/league enum values and unknown keys before filters reach the ORM"
affects: [09-03, 09-04, natural-language-search-view]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Forced tool-use (tool_choice={type:tool,name:...}) for schema-constrained LLM extraction instead of free-text prompting + parsing"
    - "Lazy client construction inside parse() (not __init__) as the dependency-injection seam that lets tests avoid the autouse real-API-call guard"
    - "Catch the parent SDK exception class (anthropic.APIError) rather than narrow subclasses, so every real failure mode maps to the same fallback signal"
    - "Provider factory with lazy in-branch import of the concrete class, so calling code has exactly one import to swap providers"

key-files:
  created:
    - get-scouted-be/players/ai/anthropic_parser.py
    - get-scouted-be/players/ai/factory.py
    - get-scouted-be/players/tests/test_ai_anthropic_parser.py
    - get-scouted-be/players/tests/test_ai_factory.py
  modified: []

key-decisions:
  - "Caught the parent anthropic.APIError (not a narrow subclass) so RateLimitError/APITimeoutError/APIConnectionError/all APIStatusError subclasses all route to NLQueryParserError uniformly, per 09-RESEARCH.md's verified SDK exception hierarchy"
  - "ANTHROPIC_MODEL read exclusively from settings.ANTHROPIC_MODEL (never hardcoded), reusing the env-driven default from Plan 01"
  - "_validate() whitelists both key names and position/league enum values -- a hallucinated position is silently dropped rather than passed to the ORM, since an invalid position value would otherwise produce a misleading zero-result query instead of degrading gracefully"

patterns-established:
  - "Provider concrete classes accept an injectable client and construct the real SDK client lazily inside the method that needs it, never in __init__ -- this is the seam any future provider (OpenAI, etc.) should reuse to stay testable under the autouse network-blocking guard"

requirements-completed: [AI-01, AI-05]

# Metrics
duration: 10min
completed: 2026-07-25
---

# Phase 09 Plan 02: Anthropic Provider Implementation + Factory Summary

**AnthropicNLQueryParser using forced tool-use against the real PlayerFilter/ClubFilter whitelist, plus get_nl_query_parser() factory selecting it from settings.LLM_PROVIDER**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-25T09:56:20Z
- **Completed:** 2026-07-25T10:06:00Z
- **Tasks:** 2 completed
- **Files modified:** 4 (all new)

## Accomplishments
- `AnthropicNLQueryParser.parse()` maps a mocked tool-use response into a `ParsedQuery` whose filters are restricted to the real PlayerFilter/ClubFilter whitelist (10 positions, 25 leagues, 4 score thresholds, 8 style fields)
- Every `anthropic.APIError` failure mode (rate-limit, timeout, connection, auth, 5xx) plus malformed/empty tool responses converts to `NLQueryParserError`
- Hallucinated position/league values are dropped defensively before reaching the ORM, never silently passed through
- `get_nl_query_parser()` dispatches on `settings.LLM_PROVIDER`, returning `AnthropicNLQueryParser` for `"anthropic"` and raising `ValueError` for any unknown provider, with the concrete class imported lazily inside the branch

## Task Commits

Each task was committed atomically:

1. **Task 1: AnthropicNLQueryParser — forced tool-use extraction + defensive whitelist validation** - `9d44312` (feat)
2. **Task 2: get_nl_query_parser() factory — provider selection from settings.LLM_PROVIDER** - `7d2b6a3` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/players/ai/anthropic_parser.py` - AnthropicNLQueryParser: FILTER_TOOL schema (10-position/25-league enums), lazy-client parse(), defensive _validate()
- `get-scouted-be/players/ai/factory.py` - get_nl_query_parser() provider dispatcher, lazy in-branch import
- `get-scouted-be/players/tests/test_ai_anthropic_parser.py` - 8 tests: happy path, style field passthrough, hallucinated-enum drop, 3x APIError subclass -> NLQueryParserError, malformed response, DI/no-network-call contract
- `get-scouted-be/players/tests/test_ai_factory.py` - 3 tests: provider selection, unknown-provider ValueError, sole-import swappability proof

## Decisions Made
- Caught the parent `anthropic.APIError` class rather than a narrow subclass, confirmed against the installed SDK's own exception `__mro__` (anthropic==0.120.0): `RateLimitError`/`APITimeoutError`/`APIConnectionError` all descend from `APIError`, so a single `except anthropic.APIError` covers every real failure mode.
- `_validate()` drops both unknown filter keys and hallucinated `position`/`league` enum values -- the LLM's tool output is treated as fully untrusted input, never passed to the ORM unchecked.
- `settings.ANTHROPIC_MODEL` used exclusively (no hardcoded model string), matching the critical note and Plan 01's existing settings.

## Deviations from Plan

None - plan executed exactly as written. Test construction for the 3 `anthropic.APIError` subclasses required building real `httpx.Request`/`httpx.Response` objects to satisfy the SDK's own exception constructors (`RateLimitError` needs a `response`, `APITimeoutError`/`APIConnectionError` need a `request`) -- this is implementation detail within the plan's Test 4 behavior spec, not a deviation from scope.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. (A real `ANTHROPIC_API_KEY` will be needed at runtime once the search view wired in Plan 03/04 actually calls the live API, but no test in this plan requires one.)

## Next Phase Readiness
- The provider-agnostic interface (AI-05) is now proven end-to-end with one real concrete implementation behind `get_nl_query_parser()`.
- Plan 03/04 (the search view/service and tier-2 keyword fallback) can call `get_nl_query_parser().parse(query)` and catch `NLQueryParserError` to fall back, with zero knowledge of the Anthropic SDK.
- No blockers.

---
*Phase: 09-ai-provider-interface-natural-language-search*
*Completed: 2026-07-25*

## Self-Check: PASSED

All created files and commit hashes verified present.
