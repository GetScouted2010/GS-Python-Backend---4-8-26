---
phase: 10-ai-grounded-report-generation
plan: 01
subsystem: ai
tags: [anthropic, llm, grounding, django, report-generation]

# Dependency graph
requires:
  - phase: 09-ai-nl-search-degradation
    provides: "NLQueryParser/AnthropicNLQueryParser/get_nl_query_parser triad shape to mirror; ANTHROPIC_MODEL/ANTHROPIC_API_KEY/LLM_PROVIDER settings; players/ai/ file-per-concern convention; players/tests/conftest.py autouse Anthropic-blocking fixture"
provides:
  - "ReportGenerator ABC + GeneratedReport dataclass + ReportGeneratorError (players/ai/report_generator.py) -- the provider-agnostic contract Plan 03 (player scouting report) and Plan 04 (club insights) both implement/consume"
  - "settings.ANTHROPIC_REPORT_MODEL -- independently-configurable flagship-tier model setting for narrative generation, separate from ANTHROPIC_MODEL's cheap extraction tier"
  - "Standalone grounding validator (players/ai/grounding.py): extract_numeric_tokens/flatten_grounding_values/is_grounded/validate_grounding -- the programmatic guarantee that no report narrative contains an LLM-invented number"
affects: [10-03-player-scouting-report, 10-04-club-insights]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ReportGenerator ABC triad (GeneratedReport dataclass + ReportGeneratorError + one-abstractmethod ABC) mirrors Phase 9's NLQueryParser triad exactly -- second instance of this project's one LLM-integration pattern"
    - "Grounding validation as a standalone, directly-tested pure-function module (never inline in a view) -- numeric-token regex extraction, recursive dict-flattening, tolerant multi-scale (value/value*100/value/100) matching"
    - "Ratio-denominator exemption in validate_grounding: numbers immediately preceded by '/' (e.g. the '10' in '7.4/10') are structural rating-scale markers, not data claims, and are excluded from grounding-checking"

key-files:
  created:
    - get-scouted-be/players/ai/report_generator.py
    - get-scouted-be/players/ai/grounding.py
    - get-scouted-be/players/tests/test_ai_report_generator.py
    - get-scouted-be/players/tests/test_ai_grounding.py
  modified:
    - get-scouted-be/config/settings/base.py

key-decisions:
  - "ANTHROPIC_REPORT_MODEL defaults to claude-sonnet-5, build-time verified against the installed anthropic==0.120.0 SDK's own ModelParam Literal type (no ANTHROPIC_API_KEY available to hit the live /v1/models endpoint) -- mirrors Phase 9's 09-01 precedent exactly"
  - "validate_grounding exempts ratio denominators (text immediately preceded by '/') from grounding-checking -- without this, the plan's own 'validate accept' behavior test (narrative containing '7.4/10') fails, since the bare '10' never traces back to any grounding dict value on its own"

patterns-established:
  - "Second ReportGenerator-style provider-agnostic interface in players/ai/, ready for Plan 03's AnthropicReportGenerator + report_factory.py to implement/dispatch"
  - "Grounding validator tolerance constants (DEFAULT_REL_TOL=0.05, DEFAULT_ABS_TOL=0.5) are module-level and intentionally left open for empirical tuning during Plan 03/04 manual verification against real LLM output"

requirements-completed: [AI-03, AI-04]

# Metrics
duration: 15min
completed: 2026-07-26
---

# Phase 10 Plan 01: AI Report Generation Foundation Summary

**ReportGenerator ABC + standalone numeric-grounding validator, mirroring Phase 9's NLQueryParser pattern, with a build-time-verified `ANTHROPIC_REPORT_MODEL` flagship-tier config setting**

## Performance

- **Duration:** 15 min
- **Completed:** 2026-07-26T04:58:50Z
- **Tasks:** 2
- **Files modified:** 5 (1 modified, 4 created)

## Accomplishments
- `settings.ANTHROPIC_REPORT_MODEL` added, env-backed, independently configurable from `ANTHROPIC_MODEL`, defaulting to a build-time-verified flagship-tier model
- `ReportGenerator`/`GeneratedReport`/`ReportGeneratorError` triad created in `players/ai/report_generator.py`, mirroring Phase 9's `NLQueryParser`/`ParsedQuery`/`NLQueryParserError` shape exactly
- Standalone grounding validator (`players/ai/grounding.py`) built from scratch with stdlib `re` (no existing money/percentage formatter found anywhere in the codebase) -- proves both the accept (tolerantly-rounded real number) and reject (hallucinated number) paths via direct unit tests

## Task Commits

Each task was committed atomically:

1. **Task 1: ANTHROPIC_REPORT_MODEL config + ReportGenerator interface contract** - `59dec32` (feat)
2. **Task 2: Grounding validator (numeric extraction + tolerance match)** - `742f918` (feat)

**Plan metadata:** (this commit) `docs(10-01): complete AI report generation foundation plan`

## Files Created/Modified
- `get-scouted-be/config/settings/base.py` - Added `ANTHROPIC_REPORT_MODEL = env("ANTHROPIC_REPORT_MODEL", default="claude-sonnet-5")` immediately after `ANTHROPIC_MODEL`
- `get-scouted-be/players/ai/report_generator.py` - `GeneratedReport` dataclass (narrative/grounding dicts), `ReportGeneratorError` exception, `ReportGenerator` ABC with one abstract `generate(grounding, report_type) -> GeneratedReport` method
- `get-scouted-be/players/ai/grounding.py` - `NUMERIC_TOKEN_RE`, `_normalize`, `extract_numeric_tokens`, `flatten_grounding_values`, `is_grounded`, `validate_grounding`, `_is_ratio_denominator`
- `get-scouted-be/players/tests/test_ai_report_generator.py` - 5 contract tests (defaults, round-trip, ABC enforcement, error subclass, concrete subclass)
- `get-scouted-be/players/tests/test_ai_grounding.py` - 7 tests covering extraction, flattening, accept/reject tolerance matching, and both validate_grounding directions

