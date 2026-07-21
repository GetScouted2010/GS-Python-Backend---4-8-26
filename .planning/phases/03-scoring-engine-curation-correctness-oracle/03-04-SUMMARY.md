---
phase: 03-scoring-engine-curation-correctness-oracle
plan: 04
subsystem: scoring
tags: [pandas, django, characterization, rmm, player-impact]

# Dependency graph
requires:
  - phase: 03-01
    provides: scoring Django app skeleton, reconstruct.py's build_players_df ORM->DataFrame bridge, assert_columns_present, real_data_available fixture
provides:
  - "get-scouted-be/scoring/characterization/impact.py: faithful port of _build_std_lookup, the 8 _calc_*_impact_raw position calculators, add_player_impact, and compute_rmm_column(players_df) -> pd.Series keyed by player_id"
  - "APPLIED_FIXES record for the Minutes-column silent-default bug, ready for Plan 07's curation map"
affects: [03-07 (oracle snapshot assembly imports compute_rmm_column), Phase 4 SCORE-01 (RMM port)]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Faithful verbatim-extraction port pattern (weights/thresholds untouched, only missing-column silent-defaults fixed) established in 03-01, continued here for the RMM/Player Impact calculators"]

key-files:
  created:
    - get-scouted-be/scoring/characterization/impact.py
    - get-scouted-be/scoring/tests/test_impact.py
  modified: []

key-decisions:
  - "APPLIED_FIXES scope kept narrow to the single CONCERNS.md-documented pattern (whole-column Minutes defaulting to 0 via _ensure_minutes) -- all other missing-column fallbacks (_get, _std's 50.0 neutral default, _build_std_lookup's per-metric 50.0 default) are source-intentional quirks and were left untouched per 03-CONTEXT.md"
  - "league_weights dict ported verbatim (identical duplicate at source lines ~3062/~4677) even though it is not read anywhere in the RMM (add_player_impact) code path -- carried forward per this plan's explicit read_first/acceptance-criteria directive for later Performance Score/Transfer Probability phases"
  - "Real-data coverage test (test_rmm_full_population_coverage) is expected to skip under pytest -- pytest-django's db fixture uses an empty test-DB clone, never the real dev DB (documented precedent from 03-01-SUMMARY.md); full-population correctness was independently verified via manage.py shell against the real dev DB"

requirements-completed: []

# Metrics
duration: 15min
completed: 2026-07-21
---

# Phase 3 Plan 04: RMM (Player Impact) Characterization Summary

**Faithful pandas port of the 8 position-specific Impact calculators + `add_player_impact`/`compute_rmm_column`, run against the real 41,708-player reconstructed population with 99.998% RMM coverage and zero out-of-range/spurious-zero values.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-21T22:34:46Z (approx, after 03-01 completion)
- **Completed:** 2026-07-21T22:47:50Z
- **Tasks:** 2 completed
- **Files modified:** 2 (both new)

## Accomplishments

- Extracted `_build_std_lookup`, `_std`, the 8 `_calc_*_impact_raw` position calculators (GK/CB/FB/CMF/DMF/AMF/Winger/CF), `POSITION_NORMALISATION`/`normalise_position`, `_failed_actions`, and the shared numeric helpers verbatim from `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` into `get-scouted-be/scoring/characterization/impact.py` -- every weight/threshold preserved unchanged
- Added `add_player_impact(df)` (verbatim) and the new `compute_rmm_column(players_df) -> pd.Series` convenience wrapper (keyed by `player_id`) that Plan 07's oracle generator will import
- Fixed the one qualifying missing-column silent-default in this code path: `_ensure_minutes` now raises `ValueError` instead of zero-filling the whole `Minutes` column when no Minutes-equivalent column exists at all -- recorded in `APPLIED_FIXES` for Plan 07's curation map
- Verified against the real reconstructed 41,708-player population directly via `manage.py shell` (pytest's `django_db` fixture uses an empty test-DB clone, so the pytest coverage test itself skips -- documented, expected behavior matching 03-01's precedent): 41,707/41,708 players scored (99.998%), all 10 position groups (GK/CB/LB/RB/CM/DMF/AMF/LW/RW/CF) have at least one scored player, every value in `[0.01, 100.0]`, zero out-of-range or spurious-zero results

