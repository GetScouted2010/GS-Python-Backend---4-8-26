---
phase: 10
slug: ai-grounded-report-generation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-25
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django, version already pinned project-wide |
| **Config file** | `get-scouted-be/pyproject.toml` (`testpaths` already includes both `clubs` and `players` — no change needed) |
| **Quick run command** | `cd get-scouted-be && pytest players/tests/test_ai_report_generator.py clubs/tests/test_ai_club_insights.py -x` |
| **Full suite command** | `cd get-scouted-be && pytest` |
| **Estimated runtime** | under a minute for the full suite |

---

## Sampling Rate

- **After every task commit:** the specific new/modified test file(s) for that task
- **After every plan wave:** `pytest players clubs` (both apps, since this phase spans two)
- **Before `/gsd:verify-work`:** Full suite green, plus a live `manage.py shell` check against the real dev DB for at least one real player+club scouting report and one real club-only insights call — a mocked-client test suite alone cannot prove the prompt produces well-grounded narrative from a real LLM call, only that the plumbing/validator logic is correct
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-0X-0X | TBD | TBD | AI-03 (interface contract) | unit | `pytest players/tests/test_ai_report_generator.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | AI-03 (Anthropic impl) | unit | `pytest players/tests/test_ai_anthropic_report_generator.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | AI-03 (factory) | unit | `pytest players/tests/test_ai_report_factory.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | AI-03/AI-04 (grounding validator) | unit | `pytest players/tests/test_ai_grounding.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | AI-03 (scouting report endpoint) | integration | `pytest players/tests/test_scouting_report_view.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | AI-04 (position-needs aggregation) | unit | `pytest clubs/tests/test_services_club_insights.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | AI-04 (club insights endpoint) | integration | `pytest clubs/tests/test_ai_club_insights.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | cross-cutting (safety net in clubs/) | unit | `pytest clubs/tests/test_ai_safety_net.py -x` | ❌ W0 | ⬜ pending |
| 10-0X-0X | TBD | TBD | AI-03/AI-04 (no fabricated fallback) | integration | `pytest players/tests/test_scouting_report_view.py -k failure -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs finalized once gsd-planner assigns actual plan/wave numbers.*

---

## Wave 0 Requirements

- [ ] `players/tests/test_ai_report_generator.py` — `ReportGenerator`/`GeneratedReport`/`ReportGeneratorError` contract
- [ ] `players/tests/test_ai_anthropic_report_generator.py` — `AnthropicReportGenerator` (injected-client pattern, mirrors `test_ai_anthropic_parser.py`)
- [ ] `players/tests/test_ai_report_factory.py` — `get_report_generator()` dispatch (mirrors `test_ai_factory.py`)
- [ ] `players/tests/test_ai_grounding.py` — numeric-extraction/tolerance-match validator, both accept and reject paths
- [ ] `players/tests/test_scouting_report_view.py` — `POST /api/players/{id}/scouting-report/` end-to-end (mocked client), including club_id-missing branch and clean-error-on-failure path
- [ ] `clubs/services.py` — does not exist yet; new module needed before its tests can run
- [ ] `clubs/tests/test_services_club_insights.py` — `position_needs_aggregate()` against a real/factory-built club squad
- [ ] `clubs/tests/test_ai_club_insights.py` — `POST /api/clubs/{id}/insights/` end-to-end (mocked client)
- [ ] `clubs/tests/conftest.py` — **critical gap found by research**: the autouse `_block_real_anthropic_calls` fixture currently only exists in `players/tests/conftest.py`, NOT `clubs/tests/` — must be ported there before any club-insights test runs, or a forgotten client DI seam could attempt a real network call
- [ ] Framework install: none — pytest/pytest-django already fully configured project-wide

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|-------------|--------------------|
| Real LLM-generated narrative is well-grounded and readable | AI-03, AI-04 | A mocked-client test suite proves the plumbing/validator logic is correct but cannot prove a real Anthropic call produces genuinely well-grounded, coherent prose | Before marking the phase complete, run one real scouting-report request and one real club-insights request against the live dev DB via `manage.py shell` (or a live HTTP call with a real `ANTHROPIC_API_KEY`), and manually confirm the narrative reads sensibly and every number matches the grounding data |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
