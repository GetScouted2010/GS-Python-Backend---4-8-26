---
phase: 11
slug: position-needs-squad-simulation
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-26
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-django (existing project-wide setup) |
| **Config file** | `get-scouted-be/pyproject.toml` (`testpaths` already includes both `clubs` and `workspace`) |
| **Quick run command** | `cd get-scouted-be && pytest clubs/tests/test_position_needs.py workspace/tests/test_squad_simulation.py -x` |
| **Full suite command** | `cd get-scouted-be && pytest` |
| **Estimated runtime** | under a minute for the full suite |

---

## Sampling Rate

- **After every task commit:** the quick run command above
- **After every plan wave:** `cd get-scouted-be && pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-0X-0X | TBD | TBD | PLAN-01 (weak classification) | unit | `pytest clubs/tests/test_position_needs.py::test_classify_weak_when_depth_below_2 -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-01 (at-risk by age) | unit | `pytest clubs/tests/test_position_needs.py::test_classify_at_risk_by_age -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-01 (at-risk by contract expiry) | unit | `pytest clubs/tests/test_position_needs.py::test_classify_at_risk_by_contract_expiry -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-01 (strong classification) | unit | `pytest clubs/tests/test_position_needs.py::test_classify_strong -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-01 (endpoint + route ordering) | integration | `pytest clubs/tests/test_views_position_needs.py -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-03 (apply add/remove/swap) | unit | `pytest workspace/tests/test_squad_simulation.py::test_apply_add_remove_swap -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-03 (invalid player id -> 400) | unit + integration | `pytest workspace/tests/test_squad_simulation.py::test_invalid_player_id_400 -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-03 (baseline/simulated/delta shape) | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_response_shape -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-03 (never persists) | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_does_not_persist -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-03 (optional override used) | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_uses_override_when_provided -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-03 (ownership denied) | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_ownership_denied -x` | ❌ W0 | ⬜ pending |
| 11-0X-0X | TBD | TBD | PLAN-03 (null-safe metrics) | unit | `pytest workspace/tests/test_squad_simulation.py::test_null_values_excluded_not_zero_filled -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs finalized once gsd-planner assigns actual plan/wave numbers.*

---

## Wave 0 Requirements

- [ ] `clubs/tests/test_position_needs.py` — unit tests for `classify_position_needs` (mirror `test_services_club_insights.py`'s factory-based, non-real-data-dependent style)
- [ ] `clubs/tests/test_views_position_needs.py` — integration tests for the new endpoint (mirror `test_ai_club_insights.py`'s `auth_client` pattern; no Anthropic mocking needed, deterministic endpoint)
- [ ] `workspace/tests/test_squad_simulation.py` — unit + integration tests for simulation (reuse `workspace/tests/conftest.py`'s existing `player_factory`/`club_factory` and `authenticated_client` directly, confirmed sufficient without modification)
- [ ] `workspace/services.py` — does not exist yet; must be created as a structural prerequisite
- [ ] Framework install: none — pytest-django/factory_boy/APIClient already fully wired project-wide

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
