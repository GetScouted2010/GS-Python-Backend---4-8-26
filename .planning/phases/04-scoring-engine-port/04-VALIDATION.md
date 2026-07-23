---
phase: 04
slug: scoring-engine-port
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-23
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django (already configured) |
| **Config file** | `get-scouted-be/pyproject.toml` `[tool.pytest.ini_options]` — `DJANGO_SETTINGS_MODULE = "config.settings.local"`, `testpaths` includes `"scoring"` |
| **Quick run command** | `cd get-scouted-be && python -m pytest scoring/tests/test_services_rmm.py -x` (per-file, fast synthetic-fixture tests) |
| **Full suite command** | `cd get-scouted-be && python -m pytest scoring -x` |
| **Estimated runtime** | ~10-30 seconds (synthetic-fixture unit tests are fast; integration tests against real data skip cleanly when the dev DB is empty, per Phase 3's established pattern) |

---

## Sampling Rate

- **After every task commit:** Run the specific new `scoring/tests/test_services_*.py` / `test_views.py` file touched by that task
- **After every plan wave:** `python -m pytest scoring -x` (full suite, including Phase 3's existing characterization tests — Phase 4 must not regress them)
- **Before `/gsd:verify-work`:** Full suite green
- **Max feedback latency:** ~30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | TBD | 0 | SCORE-01 | unit | `pytest scoring/tests/test_services_rmm.py -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | TBD | TBD | SCORE-01 | integration | `pytest scoring/tests/test_views.py::test_rmm_endpoint_returns_real_score -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | TBD | TBD | SCORE-02 | unit+integration | `pytest scoring/tests/test_services_compatibility.py -x` / `test_views.py::test_compatibility_endpoint -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | TBD | TBD | SCORE-03 | unit+integration | `pytest scoring/tests/test_services_financial_fit.py -x` / `test_views.py::test_financial_fit_endpoint -x` | ❌ W0 | ⬜ pending |
| 04-01-05 | TBD | TBD | SCORE-04 | unit+integration | `pytest scoring/tests/test_services_transfer_probability.py -x` / `test_views.py::test_transfer_probability_endpoint -x` | ❌ W0 | ⬜ pending |
| 04-01-06 | TBD | TBD | SCORE-05 | unit | `pytest scoring/tests/test_services_*.py -k breakdown -x` | ❌ W0 | ⬜ pending |
| 04-01-07 | TBD | TBD | cross-cutting | integration | `pytest scoring/tests/test_views.py::test_endpoints_require_authentication -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scoring/tests/test_services_rmm.py` — covers SCORE-01, SCORE-05 (RMM breakdown)
- [ ] `scoring/tests/test_services_compatibility.py` — covers SCORE-02, SCORE-05 (CS breakdown + null+reason envelope)
- [ ] `scoring/tests/test_services_financial_fit.py` — covers SCORE-03, SCORE-05 (TFM breakdown, feature_cols contract test against `.metrics.json`, money-scale unwrap regression test — must catch the log-scale `np.expm1()` bug the research flagged)
- [ ] `scoring/tests/test_services_transfer_probability.py` — covers SCORE-04, SCORE-05 (4-term weighted breakdown)
- [ ] `scoring/tests/test_services_summary.py` — covers the combined summary endpoint's service orchestration
- [ ] `scoring/tests/test_views.py` — DRF `APIClient`-level integration tests for all 5 endpoints, plus the shared "requires authentication" cross-cutting test
- [ ] No new pytest fixtures/framework install needed — `scoring/tests/conftest.py`'s `real_data_available` fixture (Phase 3) is directly reusable; synthetic-fixture-only tests don't need DB access at all, following `test_deterministic_scores.py`'s existing pattern

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|--------------------|
| TFM buying-club-context override actually changes predictions across different clubs | SCORE-03 | Automated tests can assert the mechanism is wired (club_id feeds into feature-building), but confirming the predictions are *sensibly* different (not just numerically different) for a real player across 2-3 real clubs benefits from a human sanity read, given the earlier finding that MAE is large relative to typical fees | Call `/players/{id}/clubs/{club_id}/financial-fit/` for the same player against 2-3 different real clubs; confirm predicted_fee varies and each club's buying-profile aggregates look plausible |
| Response envelope consistency across all 5 endpoints | SCORE-05, cross-cutting | The null+reason shape is locked in CONTEXT.md but its consistent application across 5 different endpoints/services benefits from a manual review pass, not just per-endpoint unit assertions | Read through all 5 endpoints' response shapes side by side; confirm the null+reason envelope pattern is identical everywhere a score can be unavailable |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
