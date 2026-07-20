# Field Mapping: CSV → Django → impact_model_v4.1.py

**Purpose:** Canonical, single-source-of-truth mapping between `API-Updated-/dataset/*.csv` column
names, the Django model field names this project uses, and (where the name diverges) the literal
column-name string `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` references internally.

This document is a required Phase 1 deliverable (DATA-05 prerequisite, per
`.planning/phases/01-data-foundation/01-CONTEXT.md`): the CSV-name vs. script-name divergence and
the known field-mapping mismatches from `.planning/codebase/CONCERNS.md` are resolved here, once,
in writing — not guessed ad hoc inside import code in Phase 3+.

**Sources verified directly against real project files (2026-07-20):**
- `API-Updated-/dataset/Players.csv` (header row, 135 columns)
- `API-Updated-/dataset/transferdata final.csv` (header row, 17 columns)
- `API-Updated-/dataset/Playstyles.csv` (header row, 10 columns)
- `.planning/codebase/CONCERNS.md` §"Known Issue: Missing Field Mapping"
- `API-Updated-/utils/fieldMapper.js` (existing partial mapping — team names only)
- `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` (grepped for column-name string literals)
- `.planning/phases/01-data-foundation/01-RESEARCH.md` (null/outlier rates, duplicate-header finding)

**Canonical field naming decision (locked, per CONTEXT.md):** Django model fields mirror the
original CSV's exact `Snake_Case_With_Caps` column names verbatim, wherever the column name is a
valid Python identifier. This is deliberate — it keeps Phase 5 parity testing traceable 1:1 against
`impact_model_v4.1.py` inputs, with no translation layer to get wrong. Do not lowercase or otherwise
"Pythonify" these Django field names.

---

## 1. Player fields (Players.csv)

135 total columns. 14 of them (the movement/physical tracking block, columns 122–135) are not valid
Python identifiers and are handled separately in §2. The remaining 121 columns — 11 identifier/meta
columns plus 110 stat columns — are valid identifiers and map 1:1 to Django field names of the same
name. Six of the 11 identifier/meta columns need special handling beyond "just copy the name" and
are called out explicitly in §1a before the full stat table in §1b.

### 1a. Special renames (identifier/meta columns — read this before §1b)

| CSV column | Django field | Notes |
|---|---|---|
| `UniqueID` | `unique_id` | Player-level natural key. `unique=True` on the Django field. Verified zero duplicates across all 41,708 rows — safe as the idempotent-upsert key (`bulk_create(update_conflicts=True, unique_fields=["unique_id"])`). |
| `Total_Score` | `legacy_total_score` | **Flag loudly: this is a pre-existing score from the OLD (pre-Django) system, NOT the Impact RMM output Phase 4–6 will compute.** Renamed explicitly so nobody in Phase 4+ mistakes it for the authoritative score or accidentally skips the real port because "a score already exists." Kept (not dropped) because it may be a useful sanity-check baseline during Phase 5 parity testing. |
| `Team_within_selected_timeframe` | `club` (FK to `Club`) | **This is the correct source column for the `Player.club` FK — NOT `Team`.** Verified: `impact_model_v4.1.py` itself renames `"Team within selected timeframe"` → `"Team"` internally (see `_rename_columns_safe()` / line ~1196 of the script), confirming these two CSV columns represent the same underlying concept and `Team_within_selected_timeframe` is the authoritative one. |
| `Team` | *(dropped — not carried forward)* | Duplicate concept to `Team_within_selected_timeframe`. CONTEXT.md's locked decision: model `Player.club` as one proper FK, not two string fields. Do not create a Django field for raw `Team`. |
| `Positions` | `Positions` | Full list of all positions a player can play (multi-value, e.g. `"CB, RB"`). Model as `django.contrib.postgres.fields.ArrayField` (or a comma-split at import time) — this is genuinely list-shaped data per STACK.md's ArrayField guidance, not a single category. |
| `Main_Position` | `Main_Position` | The single position group used for role-score/compatibility-score lookups (`AM`, `CB`, `CM`, `DM`, `FWD`, `LB`, `LW`, `RB`, `RW`, `GK`). Referenced by `impact_model_v4.1.py` as `"Main_Position"` (verified exact match, no divergence — the script already uses this underscore form). This is the field `PlayerRoleScore.position_group` and `PlayerClubCompatibility.position_group` join against. |
| `Position` | `Position` | Finer-grained single position label (e.g. `"RCB"`, `"AMF"`). Distinct from `Main_Position` (the position *group*). 1 known blank row (0.002% missing) per RESEARCH.md's null audit — import as nullable, flag the row, do not skip it. |
| `Season` | `Season` | Describes which season's stats populate this player's single row (`"Last Calendar Year"`, `"2024-2025"`, etc.). **Not a per-player time series** — verified `UniqueID` has zero duplicates across all 41,708 rows, i.e. Players.csv is one row per player, not one row per player-season. Model as a plain `CharField`. |
| `League` | `League` | The player's own league at time of record. Also the raw input to `Club.league` derivation (mode per club) — see the Club Model section in RESEARCH.md; not duplicated here since `Club` has no source file of its own. |
| `Player` | `Player` | Player's display name. Also used as the best-effort join key for `Transfer.player` resolution (see §4) — nullable/ambiguous matches are expected and acceptable. |
| `Age` | `Age` | Player's current age at time of this CSV snapshot. Verified: no age > 60 outliers in the current dataset, but the outlier check must still exist in the import pipeline per CONTEXT.md's policy (cheap to keep, and today's snapshot isn't guaranteed to stay outlier-free). |

