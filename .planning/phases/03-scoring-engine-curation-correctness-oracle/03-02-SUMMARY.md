---
phase: 03-scoring-engine-curation-correctness-oracle
plan: 02
subsystem: scoring-curation
tags: [impact-model, duplicate-functions, curation-map, characterization]

# Dependency graph
requires:
  - phase: 03-01
    provides: scoring Django app skeleton, scikit-learn/joblib deps, ORM->DataFrame reconstruction bridge
provides:
  - "DUPLICATE_FUNCTIONS.md: the 20-name duplicate-function catalogue for impact_model_v4.1.py, with kept/rejected/reason audit trail for the 18 mechanically-resolved names"
  - "2 four-definition names (prepare_team_and_transfer_signal, player_transfer_history) explicitly flagged ESCALATION PENDING for Plan 03's human review"
  - "test_curation_map.py: automated proof the catalogue is complete and matches the source file"
affects: [03-03-escalation-review, 04-scoring-engine-port]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Regex-based independent recomputation of a hand-authored catalogue in a test, to catch source/doc drift"]

key-files:
  created:
    - get-scouted-be/scoring/docs/DUPLICATE_FUNCTIONS.md
    - get-scouted-be/scoring/tests/test_curation_map.py
  modified: []

key-decisions:
  - "18 two-definition duplicate names resolved via last-wins, cross-checked against get_export_columns_for_position (byte-identical bodies confirm the policy is copy-invariant)"
  - "build_transfer_value_dataset and export_team_shortlist_xlsx: directly confirmed (not just inferred) that each function's first definition is truncated/dead code with no return statement, making last-wins demonstrably correct rather than just conventional"
  - "pick_first_existing (required=True->False) and format_financial (value=->x= param rename) signature differences flagged explicitly for Phase 4 port verification, per CONTEXT.md's subtle-default bug class"
  - "prepare_team_and_transfer_signal and player_transfer_history (4 defs each) left unresolved, marked ESCALATION PENDING, handed to Plan 03 per the locked policy (3+ definitions always require human review)"
  - "financial_fit_label documented as nested/duplicated-logic (not duplicated-definition) and explicitly excluded from the last-wins/escalation machinery"

patterns-established:
  - "Duplicate-function catalogue table format (Function | Def count | Line numbers | Kept line | Rejected line(s) | Reason | Escalated?) — reusable for Plan 03's escalation resolutions once decided"

requirements-completed: []

# Metrics
duration: 20min
completed: 2026-07-21
---

# Phase 3 Plan 02: Duplicate-Function Catalogue Summary

**Catalogued all 20 duplicate top-level function names in the 15,747-line impact_model_v4.1.py with a kept/rejected/reason audit trail, mechanically resolving 18 via last-wins and flagging 2 for human escalation, backed by a source-drift-detecting test suite.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-21T22:34:46Z (STATE.md session start)
- **Completed:** 2026-07-21T23:40:41+01:00
- **Tasks:** 2 completed
- **Files modified:** 2 created

