---
phase: 7
slug: core-crud-players-clubs
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-25
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-django 4.12.0 |
| **Config file** | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`; `testpaths` includes `players`, `clubs`, `transfers`) |
| **Quick run command** | `pytest players/tests/ clubs/tests/ -x` |
| **Full suite command** | `pytest` |
| **Estimated runtime** | Quick: a few seconds (plain ORM queries against the empty pytest test DB, clean-skipping real-data assertions). Full phase-gate verification additionally requires at least one live `manage.py shell` check per success criterion against the real dev DB, per this project's established pattern (Phases 1-6). |

---

## Sampling Rate

- **After every task commit:** `pytest players/tests/ clubs/tests/ -x`
- **After every plan wave:** `pytest` (full suite)
- **Before `/gsd:verify-work`:** Full suite green, plus real-data spot-checks against the live dev DB for each of CRUD-01 through CRUD-05
- **Max feedback latency:** seconds (no expensive whole-population operation is on this phase's critical path — CRUD-03's `get_summary()` call is already the ~0.2s Phase-6-fast own-club path)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-xx-01 | TBD | TBD | CRUD-01 | integration | `pytest players/tests/test_views.py -k list -x` | ❌ W0 | ⬜ pending |
| 07-xx-02 | TBD | TBD | CRUD-02 | integration | `pytest clubs/tests/test_views.py -k list -x` | ❌ W0 | ⬜ pending |
| 07-xx-03 | TBD | TBD | CRUD-03 | integration | `pytest players/tests/test_views.py -k detail -x` | ❌ W0 | ⬜ pending |
| 07-xx-04 | TBD | TBD | CRUD-04 | integration | `pytest clubs/tests/test_views.py -k detail -x` | ❌ W0 | ⬜ pending |
| 07-xx-05 | TBD | TBD | CRUD-05 | integration | `pytest players/tests/test_views.py clubs/tests/test_views.py -k ids -x` | ❌ W0 | ⬜ pending |
| 07-xx-06 | TBD | TBD | cross-cutting | unit | `pytest players/tests/test_views.py clubs/tests/test_views.py -k authentication -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Exact plan/task numbering is provisional — the planner finalizes wave/task IDs; the requirement-to-test-file mapping above is the fixed contract.*

---

## Wave 0 Requirements

- [ ] `players/tests/conftest.py` — new `real_data_available` fixture, mirroring `scoring/tests/conftest.py`'s implementation verbatim (not auto-visible across sibling app directories)
- [ ] `clubs/tests/conftest.py` — same fixture, club-scoped
- [ ] `players/tests/test_views.py`, `clubs/tests/test_views.py` — new files, following `scoring/tests/test_views.py`'s `auth_client` (force-authenticated real `accounts.User`) fixture pattern
- [ ] `django-filter` added to project dependencies (`requirements/base.txt` or equivalent) and `INSTALLED_APPS`/`REST_FRAMEWORK` settings — no test-framework install needed (pytest/pytest-django already fully configured project-wide), but this is a genuine new runtime dependency the phase introduces

---

## Manual-Only Verifications

*None — all 5 success criteria (list/filter/sort/paginate Players, list/filter Clubs, Player detail, Club detail, multi-fetch) are exercisable via automated DRF test client requests. No behavior in this phase is UI/visual or otherwise unautomatable.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
