---
phase: 8
slug: user-workspace-crud
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-25
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-django 4.9 |
| **Config file** | `get-scouted-be/pyproject.toml` (pytest-django settings) + repo-root `conftest.py` (`fixture_dir` fixture) |
| **Quick run command** | `cd get-scouted-be && pytest workspace/tests/ -x` |
| **Full suite command** | `cd get-scouted-be && pytest` |
| **Estimated runtime** | ~30-60 seconds (workspace subset); full suite several minutes |

---

## Sampling Rate

- **After every task commit:** Run `pytest workspace/tests/ -x`
- **After every plan wave:** Run `pytest` (full suite — protects Phase 7's `players`/`clubs` detail-view tests against the `RecentActivity`-logging insertion)
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-0X-0X | TBD | TBD | CRUD-06 | integration | `pytest workspace/tests/test_watchlist.py -x` | ❌ W0 | ⬜ pending |
| 08-0X-0X | TBD | TBD | CRUD-07 | integration | `pytest workspace/tests/test_shortlists.py -x` | ❌ W0 | ⬜ pending |
| 08-0X-0X | TBD | TBD | CRUD-08 | integration | `pytest workspace/tests/test_squad_plans.py -x` | ❌ W0 | ⬜ pending |
| 08-0X-0X | TBD | TBD | CRUD-09 | integration | `pytest workspace/tests/test_recent_activity.py -x` | ❌ W0 | ⬜ pending |
| 08-0X-0X | TBD | TBD | CRUD-10 | integration | `pytest workspace/tests/test_csv_export.py -x` | ❌ W0 | ⬜ pending |
| 08-0X-0X | TBD | TBD | cross-cutting | integration | `pytest workspace/tests/ -k ownership -x` | ❌ W0 | ⬜ pending |
| 08-0X-0X | TBD | TBD | cross-cutting | integration | `pytest workspace/tests/ -k scoping -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs finalized once gsd-planner assigns actual plan/wave numbers.*

---

## Wave 0 Requirements

- [ ] `workspace/tests/conftest.py` — shared fixtures (re-export `UserFactory`/`authenticated_client` pattern from `accounts/tests/conftest.py`; minimal `Player`/`Club` factory fixtures not dependent on real CSV-imported data, mirroring `players/tests/test_views.py`'s inline-create pattern)
- [ ] `workspace/tests/test_watchlist.py`, `test_shortlists.py`, `test_squad_plans.py`, `test_recent_activity.py`, `test_csv_export.py` — all new
- [ ] `workspace/__init__.py`, `apps.py`, `migrations/0001_initial.py` — new app scaffold
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
