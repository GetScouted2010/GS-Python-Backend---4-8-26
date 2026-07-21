---
gsd_state_version: 1.0
milestone: v4.1
milestone_name: milestone
status: unknown
stopped_at: Phase 2 context gathered
last_updated: "2026-07-21T09:55:40.844Z"
progress:
  total_phases: 12
  completed_phases: 1
  total_plans: 9
  completed_plans: 9
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-20)

**Core value:** The backend must serve accurate, real scouting data and real (not approximated) Impact RMM scoring — the product's credibility rests on the scores being right, not just on the API being reachable.
**Current focus:** Phase 1 — Data Foundation

## Current Position

Phase: 1 (Data Foundation) — COMPLETE
Plan: 9 of 9 (all plans complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 1
- Average duration: 25 min
- Total execution time: 0.4 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 01 P01 | 25min | 2 tasks | 24 files |

**Recent Trend:**

- Last 5 plans: 25min
- Trend: -

*Updated after each plan completion*
| Phase 01-data-foundation P03 | 10min | 2 tasks | 6 files |
| Phase 01 P04 | 12min | 2 tasks | 10 files |
| Phase 01-data-foundation P05 | 25min | 2 tasks | 6 files |
| Phase 01-data-foundation P06 | 18min | 2 tasks | 3 files |
| Phase 01-data-foundation P08 | 12min | 2 tasks | 5 files |
| Phase 01-data-foundation P07 | 35min | 2 tasks | 4 files |
| Phase 01-data-foundation P09 | 100min | 2 tasks | 6 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Phase 3-6 split scoring engine port into curation → port → parity testing → caching, matching the "fine" granularity target and treating the 15,700-line untested port as the project's highest-risk work needing its own verification step at each stage.
- Phase 3 (Curation) carries no directly-owned v1 requirement — it is prerequisite risk-mitigation work (snapshot oracle, de-dup map) that Phases 4-6 depend on to satisfy SCORE-01 through SCORE-07.
- [Phase 01]: Django field names mirror CSV column names verbatim (locked naming decision); Player.club FK sourced from Team_within_selected_timeframe not Team; Total_Score renamed legacy_total_score; 14 movement columns isolated into Player.extended_stats JSONField
- [Phase 01-data-foundation]: Player model's ~99 stat FloatFields keep exact CSV casing for parity traceability; identifier/profile fields use lowercase Django-conventional names per plan's explicit field list
- [Phase 01-data-foundation]: clubs_with_ambiguous_league counts any club with >1 distinct League value (matches 01-RESEARCH.md's verified 525/1059), tracked separately from genuine mode ties
- [Phase 01-data-foundation]: Added a repo-root get-scouted-be/conftest.py re-exporting fixture_dir so every app's test dir (sibling of core/tests/, not descendant) can use the shared fixture-path fixture
- [Phase 01-data-foundation]: Removed the redundant flagged_uids param from _build_player_kwargs -- report.add_field_issue is monkey-patched once in Command.handle() to track flagged rows, so per-row helpers only need a report reference
- [Phase 01-data-foundation]: Contract_expires' 18% 'missing' rate in the real Players.csv is encoded as the literal string '0', not a blank cell -- correctly flagged via the unparseable/strptime branch with identical null+flagged effect
- [Phase 01-data-foundation]: import_position_roles: switched UniqueID dtype from int64 to nullable Int64 -- 3 real Positions/*.csv files (CM/LB/RB) have blank all-NaN trailing rows that crashed a plain int64 parse; now flagged+skipped per row instead
- [Phase 01-data-foundation]: PlayerRoleScore full-scale row count is 230,139 (long format, one row per player-role), not the ~38,600 estimate in 01-RESEARCH.md/the plan's verification note -- that figure described the wide-format row sum across the 9 files, not the melted long-format total the must_haves truths require
- [Phase 01-data-foundation]: Transfer.club resolved strictly via transferdata's Club NAME column; UniqueID stored only as source_unique_id for cross-source confirmation, never joined to Player.unique_id
- [Phase 01-data-foundation]: Transfer player-name matching excludes non-unique (ambiguous) names from the match map entirely -- ambiguous treated identically to unmatched (player=None, logged), never guessed
- [Phase 01-data-foundation]: PlayerClubCompatibility's idempotent upsert conflict target is (player, club_name_raw), never (player, club) -- club is null for unresolved headers and Postgres treats multiple NULLs as non-conflicting, so club_name_raw is mandatory to avoid duplicating null-club rows on re-run
- [Phase 01-data-foundation]: Full-scale import_compatibility_scores run confirmed 8,188,712 PlayerClubCompatibility rows (9 files x ~212 club columns each), only 1 distinct unresolved club header ("St_DOT_ Louis City", not present in cs_field_mapping.json), 0 unmatched players; idempotent re-run left row count unchanged
- [Phase 01-data-foundation]: import_all reconciliation delegates Club/Transfer expected counts to each sub-command's own report section (club_derivation.distinct_clubs; transfer_import.duplicate_event_keys_collapsed) rather than recomputing independently, so the two calculations cannot drift apart
- [Phase 01-data-foundation]: import_transfers now collapses same-composite-event-key rows within a chunk before bulk_create (last occurrence wins, logged) -- real transferdata final.csv has ~51 genuinely-duplicated rows that otherwise crash Postgres's ON CONFLICT DO UPDATE with a CardinalityViolation
- [Phase 01-data-foundation]: Full real-dataset import_all phase-gate run reconciled to PASS: Club=1060, Player=41708, Transfer=47201 (47252 raw minus 51 collapsed duplicates), PlayerRoleScore=230139, PlayerClubCompatibility=8188712; Transfer.player unmatched rate is ~98% (46391/47252) by design given Player's per-season row granularity plus the never-guess-ambiguous-names policy

### Pending Todos

None yet.

### Blockers/Concerns

- Scoring engine curation (Phase 3) requires direct manual review of impact_model_v4.1.py to identify authoritative duplicated functions — no external pattern to follow, flagged by research as needing deeper analysis during planning.
- Transfer Probability (SCORE-04) is likely the least mature/most modeled score (sklearn-trained, not purely deterministic) — budget extra validation time in Phase 5 parity testing.
- AI layer (Phases 9-10) LLM library/API surface should get a fresh check at build time given how fast that space moves.

## Session Continuity

Last session: 2026-07-21T09:55:40.840Z
Stopped at: Phase 2 context gathered
Resume file: .planning/phases/02-auth-access-control/02-CONTEXT.md
