---
phase: 12
slug: bidirectional-matching-replacements-player-club-fit
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-26
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + pytest-django (existing project-wide setup) |
| **Config file** | `get-scouted-be/pyproject.toml` (`testpaths` already includes `scoring`, `clubs`, `players`) |
| **Quick run command** | `.venv/bin/pytest scoring/tests/test_services_matching.py -x` |
| **Full suite command** | `.venv/bin/pytest` (must use project's own `.venv` — ambient interpreter lacks scikit-learn) |
| **Estimated runtime** | under a minute for the full pytest suite; PLAN-02's live `manage.py shell` correctness/perf spike is separately ~40-50s per call, not part of pytest |

---

## Sampling Rate

- **After every task commit:** `.venv/bin/pytest scoring/tests/test_services_matching.py -x`
- **After every plan wave:** `.venv/bin/pytest scoring clubs players`
- **Before `/gsd:verify-work`:** Full suite must be green, PLUS a live `manage.py shell` correctness/perf spike against the real dev DB for both `rank_replacement_players` and `rank_clubs_for_player` (pytest's own test DB is always empty — real-data correctness and latency claims are always verified live, per this project's established convention)
- **Max feedback latency:** 60 seconds (pytest); the live shell spike is a separate, explicitly-accepted multi-second-to-under-a-minute operation for PLAN-02, not subject to the 60s pytest budget

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-0X-0X | TBD | TBD | PLAN-02 (excludes current squad) | unit | `pytest scoring/tests/test_services_matching.py::test_rank_replacement_players_excludes_current_squad -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-02 (filters to requested position) | unit | `pytest scoring/tests/test_services_matching.py::test_rank_replacement_players_filters_position -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-02 (bounds to top-N) | unit | `pytest scoring/tests/test_services_matching.py::test_rank_replacement_players_bounds_top_n -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-02 (endpoint + route ordering) | integration | `pytest clubs/tests/test_replacements_view.py -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-02 (unknown club_id -> 404) | integration | `pytest clubs/tests/test_replacements_view.py::test_unknown_club_404 -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-04 (excludes player's own current club) | unit | `pytest scoring/tests/test_services_matching.py::test_rank_clubs_for_player_excludes_own_club -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-04 (financial_score not systematically null — regression guard for the squad_stats slicing bug found in research) | unit | `pytest scoring/tests/test_services_matching.py::test_rank_clubs_for_player_financial_score_not_systematically_null -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-04 (bounds to top-N) | unit | `pytest scoring/tests/test_services_matching.py::test_rank_clubs_for_player_bounds_top_n -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-04 (endpoint + route ordering) | integration | `pytest players/tests/test_club_matches_view.py -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | PLAN-04 (unknown player_id -> 404) | integration | `pytest players/tests/test_club_matches_view.py::test_unknown_player_404 -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | Both (success criterion 3 — shared primitives, no duplicated formula) | unit (structural) | `pytest scoring/tests/test_services_matching.py::test_matching_reuses_shared_primitives -x` | ❌ W0 | ⬜ pending |
| 12-0X-0X | TBD | TBD | Both (top-N real-TFM enrichment only, never full candidate set) | unit | `pytest scoring/tests/test_services_matching.py::test_real_tfm_called_only_for_top_n -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs finalized once gsd-planner assigns actual plan/wave numbers.*

---

## Wave 0 Requirements

- [ ] `scoring/tests/test_services_matching.py` — new file, unit tests for `rank_replacement_players`/`rank_clubs_for_player` (mirror `scoring/tests/test_services_*.py`'s `real_data_available` fixture pattern — pytest's test DB is empty, these are live-data tests)
- [ ] `clubs/tests/test_replacements_view.py` — new file, integration tests for `GET /api/clubs/{id}/replacements/` (mirror `clubs/tests/test_views_position_needs.py`'s `auth_client` pattern)
- [ ] `players/tests/test_club_matches_view.py` — new file, integration tests for `GET /api/players/{id}/club-matches/` (mirror `players/tests/test_ai_*.py`'s `auth_client` pattern)
- [ ] `scoring/services/matching.py` — does not exist yet; must be created as a structural prerequisite (`rank_replacement_players`, `rank_clubs_for_player`)
- [ ] `players/tests/conftest.py` — check for `real_data_available`-equivalent fixture; add if absent (mirrors the one already in `scoring/tests/conftest.py` and `clubs/tests/conftest.py`)
- [ ] Live `manage.py shell` timing spike for Pattern 2 (`rank_clubs_for_player`'s per-club loop) — no existing benchmark covers this new orchestration; must be run once against the real dev DB before the phase is marked complete
- [ ] Framework install: none — pytest-django/factory_boy/APIClient already fully wired project-wide

---

## Manual-Only Verifications

*None — all phase behaviors have automated verification per the Phase Requirements → Test Map above. The live `manage.py shell` spike is a real-data correctness/performance check, not a manual UX verification — it supplements pytest (whose test DB is always empty for this kind of check), matching every prior phase's convention.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
