# Phase 1: Data Foundation - Context

**Gathered:** 2026-07-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Migrate real player, club, stats, and transfer data from the legacy CSVs/MongoDB (`API-Updated-/dataset/`) into the new Django/Postgres schema, producing a reviewed import report that surfaces field-mapping mismatches and data-quality issues rather than hiding them. Scoring, auth, and the API layer itself are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Club Data Gap

The legacy dataset has no dedicated Clubs file — club identity only exists as a string field on Player/Playstyles records.

- `Club.manager` and `Club.formation`: no legacy data source exists. Model as nullable fields, left empty for v1. Backfill later if/when a source is found.
- `Club.country`: same treatment — nullable, left empty for v1, no source exists.
- `Club.league`: auto-derived per team as the **most common `League` value** among that team's migrated player records (handles the rare case of mixed/stale league values for a team across seasons/records).
- `Club.squad_size`: **not** a migration-time field. Treated as a live/denormalized count of currently-linked Player records — belongs to the CRUD/Squad Planner phases (7/11), not import logic.
- `Club.playing_style`: **does** have a real source — `Playstyles.csv` is genuinely team-level data (8-style tactical breakdown per team: Control_Possession, Gegenpressing, Direct_Play, Defensive_Counter_Attack, Tiki_Taka, Counter_Attack, Wing_Play, Low_Block). This matches the "Teams.xlsx schema" referenced in `pixel-perfect-clone-60729/src/lib/domain.ts`. Migrate it as part of Club data in Phase 1.

### Mismatch & Data Quality Handling

Policy across the board: **maximize completeness, surface issues, never silently drop or halt.**

- Missing required value (e.g. no `Market_value`, no `Age`): import the row with that field null, log it in the import report. Do not skip the row.
- Implausible value (age > 60, negative market value, unrecognized position variant): import the value, flag it as an outlier in the report. Do not null it out or skip the row.
- No single bad/missing value ever halts the whole import.
- The known field-name mismatches (see CONCERNS.md) are resolved by writing an explicit `FIELD_MAPPING.md` during planning/research — not guessed ad hoc inside import code. This is a required planning deliverable, not optional documentation.
- Import must be **idempotent/re-runnable**: upsert on a stable unique key (e.g. `UniqueID` for players) so it can be safely re-run as the field mapping or source data is refined mid-project — important given the compressed timeline and iterative mismatch discovery.

### Migration Scope & Sequencing

- **Full dataset, not a subset**: all ~41,709 players are migrated in Phase 1. The scoring engine's z-score standardization needs the full population anyway, so a partial import would need redoing.
- **All CSVs migrate now, in Phase 1** — not staged across phases:
  - `dataset/Players.csv` (players)
  - `dataset/Playstyles.csv` (club playing style)
  - `dataset/Positions/*.csv` (9 files — per-position stats with league)
  - `dataset/Compatability Scores/*.csv` (9 files — compatibility matrices)
  - `dataset/transferdata final.csv` (transfer history)
  - Rationale: one phase, one coherent import report, rather than splitting migration logic and re-explaining field mappings across Phase 1 and Phase 3.

### Canonical Field Naming

- Django model fields **mirror the original CSV/Python script's exact snake_case names** where they exist (e.g. `Market_value`, `Duels_per_90`, `xG_per_90`, `Successful_defensive_actions_per_90`). This makes Phase 5 parity testing traceable 1:1 against `impact_model_v4.1.py` — a Django field maps directly to a script variable/column with no translation layer to get wrong.
- The `Team` / `Team_within_selected_timeframe` duplication is **resolved, not carried forward**: model `Player.club` as a proper FK to `Club`, not two string fields. `Team_within_selected_timeframe` is the correct source column to populate this FK from — it's the field `impact_model_v4.1.py` itself renames to `Team` internally, confirming they represent the same concept.

### Claude's Discretion