## Decisions Made
- **`ANTHROPIC_REPORT_MODEL` build-time verification:** Ran `cd get-scouted-be && .venv/bin/python -c "from anthropic.types.model_param import ModelParam; import typing; args = typing.get_args(ModelParam); literal_arg = [a for a in args if typing.get_origin(a) is typing.Literal][0]; print(typing.get_args(literal_arg))"`. Note: the plan's suggested one-liner (`[m for m in typing.get_args(ModelParam) if isinstance(m, str)]`) returned an empty list because the installed SDK's `ModelParam` is `Union[Literal[...], str]`, not a bare `Literal` -- the literal member had to be extracted from the Union args first. Output: `('claude-sonnet-5', 'claude-fable-5', 'claude-mythos-5', 'claude-opus-5', 'claude-opus-4-8', 'claude-opus-4-7', 'claude-mythos-preview', 'claude-opus-4-6', 'claude-sonnet-4-6', 'claude-haiku-4-5', 'claude-haiku-4-5-20251001', 'claude-opus-4-5', 'claude-opus-4-5-20251101', 'claude-sonnet-4-5', 'claude-sonnet-4-5-20250929', 'claude-opus-4-1', 'claude-opus-4-1-20250805')`. `'claude-sonnet-5'` is present and is a genuine flagship-tier model (distinct from Phase 9's `claude-haiku-4-5`), so the plan's proposed default was confirmed correct and kept as-is -- no fallback substitution needed. Installed SDK version: `anthropic==0.120.0` (unchanged since Phase 9's 09-01 verification).
- **Ratio-denominator exemption in `validate_grounding`:** see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `validate_grounding`'s naive tolerance-match fails the plan's own "validate accept" behavior test on ratio denominators**
- **Found during:** Task 2 (Grounding validator implementation)
- **Issue:** The plan's Pattern 5 reference implementation (10-RESEARCH.md), applied literally, produces `validate_grounding("RMM is 7.4/10 and value €2.3M", {"rmm": {"rmm": 7.42}, "fee": 2_340_000})` returning `[10.0]` instead of the plan's required `[]` -- the bare "10" extracted from "7.4/10" is a rating-scale denominator, not a data claim, and never traces back to any grounding-dict value on its own (confirmed directly: `is_grounded(10, [7.42, 2340000])` is `False` under the default `rel_tol=0.05`/`abs_tol=0.5`). This is exactly the "incidental non-data numbers" false-positive risk 10-RESEARCH.md's Pitfall 3 and Open Question 2 flag as a known, anticipated design gap in the naive validator.
- **Fix:** Added `_is_ratio_denominator(text, match)` -- detects when a matched number is immediately preceded (ignoring whitespace) by a `/` -- and excluded such matches from `validate_grounding`'s grounding-check loop (they are still returned normally by `extract_numeric_tokens`, which is unaffected, matching that function's own behavior test unchanged).
- **Files modified:** `get-scouted-be/players/ai/grounding.py`
- **Verification:** All 7 of Task 2's behavior-derived unit tests pass, including both `validate_grounding` accept (`== []`) and reject (`88_800_000.0 in result`) directions; `is_grounded`/`extract_numeric_tokens`/`flatten_grounding_values` are unaffected and still match their own literal behavior-test expectations exactly.
- **Committed in:** `742f918` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix, Rule 1)
**Impact on plan:** Necessary to satisfy the plan's own literal behavior test; no scope creep -- the fix is narrowly scoped to one exemption clause inside `validate_grounding`, does not change `extract_numeric_tokens`/`flatten_grounding_values`/`is_grounded`'s public contracts, and is explicitly anticipated by the plan's own linked research (Pitfall 3 / Open Question 2).

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required

None - no external service configuration required. `ANTHROPIC_API_KEY` (the actual secret) was already configured in Phase 9; this plan only adds a second, independently-configurable model-id setting that reuses the same key.

## Next Phase Readiness

- Plan 03 (player scouting report) can now implement `AnthropicReportGenerator(ReportGenerator)` + `players/ai/report_factory.py::get_report_generator()`, mirroring Phase 9's `anthropic_parser.py`/`factory.py` pattern, and call `validate_grounding()` after every `generate()` call.
- Plan 04 (club insights) can consume the same `ReportGenerator`/`GeneratedReport`/`ReportGeneratorError`/`grounding.py` foundation from `clubs/services.py`, per 10-RESEARCH.md's cross-app-import precedent (`clubs/serializers.py` already imports `players.serializers.PlayerListSerializer`).
- No blockers. Tolerance constants (`DEFAULT_REL_TOL=0.05`, `DEFAULT_ABS_TOL=0.5`) are deliberately left as easily-adjustable module constants for empirical tuning once Plans 03/04 observe real LLM narrative output.

---
*Phase: 10-ai-grounded-report-generation*
*Completed: 2026-07-26*

## Self-Check: PASSED

All created files confirmed present on disk; both task commits (`59dec32`, `742f918`) confirmed present in git history.
