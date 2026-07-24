---
phase: 5
slug: scoring-parity-testing
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-24
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.3.2 + pytest-django 4.8.0 |
| **Config file** | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`; `DJANGO_SETTINGS_MODULE = "config.settings.local"`, `testpaths` includes `scoring`) |
| **Quick run command** | `pytest scoring/tests/test_parity_edge_cases.py -x` |
| **Full suite command** | `pytest scoring/tests/test_parity_bulk.py scoring/tests/test_parity_api_sample.py scoring/tests/test_parity_edge_cases.py` |
| **Estimated runtime** | ~90-150s (bulk pass ~75-115s dominates; run against a dev DB with real migrated data — `real_data_available` fixture skips cleanly otherwise) |

---

## Sampling Rate

- **After every task commit:** Run the specific new test file being built (e.g. `pytest scoring/tests/test_parity_bulk.py -x`)
- **After every plan wave:** `pytest scoring/tests/test_parity_bulk.py scoring/tests/test_parity_api_sample.py scoring/tests/test_parity_edge_cases.py`
- **Before `/gsd:verify-work`:** Full suite must be green against the real dev DB with the committed oracle CSV (`scoring/oracle/scoring_oracle_v1_2026-07-22.csv`, or whichever is latest per the `_find_latest_oracle_csv` glob pattern)
- **Max feedback latency:** ~120s (bulk parity test dominates; acceptable given it exercises the full 41,708-player population by design)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | SCORE-06 | integration | `pytest scoring/tests/test_parity_bulk.py -x` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | SCORE-06 | integration | `pytest scoring/tests/test_parity_api_sample.py -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | SCORE-06 | integration | `pytest scoring/tests/test_parity_edge_cases.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

*Exact plan/task numbering above is provisional — the planner will finalize wave/task IDs; the three test files and their SCORE-06 mapping are the fixed contract.*

---

## Wave 0 Requirements

- [ ] `scoring/tests/test_parity_bulk.py` — full-population bulk parity (all 10 real position groups, per CONTEXT.md's corrected group count), covers SCORE-06's "every position group" clause
- [ ] `scoring/tests/test_parity_api_sample.py` — per-request service function + DRF endpoint parity on the ~30-player stratified sample, covers the wiring-bug-detection half of SCORE-06 (the class of bug Phase 4's CS `role_scores_wide` merge issue represents)
- [ ] `scoring/tests/test_parity_edge_cases.py` — named real-data edge cases (missing stats, boundary ages, zero-minutes players)
- [ ] Shared oracle-discovery helper — extract `_find_latest_oracle_csv` from `scoring/tests/test_oracle_snapshot.py` into `scoring/tests/conftest.py` or a small shared module, so all three new test files use the same version-agnostic lookup instead of duplicating it
- [ ] Shared tolerance/mismatch-report helper (`scoring/tests/_parity_helpers.py` or similar) — `np.isclose`-based comparator (abs tol 0.01 for RMM/CS/TP, rel tol 0.1% for TFM per CONTEXT.md) + CSV/markdown mismatch writer for failing position groups

---

## Manual-Only Verifications

*None — all phase behaviors (bulk parity, API-sample parity, edge-case parity) have automated verification via the three pytest files above. No behavior in this phase is UI/visual or otherwise unautomatable.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 150s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