### 1b. Stat columns (110 columns, `Market_value` through `Penalty_conversion_percentage`)

`impact_model_v4.1.py` uses **space-separated, comma'd names** internally (e.g.
`"Successful defensive actions per 90"`, `"PAdj Interceptions"`, `"Accurate passes, %"`) that do
**not** match the CSV's underscore snake_case column names. This is a confirmed, previously-
undocumented pitfall (see `.planning/phases/01-data-foundation/01-RESEARCH.md` Pitfall 2): the
script was written against a different (likely Excel/xlsx) export format than the CSVs actually
being migrated. The Django field name still mirrors the CSV name per the canonical naming decision
above — the third column below is what Phase 3's scoring port must use to read each Django field's
value back out under the name the ported script functions actually expect.

Where a column is marked **not referenced**, `impact_model_v4.1.py` does not use that exact column
anywhere (verified by direct grep against the 15,747-line script) — usually because only the
`_per_90` (rate) form of a stat is used by the scoring engine, not the raw season-total count.
These columns are still migrated (per CONTEXT.md's "maximize completeness" policy) — they are simply
not scoring-engine inputs.

| CSV column | Django field | impact_model_v4.1.py internal name | Notes |
|---|---|---|---|
| `Market_value` | `Market_value` | `"Market value"` | 14.0% missing/zero (5,844/41,708 rows) — blank and literal `0` both mean 'no market value on record', not two distinct states. |
| `Contract_expires` | `Contract_expires` | `"Contract expires"` | 18.0% missing (7,518/41,708 rows). Format is `DD/MM/YYYY` (e.g. `30/06/2027`) — parse explicitly; do not let pandas infer a date dtype (locale-dependent day/month swap risk). |
| `Matches_played` | `Matches_played` | `"Matches played"` | |
| `Minutes_played` | `Minutes_played` | `"Minutes played"` | |
| `Goals` | `Goals` | `"Goals"` | |
| `xG` | `xG` | not referenced | |
| `Assists` | `Assists` | `"Assists"` | |
| `xA` | `xA` | not referenced | |
| `Duels_per_90` | `Duels_per_90` | `"Duels per 90"` | |
| `Duels_won_percentage` | `Duels_won_percentage` | `"Duels won, %"` | |
| `Birth_country` | `Birth_country` | `"Birth country"` | 0.02% missing (8/41,708 rows). |
| `Passport_country` | `Passport_country` | `"Passport country"` | 0.02% missing (8/41,708 rows). |
| `Foot` | `Foot` | `"Foot"` | 512 rows literal `'0'`, 287 rows `'unknown'` — dirty categorical data, not a missing value. Flag both as outliers in the import report; do not silently coerce to null. |
| `Height` | `Height` | `"Height"` | 3.0% missing (1,251/41,708 rows). |
| `Weight` | `Weight` | not referenced | 3.9% missing (1,646/41,708 rows). Not referenced by impact_model_v4.1.py. |
| `On_loan` | `On_loan` | `"On loan"` | |
| `Successful_defensive_actions_per_90` | `Successful_defensive_actions_per_90` | `"Successful defensive actions per 90"` | |
| `Defensive_duels_per_90` | `Defensive_duels_per_90` | `"Defensive duels per 90"` | |
| `Defensive_duels_won_percentage` | `Defensive_duels_won_percentage` | `"Defensive duels won, %"` | |
| `Aerial_duels_per_90` | `Aerial_duels_per_90` | `"Aerial duels per 90"` | **Duplicate CSV header** — `Aerial_duels_per_90` appears twice in the raw Players.csv header (once in the outfield defensive block, once again in the GK block). pandas will auto-suffix the second occurrence (e.g. `Aerial_duels_per_90.1`) on `read_csv`. Import code must read both raw positions explicitly and decide which populates `Player.Aerial_duels_per_90` (recommend: GK rows use the second/GK-block occurrence, outfield rows use the first) rather than silently keeping whichever pandas orders last. |
| `Aerial_duels_won_percentage` | `Aerial_duels_won_percentage` | `"Aerial duels won, %"` | |
| `Sliding_tackles_per_90` | `Sliding_tackles_per_90` | `"Sliding tackles per 90"` | |
| `PAdj_Sliding_tackles` | `PAdj_Sliding_tackles` | not referenced | |
| `Shots_blocked_per_90` | `Shots_blocked_per_90` | `"Shots blocked per 90"` | |
| `Interceptions_per_90` | `Interceptions_per_90` | `"Interceptions per 90"` | |
| `PAdj_Interceptions` | `PAdj_Interceptions` | `"PAdj Interceptions"` | |
| `Fouls_per_90` | `Fouls_per_90` | `"Fouls per 90"` | |
| `Yellow_cards` | `Yellow_cards` | not referenced | |
| `Yellow_cards_per_90` | `Yellow_cards_per_90` | `"Yellow cards per 90"` | |
| `Red_cards` | `Red_cards` | not referenced | |
| `Red_cards_per_90` | `Red_cards_per_90` | `"Red cards per 90"` | |
| `Successful_attacking_actions_per_90` | `Successful_attacking_actions_per_90` | `"Successful attacking actions per 90"` | |
| `Goals_per_90` | `Goals_per_90` | `"Goals per 90"` | |
| `Non_penalty_goals` | `Non_penalty_goals` | not referenced | |
| `Non_penalty_goals_per_90` | `Non_penalty_goals_per_90` | `"Non-penalty goals per 90"` | Note the hyphen (`Non-penalty`), not an underscore, in the script's internal name. |
| `xG_per_90` | `xG_per_90` | `"xG per 90"` | |
| `Head_goals` | `Head_goals` | not referenced | |
| `Head_goals_per_90` | `Head_goals_per_90` | `"Head goals per 90"` | |
| `Shots` | `Shots` | not referenced | |
| `Shots_per_90` | `Shots_per_90` | `"Shots per 90"` | |
| `Shots_on_target_percentage` | `Shots_on_target_percentage` | `"Shots on target, %"` | |
| `Goal_conversion_percentage` | `Goal_conversion_percentage` | `"Goal conversion, %"` | |
| `Assists_per_90` | `Assists_per_90` | `"Assists per 90"` | |
| `Crosses_per_90` | `Crosses_per_90` | `"Crosses per 90"` | |
| `Accurate_crosses_percentage` | `Accurate_crosses_percentage` | `"Accurate crosses, %"` | |
| `Crosses_from_left_flank_per_90` | `Crosses_from_left_flank_per_90` | `"Crosses from left flank per 90"` | |
| `Accurate_crosses_from_left_flank_percentage` | `Accurate_crosses_from_left_flank_percentage` | not referenced | |
| `Crosses_from_right_flank_per_90` | `Crosses_from_right_flank_per_90` | `"Crosses from right flank per 90"` | |
| `Accurate_crosses_from_right_flank_percentage` | `Accurate_crosses_from_right_flank_percentage` | not referenced | |
| `Crosses_to_goalie_box_per_90` | `Crosses_to_goalie_box_per_90` | `"Crosses to goalie box per 90"` | |
| `Dribbles_per_90` | `Dribbles_per_90` | `"Dribbles per 90"` | |
| `Successful_dribbles_percentage` | `Successful_dribbles_percentage` | `"Successful dribbles, %"` | |
| `Offensive_duels_per_90` | `Offensive_duels_per_90` | `"Offensive duels per 90"` | |
| `Offensive_duels_won_percentage` | `Offensive_duels_won_percentage` | `"Offensive duels won, %"` | |
| `Touches_in_box_per_90` | `Touches_in_box_per_90` | `"Touches in box per 90"` | |
| `Progressive_runs_per_90` | `Progressive_runs_per_90` | `"Progressive runs per 90"` | |
| `Accelerations_per_90` | `Accelerations_per_90` | `"Accelerations per 90"` | |
| `Received_passes_per_90` | `Received_passes_per_90` | `"Received passes per 90"` | |
| `Received_long_passes_per_90` | `Received_long_passes_per_90` | `"Received long passes per 90"` | |
| `Fouls_suffered_per_90` | `Fouls_suffered_per_90` | `"Fouls suffered per 90"` | |
| `Passes_per_90` | `Passes_per_90` | `"Passes per 90"` | |
| `Accurate_passes_percentage` | `Accurate_passes_percentage` | `"Accurate passes, %"` | |
| `Forward_passes_per_90` | `Forward_passes_per_90` | `"Forward passes per 90"` | |
| `Accurate_forward_passes_percentage` | `Accurate_forward_passes_percentage` | `"Accurate forward passes, %"` | |
| `Back_passes_per_90` | `Back_passes_per_90` | `"Back passes per 90"` | |
| `Accurate_back_passes_percentage` | `Accurate_back_passes_percentage` | `"Accurate back passes, %"` | |
| `Lateral_passes_per_90` | `Lateral_passes_per_90` | `"Lateral passes per 90"` | |
| `Accurate_lateral_passes_percentage` | `Accurate_lateral_passes_percentage` | not referenced | |
| `Short_medium_passes_per_90` | `Short_medium_passes_per_90` | `"Short / medium passes per 90"` | Note the spaces around the slash in the script's internal name. |
| `Accurate_short_medium_passes_percentage` | `Accurate_short_medium_passes_percentage` | `"Accurate short / medium passes, %"` | |
| `Long_passes_per_90` | `Long_passes_per_90` | `"Long passes per 90"` | |
| `Accurate_long_passes_percentage` | `Accurate_long_passes_percentage` | `"Accurate long passes, %"` | |
| `Average_pass_length_m` | `Average_pass_length_m` | not referenced | |
| `Average_long_pass_length_m` | `Average_long_pass_length_m` | `"Average long pass length, m"` | |
| `xA_per_90` | `xA_per_90` | `"xA per 90"` | |
| `Shot_assists_per_90` | `Shot_assists_per_90` | `"Shot assists per 90"` | |
| `Second_assists_per_90` | `Second_assists_per_90` | not referenced | |
| `Third_assists_per_90` | `Third_assists_per_90` | not referenced | |
| `Smart_passes_per_90` | `Smart_passes_per_90` | `"Smart passes per 90"` | |
| `Accurate_smart_passes_percentage` | `Accurate_smart_passes_percentage` | `"Accurate smart passes, %"` | |
| `Key_passes_per_90` | `Key_passes_per_90` | `"Key passes per 90"` | |
| `Passes_to_final_third_per_90` | `Passes_to_final_third_per_90` | `"Passes to final third per 90"` | |
| `Accurate_passes_to_final_third_percentage` | `Accurate_passes_to_final_third_percentage` | `"Accurate passes to final third, %"` | |
| `Passes_to_penalty_area_per_90` | `Passes_to_penalty_area_per_90` | `"Passes to penalty area per 90"` | |
| `Accurate_passes_to_penalty_area_percentage` | `Accurate_passes_to_penalty_area_percentage` | `"Accurate passes to penalty area, %"` | |
| `Through_passes_per_90` | `Through_passes_per_90` | `"Through passes per 90"` | |
| `Accurate_through_passes_percentage` | `Accurate_through_passes_percentage` | `"Accurate through passes, %"` | |
| `Deep_completions_per_90` | `Deep_completions_per_90` | `"Deep completions per 90"` | |
| `Deep_completed_crosses_per_90` | `Deep_completed_crosses_per_90` | `"Deep completed crosses per 90"` | |
| `Progressive_passes_per_90` | `Progressive_passes_per_90` | `"Progressive passes per 90"` | |
| `Accurate_progressive_passes_percentage` | `Accurate_progressive_passes_percentage` | `"Accurate progressive passes, %"` | |
| `Conceded_goals` | `Conceded_goals` | not referenced | |
| `Conceded_goals_per_90` | `Conceded_goals_per_90` | `"Conceded goals per 90"` | |
| `Shots_against` | `Shots_against` | not referenced | |
| `Shots_against_per_90` | `Shots_against_per_90` | `"Shots against per 90"` | |
| `Clean_sheets` | `Clean_sheets` | `"Clean sheets"` | |
| `Save_rate_percentage` | `Save_rate_percentage` | `"Save rate, %"` | |
| `xG_against` | `xG_against` | not referenced | |
| `xG_against_per_90` | `xG_against_per_90` | `"xG against per 90"` | |
| `Prevented_goals` | `Prevented_goals` | not referenced | |
| `Prevented_goals_per_90` | `Prevented_goals_per_90` | `"Prevented goals per 90"` | |
| `Back_passes_received_as_GK_per_90` | `Back_passes_received_as_GK_per_90` | `"Back passes received as GK per 90"` | GK-only stat; null for outfield players. |
| `Exits_per_90` | `Exits_per_90` | `"Exits per 90"` | GK-only stat; null for outfield players. |
| `Aerial_duels_per_90` (2nd occurrence) | see note | `"Aerial duels per 90"` | This is the GK-block duplicate of the row already documented above — see that row's note. Do not treat this as a second Django field. |
| `Free_kicks_per_90` | `Free_kicks_per_90` | not referenced | |
| `Direct_free_kicks_per_90` | `Direct_free_kicks_per_90` | not referenced | |
| `Direct_free_kicks_on_target_percentage` | `Direct_free_kicks_on_target_percentage` | not referenced | |
| `Corners_per_90` | `Corners_per_90` | not referenced | |
| `Penalties_taken` | `Penalties_taken` | not referenced | |
| `Penalty_conversion_percentage` | `Penalty_conversion_percentage` | not referenced | |

---

## 2. Player.extended_stats JSONField (14 movement/physical columns)

These 14 columns are the "movement/physical tracking" block — columns 122–135 of Players.csv. They
are **not valid Python/Django identifiers as-is** (slashes, parentheses, Unicode `²`, a literal
`_DOT_` sanitization token) and, per direct grep verification against the full 15,747-line
`impact_model_v4.1.py`, **none of them are referenced anywhere in the scoring script.**

**Modeling decision:** put this entire block into a single `Player.extended_stats` `JSONField`,
keyed by the **original CSV column-name string verbatim** (valid as a JSON key even though not a
valid Python identifier). Do not sanitize these into 14 individual model fields — no scoring code
will ever read them individually, so the field-per-column cost buys nothing. Add a `GinIndex` only
if a future phase needs to query into this JSON (not needed in Phase 1).

The 14 keys (verbatim CSV column names):

```
Total_Distance_per_90
Running_Distance_per_90_(15-20_km/h)
HSR_Distance_per_90_(20-25_km/h)
Sprinting_Distance_per_90_(+25_km/h)
HI_Distance_per_90_(+20_km/h)
Meter/Min
Max_Speed_(km/h)
Count_Medium_Acceleration_per_90_(1_DOT_5_m/s²_to_3_m/s²)
Count_High_Acceleration_per_90_(+3_m/s²)
Count_Medium_Deceleration_per_90_(-1_DOT_5_m/s²_to_-3_m/s²)
Count_High_Deceleration_per_90_(-3_m/s²)
Count_HSR_per_90_(20-25_km/h)
Count_Sprint_per_90_(+25_km/h)
Count_HI_per_90_(+20_km/h)
```

None of these are referenced by `impact_model_v4.1.py`; none are sanitized into individual model
fields; all 14 are stored as-is, keyed by their original CSV column-name string, inside
`Player.extended_stats`.

---

## 3. Club fields (derived — no source file)

The legacy dataset has no dedicated Clubs file. Club identity only exists as a string field on
Player/Playstyles records. Per CONTEXT.md's locked "Club Data Gap" decisions:

| Club field | Source | Notes |
|---|---|---|
| `name` | Union of `Players.csv.Team_within_selected_timeframe` (1,059 distinct, zero nulls) and `Playstyles.csv.Team` (239 distinct, fully overlapping except one already-consistent spelling variant: `Borussia M_gladbach`) | Unique key for `Club`. Authoritative "union of all clubs" source is Players.csv — Playstyles.csv adds nothing new to the name universe, just playing-style data for a subset. |
| `league` | Mode of `League` per `Team_within_selected_timeframe`, alphabetical tie-break | 525 of 1,059 clubs (49.6%) have more than one distinct `League` value across their player rows — this is common, not a rare edge case. Every tie-break must be logged in the import report since roughly half of all clubs hit this path. |
| `playing_style_control_possession`, `playing_style_gegenpressing`, `playing_style_direct_play`, `playing_style_defensive_counter_attack`, `playing_style_tiki_taka`, `playing_style_counter_attack`, `playing_style_wing_play`, `playing_style_low_block` | `Playstyles.csv` (8 numeric columns: `Control_Possession`, `Gegenpressing`, `Direct_Play`, `Defensive_Counter_Attack`, `Tiki_Taka`, `Counter_Attack`, `Wing_Play`, `Low_Block`) | Model as 8 individual nullable `FloatField`s, not a JSONField — small, fixed-shape, and Phase 4's compatibility-score port needs to read them as typed columns. Only 239/1,059 clubs (22.6%) have Playstyles.csv coverage — **expect ~77% of `Club` rows to have null playing-style fields; this is correct, not a data quality failure.** The import report must state this coverage rate explicitly. |
| `manager` | *(no source)* | Nullable, left empty for v1. Backfill later if/when a source is found. |
| `formation` | *(no source)* | Nullable, left empty for v1. Same treatment as `manager`. |
| `country` | *(no source)* | Nullable, left empty for v1. Same treatment as `manager`. |
| `squad_size` | *(not migrated)* | **Not** a migration-time field. Treated as a live/denormalized count of currently-linked Player records — belongs to the CRUD/Squad Planner phases (7/11), not import logic. Do not add this as a stored, import-populated column in Phase 1. |

---

## 4. Transfer fields (transferdata final.csv)

**Critical trap, verified against real data, not a hypothesis:** the `UniqueID` column in
`transferdata final.csv` is a **Club identifier, not a Player identifier**, despite sharing an
identical column name with Players.csv's player-level `UniqueID`. Evidence: 47,252 rows but only
207 distinct `UniqueID` values; every distinct `UniqueID` maps to exactly one `Club` value and vice
versa (a clean 1:1 bijection). Concrete proof: `UniqueID=12` appears in 788 rows, **all** with
`Club="Atalanta"`, spanning 192 different players. **`transferdata.UniqueID` must never be joined
against `Player.UniqueID` / `Player.unique_id`.** A naive import that joins on `UniqueID` because
the column names match will "succeed" (every value plausibly exists as *some* player's UniqueID)
but silently attach every transfer record to the wrong player entirely.

| CSV column | Django field | Notes |
|---|---|---|
| `UniqueID` | *(resolves `Transfer.club`, via the `Club`/`UniqueID` pair below — never a player key)* | 207 distinct values, 1:1 with `Club`. Genuinely useful as a stable natural key for Club-identity confirmation, but semantically a Club ID here, not a Player ID. |
| `Club` | `club` (FK to `Club`) | Verified clean match against the Club universe built in the Club-derivation step (§3) — `transferdata.Club`'s 207 distinct values are a strict subset of the 1,059-club Players.csv universe. |
| `Player` | *(resolves `Transfer.player`, nullable, best-effort)* | No reliable player-ID column exists in this file at all — only this name string. Resolve via best-effort name matching against `Player.Player`; accept it will sometimes be null/ambiguous (common names, transfer-time vs. current-roster spelling differences). Never treat an unmatched row as an error — log it, keep the row. |
| `Age` | `Age` (on `Transfer`, distinct field from `Player.Age`) | Age **at transfer time**, not current age. Do not conflate with `Player.Age` — these represent different points in time. |
| `Nationality` | `Nationality` | |
| `Position` | `Position` | |
| `Short_Position` | `Short_Position` | |
| `Market_Value` | `Market_Value` (on `Transfer`, distinct field from `Player.Market_value`) | Market value **at transfer time**. Do not conflate with `Player.Market_value` — same at-transfer-time-vs-current distinction as `Age` above. |
| `Dealing_Club` | `dealing_club` (plain `CharField`, **not** an FK) | 2,909 distinct counterparty values — a much larger, mostly-foreign/lower-league universe that only partially overlaps the 1,059-club Players.csv universe. Creating stub `Club` rows for all of these would pollute the Club table with entities that have no roster/playing-style data and no product surface. Keep as a plain string field. |
| `Dealing_Country` | `Dealing_Country` | |
| `Fee` | `Fee` | |
| `Movement` | `Movement` | `arrival`/`departure`, roughly balanced (22,429 / 24,823). |
| `Window` | `Window` | e.g. `Summer`. |
| `League_Name` | `League_Name` | |
| `Year` | `Year` | |
| `is_loan` | `is_loan` | Stored as `TRUE`/`FALSE` string in the CSV — coerce to a proper `BooleanField` at import time. |
| `loan_status` | `loan_status` | |

**Idempotent upsert key:** no single natural unique column exists for a transfer *event* (confirmed:
`UniqueID` here means Club, not a transfer-event ID). Use a composite unique constraint over
`(Player, Year, Window, Movement, Club, Dealing_Club)` — all six columns are always populated (zero
nulls across all 47,252 rows in the null-count audit), and together they identify one real transfer
event.

---

## 5. Known mismatches resolved (from CONCERNS.md)

Restating each mismatch CONCERNS.md's §"Known Issue: Missing Field Mapping" and
§"Critical: Field Naming Standardization Required" flagged, and how this document resolves it:

- **"CSV has `Team_within_selected_timeframe` which is renamed in impact_model to just `Team`"** —
  Resolved in §1a: `Team_within_selected_timeframe` is the authoritative source for the `Player.club`
  FK (verified via the script's own internal rename). Raw `Team` is dropped, not carried forward as
  a second field.
- **"Mongoose schema has both `Team` and `Team_within_selected_timeframe` fields"** — Not repeated in
  Django. Only one FK field (`club`) exists on `Player`.
- **"No documented mapping between CSV columns → MongoDB fields → API response fields"** — This
  document is that mapping for the CSV → Django leg (the MongoDB/legacy-API leg is being retired,
  not carried forward per PROJECT.md's migration scope).
- **"Market_value" (snake_case in CSV) vs "Market Value" (spaces in impact_model expectations)** —
  Resolved in §1b: Django field is `Market_value` (mirrors CSV); the script's internal name is
  `"Market value"` (space, lowercase `value`) — captured explicitly in the mapping table so Phase 3
  reads the right literal string, not a guessed variant.
- **"Position field: Multiple variants in CSV (Positions, Main_Position, Position)"** — Resolved in
  §1a: all three are distinct, real Django fields with distinct purposes (`Positions` = full list,
  `Main_Position` = position group used for role/compatibility joins, `Position` = fine-grained
  single label). None of the three collapse into the others.
- **"Minutes field: Called 'Minutes', 'Minutes_played', or alternates in different sources"** — The
  CSV column is `Minutes_played`; the script's internal name is `"Minutes played"` (space). Captured
  in §1b. The script also has its own defensive fallback logic for a bare `"Minutes"` column when
  run against other (non-CSV) inputs — not relevant to this CSV-driven import, noted here only so a
  future reader isn't confused by seeing both names in the script.
- **"Attributes: Separate fields in MongoDB/CSV vs jsonb in Supabase"** — Not applicable to this
  migration: Players.csv already has 121 separate, named stat columns (§1b) plus one legitimately
  variable-shape block (§2's 14 movement columns). There is no single "attributes" blob to reconcile
  — the Django schema keeps the 121 as typed columns and only the genuinely non-identifier, unused-
  by-scoring 14 columns go into `JSONField`, consistent with STACK.md's "don't dump everything into
  jsonb" guidance.
- **New finding, not in CONCERNS.md but resolved here anyway:** `transferdata final.csv`'s
  `UniqueID` column is a Club ID, not a Player ID, despite the identical column name to Players.csv's
  player-level `UniqueID` — see §4. This is the single highest-risk trap in Phase 1 and is
  explicitly called out so Phase 1's import command never joins these two columns as if they were
  the same kind of key.
- **New finding, not in CONCERNS.md but resolved here anyway:** `Aerial_duels_per_90` appears twice
  in the raw Players.csv header (outfield block and GK block) — see the note in §1b. Import code
  must read both raw positions explicitly rather than relying on pandas' auto-suffixing behavior.

---

*Phase: 01-data-foundation*
*Deliverable: FIELD_MAPPING.md (DATA-05 prerequisite)*
*Compiled: 2026-07-20*
