---
phase: 10-ai-grounded-report-generation
verified: 2026-07-26T05:32:29Z
status: passed
score: 5/5 must-haves verified
---

# Phase 10: AI Grounded Report Generation Verification Report

**Phase Goal:** Users can request AI-written scouting reports (player: strengths/weaknesses/tactical fit/financial fit/best use case) and club insights (recruitment gaps/over-aged positions/financial constraints) that are narratively generated but numerically grounded — every number traceable to an already-computed score/stat, no LLM-invented figures ever.

**Verified:** 2026-07-26T05:32:29Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User can request an AI-generated scouting report for a player (strengths/weaknesses/tactical fit/financial fit/best use case) with every number traceable to an already-computed score/stat | ✓ VERIFIED | `POST /api/players/{id}/scouting-report/` is a real, routed endpoint (`players/urls.py`) wired to `PlayerScoutingReportView.post` (`players/views.py:76-106`), which calls `players/services.py::generate_scouting_report(player_id, club_id)`. That service builds grounding exclusively from `scoring.services.summary.get_summary()` (never re-derived) and generates narrative via `get_report_generator().generate(grounding, "player_scouting_report")`. |
| 2 | User can request AI-generated club insights (recruitment gaps/over-aged positions/financial constraints) grounded in real Position Needs and Transfer Behaviour aggregates | ✓ VERIFIED | `POST /api/clubs/{id}/insights/` is a real, routed endpoint (`clubs/urls.py`) wired to `ClubInsightsView.post` (`clubs/views.py:99-119`), which calls `clubs/services.py::generate_club_insights(club_id)`. Grounding combines `position_needs_aggregate(club)` (bounded single-club ORM query) with reused `ClubDetailSerializer.get_transfer_aggregates(club)`. |
| 3 | No report ever contains an LLM-invented number — all figures originate from the scoring/CRUD layers | ✓ VERIFIED | `players/ai/grounding.py::validate_grounding()` extracts every numeric token from generated prose and tolerance-matches it against a recursive flatten of the grounding dict; `players/ai/anthropic_report_generator.py::generate()` calls `validate_grounding(text, grounding)` after every model call (line 75), retries once with corrective feedback naming the offending numbers on failure, and raises `ReportGeneratorError` (never returns a partial/fabricated report) if the retry still fails (lines 79-82). Both `players/tests/test_ai_grounding.py` and `players/tests/test_ai_anthropic_report_generator.py` directly test the accept and reject paths, plus retry-then-raise and retry-then-recover, using an injected fake client. |
| 4 | Generation/provider failure returns a clean error, never a fabricated/template report | ✓ VERIFIED | Both views catch only `ReportGeneratorError` and return `Response({"error": ...}, status=status.HTTP_503_SERVICE_UNAVAILABLE)` — no `report`/`insights`/narrative variable is referenced in either except-branch (`players/views.py:99-104`, `clubs/views.py:111-118`). Tests assert `"narrative" not in response.data` on the 503 path (`players/tests/test_scouting_report_view.py:161`, `clubs/tests/test_ai_club_insights.py:112`). |
| 5 | The AI integration is provider-agnostic and swappable (AI-05 pattern reused) with the report-generation model independently configurable | ✓ VERIFIED | `settings.ANTHROPIC_REPORT_MODEL` is a separate env-backed setting from `ANTHROPIC_MODEL`, build-time-verified against the installed `anthropic==0.120.0` SDK's `ModelParam` Literal (recorded in 10-01-SUMMARY.md). `players/ai/report_factory.py::get_report_generator()` dispatches on `settings.LLM_PROVIDER` with a lazy in-branch import; calling code (`players/services.py`, `clubs/services.py`) imports only `get_report_generator`, never `AnthropicReportGenerator` directly. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `players/ai/report_generator.py` | `ReportGenerator` ABC + `GeneratedReport` dataclass + `ReportGeneratorError` | ✓ VERIFIED | All three present; mirrors Phase 9's `NLQueryParser` triad exactly. |
| `players/ai/grounding.py` | numeric-token extraction + tolerance-match validator | ✓ VERIFIED | `extract_numeric_tokens`, `flatten_grounding_values`, `is_grounded`, `validate_grounding` all present and exported. |
| `players/ai/anthropic_report_generator.py` | concrete generator, plain (non-tool-use) generation, grounding + retry-once | ✓ VERIFIED | `class AnthropicReportGenerator(ReportGenerator)`; `grep -n "tool_choice\|tools="` returns zero matches (plain generation confirmed); `validate_grounding(` called at line 75; bounded 2-attempt loop (`MAX_ATTEMPTS = 2`). |
| `players/ai/report_factory.py` | `get_report_generator()` | ✓ VERIFIED | Dispatches on `settings.LLM_PROVIDER`, lazy in-branch import, `ValueError` on unknown provider. |
| `players/services.py::generate_scouting_report` | grounding + generation orchestration | ✓ VERIFIED | `get_summary(player_id, club_id)` -> `get_report_generator().generate(grounding, "player_scouting_report")`; no try/except around the generate call (error propagates). |
| `players/views.py::PlayerScoutingReportView` | POST endpoint, catches `ReportGeneratorError` -> 503, clean 400 on missing club | ✓ VERIFIED | Confirmed at `players/views.py:76-106`. |
| `players/urls.py` | `scouting-report/` route | ✓ VERIFIED | `path("<uuid:pk>/scouting-report/", PlayerScoutingReportView.as_view(), name="player-scouting-report")`, placed BEFORE the bare `<uuid:pk>/` detail route — no shadowing. |
| `clubs/services.py::position_needs_aggregate` | bounded single-club ORM aggregation | ✓ VERIFIED | Single `.values("position").annotate(...)` query scoped to `club.players`; no pandas/full-dataset op anywhere in the file (`grep -niE "import pandas|read_csv|score_population|reconstruct_population"` returns zero matches). |
| `clubs/services.py::generate_club_insights` | grounding assembly + generation orchestration | ✓ VERIFIED | Combines `position_needs_aggregate` + `ClubDetailSerializer().get_transfer_aggregates(club)`; calls cross-app `get_report_generator()`; `ReportGeneratorError` not caught here (propagates to view). |
| `clubs/views.py::ClubInsightsView` | POST endpoint, catches `ReportGeneratorError` -> 503 | ✓ VERIFIED | Confirmed at `clubs/views.py:99-119`. |
| `clubs/urls.py` | `insights/` route | ✓ VERIFIED | `path("<uuid:pk>/insights/", ClubInsightsView.as_view(), name="club-insights")`, placed BEFORE the bare `<uuid:pk>/` detail route — no shadowing. |
| `clubs/tests/conftest.py` | autouse `_block_real_anthropic_calls` safety net | ✓ VERIFIED | Verbatim-mirrored fixture present, `autouse=True`, existing `real_data_available` fixture preserved. Independently confirmed by reading the file directly (not just grepped). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `players/views.py` | `players/services.py` | `PlayerScoutingReportView.post` calls `generate_scouting_report` | ✓ WIRED | Confirmed at call site line 100. |
| `players/services.py` | `scoring.services.summary.get_summary` + `players.ai.report_factory.get_report_generator` | grounding from `get_summary`, narrative from `get_report_generator().generate` | ✓ WIRED | Both imported at module top; both called in `generate_scouting_report`. |
| `players/ai/anthropic_report_generator.py` | `players/ai/grounding.py` | `validate_grounding` after each `messages.create` call | ✓ WIRED | Called at line 75 inside the retry loop, with retry-once-then-raise enforced (lines 76-82). |
| `players/ai/report_factory.py` | `players/ai/anthropic_report_generator.py` | lazy in-branch import on `LLM_PROVIDER == "anthropic"` | ✓ WIRED | Import is inside the `if` branch, not module top. |
| `clubs/views.py` | `clubs/services.py` | `ClubInsightsView.post` calls `generate_club_insights` | ✓ WIRED | Confirmed at call site line 113. |
| `clubs/services.py` | `position_needs_aggregate` + `ClubDetailSerializer.get_transfer_aggregates` + `players.ai.report_factory.get_report_generator` | `generate_club_insights` builds grounding from both aggregates, generates via cross-app factory | ✓ WIRED | All three composed into the `grounding` dict then passed to `get_report_generator().generate(grounding, "club_insights")`. |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AI-03 | 10-01, 10-02, 10-03, 10-05 | AI-generated player scouting report, strictly grounded | ✓ SATISFIED | `POST /api/players/{id}/scouting-report/` live-routed and end-to-end tested; REQUIREMENTS.md correctly marks `[x]` with an accurate, code-grounded description, not the historical premature mark (independently confirmed via `git show a980879`, the revert commit, followed by 10-03/10-05 completing the real work before the final re-mark). |
| AI-04 | 10-01, 10-02, 10-04, 10-05 | AI-generated club insights, grounded in Position Needs + Transfer Behaviour aggregates | ✓ SATISFIED | `POST /api/clubs/{id}/insights/` live-routed and end-to-end tested; same revert/re-mark history independently confirmed accurate for the current state. |

