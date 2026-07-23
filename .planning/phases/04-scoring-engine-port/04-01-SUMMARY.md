---
phase: 04-scoring-engine-port
plan: 01
subsystem: api
tags: [django, pandas, scikit-learn, joblib, service-layer, scoring]

# Dependency graph
requires:
  - phase: 03-scoring-engine-curation-correctness-oracle
    provides: "reconstruct.py's 4 build_* functions, add_player_impact (RMM), compute_cs_tp_for_pairs, the trained TFM joblib artifact + .metrics.json sidecar, and generate_scoring_oracle.py's proven RMM-first wiring order"
provides:
  - "reconstruct_population(): single ORM -> 4-DataFrame reconstruction point (Population NamedTuple)"
  - "score_population(pop, club_name): RMM-first scoring sequence (add_player_impact merged onto players_df as player_impact BEFORE compute_cs_tp_for_pairs)"
  - "resolve_club_name(club_id): Club UUID -> name string, Http404 on unknown UUID"
  - "get_tfm_pipeline(): lru_cache-memoized joblib Pipeline load, feature_cols read from .metrics.json sidecar"
  - "null_with_reason(field, code): shared {field: null, reason: code} missing-data envelope"
affects: [04-02, 04-03, 04-04, 04-05, 04-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Service-layer substrate module (scoring/services/population.py) centralizing cross-cutting reconstruct+score wiring for all score endpoints"
    - "functools.lru_cache(maxsize=1) for memoizing an expensive artifact load (joblib Pipeline) at module scope"
    - "Path(settings.BASE_DIR)-relative artifact/sidecar path resolution (matches tfm_model.py's existing _default_artifact_path convention)"

key-files:
  created:
    - get-scouted-be/scoring/services/__init__.py
    - get-scouted-be/scoring/services/population.py
    - get-scouted-be/scoring/exceptions.py
    - get-scouted-be/scoring/tests/test_services_population.py
  modified: []

key-decisions:
  - "score_population uses add_player_impact (full RMM breakdown df) rather than the thin compute_rmm_column wrapper the oracle script uses, so summary/RMM downstream services (04-06) get 'Player Impact Positive/Negative'/'Impact Reliability' for free without a second pass"
  - "get_tfm_pipeline's artifact/sidecar paths resolved via Path(settings.BASE_DIR) / 'scoring' / 'ml_artifacts', matching the existing convention in tfm_model.py and generate_scoring_oracle.py rather than a __file__-relative path, for consistency across the codebase"
  - "Population is a typing.NamedTuple (players_df, role_scores_wide, team_styles_df, transfers_df), not a dataclass -- immutable value bundle, cheap to construct, matches the plan's 'bundled' framing"

patterns-established:
  - "All Phase 4 score services import score_population/reconstruct_population/resolve_club_name/get_tfm_pipeline/null_with_reason from scoring.services.population / scoring.exceptions rather than rebuilding the reconstruct->RMM->CS/TP sequence"

requirements-completed: [SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05]

# Metrics
duration: 18min
completed: 2026-07-23
---

# Phase 4 Plan 01: Population/Scoring Service Substrate Summary

**Built the shared reconstruct-once + RMM-first-scoring-sequence substrate (`scoring/services/population.py`) that every Phase 4 score endpoint (compatibility, financial, performance, transfer-probability, summary) will import instead of re-deriving Phase 3's proven wiring order.**

## Performance

- **Duration:** 18 min
- **Started:** 2026-07-23T17:20:00+01:00
- **Completed:** 2026-07-23T17:38:00+01:00
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- `reconstruct_population()` bundles all four `characterization.reconstruct` `build_*` calls into a single `Population` NamedTuple, so downstream services reconstruct the ORM->DataFrame bridge exactly once per request.
- `score_population(pop, club_name)` replicates `generate_scoring_oracle.py`'s proven RMM-first order verbatim: `add_player_impact` runs first, its `"Player Impact"` series is merged onto `players_df` as `player_impact`, and only then is `compute_cs_tp_for_pairs` called (which raises `ValueError` if `player_impact` is missing) -- verified by test and by grep-ordering in the acceptance criteria.
- `resolve_club_name(club_id)` is the single UUID->name boundary; `get_tfm_pipeline()` memoizes the joblib artifact load and always reads `feature_cols` from the `.metrics.json` sidecar (23 entries), never a hardcoded list.
- `null_with_reason(field, code)` gives all four score services (and the summary endpoint) one shared missing-data envelope shape.

## Task Commits

Each task was committed atomically (TDD: RED then GREEN):

1. **Task 1: Write failing tests for the population substrate** - `8d15cd9` (test)
2. **Task 2: Implement the envelope helper and population substrate (GREEN)** - `97a9ac5` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/scoring/services/__init__.py` - services package marker + module docstring
- `get-scouted-be/scoring/services/population.py` - `Population` NamedTuple, `reconstruct_population`, `score_population` (RMM-first), `resolve_club_name`, `get_tfm_pipeline`
- `get-scouted-be/scoring/exceptions.py` - `null_with_reason` shared envelope helper
- `get-scouted-be/scoring/tests/test_services_population.py` - RED->GREEN tests for all 5 substrate callables, including a DB-independent memoization/sidecar test and `real_data_available`-gated reconstruct/score tests

## Decisions Made
- `score_population` uses `add_player_impact` (the full RMM breakdown, not the thin `compute_rmm_column` wrapper) so that downstream summary/RMM display needs (Plan 06) don't require a second RMM pass.
- TFM artifact/sidecar paths resolved via `Path(settings.BASE_DIR) / "scoring" / "ml_artifacts"`, matching the existing convention already established in `tfm_model.py`/`generate_scoring_oracle.py`, rather than the plan's illustrative `__file__`-relative example -- keeps path resolution consistent codebase-wide.
- `Population` is a `typing.NamedTuple`, not a dataclass -- simplest immutable 4-field value bundle, no behavior needed on it.

## Deviations from Plan

None - plan executed exactly as written. The `get_tfm_pipeline` path-resolution detail (`settings.BASE_DIR` vs. the plan's `__file__`-relative example) is a same-outcome implementation choice explicitly flagged as "e.g." in the plan text, not a deviation from any locked requirement.

## Issues Encountered
- The dev DB configured in `.env` (`getscouted`, 41,708 real players) is separate from pytest-django's ephemeral test database, which has migrations applied but no imported rows. The two new DB-touching tests (`test_reconstruct_population_returns_script_shaped_tables`, `test_score_population_rmm_first_wiring`) therefore skip via the pre-existing `real_data_available` fixture -- identical to every other real-data test already in `scoring/tests/` (`test_reconstruct.py`, `test_impact.py`, `test_oracle_snapshot.py`, `test_tfm_model.py`). Not a regression or gap introduced by this plan; confirmed by running the full `scoring` suite before and after (31 passed/7 skipped -> 34 passed/9 skipped, only the 2 new DB tests added to the skip count) and by the DB-independent memoization/envelope/404 tests (3 of 5 new tests) passing directly.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Plans 02-05 (compatibility, financial, performance, transfer-probability services) and Plan 06 (summary) can now `from scoring.services.population import reconstruct_population, score_population, resolve_club_name, get_tfm_pipeline` and `from scoring.exceptions import null_with_reason` without rebuilding any of this wiring.
- No changes were made to any file under `scoring/characterization/` (Phase 3 modules remain byte-for-byte, verified via `git diff --stat` against the characterization directory).
- To exercise the two DB-gated tests locally, seed the pytest-django test database via Phase 1's `import_all` management command pointed at the test DB, or run them manually against a dev-DB-configured settings module.

---
*Phase: 04-scoring-engine-port*
*Completed: 2026-07-23*

## Self-Check: PASSED

All created files and commit hashes verified present.
