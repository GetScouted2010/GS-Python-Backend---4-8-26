---
phase: 01-data-foundation
verified: 2026-07-21T04:30:00Z
status: passed
score: 5/5 must-haves verified
---

# Phase 1: Data Foundation Verification Report

**Phase Goal:** Real player, club, stats, and transfer data live in Postgres, accurately reflecting the legacy CSVs, with mismatches surfaced rather than hidden.
**Verified:** 2026-07-21T04:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Player table returns real profile data (position, age, nationality, foot, height, contract, market value) for every player in source CSVs | ✓ VERIFIED | Live DB: `Player.objects.count()` = 41,708, exactly matching independently-counted `Players.csv` row count (41,708, verified by direct line count of the source file, not just the import report's self-reported figure). All profile fields populated per row: `age` 41,708/41,708, `foot` 41,708/41,708, `height` 41,708/41,708, `birth_country` 41,708/41,708, `position` 41,707/41,708 (1 genuinely blank in source), `market_value` 35,864/41,708 (14.0% legitimately missing in source CSV, flagged in report, row still imported). Spot-checked `E. Haaland` row: position=FWD, age=24, market_value=180000000, foot=left, height=195, contract_expires=2027-06-30 — matches raw CSV. |
| 2 | Club table returns real club data (league, country, manager, formation, squad size, playing style) for every club in source CSVs | ✓ VERIFIED (with documented, pre-agreed scope limits) | Live DB: `Club.objects.count()` = 1,060, matching the union of `Team_within_selected_timeframe` (1,059) + 1 Playstyles-only name, as claimed. `league` populated for 1,059/1,060 clubs (the 1 null is the Playstyles-only club with no Players.csv rows to derive a mode from — logged). `playing_style` (8 floats) populated for 239/1,060 clubs (22.6%), matching `Playstyles.csv` coverage exactly, remainder correctly null. `manager`/`formation`/`country` are 0/1,060 populated — this is a locked, documented Phase-1 CONTEXT.md decision (no legacy source exists for these three fields), not a migration defect; `squad_size` is explicitly out-of-scope for migration per CONTEXT.md (deferred to live-query CRUD/Squad-Planner phases). |
| 3 | Season-by-season, position-aware performance stats (goals, assists, tackles, interceptions, passing, duels, xG/xA) are stored and queryable | ✓ VERIFIED | `Player` model has ~99 CSV-mirrored stat FloatFields (Goals, Assists, xG, xA, Duels_per_90, Interceptions_per_90, PAdj_Interceptions, Successful_defensive_actions_per_90, Passes_per_90, etc.) with a `season` field, confirmed via live DB: 4 distinct `E. Haaland` rows (unique_id 0/418/34799/35293) across seasons "Last Calendar Year"/"2024-2025"/"2023-2024"/"2022-2023", each with independently populated stats. Position-aware role scores confirmed live: `PlayerRoleScore.objects.count()` = 230,139, spanning 40 sanitized role names across 9 position files; GK exclusion confirmed by design. |
| 4 | Transfer history records (fee, date, source/destination club, market value at transfer time) are stored and queryable | ✓ VERIFIED | Live DB: `Transfer.objects.count()` = 47,201, reconciling exactly against the independently-counted raw `transferdata final.csv` (47,252 rows) minus 51 genuinely-duplicated composite-key rows (documented, logged, not silently dropped). `Transfer.club` (destination) resolved for 47,201/47,201 rows (100%); `dealing_club` (source, plain string) populated for all rows; `fee` populated with real values (e loan/free/numeric); `market_value_at_transfer` populated for 47,201/47,201; `year`/`window`/`movement` (date proxy) populated. `Transfer.player` matched for only 861/47,201 (~1.8%) — expected and documented consequence of the deliberate "never guess an ambiguous name" policy, not a join bug. |
| 5 | Running the migration produces a written import report listing every field-mapping mismatch or dropped/defaulted value found, instead of migrating silently | ✓ VERIFIED | `core/import_reports/import_all_20260721T024804Z.{json,md}` exists (42KB Markdown / 45KB JSON), status reconciliation shows Club 1060/1060 (delta 0), Player 41708/41708 (delta 0), Transfer 47201/47201 (delta 0, with the 51-row duplicate-collapse explicitly explained). Combined report aggregates all 5 sub-reports (clubs/players/position_roles/compatibility/transfers), each listing field-level issue counts/rates/sample IDs (e.g. `League ambiguous_league_tie`: 106 rows, `Market_value` 14.0% missing, `Contract_expires` 18.0% missing). No field is silently dropped or defaulted without a corresponding report entry. `docs/IMPORT_RUNBOOK.md` (180 lines) documents how to run/read the report. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `get-scouted-be/docs/FIELD_MAPPING.md` | Canonical CSV->Django->scoring-script mapping (DATA-05 prereq) | ✓ VERIFIED | 326 lines (exceeds 120-line min), documents all field-name divergences (`UniqueID`, `Team_within_selected_timeframe`, `Market_value`, duplicate `Aerial_duels_per_90` header, transferdata UniqueID-is-club trap) |
| `get-scouted-be/config/settings/base.py` | Django settings, Postgres via django-environ | ✓ VERIFIED | `env.db()` present, `python manage.py check` exits 0 against live Postgres |
| `get-scouted-be/clubs/models.py` | Club model (name unique, league, 8 playing-style floats, nullable manager/formation/country) | ✓ VERIFIED & WIRED | Confirmed field-for-field; migrated and populated (1,060 rows) |
| `get-scouted-be/players/models.py` | Player, PlayerRoleScore, PlayerClubCompatibility models | ✓ VERIFIED & WIRED | Confirmed field-for-field incl. `extended_stats` JSONField, `(player, club_name_raw)` unique constraint; all 3 tables populated (41,708 / 230,139 / 8,188,712 rows) |
| `get-scouted-be/transfers/models.py` | Transfer model (club FK, dealing_club CharField, composite unique constraint) | ✓ VERIFIED & WIRED | Confirmed; 47,201 rows populated, 100% club-resolved |
| `get-scouted-be/core/import_utils.py` | Chunked CSV reader + ImportReport accumulator | ✓ VERIFIED & WIRED | 215 lines; imported and used by every one of the 5 import commands (`update_conflicts=True` upsert pattern confirmed in all 5 files) |
| `get-scouted-be/clubs/management/commands/import_clubs_playstyles.py` | Club derivation + playstyles import | ✓ VERIFIED & WIRED | 246 lines; produced the exact live DB club count |
| `get-scouted-be/players/management/commands/import_players.py` | Player import | ✓ VERIFIED & WIRED | 353 lines; produced the exact live DB player count |
| `get-scouted-be/players/management/commands/import_position_roles.py` | Position role score import | ✓ VERIFIED & WIRED | 220 lines; produced the exact live DB PlayerRoleScore count |
| `get-scouted-be/players/management/commands/import_compatibility_scores.py` | Compatibility score import | ✓ VERIFIED & WIRED | 309 lines; produced the exact live DB PlayerClubCompatibility count |
| `get-scouted-be/transfers/management/commands/import_transfers.py` | Transfer import (UniqueID-trap-safe) | ✓ VERIFIED & WIRED | 322 lines; produced the exact live DB transfer count, dedup fix confirmed present |
| `get-scouted-be/core/management/commands/import_all.py` | Orchestrator + reconciliation | ✓ VERIFIED & WIRED | 365 lines; `call_command` confirmed chaining all 5 sub-commands in dependency order; combined report on disk with PASS reconciliation |
| `get-scouted-be/docs/IMPORT_RUNBOOK.md` | Operator runbook | ✓ VERIFIED | 180 lines, substantive (prerequisites, run command, dependency order, report-reading guide, documented coverage gaps) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `config/settings/base.py` | `DATABASE_URL` | `env.db()` | ✓ WIRED | `manage.py check` connects live |
| `players/models.py` | `clubs.Club` | `ForeignKey` | ✓ WIRED | 41,708/41,708 Player rows have `club` resolved |
| `import_clubs_playstyles.py` | `Club` table | `bulk_create(update_conflicts=True, unique_fields=['name'])` | ✓ WIRED | Confirmed in source; live count matches |
| `import_players.py` | `clubs.Club` | in-memory name->id map | ✓ WIRED | 0 unresolved club names in report; 100% FK resolution confirmed live |
| `import_position_roles.py` | `players.Player` | `unique_id` -> id map | ✓ WIRED | 230,139 rows, 0 unmatched UniqueIDs (per report) |
| `import_compatibility_scores.py` | `PlayerClubCompatibility` unique constraint | `bulk_create` on `(player, club_name_raw)` | ✓ WIRED | 8,188,712 rows created; idempotent re-run confirmed 0 net change (per SUMMARY, DB count static) |
| `import_transfers.py` | `clubs.Club` (via transferdata Club name, NOT UniqueID) | `club_id_map`, guarded by `source_unique_id` | ✓ WIRED | 47,201/47,201 Transfer.club resolved; trap-avoidance test (`test_uniqueid_is_club_not_player`) passes |
| `import_all.py` | each import command | `call_command` in dependency order | ✓ WIRED | Confirmed order: clubs -> players -> position_roles -> compatibility -> transfers; combined report + reconciliation on disk |

### Requirements Coverage

| Requirement | Source Plan(s) | Description | Status | Evidence |
|-------------|-----------------|-------------|--------|----------|
| DATA-01 | 01, 02, 03, 05 | Real player profile data migrated | ✓ SATISFIED | 41,708/41,708 Player rows, all profile fields populated per source-data availability |
| DATA-02 | 01, 03, 04 | Real club data migrated | ✓ SATISFIED | 1,060 Club rows; league + playing_style from real sources; manager/formation/country nullable by locked, documented design (no legacy source) |
| DATA-03 | 01, 03, 05, 06, 07 | Position-aware, multi-season player stats migrated & queryable | ✓ SATISFIED | ~99 stat fields per Player row (season-keyed) + 230,139 PlayerRoleScore rows + 8,188,712 PlayerClubCompatibility rows |
| DATA-04 | 01, 03, 08 | Real transfer history migrated & queryable | ✓ SATISFIED | 47,201 Transfer rows, fee/date/club/dealing_club/market_value_at_transfer populated, UniqueID-trap correctly avoided |
| DATA-05 | 01, 02, 04, 05, 09 | Migration produces reviewed import report surfacing mismatches | ✓ SATISFIED | Combined `import_all` report + per-table sub-reports on disk, PASS-status reconciliation, IMPORT_RUNBOOK.md operator doc |

No orphaned requirements found — REQUIREMENTS.md's traceability table maps only DATA-01 through DATA-05 to Phase 1, and all five appear in at least one plan's `requirements:` frontmatter field.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `config/settings/production.py` | 1 | `# Hosting target deferred per PROJECT.md — placeholder only.` | ℹ️ Info | Explicitly out-of-scope per REQUIREMENTS.md ("Concrete hosting/deployment target" — deferred by design); not a Phase 1 concern |

No blocker or warning-level anti-patterns found in any import command, model, or migration file. The `pass`/`return {}` occurrences found by the initial grep sweep were all legitimate control-flow (NaN-coercion `except` fallthrough, missing-optional-JSON-file fallback) — verified by reading each in context, not stubs.

### Human Verification Required

None. All five observable truths were verified programmatically against the live Postgres database (`getscouted`), independently-recomputed source-CSV row counts, the full automated test suite (17/17 passing), and direct row-level spot-checks (e.g. E. Haaland's profile and season history). No UI, real-time, or subjective-quality aspects exist in this phase's scope to require human judgment.

### Gaps Summary

No gaps. All 5 observable truths verified, all 13 required artifacts exist/are substantive/are wired, all 8 key links confirmed wired, all 5 requirement IDs satisfied with evidence, `manage.py check` and `makemigrations --check --dry-run` both clean, and the full automated test suite (17 tests) passes. Live database row counts match SUMMARY claims exactly and independently reconcile against raw source-CSV line counts computed directly for this verification (not reused from any prior report): Players.csv 41,708 rows = 41,708 live Player rows; transferdata final.csv 47,252 rows − 51 documented duplicates = 47,201 live Transfer rows.

One noteworthy, non-blocking observation for downstream phases: the source CSV itself contains data-quality anomalies (e.g. Haaland's `Birth_country` field reads "England" in the raw `Players.csv`) that the import pipeline faithfully preserves rather than "fixing," per this phase's explicit "surface, never silently correct" policy — this is working as designed, not an import defect, but worth downstream phases (e.g. AI scouting reports) being aware that `birth_country`/`passport_country` values inherit whatever quality issues exist in the legacy CSV.

---

_Verified: 2026-07-21T04:30:00Z_
_Verifier: Claude (gsd-verifier)_
