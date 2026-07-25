---
phase: 9
slug: ai-provider-interface-natural-language-search
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-25
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-django ≥4.9 |
| **Config file** | `get-scouted-be/pyproject.toml` (`DJANGO_SETTINGS_MODULE = "config.settings.local"`; `testpaths` already lists `players` — no new app needed) |
| **Quick run command** | `cd get-scouted-be && pytest players/tests/ -x` |
| **Full suite command** | `cd get-scouted-be && pytest` |
| **Estimated runtime** | ~20-40 seconds (players subset); full suite under a minute |

---

## Sampling Rate

- **After every task commit:** Run `pytest players/tests/ -x`
- **After every plan wave:** Run `pytest` (full suite — protects Phases 7/8's players/workspace tests)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-0X-0X | TBD | TBD | AI-05 | unit | `pytest players/tests/test_ai_factory.py -x` | ❌ W0 | ⬜ pending |
| 09-0X-0X | TBD | TBD | AI-01 | unit (mocked Anthropic client) | `pytest players/tests/test_ai_anthropic_parser.py -x` | ❌ W0 | ⬜ pending |
| 09-0X-0X | TBD | TBD | AI-01 | integration | `pytest players/tests/test_search_view.py -x` | ❌ W0 | ⬜ pending |
| 09-0X-0X | TBD | TBD | AI-01 (style field transform) | unit | `pytest players/tests/test_services_search.py::test_style_filter_field_name_transform -x` | ❌ W0 | ⬜ pending |
| 09-0X-0X | TBD | TBD | AI-02 (LLM failure → tier 2) | unit + integration | `pytest players/tests/test_search_view.py -k fallback -x` | ❌ W0 | ⬜ pending |
| 09-0X-0X | TBD | TBD | AI-02 (tier 2 → tier 3) | unit | `pytest players/tests/test_ai_fallback.py -x` | ❌ W0 | ⬜ pending |
| 09-0X-0X | TBD | TBD | AI-02 (keyword regex correctness) | unit | `pytest players/tests/test_ai_fallback.py -k keyword -x` | ❌ W0 | ⬜ pending |
| 09-0X-0X | TBD | TBD | CRUD-09 integration (RecentActivity) | integration | `pytest players/tests/test_search_view.py -k recent_activity -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs finalized once gsd-planner assigns actual plan/wave numbers.*

---

## Wave 0 Requirements

- [ ] `players/tests/test_ai_factory.py` — covers AI-05 (`get_nl_query_parser()` provider switch)
- [ ] `players/tests/test_ai_anthropic_parser.py` — covers AI-01 (mocked Anthropic client, "patch caller's own import binding" convention — never a real `client.messages.create()` call during pytest)
- [ ] `players/tests/test_ai_fallback.py` — covers AI-02's tier-2/tier-3 keyword fallback (pure regex, no network)
- [ ] `players/tests/test_services_search.py` — covers `search_players()`'s filter/style-field composition, including the field-name-transform regression test (Pitfall: `PlayerFilter` silently ignores `club__` lookups)
- [ ] `players/tests/test_search_view.py` — DRF `APIClient` integration tests for `POST /api/players/search/`: success, all 3 fallback tiers, `RecentActivity` logging, auth gate
- [ ] Safety-net fixture: `players/tests/` gets an autouse/module-level mock guard so no test can accidentally fire a real Anthropic API call (monkeypatch-based stub, no new dependency — matches this project's stdlib/existing-deps-first pattern)
- [ ] Framework install: none — pytest/pytest-django/factory_boy already in `requirements/dev.txt`

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification per the Phase Requirements → Test Map above.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
