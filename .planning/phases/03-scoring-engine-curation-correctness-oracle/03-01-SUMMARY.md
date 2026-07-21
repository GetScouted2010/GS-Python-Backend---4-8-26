---
phase: 03-scoring-engine-curation-correctness-oracle
plan: 01
subsystem: scoring
tags: [django, pandas, scikit-learn, orm-bridge, field-mapping, dataframe]

# Dependency graph
requires:
  - phase: 01-data-foundation
    provides: Real migrated Postgres data (Player, PlayerRoleScore, Club, Transfer) and FIELD_MAPPING.md's canonical CSV<->Django<->script column-name mapping
provides:
  - scikit-learn + joblib installed and pinned in requirements/base.txt (foundation for Phase 4-6 model training/scoring)
  - scoring Django app skeleton (registered in INSTALLED_APPS, pytest testpaths, real_data_available fixture)
  - scoring.characterization.reconstruct module: build_players_df(), build_role_scores_wide(), build_team_styles_df(), build_transfers_df(), assert_columns_present()
affects: [04-rmm-port, 05-cs-tp-port, 06-tfm-caching, 07-oracle-snapshot]

# Tech tracking
tech-stack:
  added: [scikit-learn>=1.5,<2.0, joblib>=1.4,<2.0]
  patterns:
    - "ORM->script-shaped DataFrame reconstruction: rename Django .values() output via FIELD_MAPPING.md's reverse mapping (Django field name -> impact_model_v4.1.py literal string), never re-derive column names ad hoc"
    - "assert_columns_present(df, required, name) as the fail-loud guard every downstream calculator must call before reading columns -- prevents the silent zero-fill bug class CONCERNS.md identified"
    - "Never .fillna(0) genuinely-absent data (club playing styles) -- leave as NaN so downstream scoring reflects missing-data uncertainty, not a confidently-wrong zero"
    - "real_data_available pytest fixture: characterization tests query real migrated data and skip cleanly (not fail) when the DB is empty"

key-files:
  created:
    - get-scouted-be/scoring/apps.py
    - get-scouted-be/scoring/characterization/reconstruct.py
    - get-scouted-be/scoring/tests/conftest.py
    - get-scouted-be/scoring/tests/test_reconstruct.py
  modified:
    - get-scouted-be/requirements/base.txt
    - get-scouted-be/pyproject.toml
    - get-scouted-be/config/settings/base.py

key-decisions:
  - "PlayerRoleScore.role_name_raw pivoted with underscore-to-space normalization rather than the sanitized snake_case role_name -- gets closer to impact_model_v4.1.py's ROLE_COLUMNS_BY_POSITION literals, but the raw CSV source headers are themselves inconsistent about hyphens/parens (e.g. 'Wide_Centre-Back_(LCB)' vs 'Wide_Centre_Back_(RCB)'), so build_role_scores_wide logs coverage gaps (18/45 role names, mostly GK roles which legitimately have zero PlayerRoleScore rows) instead of fabricating a forced match -- full role-name curation is deferred to Phase 4's RMM port"
  - "player_id (UUID) is carried as the stable join key on every reconstructed DataFrame -- the original script has no stable id, only the non-unique Player display-name string"
  - "build_players_df() exposes both 'Minutes played' (FIELD_MAPPING.md's literal) and a bare 'Minutes' alias, since impact_model_v4.1.py's functions are inconsistent about which one they read directly"

patterns-established:
  - "Pattern: reconstruct.py's rename dicts are transcribed directly from FIELD_MAPPING.md (not re-derived), with inline comments citing the exact section -- keeps the single source of truth authoritative"

requirements-completed: []

# Metrics
duration: 25min
completed: 2026-07-21
---

# Phase 3 Plan 1: Scoring Foundation (deps + scoring app + ORM->DataFrame bridge) Summary

**Installed scikit-learn/joblib, stood up a minimal `scoring` Django app, and built the `reconstruct.py` bridge that turns real migrated Postgres data (41,708 players / 230,139 role scores / 1,060 clubs / 47,201 transfers) into the four script-literal-column-named DataFrames `impact_model_v4.1.py`'s ported functions expect.**

## Performance

- **Duration:** ~25 min
- **Completed:** 2026-07-21
- **Tasks:** 2/2 completed
- **Files modified:** 10 (3 modified, 7 created)

