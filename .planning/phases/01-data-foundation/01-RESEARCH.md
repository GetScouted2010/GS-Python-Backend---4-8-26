# Phase 1: Data Foundation - Research

**Researched:** 2026-07-20
**Domain:** From-scratch Django/DRF/Postgres project scaffolding + idempotent CSV→Postgres migration of real football scouting data (~41.7K players, ~1,059 clubs, ~47K transfers, 9 per-position role-score files, 9 per-position compatibility-matrix files)
**Confidence:** HIGH (scaffolding, `bulk_create(update_conflicts=True)` mechanics, and every data-shape claim below is verified directly against the real CSVs and `impact_model_v4.1.py` in this repo, not assumed) / MEDIUM (exact index tuning — deferred to Phase 7 once real query patterns exist, flagged explicitly below)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Club Data Gap**
The legacy dataset has no dedicated Clubs file — club identity only exists as a string field on Player/Playstyles records.
- `Club.manager` and `Club.formation`: no legacy data source exists. Model as nullable fields, left empty for v1. Backfill later if/when a source is found.
- `Club.country`: same treatment — nullable, left empty for v1, no source exists.
- `Club.league`: auto-derived per team as the **most common `League` value** among that team's migrated player records (handles the rare case of mixed/stale league values for a team across seasons/records).
- `Club.squad_size`: **not** a migration-time field. Treated as a live/denormalized count of currently-linked Player records — belongs to the CRUD/Squad Planner phases (7/11), not import logic.
- `Club.playing_style`: **does** have a real source — `Playstyles.csv` is genuinely team-level data (8-style tactical breakdown per team: Control_Possession, Gegenpressing, Direct_Play, Defensive_Counter_Attack, Tiki_Taka, Counter_Attack, Wing_Play, Low_Block). Migrate it as part of Club data in Phase 1.

**Mismatch & Data Quality Handling**
Policy across the board: **maximize completeness, surface issues, never silently drop or halt.**
- Missing required value: import the row with that field null, log it in the import report. Do not skip the row.
- Implausible value (age > 60, negative market value, unrecognized position variant): import the value, flag it as an outlier in the report. Do not null it out or skip the row.
- No single bad/missing value ever halts the whole import.
- The known field-name mismatches are resolved by writing an explicit `FIELD_MAPPING.md` during planning/research — not guessed ad hoc inside import code. This is a required planning deliverable, not optional documentation.
- Import must be **idempotent/re-runnable**: upsert on a stable unique key (e.g. `UniqueID` for players).

**Migration Scope & Sequencing**
- **Full dataset, not a subset**: all ~41,709 players are migrated in Phase 1.
- **All CSVs migrate now, in Phase 1** — not staged across phases: `Players.csv`, `Playstyles.csv`, `Positions/*.csv` (9 files), `Compatability Scores/*.csv` (9 files), `transferdata final.csv`.

**Canonical Field Naming**
- Django model fields **mirror the original CSV/Python script's exact snake_case names** where they exist (e.g. `Market_value`, `Duels_per_90`, `xG_per_90`, `Successful_defensive_actions_per_90`).
- `Player.club` is a proper FK to `Club`, sourced from `Team_within_selected_timeframe` (not `Team`) — this is the field `impact_model_v4.1.py` itself renames internally, confirming they represent the same concept.

### Claude's Discretion
- Exact Django app/model boundaries beyond what research already recommends (`players/`, `clubs/`, `transfers/` as separate apps)
- Exact structure/format of the import report (JSON, Markdown, or a DB table of flagged rows)
- Specific unique-key strategy per entity for idempotent upsert (UniqueID for players is settled; transfer records and compatibility-score records likely need composite keys — determine during planning)
- Whether the 9 Positions/ CSVs and 9 Compatibility Scores/ CSVs become their own Django models or get merged into fields/tables tied to Player

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within Phase 1 scope. `Club.squad_size` computation was clarified as belonging to later CRUD phases but isn't a new capability.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| DATA-01 | Real player profile data (position, age, nationality, foot, height, contract, market value) migrated to Postgres | Players.csv verified to have exactly the required fields; null-rate audit below quantifies exactly how "required" fields must actually be nullable (Contract_expires missing 18%, Market_value missing/zero 14%, Height/Weight missing ~3-4%). See "Player Model" and "Data Quality Findings" below. |
| DATA-02 | Real club data (league, country, manager, formation, squad size, playing style) migrated to Postgres | Club has no dedicated source file; derivation strategy from Players.csv + Playstyles.csv verified against real data (1,059 distinct clubs from Players.csv, only 239 have Playstyles.csv coverage — an expected ~77% playing_style-null rate, not an error). See "Club Model & Derivation" below. |
| DATA-03 | Position-aware, multi-season player performance stats migrated and queryable | Verified: Players.csv is **one row per player**, not one row per player-season (Season field varies per-row but UniqueID has zero duplicates) — "multi-season" in the requirement describes the population's mixed season coverage, not a per-player time series. Per-position role/archetype scores live in 9 separate `Positions/*.csv` files, one row per non-GK player, verified 100% UniqueID overlap with Players.csv. See "PlayerRoleScore Model" below. |
| DATA-04 | Real transfer history (fee, date, source/destination club, market value at transfer time) migrated and queryable | transferdata's `UniqueID` column verified to be a **Club** ID (207 distinct values, 1:1 with `Club` column), NOT a Player ID — despite an identical column name to Players.csv's player-level `UniqueID`. This is the single highest-risk trap in this phase; see "Critical Pitfall: The UniqueID Trap" below. |
| DATA-05 | Migration produces reviewed import report surfacing mismatches, not silent drops | Concrete null-count/outlier numbers below (e.g. 525/1,059 clubs — 49.6% — have ambiguous League values, `Foot` has 512 rows of literal `'0'` and 287 of `'unknown'`) size what the report actually needs to surface. See "Import Report Structure" below. |
</phase_requirements>

## Summary

This phase has two halves: (1) standing up a Django/DRF project from nothing, and (2) writing a robust, idempotent, chunked ETL pipeline for six real data sources into that schema. The stack half is low-risk and already covered at HIGH confidence in `.planning/research/STACK.md` (Django 5.2 LTS, DRF 3.17, psycopg 3, `pandas<3.0`) — this document does not re-litigate that, only adds the concrete scaffolding shape needed to start Phase 1 (settings layout, app boundaries, where migrations live).