- Exact Django app/model boundaries beyond what research already recommends (`players/`, `clubs/`, `transfers/` as separate apps)
- Exact structure/format of the import report (JSON, Markdown, or a DB table of flagged rows)
- Specific unique-key strategy per entity for idempotent upsert (UniqueID for players is settled; transfer records and compatibility-score records likely need composite keys — determine during planning)
- Whether the 9 Positions/ CSVs and 9 Compatibility Scores/ CSVs become their own Django models or get merged into fields/tables tied to Player — this touches Phase 1 schema design but is primarily informed by what Phase 3/4 (scoring engine) actually needs to query

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Known field-mapping issues (read before writing FIELD_MAPPING.md)
- `.planning/codebase/CONCERNS.md` §"Known Issue: Missing Field Mapping" — documents `Team` vs `Team_within_selected_timeframe`, `Market_value` vs `"Market Value"`, `Position`/`Main_Position`/`Positions` variants
- `.planning/codebase/CONCERNS.md` §"Data Quality: Large CSV with No Validation" — 41,709-row Players.csv has no validation; Mongoose schema marks all fields required but CSV may have nulls
- `.planning/codebase/CONCERNS.md` §"Schema mismatch between MongoDB and Supabase" — attributes as separate MongoDB/CSV fields vs jsonb in Supabase reference schema
- `API-Updated-/cs_field_mapping.json` — existing partial mapping (team names only, not player stats)
- `API-Updated-/utils/fieldMapper.js` — existing partial CSV-to-schema mapping logic, reference only

### Legacy schema & data sources
- `API-Updated-/models/player.js` — legacy Mongoose Player schema (100+ stat fields), the field inventory to map from
- `.planning/codebase/STRUCTURE.md` §"Data/Datasets" — full dataset directory layout and file sizes
- `API-Updated-/dataset/Players.csv` (~25MB, 41,709 rows) — player master data
- `API-Updated-/dataset/Playstyles.csv` — team-level tactical style data (confirmed source for Club.playing_style)
- `API-Updated-/dataset/Positions/*.csv` (9 files) — per-position stat breakdowns with league
- `API-Updated-/dataset/Compatability Scores/*.csv` (9 files) — compatibility matrices
- `API-Updated-/dataset/transferdata final.csv` (~6.7MB) — transfer history

### Product requirements for Club fields
- `GetScouted PRD.docx` §4.0 "Club Overview" — defines required Club fields (name, league, country, manager, formation, squad size) that motivated the Club Data Gap discussion

### Research informing migration approach
- `.planning/research/STACK.md` §"CSV migration pattern" — recommends `pandas.read_csv(chunksize=...)` + `bulk_create(update_conflicts=True)` for idempotent, re-runnable upserts
- `.planning/research/PITFALLS.md` — silent CSV/Mongo import data loss pitfall; explicit dtype schema and reconciliation report requirement

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `API-Updated-/utils/fieldMapper.js` — partial existing field-mapping logic; not reusable as Python code but documents intent/edge cases worth reading before writing `FIELD_MAPPING.md`
- `API-Updated-/models/player.js` — complete field inventory (100+ stat fields) to model against in Django

### Established Patterns
- Legacy CSVs use `Snake_Case_With_Caps` field naming (e.g. `Market_value`, `Duels_per_90`) — this phase's naming decision (mirror original names) aligns with what's already there, minimizing translation
- No existing validation layer anywhere in the legacy stack — this phase is the first place data quality gets systematically checked

### Integration Points
- Downstream: Phase 3 (Scoring Curation) needs this migrated data as its snapshot-oracle input — the scoring engine cannot be validated without it
- Downstream: Phase 2 (Auth) is independent of this phase's data but both are prerequisites for Phase 7+ (CRUD)
- Downstream: Phase 7 (Core CRUD) and Phase 11 (Squad Simulation) will compute `Club.squad_size` live from Player↔Club relationships established here

</code_context>

<specifics>
## Specific Ideas

No specific product references or "I want it like X" moments — this phase was entirely policy/technical decisions (data completeness, field naming, scope).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 1 scope. `Club.squad_size` computation was clarified as belonging to later CRUD phases but isn't a new capability, just a migration-time exclusion already reflected in the decisions above.

</deferred>

---

*Phase: 01-data-foundation*
*Context gathered: 2026-07-20*