## Accomplishments
- scikit-learn 1.9.0 and joblib 1.5.3 installed into the existing venv and pinned in `requirements/base.txt`
- `scoring` Django app registered (INSTALLED_APPS + pytest testpaths), passes `manage.py check`
- `reconstruct.py` produces all four script-shaped DataFrames from the ORM, verified directly against the real dev dataset via `manage.py shell` (not just unit-test skip paths): 41,708-row players_df with `player_id`/`Minutes`/`Team`/`Market value` present, 38,626-row role-scores wide pivot with 42 role columns, 1,060-row team-styles df with a 77.45% null-style rate (matches FIELD_MAPPING.md's documented ~77% expectation, proving no silent zero-fill), 47,201-row transfers_df with all required columns

## Task Commits

1. **Task 1: scikit-learn/joblib deps + scoring app skeleton + pytest wiring** - `5ac4efa` (feat)
2. **Task 2: ORM->script-shaped DataFrame reconstruction module** - `312a1c1` (feat)

_No separate plan-metadata commit yet -- this SUMMARY/STATE/ROADMAP update is committed as the final commit below._

## Files Created/Modified
- `get-scouted-be/requirements/base.txt` - Added scikit-learn/joblib pins
- `get-scouted-be/pyproject.toml` - Added "scoring" to pytest testpaths
- `get-scouted-be/config/settings/base.py` - Registered "scoring" in INSTALLED_APPS
- `get-scouted-be/scoring/apps.py` - ScoringConfig
- `get-scouted-be/scoring/characterization/reconstruct.py` - build_players_df/build_role_scores_wide/build_team_styles_df/build_transfers_df/assert_columns_present
- `get-scouted-be/scoring/tests/conftest.py` - real_data_available fixture
- `get-scouted-be/scoring/tests/test_reconstruct.py` - 4 tests covering join-key presence, role-column pivot shape, NaN-preservation, transfer-column presence

## Decisions Made
- Used `role_name_raw` (not the sanitized `role_name`) as the pivot source for role scores, with a best-effort underscore->space normalizer, because it's structurally closer to `impact_model_v4.1.py`'s literal role-name strings -- but did not force a perfect match against every `ROLE_COLUMNS_BY_POSITION` entry, since the raw CSV source headers are themselves inconsistent (confirmed via direct inspection: 18/45 names have no normalized match, most of them GK roles that legitimately have zero `PlayerRoleScore` rows per `import_position_roles.py`'s own documented behavior). Logged, not fabricated -- full curation of this mismatch is explicitly Phase 4's job, not this plan's.
- Corrected several Django field names against FIELD_MAPPING.md's stated (but stale) casing: the model docstring's "lowercase for identifier/profile fields" decision means `market_value`, `contract_expires`, `birth_country`, `passport_country`, `foot`, `height`, `on_loan` are lowercase on `Player`, not the capitalized names FIELD_MAPPING.md's table literally shows -- verified directly against `players/models.py` rather than trusting the doc's casing at face value.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `@pytest.mark.django_db` cannot decorate a fixture function**
- **Found during:** Task 1, first `pytest scoring/` run
- **Issue:** `scoring/tests/conftest.py`'s `real_data_available` fixture was decorated with both `@pytest.fixture` and `@pytest.mark.django_db`, which modern pytest rejects ("Marks cannot be applied to fixtures") -- collection failed for the whole `scoring/` test package.
- **Fix:** Removed the `@pytest.mark.django_db` decorator and added `db` as a fixture-function parameter instead (pytest-django's documented way to give a fixture database access).
- **Files modified:** `get-scouted-be/scoring/tests/conftest.py`
- **Verification:** `pytest scoring/tests/test_reconstruct.py -x -q` collects and runs cleanly (4 skipped, 0 errors)
- **Committed in:** `5ac4efa` (part of Task 1 commit)

### Notable non-deviation observation

`pytest scoring/tests/test_reconstruct.py` skips all 4 tests even though the dev database has real migrated data (41,708 players) -- this is expected pytest-django behavior, not a bug: pytest-django's `db`/`django_db` fixtures run against a fresh, empty test-database clone created via migrations, entirely separate from whatever the real dev `DATABASE_URL` database contains. The plan's own `<done>` criterion anticipates this explicitly ("its tests pass against real migrated data (or skip cleanly if DB empty)"). To confirm the reconstruction functions are actually correct against the real dataset (not just that they skip safely), all four were additionally exercised directly via `manage.py shell` against the real dev DB -- see Accomplishments above for the resulting shapes/coverage numbers.

## Self-Check: PASSED
