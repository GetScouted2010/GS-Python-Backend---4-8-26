---
phase: 01-data-foundation
plan: 03
subsystem: database
tags: [django, postgres, orm, migrations, data-modeling]

# Dependency graph
requires:
  - phase: 01-data-foundation (plan 01)
    provides: Django project skeleton, Postgres-backed settings, FIELD_MAPPING.md canonical naming decisions
provides:
  - Club model (name unique, league, 8 playing-style floats, nullable manager/formation/country)
  - Player model (unique_id unique, club FK, ~99 CSV-mirrored stat FloatFields, extended_stats JSONField, legacy_total_score)
  - PlayerRoleScore model (player + role_name unique)
  - PlayerClubCompatibility model (player + club_name_raw unique, dual score indexes)
  - Transfer model (club FK, dealing_club plain CharField, composite unique constraint)
  - Applied 0001_initial migrations for clubs, players, transfers against Postgres
affects: [phase-03-curation, phase-04-scoring-port, phase-05-parity-testing, phase-02-import-commands]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Django field names mirror CSV column names verbatim for stat columns (parity traceability); meta/profile fields use lowercase Django convention per plan"
    - "Real DB-level unique constraints (not just Meta.unique_together) on every bulk-upsert conflict target, required for bulk_create(update_conflicts=True)"
    - "PlayerClubCompatibility keyed on (player, club_name_raw) not (player, club) to avoid Postgres NULL-non-conflict trap"

key-files:
  created:
    - get-scouted-be/clubs/models.py
    - get-scouted-be/players/models.py
    - get-scouted-be/transfers/models.py
    - get-scouted-be/clubs/migrations/0001_initial.py
    - get-scouted-be/players/migrations/0001_initial.py
    - get-scouted-be/transfers/migrations/0001_initial.py
  modified: []

key-decisions:
  - "Player model's ~99 stat FloatFields keep exact CSV casing (e.g. xG_per_90, PAdj_Interceptions, Successful_defensive_actions_per_90) for 1:1 Phase 5 parity traceability; identifier/profile fields (player, season, league, positions, main_position, position, age, market_value, contract_expires, birth_country, passport_country, foot, height, weight, on_loan) use lowercase Django-conventional names per this plan's explicit field list"
  - "Duplicate CSV header Aerial_duels_per_90 (outfield + GK block) modeled as a single Django field, not two; import code in Phase 2 must resolve which raw occurrence populates it"
  - "Transfer.dealing_club modeled as plain CharField, not FK, to avoid polluting Club table with 2,909 mostly-foreign counterparty entities that have no roster/playing-style data"

patterns-established:
  - "Bulk-upsert-target fields always get a real DB unique constraint (Club.name, Player.unique_id, PlayerRoleScore(player,role_name), PlayerClubCompatibility(player,club_name_raw), Transfer composite) rather than relying on Meta.unique_together alone"

requirements-completed: [DATA-01, DATA-02, DATA-03, DATA-04]

# Metrics
duration: 10min
completed: 2026-07-20
---

# Phase 01 Plan 03: Data Foundation - Core Models Summary

**Five Django models (Club, Player, PlayerRoleScore, PlayerClubCompatibility, Transfer) with CSV-mirrored field names and real DB unique constraints, migrations generated and applied cleanly against Postgres.**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-20T19:18:00+01:00 (approx, following prior commit)
- **Completed:** 2026-07-20T19:23:47+01:00
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Defined `Club` with a real unique constraint on `name` and all 8 nullable playing-style floats (`control_possession` ... `low_block`)
- Defined `PlayerRoleScore` and `PlayerClubCompatibility` with the load-bearing `(player, club_name_raw)` unique constraint (not `(player, club)`) to avoid the Postgres NULL-non-conflict trap called out in RESEARCH.md Open Question 2, plus dual score indexes for both query directions
- Defined `Player` with `unique_id` as the real bulk-upsert unique constraint, `club` FK sourced conceptually from `Team_within_selected_timeframe`, `legacy_total_score` (renamed from `Total_Score`), ~99 stat FloatFields mirroring CSV names 1:1, and the 14 non-identifier movement columns isolated into `extended_stats` JSONField
- Defined `Transfer` with `dealing_club` as a plain CharField (never a FK) and the 6-column composite unique constraint `(player_name_raw, year, window, movement, club, dealing_club)`
- Generated and applied all three `0001_initial` migrations against Postgres with zero errors; `makemigrations --check --dry-run` reports no missing migrations

## Task Commits

Each task was committed atomically:

1. **Task 1: Define Club, PlayerRoleScore, and PlayerClubCompatibility models** - `040e281` (feat)
2. **Task 2: Define Player and Transfer models + generate and apply all migrations** - `6ca8557` (feat)

**Plan metadata:** (this commit, docs: complete 01-03 plan)

## Files Created/Modified
- `get-scouted-be/clubs/models.py` - `Club` model (name unique, league/country/manager/formation nullable, source_unique_id, 8 playing-style floats)
- `get-scouted-be/players/models.py` - `Player`, `PlayerRoleScore`, `PlayerClubCompatibility` models
- `get-scouted-be/transfers/models.py` - `Transfer` model
- `get-scouted-be/clubs/migrations/0001_initial.py` - generated migration for Club
- `get-scouted-be/players/migrations/0001_initial.py` - generated migration for Player, PlayerRoleScore, PlayerClubCompatibility
- `get-scouted-be/transfers/migrations/0001_initial.py` - generated migration for Transfer

## Decisions Made
- Task 1's `players/models.py` write included the full `Player` class (originally scoped to Task 2) alongside `PlayerRoleScore`/`PlayerClubCompatibility` in a single file write, since all three models share one file. This combined the "Player portion" naming split from the plan into one physical edit; both tasks' acceptance criteria for `players/models.py` were still verified independently at their respective checkpoints. No functional deviation — same end state the plan specified.
- Followed the plan's explicit field-casing instructions literally: profile/meta fields (`player`, `season`, `league`, `positions`, `main_position`, `position`, `age`, `market_value`, `contract_expires`, `birth_country`, `passport_country`, `foot`, `height`, `weight`, `on_loan`) use lowercase Django names, while the ~99 stat columns preserve exact CSV casing — this is a deliberate readability/traceability split specified in the plan's Task 2 action text, distinct from (but not contradicting) FIELD_MAPPING.md's general "mirror verbatim" framing for those specific fields.

## Deviations from Plan

None - plan executed exactly as written (see "Decisions Made" above for one file-write-ordering note; no functional deviation).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Postgres was already running and configured via `DATABASE_URL` from Phase 01 Plan 01's scaffolding.

## Next Phase Readiness
- All five Phase 1 data models exist with load-bearing DB-level unique constraints, ready for Phase 2's bulk-upsert import commands (`bulk_create(update_conflicts=True)`) to target directly.
- `get-scouted-be/docs/FIELD_MAPPING.md` remains the authoritative CSV -> Django -> impact_model_v4.1.py name reference for Phase 2 import code and Phase 3+ scoring port work.
- No blockers for subsequent Phase 1 plans (01-02, 01-04 through 01-09) that depend on this schema.

---
*Phase: 01-data-foundation*
*Completed: 2026-07-20*

## Self-Check: PASSED

All created files verified present on disk; both task commits (`040e281`, `6ca8557`) verified present in git history.
