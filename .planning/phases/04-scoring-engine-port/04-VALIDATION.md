---
phase: 04
slug: scoring-engine-port
status: ready
nyquist_compliant: true
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

Each plan's Task 1 (RED) creates its test file first (Wave 0 within that plan), then Task 2+ (GREEN) implements against it.

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| population substrate | 04-01 | 1 | SCORE-01..05 (substrate) | unit | `pytest scoring/tests/test_services_population.py -x` | 🔨 04-01 T1 | ⬜ pending |
| RMM service + breakdown | 04-02 | 2 | SCORE-01, SCORE-05 | unit | `pytest scoring/tests/test_services_rmm.py -x` | 🔨 04-02 T1 | ⬜ pending |
| Compatibility (CS) + breakdown | 04-03 | 2 | SCORE-02, SCORE-05 | unit+integration | `pytest scoring/tests/test_services_compatibility.py -x` | 🔨 04-03 T1 | ⬜ pending |
| Transfer Probability (TP) + 4-term breakdown | 04-03 | 2 | SCORE-04, SCORE-05 | unit+integration | `pytest scoring/tests/test_services_transfer_probability.py -x` | 🔨 04-03 T1 | ⬜ pending |
| Financial Fit (TFM) + money-scale unwrap | 04-04 | 2 | SCORE-03, SCORE-05 | unit+integration | `pytest scoring/tests/test_services_financial_fit.py -x` | 🔨 04-04 T1 | ⬜ pending |
| Combined summary orchestration | 04-05 | 3 | SCORE-01..05 | unit | `pytest scoring/tests/test_services_summary.py -x` | 🔨 04-05 T1 | ⬜ pending |
| 5 DRF endpoints + auth gate | 04-06 | 4 | cross-cutting + SCORE-01..05 | integration | `pytest scoring/tests/test_views.py -x` | 🔨 04-06 T1 | ⬜ pending |

*File Exists: 🔨 = created by that plan's Task 1 (RED) during execution · Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Each is created as the first (RED) task of the plan noted:

- [ ] `scoring/tests/test_services_population.py` (04-01) — covers the shared reconstruct→RMM-first→CS/TP substrate + resolve_club_name + null envelope
- [ ] `scoring/tests/test_services_rmm.py` (04-02) — covers SCORE-01, SCORE-05 (RMM breakdown)
- [ ] `scoring/tests/test_services_compatibility.py` (04-03) — covers SCORE-02, SCORE-05 (CS breakdown that RECONSTRUCTS compatibility_score via the role_scores_wide-merged player_row + null+reason envelope)
- [ ] `scoring/tests/test_services_transfer_probability.py` (04-03) — covers SCORE-04, SCORE-05 (4-term weighted breakdown)
- [ ] `scoring/tests/test_services_financial_fit.py` (04-04) — covers SCORE-03, SCORE-05 (TFM breakdown, feature_cols contract test against `.metrics.json`, money-scale unwrap regression test — must catch the log-scale `np.expm1()` bug the research flagged)
- [ ] `scoring/tests/test_services_summary.py` (04-05) — covers the combined summary endpoint's service orchestration (single reconstruction + CS-reconstruction consistency)
- [ ] `scoring/tests/test_views.py` (04-06) — DRF `APIClient`-level integration tests for all 5 endpoints, plus the shared "requires authentication" cross-cutting test
- [ ] No new pytest fixtures/framework install needed — `scoring/tests/conftest.py`'s `real_data_available` fixture (Phase 3) is directly reusable; synthetic-fixture-only tests don't need DB access at all, following `test_deterministic_scores.py`'s existing pattern

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|--------------------|
| TFM buying-club-context override actually changes predictions across different clubs | SCORE-03 | Automated tests can assert the mechanism is wired (club_id feeds into feature-building), but confirming the predictions are *sensibly* different (not just numerically different) for a real player across 2-3 real clubs benefits from a human sanity read, given the earlier finding that MAE is large relative to typical fees | Call `/players/{id}/clubs/{club_id}/financial-fit/` for the same player against 2-3 different real clubs; confirm predicted_fee varies and each club's buying-profile aggregates look plausible |
| Response envelope consistency across all 5 endpoints | SCORE-05, cross-cutting | The null+reason shape is locked in CONTEXT.md but its consistent application across 5 different endpoints/services benefits from a manual review pass, not just per-endpoint unit assertions | Read through all 5 endpoints' response shapes side by side; confirm the null+reason envelope pattern is identical everywhere a score can be unavailable |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready — plans validated for execution
