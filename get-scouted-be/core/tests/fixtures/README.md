# Fixture CSVs

Small, hand-seeded stand-ins for the real dataset CSVs under `API-Updated-/dataset/`.
Each file starts with the EXACT header row copied from its real counterpart, followed
by 10-20 rows deliberately seeded with the known data-quality edge cases the import
tasks must handle. Import unit tests (`pytest -x -q -k "not integration"`) run
against these files via the `fixture_dir` fixture in `core/tests/conftest.py`.

## players_sample.csv

Mirrors `API-Updated-/dataset/Players.csv` (135-column header, only the columns
below carry meaningful seeded values; the rest are blank).

| UniqueID | Row demonstrates |
|----------|------------------|
| 1, 2, 12 | Manchester City players with League = "Premier League (England)" |
| 4 | Manchester City player with League = "La Liga (Spain)" -- ambiguous club/league combination across rows for the SAME club (Manchester City appears with 2 different League values across 4 rows), exercising mode-derivation + tie-break logic for `Club.league` |
| 2 | Blank `Market_value` |
| 7 | Blank `Market_value` (second case, different club) |
| 4 | `Market_value` = `0` |
| 3 | Blank `Contract_expires` |
| 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 81 | Populated `Contract_expires` in `DD/MM/YYYY` format (e.g. `30/06/2027`) |
| 7 | `Foot` = `"0"` (dirty/placeholder value) |
| 5 | `Foot` = `"unknown"` |
| 13 | `Foot` = `"both"` |
| 6, 14 | `Position` = `GK` -- used to assert goalkeepers get zero role/compatibility rows by design |
| 1, 2, 5, 7 | Non-GK `CB` rows whose `UniqueID` also appears in `positions_CB_sample.csv` and `compatibility_CB_sample.csv` |
| 81 | **The cross-file trap**: `UniqueID = 81` here is a genuine player ("D. Solanke", Tottenham Hotspur). The SAME `UniqueID = 81` value appears in `transferdata_sample.csv` as a **club-scoped** id (Genk) mapping to several unrelated players -- the importer must not link Genk's transfer rows to this player. |

All `UniqueID` values in this file are unique (player-scoped).

## playstyles_sample.csv

Mirrors `API-Updated-/dataset/Playstyles.csv` (`Team,UniqueID,<8 style floats>`).
Rows exist for only 2 of the 5 clubs referenced in `players_sample.csv`
(Manchester City, Arsenal) -- Real Madrid, Bayern München and Tottenham Hotspur are
deliberately absent, exercising the real dataset's ~77% playing-style-null club
coverage gap. Note the `UniqueID` in this file is a team/style-row id, unrelated to
player `UniqueID` -- the join to `players_sample.csv` is by `Team` name.

## positions_CB_sample.csv

Mirrors `API-Updated-/dataset/Positions/CB with league.csv`. One row per non-GK
CB `UniqueID` present in `players_sample.csv`: `1`, `2`, `5`, `7`, each with the 5
CB role float columns (`Wide_Centre-Back_(LCB)`, `No_Nonsense_Centre_Back`,
`Ball_Playing_Defender`, `Wide_Centre_Back_(RCB)`, `Libero`) populated.

## compatibility_CB_sample.csv

Mirrors `API-Updated-/dataset/Compatability Scores/CS_CB_25.csv`, trimmed to 6
club columns (real file has 212). Header: `UniqueID,Position,Manchester
City,Arsenal,Real Madrid,Bayern München,AGF,St_DOT_ Louis City`.

- `Manchester City`, `Arsenal`, `Real Madrid`, `Bayern München` match `Club` values
  in `players_sample.csv` exactly -- resolvable compatibility columns.
- `St_DOT_ Louis City` is **deliberately unresolvable** (no matching `Club` in
  `players_sample.csv`) -- exercises the `club=null` / `club_name_raw` fallback path.
- `AGF` is a real-dataset club name that also does not resolve against
  `players_sample.csv`'s clubs, providing a second unresolved case.
- One row per CB `UniqueID` from `players_sample.csv`: `1`, `2`, `5`, `7`.

## transferdata_sample.csv (THE TRAP FIXTURE)

Mirrors `API-Updated-/dataset/transferdata final.csv`. 12 rows.

| UniqueID | Row(s) demonstrate |
|----------|---------------------|
| 81 (4 rows) | `UniqueID` is **club-scoped**, not player-scoped: all 4 rows are Genk transfers involving 3 DIFFERENT players (Leandro Trossard appears twice -- arrival and departure -- plus Mike Trésor and Joseph Paintsil, all sharing `UniqueID = 81`). This mirrors the real dataset exactly (Genk really is `UniqueID = 81` in `transferdata final.csv`). Critically, `UniqueID = 81` ALSO exists as a genuine player in `players_sample.csv` (D. Solanke, Tottenham Hotspur) -- a test must assert the importer does NOT link Genk's transfer rows to that player. |
| 109 (2 rows), 235 (2 rows), 300 (2 rows) | Additional club-scoped `UniqueID`s, each with 2+ rows for different players, reinforcing the same-`UniqueID`-different-`Player` pattern |
| 109, 235 | `is_loan = "TRUE"` rows with populated `loan_status` ("Loan transfer") |
| 81 (arrival + departure rows), 235, 300 | Both `Movement = "arrival"` and `Movement = "departure"` present |
| Several rows (`Dealing_Club = "Independent FC"`) | A `Dealing_Club` counterparty that never appears as a `Club` value anywhere in this file -- exercises the case where the dealing-club side cannot be resolved to a known `Club` |
| 400 | `Player = "Random Player C"` does not appear anywhere in `players_sample.csv` -- the **unmatched-player-kept case**: the importer must still create this transfer row with `player = None` rather than dropping it |
| All rows | Populated `Year`, `Window`, `Movement`, `Fee` |
