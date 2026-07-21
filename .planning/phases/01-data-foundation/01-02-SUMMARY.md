---
phase: 01-data-foundation
plan: 02
subsystem: testing
tags: [pytest, pytest-django, factory_boy, fixtures, csv]

# Dependency graph
requires:
  - phase: 01-data-foundation (plan 01)
    provides: Django project skeleton, config.settings.local, DATASET_DIR setting
provides:
  - pytest + pytest-django + factory_boy installed and wired to config.settings.local
  - core/tests/conftest.py with a fixture_dir path fixture used by every import test
  - Five hand-seeded fixture CSVs (players, playstyles, positions/CB, compatibility/CB,
    transferdata) mirroring the real dataset headers exactly, each carrying the known
    data-quality edge cases import tasks must handle
affects: [01-03 (models), 01-04 (club derivation), 01-05 (player import), 01-06 (role scores), 01-07 (compatibility import), 01-08 (transfer import), 01-09 (import-all orchestration)]

# Tech tracking
tech-stack:
  added: [pytest>=8.0, pytest-django>=4.9, factory_boy>=3.3]
  patterns:
    - "Import unit tests run against tiny hand-seeded fixture CSVs (core/tests/fixtures/), never the real 41.7K/8.1M-row files, via the shared fixture_dir fixture"
    - "Each fixture file's first line is copied verbatim from the corresponding real CSV header so column-name assumptions in import code are exercised exactly"
    - "One deliberately-unresolvable identifier is seeded per fixture (compatibility club header, transferdata Player not present in players_sample) so fallback/edge-case code paths have a concrete row to assert against"

key-files:
  created:
    - get-scouted-be/requirements/dev.txt
    - get-scouted-be/pyproject.toml
    - get-scouted-be/core/tests/__init__.py
    - get-scouted-be/core/tests/conftest.py
    - get-scouted-be/core/tests/fixtures/players_sample.csv
    - get-scouted-be/core/tests/fixtures/playstyles_sample.csv
    - get-scouted-be/core/tests/fixtures/positions_CB_sample.csv
    - get-scouted-be/core/tests/fixtures/compatibility_CB_sample.csv
    - get-scouted-be/core/tests/fixtures/transferdata_sample.csv
    - get-scouted-be/core/tests/fixtures/README.md

key-decisions:
  - "transferdata_sample.csv reuses the REAL dataset's own coincidence (UniqueID=81 is Genk, a club, in transferdata final.csv, while UniqueID=81 is the genuine player D. Solanke in Players.csv) instead of inventing a synthetic trap, so the fixture is provably representative of the actual bug class"
  - "Compatibility fixture trims the real 212 club columns down to 6, including one resolvable set (matching Club values in players_sample.csv) and two unresolvable ones (St_DOT_ Louis City, AGF) to exercise the club=null / club_name_raw fallback without bloating the fixture"
  - "Playstyles fixture covers only 2 of 5 clubs referenced by players_sample.csv, mirroring the real dataset's ~77% playing-style-null club coverage gap"

requirements-completed: [DATA-01, DATA-02, DATA-04, DATA-05]

# Metrics
duration: 22min
completed: 2026-07-20
---

# Phase 01 Plan 02: Test Infrastructure + Seeded Fixture CSVs Summary

**pytest-django wired to config.settings.local plus five hand-seeded fixture CSVs (headers copied verbatim from the real dataset) encoding every known data-quality trap the Phase 1 import tasks must handle, including the real UniqueID-is-club-not-player collision (Genk=81 vs. player D. Solanke=81).**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-20T18:05:00Z
- **Completed:** 2026-07-20T18:27:08Z
- **Tasks:** 2
- **Files modified:** 10

## Accomplishments
- pytest + pytest-django + factory_boy installed in the project venv and configured via `pyproject.toml [tool.pytest.ini_options]` against `config.settings.local`; `pytest --collect-only` runs cleanly with zero configuration errors
- `core/tests/conftest.py` provides a `fixture_dir` fixture (derived from `__file__`, no hardcoded absolute paths) that every downstream import test will use to locate its sample CSV
- Five fixture CSVs created, each starting with the exact header row from its real counterpart, seeded with 10-20 rows covering: ambiguous club/league (mode-derivation), blank/zero Market_value, dirty Foot values, GK exclusion, playing-style coverage gaps, an unresolvable compatibility club header, and the transferdata club-scoped-UniqueID trap
- `README.md` documents exactly which row in each fixture demonstrates which edge case, so downstream test authors (plans 04-09) know which rows to assert against

## Task Commits

1. **Task 1: Install and configure pytest-django** - `df93b67` (chore)
2. **Task 2: Author seeded fixture CSVs for every source file** - `5711ba9` (test)

**Plan metadata:** (final commit below)

## Files Created/Modified
- `get-scouted-be/requirements/dev.txt` - pytest, pytest-django, factory_boy dev dependencies
- `get-scouted-be/pyproject.toml` - `[tool.pytest.ini_options]`: DJANGO_SETTINGS_MODULE, testpaths, integration marker
- `get-scouted-be/core/tests/__init__.py` - empty package marker
- `get-scouted-be/core/tests/conftest.py` - shared `fixture_dir` fixture, django_db marker documented
- `get-scouted-be/core/tests/fixtures/players_sample.csv` - 15 player rows, 135-col real header, all seeded edge cases
- `get-scouted-be/core/tests/fixtures/playstyles_sample.csv` - 2-club playing-style coverage gap
- `get-scouted-be/core/tests/fixtures/positions_CB_sample.csv` - 4 CB role rows matching players_sample UniqueIDs
- `get-scouted-be/core/tests/fixtures/compatibility_CB_sample.csv` - 6-club header incl. one unresolvable club
- `get-scouted-be/core/tests/fixtures/transferdata_sample.csv` - 12-row club-scoped-UniqueID trap fixture
- `get-scouted-be/core/tests/fixtures/README.md` - per-row edge-case documentation

## Decisions Made
- Reused the real dataset's own UniqueID=81 collision (Genk club vs. D. Solanke player) as the transferdata trap row rather than inventing a synthetic one, so the fixture is a faithful, provably-representative reproduction of the actual data-quality hazard import code must guard against.
- Compatibility fixture kept at 6 club columns (not the real 212) with one deliberately-unresolvable header (`St_DOT_ Louis City`) and one incidentally-unresolvable real club name (`AGF`), balancing fixture size against edge-case coverage.
- Playstyles fixture intentionally omits 3 of 5 players_sample.csv clubs to mirror the real dataset's playing-style-null coverage gap (~77% of real clubs lack playing-style rows).

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria satisfied on first pass; no bugs, missing functionality, or blocking issues encountered.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Test infrastructure (pytest-django, factory_boy) and all five seeded fixture CSVs are in place and verified (`pytest --collect-only` green, trap-fixture assertion passes).
- Plans 04-09 (club derivation, player import, role scores, compatibility import, transfer import, import-all orchestration) can now write `pytest -x -q -k "not integration"` unit tests against `core/tests/fixtures/` immediately, with the `fixture_dir` fixture already available from `core/tests/conftest.py`.
- No blockers for downstream import-task plans.

---
*Phase: 01-data-foundation*
*Completed: 2026-07-20*