## Accomplishments
- Verified via anchored grep that exactly 20 top-level function names are duplicated in `impact_model_v4.1.py`, and exactly 2 of those (`prepare_team_and_transfer_signal`, `player_transfer_history`) have more than 2 definitions
- Wrote `DUPLICATE_FUNCTIONS.md`: a full audit-trail table for all 20 names — kept line, rejected line(s), and a specific reason per row, not a generic placeholder
- Directly diffed (rather than trusted research's summary of) the two hardest cases: `get_export_columns_for_position` (byte-identical except one blank line) and `build_transfer_value_dataset` / `export_team_shortlist_xlsx` (first definitions of both are provably truncated dead code, no `return` statement — hard evidence last-wins is correct, not just a convention)
- Flagged the two subtle signature-drift cases (`pick_first_existing`'s `required=True→False` default flip, `format_financial`'s `value=`→`x=` param rename) called out in `03-CONTEXT.md` as the exact bug class this phase's fix-threshold targets
- Documented `financial_fit_label` as nested/scoped duplicated logic, explicitly out of scope for the last-wins/escalation machinery
- Wrote `test_curation_map.py` with 3 tests, including one that independently recomputes the duplicate set from the source file via regex and asserts it equals the hardcoded 20-name set — this will catch any future drift between the source script and the catalogue document

## Task Commits

Each task was committed atomically:

1. **Task 1: Write the 20-name duplicate-function catalogue** - `209ed45` (docs)
2. **Task 2: Automated catalogue-completeness test** - `84412b9` (test)

**Cleanup commit:** `1ec0d89` (chore) — untracked an unrelated file (`ESCALATION_REVIEW.md`) that a concurrently-executing plan-03 agent wrote to the working tree at the same moment; see Deviations below.

_Note: no plan metadata commit yet — will follow this SUMMARY.md and STATE.md update._

## Files Created/Modified
- `get-scouted-be/scoring/docs/DUPLICATE_FUNCTIONS.md` - the 20-name duplicate-function catalogue with kept/rejected/reason audit trail and an escalation handoff note
- `get-scouted-be/scoring/tests/test_curation_map.py` - 3 tests proving the catalogue is complete, matches the source file, and correctly flags the 2 escalations

## Decisions Made
- Last-wins policy applied mechanically and verified (not just asserted) for all 18 two-definition names, with two of them (`build_transfer_value_dataset`, `export_team_shortlist_xlsx`) independently confirmed via direct code inspection to have provably-dead first definitions
- `pick_first_existing` and `format_financial` signature differences documented explicitly, flagged for verification during the Phase 4 port rather than silently accepted
- The 2 four-definition names left unresolved and clearly handed off to Plan 03, per the locked CONTEXT.md policy (never mechanically resolve 3+ definition names)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed incorrect relative path in test_curation_map.py**
- **Found during:** Task 2 (first pytest run)
- **Issue:** `DUPLICATE_FUNCTIONS_MD` path was built as `parents[1] / "scoring" / "docs" / ...`, which resolved to a nonexistent double-nested `scoring/scoring/docs/` path (since `parents[1]` from `scoring/tests/test_curation_map.py` is already the `scoring/` directory)
- **Fix:** Removed the redundant `"scoring"` path segment
- **Files modified:** get-scouted-be/scoring/tests/test_curation_map.py
- **Verification:** `pytest scoring/tests/test_curation_map.py -x -q` now passes (3/3)
- **Committed in:** 84412b9 (Task 2 commit, fixed before commit)

**2. [Rule 3 - Blocking] Untracked a file swept in by a concurrently-running plan**
- **Found during:** Post-Task-2 commit review (`git show --stat`)
- **Issue:** `get-scouted-be/scoring/docs/ESCALATION_REVIEW.md` (645 lines, owned by Plan 03, not this plan) appeared in the Task 2 commit despite only `test_curation_map.py` being explicitly `git add`-ed — a concurrently-executing agent working on Plan 03 wrote that file to the shared working tree at the same moment, and it got included in the commit
- **Fix:** `git rm --cached` to remove it from git's index (restoring it to untracked-on-disk) without deleting its content, then committed the fix separately
- **Files modified:** get-scouted-be/scoring/docs/ESCALATION_REVIEW.md (removed from git tracking, still present on disk, untracked)
- **Verification:** `git log --oneline -5` confirms 03-02's history now contains only its own two task commits plus this cleanup commit; `git status --short` shows the file as untracked (`??`), available for its owning plan to commit
- **Committed in:** 1ec0d89 (separate cleanup commit)

---

**Total deviations:** 2 auto-fixed (1 blocking path bug, 1 blocking cross-plan file-tracking conflict from concurrent execution)
**Impact on plan:** Both fixes necessary for commit correctness/isolation. No scope creep — no content from Plan 03's escalation review was read or relied upon here.

## Issues Encountered
- Concurrent execution of another Phase 3 plan (writing `ESCALATION_REVIEW.md`) shares the same working tree, creating a race window between `git add <specific-file>` and `git commit`, during which another process's staged file can be swept into an unrelated commit. Resolved for this plan via the cleanup commit above; worth flagging to the orchestrator if future waves run plans in parallel against a single working tree.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The 18-name mechanically-resolved portion of Phase 3 Success Criterion 1 is complete and tested
- Plan 03 can proceed directly to reviewing the 2 escalated names (`prepare_team_and_transfer_signal`, `player_transfer_history`); its own `ESCALATION_REVIEW.md` groundwork was already in progress concurrently and remains untracked/available on disk
- Phase 4's port has an authoritative, tested list of which definition of each of the 18 resolved duplicated functions to port; the 2 escalated names are the only open item blocking full Criterion 1 completion

---
*Phase: 03-scoring-engine-curation-correctness-oracle*
*Completed: 2026-07-21*

## Self-Check: PASSED

- FOUND: get-scouted-be/scoring/docs/DUPLICATE_FUNCTIONS.md
- FOUND: get-scouted-be/scoring/tests/test_curation_map.py
- FOUND: .planning/phases/03-scoring-engine-curation-correctness-oracle/03-02-SUMMARY.md
- FOUND: commit 209ed45
- FOUND: commit 84412b9
- FOUND: commit 1ec0d89