No orphaned requirements: REQUIREMENTS.md's phase-mapping table lists only AI-03/AI-04 against Phase 10, matching both plans' frontmatter `requirements:` declarations exactly.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | None found | — | Grepped all 11 Phase-10-touched source files (`report_generator.py`, `grounding.py`, `anthropic_report_generator.py`, `report_factory.py`, `players/services.py`, `players/views.py`, `players/urls.py`, `clubs/services.py`, `clubs/views.py`, `clubs/urls.py`, `clubs/tests/conftest.py`) for TODO/FIXME/XXX/HACK/PLACEHOLDER/"not implemented"/"coming soon" — zero matches. |

**Minor documentation-only inconsistency (not a code gap):** `.planning/ROADMAP.md`'s Phase 10 section still shows all five plan checkboxes as `- [ ]` (unchecked) even though the phase-level line and every 10-0X-SUMMARY.md confirm completion, and REQUIREMENTS.md's own phase-mapping table correctly shows both as Complete. This is a stale roadmap-detail bookkeeping gap, not a functional or requirements-tracking issue — flagged for hygiene only.

### Human Verification Required

### 1. Live real-LLM narrative quality + grounding spot-check

**Test:** With a real `ANTHROPIC_API_KEY` configured, run `players.services.generate_scouting_report(<real player id>, <real club id>)` and `clubs.services.generate_club_insights(<real club id>)` against the real dev DB (real migrated Phase-1 data), then manually read the narrative and cross-check every number against the returned `grounding` dict.
**Expected:** Narrative prose reads coherently/professionally, all five (player) / three (club) sections are substantive (not boilerplate), and every number quoted in the prose is traceable to a value in `grounding`.
**Why human:** No `ANTHROPIC_API_KEY` is configured in this environment (confirmed absent from `.env`, `.env.example`, and the shell — same constraint as Phase 9's 09-01), so no real Anthropic call can be made. The mocked-client test suite (40 Phase-10 tests, including explicit accept/reject grounding-validator tests and retry-then-raise/retry-then-recover generator tests) already proves the plumbing and validator logic is structurally correct; what remains unverified is purely the qualitative behavior of a live model's actual prose. This is consistent with the phase's own 10-05-SUMMARY.md, which recorded the identical deferral for the identical reason — independently re-confirmed here, not merely trusted.

### Gaps Summary

No gaps. All 5 derived observable truths verified against live code (not SUMMARY claims): both endpoints are real, correctly routed (specific routes precede the catch-all `<uuid:pk>/` pattern in both `players/urls.py` and `clubs/urls.py`), the grounding validator is genuinely invoked with bounded retry-once semantics before any report is returned, both views map `ReportGeneratorError` to a clean 503 with zero narrative/report leakage in the error body, `position_needs_aggregate` is confirmed to be a single bounded per-club ORM `.values().annotate()` query with no pandas/full-dataset operation anywhere in `clubs/services.py`, the `clubs/tests/conftest.py` autouse Anthropic-blocking safety net is genuinely present and autouse (read directly, not grepped only), and `AnthropicReportGenerator` is confirmed to use plain `client.messages.create()` with zero `tools`/`tool_choice` occurrences anywhere in the file. The full pytest suite was independently re-run: `214 passed, 315 skipped, 0 failed`, and the `players clubs`-scoped regression slice independently re-run: `89 passed, 22 skipped, 0 failed` — both numbers match (not merely trusted from) 10-05-SUMMARY.md's reported counts. REQUIREMENTS.md's AI-03/AI-04 checkboxes are correctly `[x]` in the current state, and the earlier premature-completion mistake (caught and reverted mid-phase per commit `a980879`) does not linger anywhere in the current tree. Only a documented, environment-constrained live-LLM qualitative spot-check remains outstanding, matching the phase's own established convention for this exact constraint (no local `ANTHROPIC_API_KEY`).

---

*Verified: 2026-07-26T05:32:29Z*
*Verifier: Claude (gsd-verifier)*