## Task Commits

1. **Task 1: Extract std_lookup + the 8 position impact calculators** - `88e5be5` (feat)
2. **Task 2: add_player_impact wrapper + full-population RMM smoke over real data** - `c0795b3` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified

- `get-scouted-be/scoring/characterization/impact.py` - Faithful RMM/Player Impact port: `_build_std_lookup`, 8 `_calc_*_impact_raw` calculators, `add_player_impact`, `compute_rmm_column`, `APPLIED_FIXES`, `league_weights` (verbatim, unused in this path)
- `get-scouted-be/scoring/tests/test_impact.py` - Synthetic-data unit tests (std_lookup percentile shape, single calculator 4-tuple shape, missing-Minutes ValueError guard, Minutes-fallback acceptance) + `test_rmm_full_population_coverage` (real-data, `django_db`, skips cleanly against empty test DB)

## Decisions Made

See `key-decisions` in frontmatter above:
- Narrow APPLIED_FIXES scope (only the whole-column Minutes silent-default)
- `league_weights` ported verbatim though unused in this path, per plan directive
- Real-data coverage test's expected pytest-skip + independent `manage.py shell` verification, matching 03-01's established pattern

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Test-only crash in `add_player_impact`'s `finishing_waste` computation when `xG per 90`/`Non-penalty goals per 90` are absent**
- **Found during:** Task 2 (writing `test_add_player_impact_accepts_minutes_played_fallback`)
- **Issue:** The verbatim-ported line `df.get("xG per 90", 0).fillna(0)...` crashes with `AttributeError: 'int' object has no attribute 'fillna'` when a df lacks those columns entirely (`DataFrame.get` returns the scalar default `0`, not a Series). This is a genuine source quirk, but it only manifests when a df is missing columns that the real reconstructed `players_df` always provides (`FIELD_MAPPING.md`'s `_STAT_RENAME` guarantees both). Since this crash never occurs in the actual pipeline and the plan's fix-scope is deliberately narrow (only the documented Minutes silent-default pattern), the implementation was left untouched (faithful port preserved) and the synthetic test fixture was corrected instead to include those two always-present columns, matching the real-world contract `add_player_impact` actually receives.
- **Fix:** Added `"xG per 90"` and `"Non-penalty goals per 90"` columns to the synthetic test DataFrame in `test_add_player_impact_accepts_minutes_played_fallback`, with an explanatory code comment.
- **Files modified:** `get-scouted-be/scoring/tests/test_impact.py`
- **Verification:** `pytest scoring/tests/test_impact.py -x -q` passes
- **Committed in:** `c0795b3` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking, test-fixture-only -- no production code changed beyond the plan's own scope)
**Impact on plan:** No scope creep; the source quirk itself is preserved untouched per 03-CONTEXT.md, since it never fires against real reconstructed data.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `compute_rmm_column(players_df)` is ready for Plan 07's oracle snapshot generator to import directly
- `APPLIED_FIXES` is ready to be copied into Plan 07's curation map "Fixes applied" section
- Phase 4's SCORE-01 port can lift `impact.py`'s calculators as its starting point (already faithfully extracted and unit-tested)
- No blockers

---
*Phase: 03-scoring-engine-curation-correctness-oracle*
*Completed: 2026-07-21*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/characterization/impact.py
- FOUND: get-scouted-be/scoring/tests/test_impact.py
- FOUND: .planning/phases/03-scoring-engine-curation-correctness-oracle/03-04-SUMMARY.md
- FOUND commit: 88e5be5 (Task 1)
- FOUND commit: c0795b3 (Task 2)
- Verified: `def add_player_impact`, `APPLIED_FIXES`, `league_weights` all present in impact.py; `def test_rmm_full_population_coverage` present in test_impact.py
