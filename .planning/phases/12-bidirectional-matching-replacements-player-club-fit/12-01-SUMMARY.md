---
phase: 12-bidirectional-matching-replacements-player-club-fit
plan: 01
subsystem: api
tags: [django, pytest, scoring, matching, tfm, structural-scaffold]

# Dependency graph
requires:
  - phase: 06-scoring-performance-caching-layer
    provides: get_scored_population/reconstruct_population memoized substrate and is_own_club/get_own_club_id helpers
  - phase: 04-scoring-engine-port
    provides: get_financial_fit (TFM) and compute_cs_tp_for_pairs/add_player_impact primitives this module will reuse
provides:
  - "scoring/services/matching.py module skeleton with rank_replacement_players and rank_clubs_for_player NotImplementedError stubs"
  - "Fully-implemented shared _attach_real_tfm helper (bounded top-N real-TFM enrichment primitive both directions will call)"
  - "3 Wave 0 RED test files pinning PLAN-02/PLAN-04 named-test contracts from 12-VALIDATION.md"
affects: [12-02-PLAN.md, 12-03-PLAN.md, 12-04 (phase verification)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Single shared matching.py module + single shared _attach_real_tfm enrichment helper structurally guarantees success criterion 3 (both directions reuse one shared service, never duplicated formula logic)"
    - "Real TFM (predicted_fee/value_verdict) is attached only to a bounded top-N slice via _attach_real_tfm, kept in a distinct `financial_fit` key separate from the cheap `financial_score` label-average ranking column"

key-files:
  created:
    - get-scouted-be/scoring/services/matching.py
    - get-scouted-be/scoring/tests/test_services_matching.py
    - get-scouted-be/clubs/tests/test_replacements_view.py
    - get-scouted-be/players/tests/test_club_matches_view.py
  modified: []

key-decisions:
  - "test_matching_reuses_shared_primitives asserts actual `from ... import ...` statements via ast.parse (not substring-in-source-text), since a plain substring check would trivially pass once the module docstring merely mentions the shared-primitive names in prose -- confirmed this by observing a false-positive pass before switching to the ast-based check"

patterns-established:
  - "Wave 0 RED test scaffold convention for a not-yet-implemented service module: unit tests skip cleanly (real_data_available gate) or fail (NotImplementedError/missing import), integration tests fail (404, route not wired) except accidental-pass 404-vs-404 checks -- all still collect successfully, proven by --collect-only exiting 0"

requirements-completed: []  # PLAN-02/PLAN-04 not yet functionally satisfied -- this plan only lays the shared structural foundation; implementation lands in 12-02/12-03

# Metrics
duration: 15min
completed: 2026-07-26
---

# Phase 12 Plan 01: Shared Matching Foundation + Wave 0 Test Scaffold Summary

**New `scoring/services/matching.py` module holding both ranking function contracts plus a fully-implemented shared `_attach_real_tfm` top-N enrichment helper, backed by 3 new Wave 0 RED pytest files (16 tests) pinning every named test from 12-VALIDATION.md before either ranking direction is implemented.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-26T16:43:00Z (approx)
- **Completed:** 2026-07-26T16:58:24Z
- **Tasks:** 2
- **Files modified:** 4 (all new)

## Accomplishments
- `scoring/services/matching.py` created with `DEFAULT_TOP_N = 10`, signature-only `rank_replacement_players`/`rank_clubs_for_player` stubs (raise `NotImplementedError`, implemented in 12-02/12-03), and the fully-implemented shared `_attach_real_tfm(entries, pairs, key="financial_fit")` helper that calls `get_financial_fit` exactly once per top-N entry.
- 3 new Wave 0 test files (`scoring/tests/test_services_matching.py`, `clubs/tests/test_replacements_view.py`, `players/tests/test_club_matches_view.py`) collecting exactly the 16 named tests specified in 12-VALIDATION.md's Per-Task Verification Map.
- Confirmed no duplicate `real_data_available` fixture was added to `players/tests/conftest.py` (it already existed there).
- Live-verified the expected Wave 0 RED/GREEN split against the real dev-DB-backed suite: `_attach_real_tfm`'s call-count guard (`test_real_tfm_called_only_for_top_n`) passes now (the helper is fully implemented); the structural shared-primitives guard and both integration endpoint suites correctly fail now (routes/imports not yet wired) and will turn green once 12-02/12-03 land; unit tests requiring real DB data skip cleanly against the empty pytest test DB.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scoring/services/matching.py skeleton + shared _attach_real_tfm helper** - `a15a02b` (feat)
2. **Task 2: Create the 3 Wave 0 test files (RED scaffold) with all named tests** - `84bd4a7` (test)

**Plan metadata:** (this commit)

## Files Created/Modified
- `get-scouted-be/scoring/services/matching.py` - Shared bidirectional-matching module: `DEFAULT_TOP_N`, both ranking function stubs, and the fully-implemented `_attach_real_tfm` helper
- `get-scouted-be/scoring/tests/test_services_matching.py` - 8 unit tests: exclusion/position-filter/top-N-bound tests for both directions, a structural shared-primitives-import guard, and a real-TFM call-count guard
- `get-scouted-be/clubs/tests/test_replacements_view.py` - 4 integration tests for `GET /api/clubs/{id}/replacements/`
- `get-scouted-be/players/tests/test_club_matches_view.py` - 4 integration tests for `GET /api/players/{id}/club-matches/`

## Decisions Made
- Made `test_matching_reuses_shared_primitives` parse actual AST import statements (`ast.parse` + `ImportFrom` node inspection) rather than a plain substring-in-source check. A first-draft substring check trivially passed because the module's own docstring prose mentions `compatibility_score`/`role_fit`/`financial_score`/`transfer_probability`/`deterministic_scores` -- the ast-based check makes this test a genuine structural regression guard that stays RED until 12-02/12-03 add real import statements, matching the plan's stated Wave 0 RED-scaffold intent.

## Deviations from Plan

None - plan executed as written, with one self-correction applied before committing (see Decisions Made above: the structural test was tightened from a substring check to an AST-based check to avoid a false-positive pass, discovered during the plan's own required verification step, not a deviation from the plan's instructions).

## Issues Encountered
- The plan's literal `<automated>` verify commands (bare `.venv/bin/python -c ...` / `.venv/bin/pytest ...`) require `DJANGO_SETTINGS_MODULE=config.settings.local` and `django.setup()` to run standalone outside pytest (pytest itself picks up `DJANGO_SETTINGS_MODULE` from `pyproject.toml`'s `[tool.pytest.ini_options]` automatically). Resolved by exporting the env var / calling `django.setup()` explicitly for the Task 1 standalone import check; the Task 2 pytest `--collect-only` command worked as written with no adjustment needed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `scoring/services/matching.py` and `_attach_real_tfm` are the fixed shared contract 12-02-PLAN.md (`rank_replacement_players`) and 12-03-PLAN.md (`rank_clubs_for_player`) must implement against.
- All 16 Wave 0 tests collect cleanly; 7 are currently RED (structural import guard + both integration endpoint suites) by design, 4 pass immediately (`_attach_real_tfm` call-count guard + both unknown-id 404 checks), 6 skip cleanly against the empty pytest test DB pending 12-02/12-03's real-data assertions. No regression in the existing 156-test scoring/clubs/players suite.
- Live `manage.py shell` correctness/perf spike for `rank_clubs_for_player` (12-VALIDATION.md Wave 0 Requirements) is deferred to 12-03-PLAN.md, since that function isn't implemented yet in this plan.

---
*Phase: 12-bidirectional-matching-replacements-player-club-fit*
*Completed: 2026-07-26*

## Self-Check: PASSED

All 4 created files exist on disk; both task commits (`a15a02b`, `84bd4a7`) found in git history.
