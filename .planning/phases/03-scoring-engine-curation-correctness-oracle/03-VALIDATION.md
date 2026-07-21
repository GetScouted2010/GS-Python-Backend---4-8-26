---
phase: 03
slug: scoring-engine-curation-correctness-oracle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-07-21
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-django 4.12.0 (already installed and configured — `get-scouted-be/pyproject.toml` sets `DJANGO_SETTINGS_MODULE`, `testpaths = ["clubs", "players", "transfers", "core", "accounts"]`) |
| **Config file** | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`) — `testpaths` needs a new entry once this phase's deliverables land |
| **Quick run command** | `cd get-scouted-be && .venv/bin/pytest <new-phase-3-test-path> -x -q` |
| **Full suite command** | `cd get-scouted-be && .venv/bin/pytest -q` |
| **Estimated runtime** | ~30-90 seconds (depends on full-population snapshot generation cost) |

---

## Sampling Rate

- **After every task commit:** Run the specific new test file for that task (`pytest <file> -x -q`)
- **After every plan wave:** Run `pytest scoring/tests/ -q` (or wherever this phase's tests land)
- **Before `/gsd:verify-work`:** Full suite green, plus manual review of the curation map's escalation items (the 2 four-definition functions + the resolved TFM/Transfer-Probability mapping) since those are judgment calls no automated test can fully verify
- **Max feedback latency:** ~90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | TBD | 0 | SC-1 (duplicate catalogue) | unit/data-check | `pytest scoring/tests/test_curation_map.py::test_all_20_names_present -x` | ❌ W0 | ⬜ pending |
| 03-01-02 | TBD | TBD | SC-2 (oracle snapshot) | integration | `pytest scoring/tests/test_oracle_snapshot.py::test_snapshot_coverage -x` | ❌ W0 | ⬜ pending |
| 03-01-03 | TBD | TBD | SC-3 (sklearn artifact separated/versioned) | unit | `pytest scoring/tests/test_transfer_value_model.py::test_artifact_loads_and_predicts -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | TBD | TBD | SC-4 (written curation map) | manual + doc-existence | `test -f .planning/phases/03-.../CURATION_MAP.md` (exact path decided at plan time) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scoring/` Django app (or equivalent standalone `scripts/`+`tests/` location — Claude's discretion per CONTEXT.md) needs at minimum a `tests/` dir and `__init__.py` before any of the above tests can be written
- [ ] `get-scouted-be/requirements/base.txt` — add `scikit-learn>=1.5,<2.0` and `joblib>=1.4,<2.0`, then `pip install -r requirements/base.txt` re-run in `.venv`
- [ ] No existing fixtures/conftest for scoring-domain tests — given CONTEXT.md's "full population, real data" oracle requirement, tests here should query real migrated Phase 1 data rather than using `factory_boy`-built synthetic fixtures (unlike Phase 1/2's pattern)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|--------------------|
| Duplicate-function escalation review (`prepare_team_and_transfer_signal`, `player_transfer_history` — both 4 definitions) | SC-1 | Requires human judgment on which of 4 divergent implementations is authoritative; policy explicitly requires user review, not automated resolution | Present the 4 versions of each function (line numbers 7041/11427/11702/12192 and 7093/11488/11870/12329) with diffs to the user; record their decision + reason in the curation map |
| TFM/Transfer-Probability score-mapping correctness | SC-3, SC-4 | Already resolved this session (RF → TFM, deterministic formula → Transfer Probability) but the curation map's write-up of this resolution needs a read-through, not just an automated existence check | Read the curation map's score-mapping section and confirm it matches the resolution recorded in `03-CONTEXT.md` |
| Sklearn model quality metrics (MAE, R²) sanity check | SC-3 | No minimum quality bar enforced this phase (by design) — a human should still glance at the numbers to catch a training pipeline that's obviously broken (e.g. R² wildly negative) vs. merely mediocre | Read the printed/logged MAE and R² values after training; confirm they're finite, non-NaN, and R² is not catastrophically negative (e.g. < -1) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
