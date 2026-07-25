---
phase: 09-ai-provider-interface-natural-language-search
plan: 01
subsystem: api
tags: [anthropic, django-environ, abc, pytest, natural-language-search]

# Dependency graph
requires:
  - phase: 07-core-crud-players-clubs
    provides: "PlayerFilter/style whitelist that ParsedQuery.filters keys will be restricted to"
provides:
  - "anthropic>=0.120,<0.130 SDK pinned and installed in the project .venv"
  - "settings.LLM_PROVIDER / ANTHROPIC_API_KEY / ANTHROPIC_MODEL (env-driven, django-environ pattern)"
  - "players/ai/base.py: NLQueryParser ABC, ParsedQuery dataclass, NLQueryParserError exception"
  - "Autouse pytest safety-net (players/tests/conftest.py) blocking any real anthropic.Anthropic() construction in tests"
affects: [09-02-anthropic-nl-query-parser, 09-03, 09-04]

# Tech tracking
tech-stack:
  added: ["anthropic 0.120.0 (Python SDK for Anthropic Messages API)"]
  patterns:
    - "players/ai/ sub-package mirrors scoring/services/ convention"
    - "LLM_PROVIDER env var selects concrete NLQueryParser implementation via a future factory (players.ai.factory.get_nl_query_parser()), calling code never imports concrete classes"
    - "Autouse pytest fixture as the sole test-isolation guard when no test-settings module isolates a secret env var"

key-files:
  created:
    - get-scouted-be/players/ai/__init__.py
    - get-scouted-be/players/ai/base.py
    - get-scouted-be/players/tests/test_ai_base.py
    - get-scouted-be/players/tests/test_ai_safety_net.py
  modified:
    - get-scouted-be/requirements/base.txt
    - get-scouted-be/config/settings/base.py
    - get-scouted-be/.env.example
    - get-scouted-be/players/tests/conftest.py

key-decisions:
  - "anthropic pinned to >=0.120,<0.130 (narrow 0.x minor-band cap, not next-major) per 09-RESEARCH.md's flag that 0.x minors can carry breaking changes"
  - "ANTHROPIC_MODEL default claude-haiku-4-5 build-time verified via the installed anthropic==0.120.0 SDK's own generated ModelParam Literal type (anthropic/types/model_param.py), which lists claude-haiku-4-5 and its dated snapshot claude-haiku-4-5-20251001 as currently valid model ids -- no ANTHROPIC_API_KEY was available locally to hit the live /v1/models endpoint, so the freshly-downloaded SDK's bundled model list was used as the build-time source of truth instead. Newer generations (claude-sonnet-5, claude-opus-5, claude-fable-5, claude-mythos-5) also appear in that list but are higher-tier/pricier models, not the fast/cheap Haiku tier this setting targets, so claude-haiku-4-5 was confirmed as the correct current default."
  - "Test isolation for ANTHROPIC_API_KEY implemented as an autouse monkeypatch guard in players/tests/conftest.py (raises RuntimeError on any real anthropic.Anthropic() construction) rather than a test-settings module, since 09-RESEARCH.md Pitfall 2 flagged no such isolation currently exists"

requirements-completed: [AI-05]

# Metrics
duration: 12min
completed: 2026-07-25
---

# Phase 09 Plan 01: AI Provider Interface Foundation Summary

**Anthropic SDK pinned + installed, 3 env-driven LLM settings added, and a provider-agnostic NLQueryParser ABC contract built alongside an autouse pytest safety-net that hard-blocks any real, billed Anthropic API call in tests.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-25T09:42Z
- **Completed:** 2026-07-25T09:47Z
- **Tasks:** 3 (Task 2 executed as TDD: RED test commit, GREEN implementation commit)
- **Files modified:** 8 (4 created, 4 modified)

## Accomplishments
- `anthropic` SDK installed into the project `.venv` (0.120.0) and pinned in `requirements/base.txt`
- `LLM_PROVIDER` / `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` settings added to `config/settings/base.py`, mirroring the existing `EMAIL_BACKEND` django-environ pattern exactly, and documented (blank secrets) in `.env.example`
- `players/ai/base.py` defines the AI-05 provider-agnostic contract: `NLQueryParser` ABC (`parse(query: str) -> ParsedQuery`), `ParsedQuery` dataclass, `NLQueryParserError` exception
- Autouse pytest fixture in `players/tests/conftest.py` guarantees no players test can ever construct a real `anthropic.Anthropic()` client and reach the network — the mandatory safety-net Plan 02's Anthropic-calling tests depend on

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin + install anthropic SDK, add settings, document env vars** - `ebc68ab` (chore)
2. **Task 2: Define the NLQueryParser interface contract** - `91789cd` (test, RED) + `4f0f895` (feat, GREEN)
3. **Task 3: Build the pytest safety-net blocking real Anthropic calls** - `7beda84` (feat)

