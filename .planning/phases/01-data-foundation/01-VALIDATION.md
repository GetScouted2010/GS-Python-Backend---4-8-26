---
phase: 1
slug: data-foundation
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-django (per `.planning/research/STACK.md`, not yet installed — Wave 0 must add it) |
| **Config file** | none yet — `pyproject.toml [tool.pytest.ini_options]` created in Wave 0 |
| **Quick run command** | `pytest -x -q -k "not integration"` |
| **Full suite command** | `pytest -q` |
| **Estimated runtime** | ~30s (unit, fixture-based) / ~3-5 min (full, including integration against real CSVs) |

---

## Sampling Rate

- **After every task commit:** Run `pytest -x -q -k "not integration"` (unit tests against small fixture CSVs, not the full 41.7K/8.1M-row real files)
- **After every plan wave:** Run `pytest -q` (full suite, including integration tests against a real or realistically-sized sampled subset of the actual CSVs)
- **Before `/gsd:verify-work`:** Full suite must be green, plus a manual row-count reconciliation (`SELECT COUNT(*)` per table vs. source CSV row counts)
- **Max feedback latency:** 30 seconds (quick run)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-02 | 02 (test infra) | 2 | Wave 0 | infra | `pytest --collect-only` | 01-02 T1 | ⬜ pending |
| 01-05-T2 | 05 | 4 | DATA-01 | integration | `pytest players/tests/test_import.py::test_player_row_count -x` | 01-05 T2 | ⬜ pending |
| 01-05-T2 | 05 | 4 | DATA-01 | unit | `pytest players/tests/test_import.py::test_player_missing_field_handling -x` | 01-05 T2 | ⬜ pending |
| 01-05-T2 | 05 | 4 | DATA-03 | unit | `pytest players/tests/test_import.py::test_player_missing_field_handling -x` (also asserts extended_stats key/value + legacy_total_score at runtime) | 01-05 T2 | ⬜ pending |
| 01-04-T2 | 04 | 3 | DATA-02 | unit | `pytest clubs/tests/test_club_derivation.py::test_league_mode -x` | 01-04 T2 | ⬜ pending |
| 01-04-T2 | 04 | 3 | DATA-02 | unit | `pytest clubs/tests/test_club_derivation.py::test_playing_style_coverage -x` | 01-04 T2 | ⬜ pending |
| 01-04-T2 | 04 | 3 | DATA-05 | unit | `pytest clubs/tests/test_club_derivation.py::test_club_idempotent -x` (per-command idempotent upsert on Club.name) | 01-04 T2 | ⬜ pending |
| 01-06-T2 | 06 | 5 | DATA-03 | integration | `pytest players/tests/test_import.py::test_role_score_coverage -x` | 01-06 T2 | ⬜ pending |
| 01-08-T2 | 08 | 5 | DATA-04 | unit | `pytest transfers/tests/test_transfer_import.py::test_uniqueid_is_club_not_player -x` | 01-08 T2 | ⬜ pending |
| 01-08-T2 | 08 | 5 | DATA-04 | integration | `pytest transfers/tests/test_transfer_import.py::test_every_row_imports_unmatched_kept -x` (count == fixture rows; unmatched player kept with player=None) | 01-08 T2 | ⬜ pending |
| 01-08-T2 | 08 | 5 | DATA-04 | integration | `pytest transfers/tests/test_transfer_import.py::test_idempotent_rerun -x` | 01-08 T2 | ⬜ pending |
| 01-04-T1 | 04 | 3 | DATA-05 | unit | `pytest core/tests/test_import_report.py::test_report_shape -x` | 01-04 T1 | ⬜ pending |
| 01-05-T2 | 05 | 4 | DATA-05 | integration | `pytest players/tests/test_import.py::test_reimport_idempotent -x` | 01-05 T2 | ⬜ pending |
| 01-07-T2 | 07 | 5 | DATA-03 | integration | `pytest players/tests/test_compatibility.py -x` | 01-07 T2 | ⬜ pending |
| 01-09-T2 | 09 | 6 | DATA-05 | integration | `pytest core/tests/test_import_all.py::test_import_all_idempotent -x` | 01-09 T2 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs and exact wave/plan assignments filled in by the planner.*

---

## Wave 0 Requirements

- [ ] `pytest`, `pytest-django`, `factory_boy` install — no test framework exists yet (from-scratch Django project)
- [ ] `pyproject.toml [tool.pytest.ini_options]` (or `pytest.ini`) — test config
- [ ] `core/tests/conftest.py` — shared Postgres test DB fixtures, `django_db` marker setup
- [ ] Small fixture CSVs (10-20 representative rows per source file: Players, Playstyles, one Positions/ file, one Compatability Scores/ file, transferdata) — must include at least one row per known data-quality case: missing `Market_value`, dirty `Foot` value, ambiguous club league, unresolvable compatibility-score club header, a transferdata row exercising the `UniqueID`-is-Club-not-Player trap, and a transferdata row whose `Player` name is absent from `players_sample.csv` (unmatched-player-kept case)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Full-scale import performance/throughput against the real 41,708-row Players.csv and the ~8.1M-value compatibility matrices | DATA-01, DATA-03 | Real hardware throughput for `bulk_create` at this scale can't be verified in advance by research; needs an actual timed run | Run the real management command against the full dataset, record wall-clock time, confirm no OOM/timeout |
| Import report is genuinely reviewable (readable, actionable) by a human, not just structurally present | DATA-05 | "Reviewed" is a human judgment call per CONTEXT.md's mismatch-handling policy, not something a test assertion can capture | After a full real-data import, open the generated report and manually confirm flagged issues are legible and traceable to source rows |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
</content>
