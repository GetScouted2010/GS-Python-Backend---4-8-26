---
phase: 09-ai-provider-interface-natural-language-search
verified: 2026-07-25T10:24:38Z
status: passed
score: 7/7 must-haves verified
---

# Phase 09: AI Provider Interface & Natural Language Search Verification Report

**Phase Goal:** Users can search using plain language and get real, structured Player results filtered by a fixed whitelist of real fields (position, age, value, league, style-via-club), with ambiguous/unparseable queries degrading gracefully (never an error or empty crash), and the LLM call for parsing going through a provider-agnostic interface so swapping providers requires no changes to search-calling code.

**Verified:** 2026-07-25T10:24:38Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `POST /api/players/search/` is a real, reachable, routed endpoint | ✓ VERIFIED | `players/urls.py` has `path("search/", PlayerSearchView.as_view(), name="player-search")`; `reverse('player-search')` resolves to `/api/players/search/`; live DRF `APIClient` round-trips against the real dev DB (41,708 players) return HTTP 200/401 as expected. |
| 2 | Natural language maps to structured filters restricted to the real whitelist (AI-01) | ✓ VERIFIED | `AnthropicNLQueryParser._validate()` whitelists exactly `WHITELIST_KEYS` (10 PlayerFilter keys + 8 `club__<field>_min` style keys) and drops hallucinated `position`/`league` values before they reach the ORM. `keyword_extract()` only ever emits `position`, `market_value_min/max`, `league`. Live test: `"strikers under 5m"` → `{'position': 'FWD', 'market_value_max': 5000000}`, 4,504 real filtered results, all `position == 'FWD'`. |
| 3 | Ambiguous/unparseable queries degrade gracefully, never an error or empty crash (AI-02) | ✓ VERIFIED | Live test with no `ANTHROPIC_API_KEY` set: `"asdfghjkl nonsense"` → tier-1 real network call fails (auth error, an `anthropic.APIError` subclass) → tier-2 `keyword_extract` returns `{}` → tier-3 unfiltered list. Response: HTTP 200, `fallback_used=True`, `parsed_filters={}`, `results.count == 41708` (full unfiltered list, not empty/crash). |
| 4 | The LLM call goes through a provider-agnostic interface; swapping providers requires no change to search-calling code (AI-05) | ✓ VERIFIED | `players/views.py` imports only `from players.ai.factory import get_nl_query_parser` — no import of `AnthropicNLQueryParser` anywhere in views.py or services.py (`grep -c AnthropicNLQueryParser players/views.py` = 0). `get_nl_query_parser()` dispatches on `settings.LLM_PROVIDER` and lazily imports the concrete class only inside the `if` branch. |
| 5 | 3-tier fallback is real and observably correct (all tiers HTTP 200) | ✓ VERIFIED | Code: only `get_nl_query_parser().parse()` is wrapped in `try/except NLQueryParserError`; `search_players()` call and `RecentActivity.objects.create()` are outside the try. Live-verified all 3 tiers return 200 (see Truth 3 + Truth 2 evidence; tier-1 success path additionally covered by mocked integration test `test_search_success_returns_filters_and_results`, passing). |
| 6 | Style filter (`club__<field>_min`) genuinely narrows real results, not a silent no-op | ✓ VERIFIED (independently re-run live) | Live re-run against real dev DB: baseline `search_players({}, request)["count"] == 41708`; `search_players({"club__control_possession_min": 15}, request)["count"] == 14252` (narrowed); `PlayerFilter(data={"club__control_possession_min": 15}, ...).qs.count() == 41708` (proves PlayerFilter alone silently ignores the key — the pitfall the manual step protects against). Exactly reproduces 09-03-SUMMARY.md's prior figures. |
| 7 | RecentActivity gets exactly one "searched" row per search call, all tiers | ✓ VERIFIED | Read `players/views.py::PlayerSearchView.post` — exactly one `RecentActivity.objects.create(...)` call, placed after the tier-1/2/3 branching resolves and unconditionally executed once per request (not inside try/except, not duplicated). Live-verified: one row created with `query_text="asdfghjkl nonsense"`, `target_id=None`, `activity_type="searched"`. |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/players/ai/base.py` | NLQueryParser ABC + ParsedQuery + NLQueryParserError | ✓ VERIFIED | All 3 symbols present; `NLQueryParser` is ABC with one `@abstractmethod parse()`. |
| `get-scouted-be/config/settings/base.py` | LLM_PROVIDER/ANTHROPIC_API_KEY/ANTHROPIC_MODEL env-driven | ✓ VERIFIED | All 3 settings present via `env(...)`, mirroring `EMAIL_BACKEND` pattern. `ANTHROPIC_MODEL` default `claude-haiku-4-5` confirmed present in installed SDK's own `ModelParam` Literal (independently re-checked via `anthropic.types.model_param`). |
| `get-scouted-be/players/tests/conftest.py` | autouse safety-net blocking real Anthropic calls | ✓ VERIFIED | `_block_real_anthropic_calls` fixture present, `autouse=True`, monkeypatches `anthropic.Anthropic` to raise `RuntimeError`. Only `players/tests/` imports anthropic-touching code, so guard scope matches risk surface. |
| `get-scouted-be/players/ai/anthropic_parser.py` | AnthropicNLQueryParser — forced tool-use + whitelist validation | ✓ VERIFIED | `class AnthropicNLQueryParser(NLQueryParser)`, forced `tool_choice`, `except anthropic.APIError` (parent class), `_validate()` drops unknown keys + hallucinated enums. |
| `get-scouted-be/players/ai/factory.py` | get_nl_query_parser() dispatching on settings.LLM_PROVIDER | ✓ VERIFIED | Dispatches on `settings.LLM_PROVIDER == "anthropic"`, lazy in-branch import, raises `ValueError` for unknown provider. |
| `get-scouted-be/players/ai/fallback.py` | keyword_extract(query) -> dict, tier-2 deterministic | ✓ VERIFIED | stdlib `re` only, returns `{}` on nothing usable, ambiguous leagues (bundesliga/serie/la liga/ligue/efl) never guessed. |
| `get-scouted-be/players/services.py` | search_players(filters, request) -> paginated envelope | ✓ VERIFIED | Composes `PlayerFilter` + separate manual `club__<field>__gte` step + `IdsBypassPagination` + `PlayerListSerializer`; does not import `PlayerListView`. |
| `get-scouted-be/players/views.py` | PlayerSearchView — 3-tier orchestration + RecentActivity logging | ✓ VERIFIED | Present, wired, matches described behavior exactly (read in full). |
| `get-scouted-be/players/urls.py` | route for POST /api/players/search/ | ✓ VERIFIED | `path("search/", PlayerSearchView.as_view(), name="player-search")` present and resolves live. |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `players/views.py::PlayerSearchView` | `players.ai.factory.get_nl_query_parser` | `get_nl_query_parser().parse(query)` inside `try/except NLQueryParserError` | ✓ WIRED | Confirmed by reading the file; imports the factory function only, never `AnthropicNLQueryParser` directly. |
| `players/views.py::PlayerSearchView` | `players.services.search_players` | `search_players(filters, request)` | ✓ WIRED | Called outside the tier-1 try block, exactly as designed. |
| `players/views.py::PlayerSearchView` | `workspace.models.RecentActivity` | `RecentActivity.objects.create(activity_type='searched', ...)` | ✓ WIRED | Single unconditional call after tier resolution; live-verified one row per call with correct `query_text`/`target_id`. |
| `players/ai/factory.py` | `settings.LLM_PROVIDER` | provider dispatch | ✓ WIRED | `if settings.LLM_PROVIDER == "anthropic":` with lazy in-branch concrete-class import. |
| `players/ai/anthropic_parser.py` | `anthropic.APIError` | `except anthropic.APIError -> raise NLQueryParserError` | ✓ WIRED | Catches the parent exception class, confirmed to cover RateLimitError/APITimeoutError/APIConnectionError/APIStatusError subclasses. |
| `players/services.py` | `PlayerFilter` | `PlayerFilter(data=player_filter_data, queryset=...).qs` | ✓ WIRED | Confirmed live: baseline 41,708 → CB-filtered subset works via unit/integration tests. |
| `players/services.py` | Player queryset (style) | manual `.filter(club__<field>__gte=value)` | ✓ WIRED, independently re-verified live | 41,708 → 14,252 with `club__control_possession_min=15`; PlayerFilter-alone path confirmed to silently no-op (41,708, unchanged) — proving the manual step is load-bearing, not redundant. |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|----------------|--------------|--------|----------|
| AI-01 | 09-02, 09-03, 09-04 | NL query parsed into structured filters against fixed real-field whitelist | ✓ SATISFIED | `AnthropicNLQueryParser` (tier 1) + `keyword_extract` (tier 2), both whitelist-restricted; live end-to-end results confirmed (4,504 FWD players under €5M). |
| AI-02 | 09-03, 09-04 | Graceful fallback (partial parse / keyword fallback) on ambiguous/unparseable input | ✓ SATISFIED | Live-verified 3-tier degradation always returns HTTP 200; `keyword_extract` never raises, returns `{}` for nonsense input; tier 3 (unfiltered list) confirmed live. |
| AI-05 | 09-01, 09-02 | LLM integration behind provider-agnostic interface; swapping providers needs no calling-code change | ✓ SATISFIED | `players/views.py` and `players/services.py` import only `get_nl_query_parser` / `NLQueryParser` / `NLQueryParserError` — zero references to `AnthropicNLQueryParser` outside `players/ai/factory.py`'s lazy in-branch import and the parser's own test file. |

**No orphaned requirements.** Cross-referenced against `.planning/REQUIREMENTS.md` lines 121-125: AI-01/AI-02/AI-05 map to Phase 9 (all claimed by plans); AI-03/AI-04 map to Phase 10 and are correctly out of scope for this phase (not claimed by any Phase 9 plan, and correctly not attempted).

### Anti-Patterns Found

None. Scanned `players/ai/*.py`, `players/views.py`, `players/services.py`, `players/urls.py` for TODO/FIXME/XXX/HACK/PLACEHOLDER/"not implemented"/"coming soon" — zero matches.

### Human Verification Required

None required — all must-haves were independently verifiable via live code execution against the real dev database (41,708 players), not just mocked unit tests. One item worth noting for awareness rather than action: true tier-1 LLM success (a real Anthropic API call actually succeeding) could not be independently re-verified end-to-end because no `ANTHROPIC_API_KEY` is configured in this environment — this is expected/by-design (the system is required to degrade gracefully without one, which it does). Tier-1 success logic itself is verified via a fully-mocked DRF integration test (`test_search_success_returns_filters_and_results`) that exercises the real view/service/serializer stack with only the LLM call boundary mocked, plus `AnthropicNLQueryParser`'s own mocked unit tests for the Anthropic-response-mapping logic. This does not block phase completion; it is inherent to using an external paid LLM API in a verification environment with no configured key.

### Full Test Suite Results (independently re-run)

`cd get-scouted-be && .venv/bin/pytest -q`:
```
174 passed, 315 skipped, 985 warnings in 18.44s
```
Matches 09-04-SUMMARY.md's claimed counts exactly. Zero failures. All skips are the established `real_data_available` pattern (empty pytest test DB — Phase 1's real data lives only in the dev DB), not Phase 9 regressions. `players/tests/` subset: 43 passed, 16 skipped (0 failed) — all 7 Phase 9 AI test files (`test_ai_base`, `test_ai_safety_net`, `test_ai_anthropic_parser`, `test_ai_factory`, `test_ai_fallback`, `test_services_search`, `test_search_view`) collected and passing/skipping cleanly.

Confirmed no test can fire a real, billed Anthropic API call: `players/tests/conftest.py::_block_real_anthropic_calls` is `autouse=True` and monkeypatches `anthropic.Anthropic` to raise `RuntimeError` on construction, for every test under `players/tests/` (the only test directory in the repo that touches `anthropic`, verified via `grep -rn "import anthropic"` across the whole codebase — matches were only in `players/ai/anthropic_parser.py`, `players/tests/conftest.py`, `players/tests/test_ai_safety_net.py`, `players/tests/test_ai_anthropic_parser.py`).

### Gaps Summary

None. All 7 derived observable truths verified against live code and live behavior (not just SUMMARY self-reports), all 9 required artifacts verified at exists/substantive/wired levels, all 7 key links independently confirmed wired, all 3 requirement IDs (AI-01, AI-02, AI-05) satisfied with no orphaned requirements, zero anti-patterns, and the full test suite independently re-run with matching pass/skip/fail counts. The style-filter pitfall fix (the highest-risk correctness pivot per 09-03-SUMMARY.md) was independently re-executed live against the real 41,708-player dev DB and reproduced the exact same before/after counts (41,708 → 14,252) reported by the original executor, plus reproduced the silent-ignore trap it protects against.

---

*Verified: 2026-07-25T10:24:38Z*
*Verifier: Claude (gsd-verifier)*