**Plan metadata:** (final commit follows this SUMMARY)

_Note: Task 2 was TDD (test → feat), no refactor commit was needed — the implementation matched the plan's literal contract exactly._

## Files Created/Modified
- `get-scouted-be/requirements/base.txt` - Pinned `anthropic>=0.120,<0.130`
- `get-scouted-be/config/settings/base.py` - Added `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` env-driven settings
- `get-scouted-be/.env.example` - Documented the 3 new env vars with blank secret values
- `get-scouted-be/players/ai/__init__.py` - New sub-package marker
- `get-scouted-be/players/ai/base.py` - `NLQueryParser` ABC, `ParsedQuery` dataclass, `NLQueryParserError`
- `get-scouted-be/players/tests/test_ai_base.py` - 4 contract tests (instantiation guard, concrete subclass, dataclass field access, exception subclassing)
- `get-scouted-be/players/tests/conftest.py` - Appended autouse `_block_real_anthropic_calls` fixture (existing `real_data_available` fixture preserved)
- `get-scouted-be/players/tests/test_ai_safety_net.py` - Test asserting the guard is active

## Decisions Made
- `anthropic` pinned to a narrow 0.x minor-band (`>=0.120,<0.130`) rather than the usual next-major cap, since the package is pre-1.0 and 09-RESEARCH.md flagged that 0.x minors can carry breaking changes.
- Build-time model-id verification used the installed SDK's own bundled `ModelParam` Literal type (`anthropic/types/model_param.py` in the freshly pip-installed 0.120.0 package) as the source of truth, since no local `ANTHROPIC_API_KEY` was available to call the live `/v1/models` endpoint. This literal type is generated from Anthropic's own OpenAPI spec at SDK release time, so it reflects the real current model catalog as of the SDK version actually installed. `claude-haiku-4-5` (and its dated snapshot `claude-haiku-4-5-20251001`) is present in that list — confirmed current, no correction needed. Also observed in the same list: newer `claude-sonnet-5`, `claude-opus-5`, `claude-fable-5`, `claude-mythos-5` — all higher-tier models than Haiku, not relevant to the "fast/cheap" intent of this default.
- Test isolation implemented as an autouse `monkeypatch` fixture (no new test dependency, matches project's existing-deps-first convention) rather than a dedicated test-settings module, per the plan's explicit design.

## Deviations from Plan

None - plan executed exactly as written. Task 2 was executed with a strict TDD RED/GREEN split (two commits) rather than the plan's single combined action step, per this executor's TDD protocol — the resulting code is identical to the plan's literal contract.

## Issues Encountered
None. `ANTHROPIC_API_KEY` was not set locally, so the live-API verification path in Task 1's action step 4 could not run; the SDK-bundled `ModelParam` Literal type was used as the build-time verification method instead (see Decisions Made above), which is arguably a stronger signal than a single live API response since it reflects Anthropic's full published model catalog at the exact SDK version pinned.

## User Setup Required

**External service requires manual configuration to enable live Anthropic calls in Plan 02+.**
- Env var: `ANTHROPIC_API_KEY` — get one from https://console.anthropic.com/settings/keys
- Set it in `get-scouted-be/.env` (left blank in `.env.example` per convention — no secret committed)
- Leaving it blank is safe: `players.ai.factory` (built in Plan 02) will force every NL search onto the deterministic keyword fallback, never erroring
- Verification: `cd get-scouted-be && .venv/bin/python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.local'); import django; django.setup(); from django.conf import settings; print(bool(settings.ANTHROPIC_API_KEY))"`

## Next Phase Readiness
- The `NLQueryParser` contract and safety-net are in place; Plan 02 can now write `AnthropicNLQueryParser(NLQueryParser)` and its tests with zero risk of a real billed API call.
- `settings.LLM_PROVIDER` is ready for Plan 02's factory function to read.
- No blockers. The only outstanding external dependency is the user supplying a real `ANTHROPIC_API_KEY` in their local `.env` before live (non-test) Anthropic calls will succeed — the system degrades gracefully (deterministic fallback) without it.

---
*Phase: 09-ai-provider-interface-natural-language-search*
*Completed: 2026-07-25*

## Self-Check: PASSED

All 8 claimed files verified present on disk; all 4 claimed commits (`ebc68ab`, `91789cd`, `4f0f895`, `7beda84`) verified present in git history.