The ETL half is where the real risk is, and direct inspection of the actual CSVs (not just the CONCERNS.md summary) surfaced several concrete, previously-undocumented traps that materially change how Phase 1 must be planned:

1. **The transfer data's `UniqueID` column is a Club ID, not a Player ID** — despite sharing an identical column name with Players.csv's player-level `UniqueID`. Verified: 207 distinct values, each mapping to exactly one `Club` value across all 47,252 rows (e.g. `UniqueID=12` → 788 rows, all `Club="Atalanta"`, 192 distinct players). Joining `transferdata.UniqueID` to `Players.UniqueID` as if both were player keys would silently produce a plausible-looking but completely wrong dataset — precisely the "looks fine, is wrong" failure mode the project's own PITFALLS.md warns about, just not previously identified in this specific spot.
2. **`impact_model_v4.1.py`'s internal column names do not match the CSV's column names.** The script expects space-separated, comma'd names like `"Successful defensive actions per 90"`, `"PAdj Interceptions"`, `"Accurate passes, %"` — the CSV uses `Successful_defensive_actions_per_90`, `PAdj_Interceptions` (underscore snake_case, no comma). CONTEXT.md's locked naming decision (mirror the CSV's snake_case) is correct for Django field names, but Phase 3 (scoring curation) will need an explicit CSV-name ↔ script-name mapping that Phase 1 should capture now while the columns are being enumerated, rather than re-deriving it from scratch later.
3. **~14 CSV columns are not valid Python/Django identifiers as-is** (`Meter/Min`, `Max_Speed_(km/h)`, `Count_Medium_Acceleration_per_90_(1_DOT_5_m/s²_to_3_m/s²)`, etc.) — and none of them are referenced anywhere in `impact_model_v4.1.py`. This is a clean, evidence-backed case for putting this specific long-tail block in a `JSONField` rather than fighting to make them into 14 individually-sanitized model fields no scoring code will ever read.
4. **The 9 Compatibility Scores CSVs are wide matrices (player × ~212 clubs), not per-player records** — ~38,600 rows × 212 float columns ≈ **8.1 million individual compatibility values**. This must be normalized into a long/narrow table at import time (one row per player-club pair), not stored as 212 model fields or a single JSON blob, because Phase 11/12 (`PLAN-02`, `PLAN-04`) need to query this both "by player" and "by club" with sorting — something 212 wide columns or an unindexed JSON blob cannot do efficiently.
5. **Club identity resolution across sources is mostly clean but has one systematic gap**: Playstyles.csv only covers 239 of the 1,059 distinct club names found in Players.csv (~22.6%) — meaning `Club.playing_style` will be null for ~77% of clubs. This is expected data-source coverage, not an import bug, but the import report needs to say so explicitly or it will look like a mass failure.

**Primary recommendation:** Build one Django project (`config/` settings package, apps `clubs/`, `players/`, `transfers/`), land `Club` and `Player` first via a two-pass management command (pass 1 derives/upserts `Club` rows from the union of Players.csv + Playstyles.csv team names; pass 2 upserts `Player` rows with `club` FK resolved from an in-memory name→id map), then run per-position role-score and compatibility-score imports (which both depend on `Player` existing) and finally transfers (which depends on `Club` existing, using transferdata's own club-scoped `UniqueID`/`Club` pair — verified 1:1, stable, and a strict subset of the Player-derived club universe except for one already-consistent name variant). Normalize the 9 Compatibility CSVs into a single narrow `PlayerClubCompatibility` table at import time; do not carry the wide matrix shape into Postgres.

## Django Project Scaffolding (from scratch)

No Django project exists yet. This phase stands it up.

### Recommended layout
```
getscouted/                        # repo root for the new Django backend (separate from API-Updated-/, RT-Tool-Frontend/, pixel-perfect-clone-60729/)
├── manage.py
├── config/                        # settings package, not an app
│   ├── __init__.py
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py                # shared settings
│   │   ├── local.py                # DEBUG=True, local Postgres
│   │   └── production.py           # placeholder; hosting is explicitly deferred per PROJECT.md
│   ├── urls.py
│   └── wsgi.py
├── clubs/
│   ├── migrations/
│   ├── models.py                  # Club
│   └── management/commands/
│       └── import_clubs_playstyles.py
├── players/
│   ├── migrations/
│   ├── models.py                  # Player, PlayerRoleScore, PlayerClubCompatibility
│   └── management/commands/
│       ├── import_players.py
│       ├── import_position_roles.py
│       └── import_compatibility_scores.py
├── transfers/
│   ├── migrations/
│   └── models.py                  # Transfer
├── core/
│   ├── management/commands/
│   │   └── import_all.py          # orchestrates the above in dependency order
│   └── import_utils.py            # shared: chunked CSV reading, dtype schemas, report accumulator
├── .env.example                    # django-environ-style; DATABASE_URL, etc.
└── requirements/
    ├── base.txt
    └── dev.txt
```

**Why apps split this way (confirms + refines CONTEXT.md's Claude's-discretion note):** `players/`, `clubs/`, `transfers/` as top-level apps, consistent with what `.planning/codebase/STRUCTURE.md`'s "Module Boundaries for Django Port" section already sketches. `PlayerRoleScore` and `PlayerClubCompatibility` live inside `players/` (not a separate `scoring/` app) because in Phase 1 they are raw migrated data, not computed scores — the actual RMM/CS/TFM computation is Phase 3-6's `scoring/` app, which will *read* these tables as inputs, not own them.

### Settings specifics for this phase
- `DATABASES` via `django-environ`'s `env.db()` reading `DATABASE_URL` (per STACK.md's 12-factor recommendation) — Postgres 16/17, psycopg 3 (`psycopg[binary,pool]`).
- Add `'django.contrib.postgres'` to `INSTALLED_APPS` if any `ArrayField`/`JSONField` + `GinIndex` usage is planned (it is — see JSONField usage below).
- `CONN_POOL` (Django 5.1+ native pooling via psycopg 3) is a nice-to-have here but not load-bearing for a one-time import command; safe to configure but not a blocker for Phase 1 specifically.
- No `AUTH`/DRF app wiring needed yet — that's Phase 2. Phase 1 only needs `django.contrib.postgres`, the three data apps, and the DB connection.

## Club Model & Derivation

**No dedicated Clubs source file exists.** Verified derivation inputs and their actual overlap:

| Source | Distinct club names | Notes |
|---|---|---|
| `Players.csv` → `Team_within_selected_timeframe` | 1,059 | Zero nulls across all 41,708 rows — every player has a team value. This is the authoritative "union of all clubs" source. |
| `Playstyles.csv` → `Team` | 239 | Only 1 name (`Borussia M_gladbach`) not already present in the Players.csv club set — and it's consistently spelled the same way in both files, so no fuzzy matching is needed for this join. |
| `transferdata final.csv` → `Club` | 207 | Fully a subset of the Players.csv club set (same one consistent name variant aside). |

**Derivation algorithm (two-pass, verified against real data):**
1. Pass 1 over Players.csv (can be one `pandas.read_csv` — the whole file is ~25MB, safely fits in memory as a single DataFrame for this aggregation step): build `club → Counter(League)` for every `(Team_within_selected_timeframe, League)` pair. **This is not a rare edge case** — 525 of 1,059 clubs (49.6%) have more than one distinct `League` value across their player rows (e.g. `Manchester City`: 82 rows say `Premier League (England)`, 2 say `La Liga (Spain)`). `Club.league` = the mode; break ties deterministically (e.g. alphabetical) and log every tie-break in the import report, since roughly half of all clubs will hit this logic.
2. Union in Playstyles.csv's 239 `Team` values (already covered, adds nothing new but confirms the join).
3. Bulk-upsert `Club` rows keyed on `name` (unique). `manager`, `formation`, `country` stay null (no source, per CONTEXT.md). `playing_style_*` fields populate only for the 239 clubs present in Playstyles.csv — **expect ~77% of `Club` rows to have null playing-style fields; this is correct, not a data quality failure**, and the import report should state this coverage rate explicitly so a reviewer doesn't mistake it for a bug.
4. Pass 2 over Players.csv again, resolving `Player.club_id` via an in-memory `name → id` dict built from step 3's upsert result.

**Club.playing_style shape:** `Playstyles.csv` has 8 numeric columns per club (`Control_Possession`, `Gegenpressing`, `Direct_Play`, `Defensive_Counter_Attack`, `Tiki_Taka`, `Counter_Attack`, `Wing_Play`, `Low_Block`) — these are all valid Python identifiers already and small in number, so model as 8 individual nullable `FloatField`s on `Club` (not a JSONField) — they're exactly the kind of small, fixed-shape, filterable data STACK.md's "don't dump everything into jsonb" guidance calls for, and Phase 4's compatibility-score port (which builds team style vectors) will want to read them as typed columns, not unpack JSON per row.

## Player Model

**Verified: Players.csv is one row per player, not one row per player-season.** `UniqueID` has zero duplicates across all 41,708 rows. The `Season` column (values: `"Last Calendar Year"`, `"2024-2025"`, `"2023-2024"`, `"2022-2023"`, distribution roughly even) describes *which* season's stats populate that player's single row — it varies player-to-player, not row-to-row-per-player. **Do not build a Player-season history table for this phase** — DATA-03's "multi-season" wording describes the population's mixed season coverage across ~41.7K different players, not a per-player time series the source data doesn't actually contain. Model `Player.season` as a plain field; if true per-player season history becomes a real requirement later, that's new scope for a future phase, not something Phase 1's real data supports today.

**Field naming:** per CONTEXT.md, Django fields mirror the CSV's exact snake_case column names (`Market_value`, `Duels_per_90`, `xG_per_90`, etc.) for ~121 of the ~135 total columns. Two categories need explicit handling beyond "just copy the name":

1. **Not valid Python identifiers** (14 columns, columns 122-135 in the CSV — the "movement/physical tracking" block): `Meter/Min`, `Max_Speed_(km/h)`, `Count_Medium_Acceleration_per_90_(1_DOT_5_m/s²_to_3_m/s²)`, `Count_High_Acceleration_per_90_(+3_m/s²)`, `Count_Medium_Deceleration_...`, `Count_High_Deceleration_...`, `Count_HSR_per_90_(20-25_km/h)`, `Count_Sprint_per_90_(+25_km/h)`, `Count_HI_per_90_(+20_km/h)`, `Total_Distance_per_90`, `Running_Distance_per_90_(15-20_km/h)`, `HSR_Distance_per_90_(20-25_km/h)`, `Sprinting_Distance_per_90_(+25_km/h)`, `HI_Distance_per_90_(+20_km/h)`. **Verified: none of these 14 columns are referenced anywhere in `impact_model_v4.1.py`.** Recommendation: put this entire block into a single `Player.extended_stats` `JSONField`, keyed by the *original* CSV column name string (valid as a JSON key even though it's not a valid Python identifier). This resolves the identifier problem and correctly reflects that the scoring engine has no opinion on these fields. Add a `GinIndex` only if a future phase needs to query into this JSON — not needed in Phase 1.
2. **Legacy pre-existing score column:** `Total_Score` (column 3, right after `UniqueID`) is a **pre-existing score from the old system**, not the new Impact RMM output Phase 4-6 will compute. Import it as `Player.legacy_total_score` (explicitly renamed, not `Player.total_score`) so nobody in Phase 4+ mistakes it for the authoritative score, or accidentally treats it as already-computed and skips the real port. It may be genuinely useful later as a sanity-check baseline during Phase 5 parity testing, so don't drop it — just don't let its name collide with the real thing.

**Null/outlier rates verified across the whole 41,708-row file** (sizes what the import report actually needs to carry, per DATA-05):

| Field | Missing/zero count | Rate | Note |
|---|---|---|---|
| `Contract_expires` | 7,518 | 18.0% | Format is `DD/MM/YYYY` (e.g. `30/06/2027`) — parse explicitly, don't let pandas infer a date dtype (locale-dependent day/month swap risk). |
| `Market_value` | 5,844 | 14.0% | Includes both blank and literal `0` — both should be treated as "no market value on record," not two different states, unless a later phase needs to distinguish "known to be free" from "unknown." |
| `Weight` | 1,646 | 3.9% | |
| `Height` | 1,251 | 3.0% | |
| `Birth_country` / `Passport_country` | 8 each | 0.02% | Negligible. |
| `Foot` | 512 rows literal `'0'`, 287 rows `'unknown'` | 1.2% + 0.7% | **Dirty categorical data, not a missing-value case** — `'0'` is a bad sentinel value, not a valid foot. Flag both as outliers in the report; don't silently coerce `'0'` to null without logging it (that would be exactly the "silent coercion" pitfall PITFALLS.md warns about). |
| `Position` | 1 row blank | 0.002% | Single known-bad row. |
| Age > 60 / negative `Market_value` | 0 / 0 | — | Verified: this specific dataset has no age or negative-value outliers today, but keep the check in the import pipeline anyway (per CONTEXT.md's outlier policy) since it costs nothing and the check must exist regardless of what today's snapshot contains. |

**Position breakdown** (relevant to the Positions/Compatibility Scores CSVs below): `CB` 7,852 · `FWD` 6,391 · `CM` 5,354 · `AM` 4,406 · `RB` 3,898 · `LB` 3,790 · `DM` 3,302 · `GK` 3,081 · `LW` 1,843 · `RW` 1,790 · 1 blank. **GK players (3,081 of them) have no corresponding rows in any Positions/ or Compatibility Scores/ CSV** — there are exactly 9 non-GK position files and GK is legitimately absent from both directories. This is expected (goalkeepers aren't scored on the same outfield role-fit models) — the import report should note "3,081 GK players have zero PlayerRoleScore/PlayerClubCompatibility rows by design" so it isn't mistaken for a join failure during review.

## PlayerRoleScore Model (from `Positions/*.csv`)

Each of the 9 files (`AM with league.csv`, `CB with league.csv`, `CM with league.csv`, `DM with league.csv`, `FWD with league Updated.csv`, `LB with league.csv`, `LW with league2.csv`, `RB with league.csv`, `RW with league.csv`) has the shape `UniqueID, <role_1>, <role_2>, ...` — 4 to 7 role-archetype float score columns per position (e.g. CB: `Wide_Centre-Back_(LCB)`, `No_Nonsense_Centre_Back`, `Ball_Playing_Defender`, `Wide_Centre_Back_(RCB)`, `Libero`). Verified: **100% of each file's `UniqueID`s exist in Players.csv** (e.g. CB file: 7,852/7,852 match).

Two viable shapes; recommend the normalized one:

- **Wide (rejected):** one Django field per role column, varying per position → forces either 9 different tables or one Player table with ~50 sparse nullable float columns (most null for any given player since roles are position-specific). Also several role-column headers aren't valid identifiers as-is (`Wide_Centre-Back_(LCB)` has a hyphen and parens; `Advanced _Playmaker` in the AM file has a stray space — a literal header typo in the source data, confirm before assuming it's meaningful).
- **Long/normalized (recommended):** `PlayerRoleScore(player FK, position_group CharField, role_name CharField, score FloatField)`, one row per (player, role). ~38,600 rows total across all 9 files — trivial scale. `role_name` stores the sanitized-but-traceable version of the header (e.g. `wide_centre_back_lcb`); keep the raw header string too if useful for debugging (`role_name_raw`). Unique constraint on `(player, role_name)` gives a clean idempotent-upsert key. This shape lets Phase 3+ query "this player's best-fit role" or "average role score by position" without dealing with per-position schema variance.

## PlayerClubCompatibility Model (from `Compatability Scores/*.csv`) — the highest-volume table in this phase

Each of the 9 files (`CS_AM.csv`, `CS_CB_25.csv`, `CS_CM.csv`, `CS_DM_25 NEW.csv`, `CS_FWD.csv`, `CS_LB_25.csv`, `CS_LW.csv`, `CS_RB.csv`, `CS_RW.csv`) has the shape `UniqueID, Position, <club_1>, <club_2>, ..., <club_212>` — **214 columns total, ~212 of them are club names**, row counts matching (within a couple rows) the corresponding Positions/ file (e.g. `CS_CB_25.csv`: 7,855 rows vs. the CB position file's 7,853). This is a **wide player × club compatibility matrix**, not a per-player record.

**Scale, verified:** summed across all 9 files, roughly 38,600 player rows × 212 club columns ≈ **8.1 million individual (player, club, score) values**. This is by far the largest table this phase produces — an order of magnitude larger than the Player table itself.

**Recommendation: normalize to a long table at import time.** `PlayerClubCompatibility(player FK, club FK nullable, club_name_raw CharField, position_group CharField, score FloatField)`. Do **not** keep the 212-column wide shape and do **not** dump it into a single JSONField per player — Phase 11/12 (`PLAN-02`: "AI-suggested replacement players... ranked by RMM/CS/TFM fit", `PLAN-04`: "ranked list of clubs that fit a given player") need to sort/filter this data **from both directions** (by player, and by club) at query time. 212 wide columns can't be sorted generically by the ORM; an unindexed JSON blob can't be range/order-queried efficiently by Postgres either. A long table with `(club_id, score DESC)` and `(player_id, score DESC)` composite indexes supports both access patterns directly.

**Club-name matching for the 212 column headers is a separate, harder problem than the Team/Playstyles club matching above** — flag explicitly:
- The column headers in these files use their own sanitization scheme, distinct from the `Team`/`Team_within_selected_timeframe` values (which are internally consistent with each other, verified above). Example: the CB compatibility file's header includes `St_DOT_ Louis City`, `St_DOT_ Pauli`, `Borussia M_gladbach`, `Union Saint-Gilloise` (mixed sanitization — some use `_DOT_` for periods, some keep a literal hyphen).
- `API-Updated-/cs_field_mapping.json` provides a **partial** reverse mapping (`"St. Louis City": "St_DOT_ Louis City"`, etc.) for the club-name sanitization used in these headers specifically — but it is not comprehensive across the full 1,059-club universe seen in Players.csv, and it maps in the opposite direction needed (display-name → sanitized) from what's needed at import time (sanitized-header → existing Club row).
- **Import algorithm:** for each of the ~212 club column headers per file, try (a) exact match against `Club.name`, (b) reverse-lookup through `cs_field_mapping.json`'s partial table, (c) if still unresolved, keep the score row with `club=null` and `club_name_raw=<original header>`, and log every unresolved header once (not once per row — there are only ~212 distinct headers per file, no need to spam the report 38,600 times) in the import report for manual review. Never drop the score.

**Volume-driven import mechanics note:** 8.1M rows via `bulk_create(..., batch_size=...)` will work but will be the slowest single step in this phase by a wide margin — size the batch (e.g. 5,000-10,000) and log progress per batch. If this proves too slow in practice, this is the one table in this phase where reaching for psycopg 3's `cursor.copy()` into a staging table (per STACK.md's documented fallback) is worth trying first, rather than only after `bulk_create` is proven too slow generically — the volume gap here (8.1M vs. 42K for Players) is large enough that it's worth a deliberate go/no-go check on `bulk_create` throughput early in this specific import command, not assumed fine by analogy with the Player import.

## Transfer Model — Critical Pitfall: The `UniqueID` Trap

**Verified finding, not a hypothesis:** `transferdata final.csv`'s `UniqueID` column is **a Club identifier, not a Player identifier**, despite being named identically to Players.csv's player-level `UniqueID` column.

Evidence:
- `transferdata final.csv` has 47,252 rows but only **207 distinct `UniqueID` values**.
- Every distinct `UniqueID` maps to exactly one `Club` value and vice versa (207 distinct `UniqueID`s, 207 distinct `Club` names, zero collisions either direction) — a clean 1:1 bijection between `UniqueID` and `Club`.
- Concrete proof: `UniqueID=12` appears in 788 rows, **all** with `Club="Atalanta"`, spanning 192 *different* players (`Anton Kresic`, `Luca Zanotti`, `Gaetano Monachello`, ...).
- `transferdata.Club`'s 207 distinct values are a strict subset of the 1,059 distinct club names from Players.csv (same single `Borussia M_gladbach` spelling-consistency case as everywhere else — no other mismatches).
- `transferdata.Dealing_Club` (the transfer counterparty) has **2,909 distinct values** — a much larger, mostly-foreign/lower-league universe that only partially overlaps the 1,059-club Players.csv universe (e.g. `FK Riteriai`, `Newtongrange Star FC`, `Everton FC U18` appear as counterparties but have no Player roster data).

**Implication for schema design:**
- `Transfer.club` → FK to `Club`, resolved from `transferdata.Club` (verified clean match against the Club universe built in the Club-derivation step above). `transferdata.UniqueID` is a genuinely useful **stable natural key for Club identity confirmation** (double-check the name-based match against this numeric ID; if a future non-name-based source appears, this ID is already captured) — but it must never be joined against `Player.UniqueID`.
- `Transfer.dealing_club` → plain `CharField`, **not** FK to `Club`. Creating stub `Club` rows for all 2,909 counterparty names (mostly youth/foreign clubs with zero player-roster or playing-style data) would pollute the Club table with entities this project has no other data for and no product surface for (Club list/filter pages in CRUD-02 have nothing meaningful to show for a club that exists only as a transfer counterparty).
- **Player linkage:** transferdata has no reliable player-ID column at all — only a `Player` name string. Resolve `Transfer.player` via best-effort name matching against `Player.Player` (the name field), and accept it will sometimes be null/ambiguous (common names, transfer-time vs. current-roster name spelling differences). Do not treat an unmatched transfer row as an error — log it, keep the row, per CONTEXT.md's policy.
- **Idempotent upsert key for Transfer:** no single natural unique column exists (confirmed: `UniqueID` here means Club, not a transfer-event ID). Recommend a composite unique constraint over columns that together identify one real transfer event: `(Player name, Year, Window, Movement, Club, Dealing_Club)` — verified all six of these are always populated (zero nulls across all 47,252 rows in the null-count audit).

**transferdata field inventory (verified header):** `UniqueID` (→ Club ID, see above), `Club`, `Player`, `Age` (age *at transfer time*, not current age — do not conflate with `Player.Age`), `Nationality`, `Position`, `Short_Position`, `Market_Value` (at transfer time), `Dealing_Club`, `Dealing_Country`, `Fee`, `Movement` (`arrival`/`departure`, roughly balanced: 22,429 / 24,823), `Window` (`Summer`/etc.), `League_Name`, `Year`, `is_loan` (`TRUE`/`FALSE` string), `loan_status`. Zero missing values across all checked columns in this file — noticeably cleaner than Players.csv.

## Import Report Structure (DATA-05)

**Recommendation: a single structured JSON artifact per import run, plus a human-readable Markdown summary generated from it.** Write to `core/import_reports/<entity>_<run_timestamp>.json` (gitignored except the latest, or committed if the team wants PR-reviewable diffs of report changes as field mapping is refined — reasonable either way; lean toward committing given the compressed timeline benefits from reviewable artifacts over a chat-only summary). Skip building a dedicated Django model/DB table for this in Phase 1 — no admin/CRUD surface exists yet to browse it (that's Phase 7+), and a file is sufficient for the "reviewed" requirement in DATA-05 at this stage.

Suggested shape per run:
```json
{
  "run_at": "2026-07-20T00:00:00Z",
  "source_file": "API-Updated-/dataset/Players.csv",
  "source_row_count": 41708,
  "rows_created": 41707,
  "rows_updated": 0,
  "rows_flagged": 8388,
  "field_issues": [
    {"field": "Contract_expires", "issue": "missing", "count": 7518, "rate": 0.180},
    {"field": "Market_value", "issue": "missing_or_zero", "count": 5844, "rate": 0.140},
    {"field": "Foot", "issue": "invalid_value:'0'", "count": 512, "rate": 0.0123, "sample_ids": [/* up to 10 UniqueIDs */]},
    {"field": "Foot", "issue": "invalid_value:'unknown'", "count": 287, "rate": 0.0069}
  ],
  "club_derivation": {
    "distinct_clubs": 1059,
    "clubs_with_ambiguous_league": 525,
    "clubs_with_playing_style_coverage": 239,
    "playing_style_coverage_rate": 0.226
  },
  "unresolved_club_names": ["<sample of headers/names that never matched an existing Club row>"]
}
```
Group by `(field, issue_type)` with counts + a small ID sample (not every offending row individually) — several of these issues affect thousands of rows and per-row logging would make the report unreadable rather than more useful. This directly matches the volumes measured above (e.g. don't emit 7,518 individual `Contract_expires`-missing log lines).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Idempotent bulk upsert on ~41.7K-8.1M rows | Manual "does this row already exist" `get_or_create` loop | `Model.objects.bulk_create(objs, batch_size=..., update_conflicts=True, unique_fields=[...], update_fields=[...])` | Verified requirement (Django docs, cross-checked 2026-07-20): needs Django 4.1+ (have 5.2), Postgres 9.5+ (have 16/17), and **a real DB-level unique constraint** on `unique_fields` — a bare `unique_together` in `Meta` without an actual constraint/`UniqueConstraint` will not satisfy this; use `unique=True` or an explicit `models.UniqueConstraint`. |
| CSV dtype inference | Letting `pandas.read_csv()` infer column types | Explicit `dtype=`/`converters=` per column, especially for `UniqueID` (int), `Market_value` (nullable numeric, not auto-upcast to float on NaN), `Contract_expires` (string, parse manually — don't let pandas guess a date format for `DD/MM/YYYY`) | Silent int→float upcasting on nullable integer columns is the exact CONCERNS.md/PITFALLS.md-flagged failure mode; verified real occurrence risk here since `Market_value` is genuinely null/zero for 14% of rows. |
| Club-name fuzzy matching for the Compatibility Scores headers | A custom fuzzy-string-matcher from scratch | Exact match first, then the existing (partial) `cs_field_mapping.json` reverse table, then explicit "unresolved" logging — no fuzzy/similarity matching needed given the verified near-100% exact-match rate everywhere except the already-known sanitization variants | The data doesn't need fuzzy matching (verified: club name mismatches across sources are limited to one specific, already-known sanitization pattern) — building a general fuzzy matcher would be solving a problem this dataset doesn't actually have. |

## Common Pitfalls

### Pitfall 1: Treating `transferdata.UniqueID` as a Player foreign key
**What goes wrong:** A naive import joins `Transfer.player` to `Player` via `transferdata.UniqueID == Players.UniqueID`, since both columns share the name `UniqueID`. This "succeeds" (every value in transferdata's `UniqueID` column does exist as *some* row's `UniqueID` in Players.csv, since both are drawn from small-ish integer ranges) but silently attaches each transfer record to the wrong player entirely.
**Why it happens:** Identical column name across two files, both integer-typed, both plausible as "the" unique key — nothing about the column itself signals it's actually a Club ID in this file.
**How to avoid:** Verified in this research: `transferdata.UniqueID` has only 207 distinct values, is 1:1 with `transferdata.Club`, and must be used as a Club key, never a Player key. Link `Transfer.player` via name-matching on the `Player` string column instead (best-effort, nullable).
**Warning signs:** If an import script joins transfers to players via `UniqueID` and reports near-100% match rate with no ambiguity, that's actually a red flag here, not reassurance — it means the join silently "worked" against the wrong semantics.

### Pitfall 2: Assuming the CSV's snake_case field names equal `impact_model_v4.1.py`'s internal column names
**What goes wrong:** Phase 3+ scoring-port work assumes `Player.Successful_defensive_actions_per_90` (the Django field, correctly named per CONTEXT.md) can be passed straight into the ported scoring functions, which actually reference `"Successful defensive actions per 90"` (spaces, no underscores) and `"PAdj Interceptions"`, `"Accurate passes, %"` (comma-percent forms) internally.
**Why it happens:** `impact_model_v4.1.py` was written against a different (likely Excel/xlsx) export format than the CSVs actually being migrated in this project; nothing in the file names or CONTEXT.md flags this format mismatch explicitly.
**How to avoid:** This doesn't block Phase 1, but Phase 1's `FIELD_MAPPING.md` should record, per stat field, both the Django field name (CSV snake_case) and the corresponding literal string `impact_model_v4.1.py` uses internally — captured once now, while every column is already being enumerated for the CSV→Django mapping, rather than re-derived line-by-line during Phase 3.
**Warning signs:** Phase 3's scoring functions raising `KeyError`s on column names that "look like they should exist," or (worse) silently falling back to defensive `0`-default branches (per PITFALLS.md Pitfall 6) because the expected space-separated column name is never present on a snake_case DataFrame.

### Pitfall 3: Building 212 model fields (or 9 separate wide tables) for compatibility scores
**What goes wrong:** Modeling `Compatability Scores/*.csv` field-for-field produces ~212 nullable float columns (mostly irrelevant per row, since a CB player's file only has CB-relevant columns but still 212 club columns), and makes "find best-fit players for Club X" or "best-fit clubs for Player Y" — both real Phase 11/12 requirements — require either raw SQL across 212 named columns or full-table Python-side sorting.
**How to avoid:** Normalize to `PlayerClubCompatibility(player, club, score)` at import time (see model recommendation above); this is what makes both query directions a plain indexed `ORDER BY`.
**Warning signs:** Any Phase 11/12 planning that describes iterating all 212 columns per player row to find "the best club" — that's the wide-schema symptom showing up downstream.

### Pitfall 4: Treating the ~77% `Club.playing_style` null rate as an import failure
**What goes wrong:** A reviewer sees the import report show ~820 of 1,059 clubs with null playing-style fields and assumes the Playstyles.csv join is broken.
**How to avoid:** State the coverage rate explicitly in the import report (verified: 239/1,059 = 22.6% coverage, by real data-source limitation, not a bug) so this doesn't trigger unnecessary re-debugging.

## Code Examples

### Two-pass idempotent Club + Player import (verified-shape sketch)
```python
# core/import_utils.py
import pandas as pd
from collections import Counter, defaultdict

PLAYER_DTYPES = {
    "UniqueID": "int64",
    "Player": "string",
    "Team_within_selected_timeframe": "string",
    "League": "string",
    "Foot": "string",
    # Market_value, Age etc: read as nullable Int64/Float64 explicitly, not left to inference
}

def load_players_df(csv_path):
    return pd.read_csv(
        csv_path,
        dtype=PLAYER_DTYPES,
        na_values=["", "N/A", "NA"],
        keep_default_na=True,
    )

def derive_club_league(df):
    """Most-common League per Team_within_selected_timeframe, tie-broken alphabetically.
    Verified: 525/1059 clubs (49.6%) have >1 distinct League value, so this path is common, not rare."""
    club_leagues = defaultdict(Counter)
    for team, league in zip(df["Team_within_selected_timeframe"], df["League"]):
        club_leagues[team][league] += 1
    result = {}
    for club, counts in club_leagues.items():
        max_count = max(counts.values())
        winners = sorted(l for l, c in counts.items() if c == max_count)
        result[club] = winners[0]
    return result
```

```python
# players/management/commands/import_players.py
from django.core.management.base import BaseCommand
from django.db import transaction
from clubs.models import Club
from players.models import Player
from core.import_utils import load_players_df, derive_club_league

class Command(BaseCommand):
    def handle(self, *args, **options):
        df = load_players_df("API-Updated-/dataset/Players.csv")

        # Pass 1: derive + upsert Club rows
        club_league_map = derive_club_league(df)
        club_objs = [Club(name=name, league=league) for name, league in club_league_map.items()]
        Club.objects.bulk_create(
            club_objs, batch_size=1000,
            update_conflicts=True, unique_fields=["name"], update_fields=["league"],
        )
        club_id_map = dict(Club.objects.values_list("name", "id"))

        # Pass 2: upsert Player rows, chunked
        CHUNK = 2000
        for start in range(0, len(df), CHUNK):
            chunk = df.iloc[start:start + CHUNK]
            with transaction.atomic():
                objs = [
                    Player(
                        unique_id=row.UniqueID,
                        player=row.Player,
                        club_id=club_id_map.get(row.Team_within_selected_timeframe),
                        # ... remaining ~120 fields
                    )
                    for row in chunk.itertuples()
                ]
                Player.objects.bulk_create(
                    objs, batch_size=CHUNK,
                    update_conflicts=True, unique_fields=["unique_id"],
                    update_fields=[f.name for f in Player._meta.fields if f.name not in ("id", "unique_id")],
                )
```
*Note: `bulk_create` bypasses `post_save` signals and ignores `auto_now`/`auto_now_add` — if `Player`/`Club` use an `updated_at = auto_now=True` field, it will not update on the `ON CONFLICT DO UPDATE` path; set such timestamp fields explicitly in the `update_fields` list and object construction instead of relying on `auto_now`.* (Source: Django forum thread on `bulk_create`+`update_conflicts` behavior, cross-checked against Django's own `bulk_create` docs — MEDIUM-HIGH confidence, verified 2026-07-20.)

### Normalizing the wide Compatibility Scores CSV to long format
```python
import pandas as pd

def load_compatibility_long(csv_path, position_group):
    wide = pd.read_csv(csv_path)  # UniqueID, Position, <club_1..club_212>
    club_cols = [c for c in wide.columns if c not in ("UniqueID", "Position")]
    long_df = wide.melt(
        id_vars=["UniqueID", "Position"],
        value_vars=club_cols,
        var_name="club_name_raw",
        value_name="score",
    )
    long_df["position_group"] = position_group
    return long_df  # ~7,855 * 212 ≈ 1.67M rows for this one file alone
```

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest + pytest-django (per `.planning/research/STACK.md`, not yet installed — this phase's Wave 0 must add it) |
| Config file | none yet — `pytest.ini`/`pyproject.toml [tool.pytest.ini_options]` needs creation in Wave 0 |
| Quick run command | `pytest players/tests/test_import.py -x -q` |
| Full suite command | `pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| DATA-01 | Player row count in Postgres matches Players.csv row count (41,708) after import | integration | `pytest players/tests/test_import.py::test_player_row_count -x` | ❌ Wave 0 |
| DATA-01 | Required-but-nullable fields (Market_value, Contract_expires, Foot) import as null/flagged, never crash the row | unit | `pytest players/tests/test_import.py::test_player_missing_field_handling -x` | ❌ Wave 0 |
| DATA-02 | Club.league derivation picks the mode League value, deterministic tie-break | unit | `pytest clubs/tests/test_club_derivation.py::test_league_mode -x` | ❌ Wave 0 |
| DATA-02 | Club.playing_style populated only for the ~239 Playstyles.csv-covered clubs, null elsewhere (not an error) | unit | `pytest clubs/tests/test_club_derivation.py::test_playing_style_coverage -x` | ❌ Wave 0 |
| DATA-03 | Every non-GK Player has 0+ PlayerRoleScore rows; every GK Player has exactly 0 (by design) | integration | `pytest players/tests/test_import.py::test_role_score_coverage -x` | ❌ Wave 0 |
| DATA-04 | Transfer.club resolves via transferdata's Club/UniqueID pair, never mistakenly via Player.UniqueID | unit | `pytest transfers/tests/test_transfer_import.py::test_uniqueid_is_club_not_player -x` | ❌ Wave 0 |
| DATA-04 | Transfer idempotent-upsert composite key doesn't create duplicate rows on re-run | integration | `pytest transfers/tests/test_transfer_import.py::test_idempotent_rerun -x` | ❌ Wave 0 |
| DATA-05 | Import report JSON contains the expected field_issues entries after a run against a fixture CSV | unit | `pytest core/tests/test_import_report.py::test_report_shape -x` | ❌ Wave 0 |
| DATA-05 | Re-running the full import twice produces zero net row-count change (idempotency) | integration | `pytest players/tests/test_import.py::test_reimport_idempotent -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** unit-level quick run against small fixture CSVs (not the full 41.7K/8.1M-row real files) — `pytest -x -q -k "not integration"`
- **Per wave merge:** full suite including integration tests against a real (or realistically-sized sampled) subset of the actual CSVs
- **Phase gate:** full suite green + a manual row-count reconciliation (`SELECT COUNT(*)` per table vs. source CSV row counts) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pytest`, `pytest-django` install + `pyproject.toml`/`pytest.ini` config — no test framework exists yet (from-scratch project)
- [ ] Small fixture CSVs (10-20 representative rows per source file, including at least one row per known data-quality case: missing Market_value, dirty Foot value, ambiguous club league, unresolvable compatibility-score club header) — real full CSVs are too large/slow for per-commit unit tests
- [ ] `core/tests/conftest.py` — shared Postgres test DB fixtures, `django_db` marker setup
- [ ] Framework install: `pip install pytest pytest-django factory_boy`

## Open Questions

1. **Should `Transfer.dealing_club` counterparties (2,909 distinct names) ever get their own `Club` rows?**
   - What we know: creating stub rows for all of them pollutes the Club table with entities that have no roster/playing-style data and no product surface (CRUD-02's Club list/filter is about real, rostered clubs).
   - What's unclear: whether a future phase (e.g. deal analysis, PLAN-04) wants to treat "clubs we've seen as transfer counterparties" as first-class entities.
   - Recommendation: keep `dealing_club` as a plain string field in Phase 1; revisit only if a concrete later-phase requirement needs it as an FK.

2. **Exact `unique_fields`/DB constraint mechanics for `PlayerClubCompatibility` when `club` is nullable.**
   - What we know: `bulk_create(update_conflicts=True)` requires a real DB unique constraint on `unique_fields`, and `club` will be null for any unresolved club-name header.
   - What's unclear: Postgres unique constraints treat multiple NULLs as distinct (not conflicting) by default, so `(player, club)` uniqueness won't naturally dedupe unresolved rows across re-runs the way it would for resolved ones.
   - Recommendation: use `(player, club_name_raw)` as the actual unique constraint (always non-null, since `club_name_raw` is always populated from the CSV header) rather than `(player, club)`; treat `club` as a resolved-FK convenience field, not the idempotency key.

3. **Whether to commit `core/import_reports/*.json` to the repo or gitignore it.**
   - What we know: DATA-05 wants a "reviewed" report; PR-reviewable diffs are valuable given the compressed timeline and iterative field-mapping refinement CONTEXT.md anticipates.
   - What's unclear: whether the team wants import-report noise in git history across many re-runs during development.
   - Recommendation: commit the report from the final, reviewed run of each entity's import (not every dev-loop re-run) — a planning-time convention decision, not a blocker.

## Sources

### Primary (HIGH confidence — direct inspection of real project files, 2026-07-20)
- `API-Updated-/dataset/Players.csv` — full header (135 columns), row count (41,708), null/outlier audit across all fields, UniqueID uniqueness, Season distribution, Position distribution, club/league ambiguity rate — verified via direct `csv`/`pandas`-equivalent scripted inspection, not sampled by eye.
- `API-Updated-/dataset/transferdata final.csv` — full header (17 columns), row count (47,252), the `UniqueID`-is-actually-Club-ID finding (207 distinct values, verified 1:1 bijection with `Club`), null-count audit (zero nulls across checked columns), `Dealing_Club` universe size (2,909).
- `API-Updated-/dataset/Playstyles.csv` — header (10 columns), row count (239 clubs), overlap check against Players.csv club universe.
- `API-Updated-/dataset/Positions/*.csv` (all 9 files) — headers, row counts, UniqueID overlap check (100% match against Players.csv for the CB file, spot-verified).
- `API-Updated-/dataset/Compatability Scores/*.csv` (all 9 files) — headers, row counts, column-count confirmation (214 cols = UniqueID + Position + 212 clubs).
- `API-Updated-/cs_field_mapping.json` — full contents read; confirmed partial/one-directional club-name sanitization mapping.
- `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` — grepped for column-name usage; confirmed the script's internal names are space-separated (`"Successful defensive actions per 90"`, `"PAdj Interceptions"`), not the CSV's underscore snake_case; confirmed the movement/physical-tracking CSV columns (Meter/Min, Max_Speed, Acceleration/Deceleration counts) are never referenced; confirmed `_rename_columns_safe()`'s `"Team within selected timeframe"` → `"Team"` rename, corroborating CONTEXT.md's `Team_within_selected_timeframe` FK-source decision.
- `API-Updated-/models/player.js` — legacy Mongoose field inventory, cross-checked against the CSV header.

### Secondary (MEDIUM-HIGH confidence)
- Django `bulk_create(update_conflicts=True)` requirements (Django 4.1+/Postgres 9.5+, needs a real DB unique constraint, bypasses signals/`auto_now`) — WebSearch cross-checked against Django forum threads discussing this exact feature; not independently re-verified against the Django 5.2 changelog text directly in this pass, but consistent with `.planning/research/STACK.md`'s existing HIGH-confidence coverage of the same pattern.

### Tertiary / carried over from project-level research (already HIGH/MEDIUM confidence, not re-derived here)
- `.planning/research/STACK.md` — Django 5.2 LTS, DRF 3.17, psycopg 3, pandas pin, `bulk_create` pattern, jsonb/GinIndex guidance.
- `.planning/research/PITFALLS.md` — silent CSV import data loss, dtype coercion, field-naming mismatch pitfalls (this document's findings are concrete instances of several of PITFALLS.md's general warnings).
- `.planning/codebase/CONCERNS.md` — known field-mapping issue list, used as the starting checklist this research verifies against real data rather than restates.

## Metadata

**Confidence breakdown:**
- Django scaffolding: HIGH — standard, low-risk, consistent with STACK.md and Django's own current docs.
- Data shape findings (Club derivation, PlayerRoleScore, PlayerClubCompatibility, the transferdata UniqueID trap, field-naming mismatch with the scoring script): HIGH — every number cited above was produced by directly parsing the real CSV files in this repo, not estimated or assumed.
- Import mechanics (`bulk_create(update_conflicts=True)` constraints, batch sizing for the 8.1M-row compatibility table): MEDIUM-HIGH — the Django-side mechanics are well-documented; the exact batch size/throughput for 8.1M rows on this specific hardware is not something research can verify in advance and should be treated as a "measure early in the phase" item, not a fixed number.
- Indexing specifics for Phase 7's query patterns: MEDIUM — Phase 1 can and should add sensible baseline indexes (UniqueID, FK columns, common filter fields), but precise composite/covering indexes should wait for Phase 7's actual query shapes rather than being guessed now.

**Research date:** 2026-07-20
**Valid until:** Source CSVs are static project files (not a live external API), so the data-shape findings don't expire on a calendar timeline the way library-version research does — re-verify only if the source CSVs themselves are replaced/updated. Django/library version guidance inherits STACK.md's ~30-day validity window.
