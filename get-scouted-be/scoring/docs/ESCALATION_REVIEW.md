# Escalation Review: Functions With More Than 2 Definitions

Per `03-CONTEXT.md`'s locked Duplicate-Function Resolution Policy, any function name with
**more than 2 definitions** in `impact_model_v4.1.py` must be escalated to the user for
explicit review — the mechanical last-wins rule (used for the other 18 duplicated names,
see `DUPLICATE_FUNCTIONS.md`) is NOT applied here without sign-off.

Two names hit this trigger, each with exactly 4 definitions:

- `prepare_team_and_transfer_signal` — lines 7041, 11427, 11702, 12192
- `player_transfer_history` — lines 7093, 11488, 11870, 12329

This document extracts all four bodies of each, summarizes how they diverge, and gives a
non-binding recommendation. The final authoritative choice for each function — made by the
user, not inferred mechanically — is recorded in the `DECISION:`/`REASON:` fields at the end
of each section. This decision feeds `DUPLICATE_FUNCTIONS.md` / the master curation map
(Plan 07) alongside the 18 mechanically-resolved names.

---

## Section A — `prepare_team_and_transfer_signal` (4 defs: 7041 / 11427 / 11702 / 12192)

**Verified fact:** all four definitions share an identical first ~9 lines (build `Team_Final`
via `Team within selected timeframe` → `Team` fallback) before diverging in how they handle
a missing `Minutes` column and how they build the sort key. Body lengths (`def` line to the
line before the next top-level `def`): def #1 = 46 lines, def #2 = 55 lines, def #3 = 54
lines, def #4 = 60 lines (def #2/#4 include extra inline comments not present in #1/#3,
which inflates raw line count without adding logic).

### Def #1 — line 7041

```python
def prepare_team_and_transfer_signal(df):
    work_df = df.copy()

    if "Team within selected timeframe" not in work_df.columns:
        work_df["Team within selected timeframe"] = np.nan
    if "Team" not in work_df.columns:
        work_df["Team"] = np.nan

    work_df["Team_Final"] = work_df["Team within selected timeframe"].fillna(work_df["Team"])

    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break
    if "Minutes" not in work_df.columns:
        work_df["Minutes"] = 0

    if "Main_Position" not in work_df.columns and "Position" in work_df.columns:
        work_df["Main_Position"] = work_df["Position"]

    def _season_sort(s):
        try:
            return int(str(s).split("-")[0].split("/")[0])
        except:
            return 0

    work_df["_season_sort"] = work_df["Season"].apply(_season_sort)

    work_df = work_df.sort_values(["Player", "_season_sort", "Minutes"], ascending=[True, True, False])
    work_df = work_df.drop_duplicates(subset=["Player", "Season"], keep="first").copy()

    work_df = work_df.sort_values(["Player", "_season_sort"])
    work_df["Previous_Season_Team"] = work_df.groupby("Player")["Team_Final"].shift(1)

    work_df["Transfer_Signal"] = np.where(
        (work_df["Previous_Season_Team"].notna()) &
        (work_df["Team_Final"].notna()) &
        (work_df["Previous_Season_Team"] != work_df["Team_Final"]),
        1,
        0
    )

    work_df["Transfer_Flag"] = np.where(work_df["Transfer_Signal"] == 1, "Moved", "Same Club")

    return work_df
```

### Def #2 — line 11427

```python
def prepare_team_and_transfer_signal(df):
    work_df = df.copy()

    if "Team within selected timeframe" not in work_df.columns:
        work_df["Team within selected timeframe"] = np.nan
    if "Team" not in work_df.columns:
        work_df["Team"] = np.nan

    # main team field
    work_df["Team_Final"] = work_df["Team within selected timeframe"].fillna(work_df["Team"])

    # minutes fallback
    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break

    # season sort
    def _season_sort(s):
        try:
            return int(str(s).split("-")[0].split("/")[0])
        except:
            return 0

    work_df["_season_sort"] = work_df["Season"].apply(_season_sort)

    # keep only the best / main row per player-season
    sort_cols = ["Player", "_season_sort"]
    ascending = [True, True]

    if "Minutes" in work_df.columns:
        sort_cols.append("Minutes")
        ascending.append(False)

    work_df = work_df.sort_values(sort_cols, ascending=ascending)

    # one row per player-season
    work_df = work_df.drop_duplicates(subset=["Player", "Season"], keep="first").copy()

    # now compute previous season team
    work_df = work_df.sort_values(["Player", "_season_sort"])
    work_df["Previous_Season_Team"] = work_df.groupby("Player")["Team_Final"].shift(1)

    work_df["Transfer_Signal"] = np.where(
        (work_df["Previous_Season_Team"].notna()) &
        (work_df["Team_Final"].notna()) &
        (work_df["Previous_Season_Team"] != work_df["Team_Final"]),
        1,
        0
    )

    work_df["Transfer_Flag"] = np.where(work_df["Transfer_Signal"] == 1, "Moved", "Same Club")

    return work_df
```

**Diff vs #1:** (a) DOES NOT add the `if "Minutes" not in work_df.columns: work_df["Minutes"] = 0`
fallback — if `Minutes` is genuinely absent after the alt-column check, this version leaves it
missing rather than silently zero-filling it. (b) drops the `Main_Position` fallback entirely.
(c) builds `sort_cols`/`ascending` conditionally (`Minutes` only appended if the column exists)
instead of hardcoding `["Player", "_season_sort", "Minutes"]` — this is defensive against a
`KeyError` if `Minutes` is still absent, which is only possible because (a) removed the 0-fill
safety net. This is the functional outlier among the four.

### Def #3 — line 11702

```python
def prepare_team_and_transfer_signal(df):
    work_df = df.copy()

    if "Team within selected timeframe" not in work_df.columns:
        work_df["Team within selected timeframe"] = np.nan
    if "Team" not in work_df.columns:
        work_df["Team"] = np.nan

    work_df["Team_Final"] = work_df["Team within selected timeframe"].fillna(work_df["Team"])

    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break

    if "Minutes" not in work_df.columns:
        work_df["Minutes"] = 0

    if "Main_Position" not in work_df.columns and "Position" in work_df.columns:
        work_df["Main_Position"] = work_df["Position"]

    def _season_sort(s):
        try:
            return int(str(s).split("-")[0].split("/")[0])
        except:
            return 0

    work_df["_season_sort"] = work_df["Season"].apply(_season_sort)

    sort_cols = ["Player", "_season_sort", "Minutes"]
    ascending = [True, True, False]

    work_df = work_df.sort_values(sort_cols, ascending=ascending)
    work_df = work_df.drop_duplicates(subset=["Player", "Season"], keep="first").copy()

    work_df = work_df.sort_values(["Player", "_season_sort"])
    work_df["Previous_Season_Team"] = work_df.groupby("Player")["Team_Final"].shift(1)

    work_df["Transfer_Signal"] = np.where(
        (work_df["Previous_Season_Team"].notna()) &
        (work_df["Team_Final"].notna()) &
        (work_df["Previous_Season_Team"] != work_df["Team_Final"]),
        1,
        0
    )

    work_df["Transfer_Flag"] = np.where(
        work_df["Transfer_Signal"] == 1,
        "Moved",
        "Same Club"
    )

    return work_df
```

**Diff vs #1:** functionally identical to #1 (re-adds the `Minutes` → 0 fallback and the
`Main_Position` fallback that #2 had dropped; `sort_cols`/`ascending` are hardcoded again
instead of #2's conditional build). Only cosmetic differences from #1 (assignment of
`sort_cols`/`ascending` to named variables before calling `.sort_values`, and a multi-line
`np.where` call for `Transfer_Flag`).

### Def #4 — line 12192

```python
def prepare_team_and_transfer_signal(df):
    work_df = df.copy()

    if "Team within selected timeframe" not in work_df.columns:
        work_df["Team within selected timeframe"] = np.nan
    if "Team" not in work_df.columns:
        work_df["Team"] = np.nan

    # Main team field
    work_df["Team_Final"] = work_df["Team within selected timeframe"].fillna(work_df["Team"])

    # Minutes fallback
    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break

    if "Minutes" not in work_df.columns:
        work_df["Minutes"] = 0

    # Position fallback
    if "Main_Position" not in work_df.columns and "Position" in work_df.columns:
        work_df["Main_Position"] = work_df["Position"]

    # Season sort helper
    def _season_sort(s):
        try:
            return int(str(s).split("-")[0].split("/")[0])
        except:
            return 0

    work_df["_season_sort"] = work_df["Season"].apply(_season_sort)

    # Keep best/main row per player-season
    work_df = work_df.sort_values(
        ["Player", "_season_sort", "Minutes"],
        ascending=[True, True, False]
    )
    work_df = work_df.drop_duplicates(subset=["Player", "Season"], keep="first").copy()

    # Previous season team
    work_df = work_df.sort_values(["Player", "_season_sort"])
    work_df["Previous_Season_Team"] = work_df.groupby("Player")["Team_Final"].shift(1)

    work_df["Transfer_Signal"] = np.where(
        (work_df["Previous_Season_Team"].notna()) &
        (work_df["Team_Final"].notna()) &
        (work_df["Previous_Season_Team"] != work_df["Team_Final"]),
        1,
        0
    )

    work_df["Transfer_Flag"] = np.where(
        work_df["Transfer_Signal"] == 1,
        "Moved",
        "Same Club"
    )

    return work_df
```

**Diff vs #1/#3:** logic-identical to #1 and #3 (has both the `Minutes` → 0 fallback and the
`Main_Position` fallback; hardcoded sort key). Only difference from #3 is added explanatory
comments and inlining `sort_cols`/`ascending` directly into the `.sort_values(...)` call
instead of naming them first. No behavioral change from #1/#3.

**Claude's recommendation (non-binding):** last-wins would pick **def #4 (12192)**. Defs #1,
#3, and #4 are all functionally identical (differ only in comments/formatting) — def #2
(11427) is the sole functional outlier, having removed the `Minutes` → 0 silent-default
fallback and the `Main_Position` fallback that the other three share. Because def #4 is
functionally indistinguishable from #1 and #3 (the three-way majority) and represents the
most-recently-edited, most-commented converged form, last-wins looks like a reasonable pick
here — it is not "genuinely different," it's the same logic restated with comments. **However:**
def #4 (like #1 and #3) still contains the `Minutes` → 0 silent default, which is exactly the
bug pattern `03-CONTEXT.md`'s narrow fix-threshold targets (missing data silently defaulted to
0, distorting downstream scores). Whichever version is chosen as authoritative, this specific
default should be corrected during the Phase 4 port per the locked "fix, don't faithfully
preserve" policy for this bug class — that correction is independent of which duplicate is
picked as the base.

DECISION: 12192
REASON: Matches the 3-way functional majority (7041/11702/12192, identical logic differing only in comments/formatting), consistent with CONTEXT.md's locked default policy (last-wins + export-column cross-check). The Minutes->0 silent default this version carries is a known instance of the CONCERNS.md-flagged bug class already being corrected elsewhere in this phase via the fix-threshold mechanism (Plans 04/05 both applied it) — so it will be handled there rather than by preferring an unverified minority-of-1 outlier.

---

## Section B — `player_transfer_history` (4 defs: 7093 / 11488 / 11870 / 12329)

**Verified fact:** body lengths (`def` line to the line before the next top-level `def`):
def #1 = 51 lines, def #2 = 83 lines, def #3 = 66 lines, def #4 = 65 lines. Def #2 (11488)
uses a multi-line signature:

```python
def player_transfer_history(
    df,
    player_name,
    season=None,
    team=None
):
```

versus the single-line `def player_transfer_history(df, player_name, season=None, team=None):`
used by the other three — an initial signal that #2 might be a more substantially reworked
version. On inspection, most of #2's extra ~30 lines come from the multi-line signature (+5
lines), an added docstring block (+7 lines), and reformatting the `cols` list to one-item-per-
line (+13 lines) — not from added logic.

### Def #1 — line 7093

```python
def player_transfer_history(df, player_name, season=None, team=None):
    work_df = df.copy()

    if "Team_Final" not in work_df.columns:
        work_df = prepare_team_and_transfer_signal(work_df)

    if "Player Impact" not in work_df.columns:
        work_df = add_player_impact(work_df)

    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break
    if "Minutes" not in work_df.columns:
        work_df["Minutes"] = 0

    if "Main_Position" not in work_df.columns and "Position" in work_df.columns:
        work_df["Main_Position"] = work_df["Position"]

    out = work_df[
        work_df["Player"].astype(str).str.lower().str.strip() == player_name.lower().strip()
    ].copy()

    if team:
        out = out[
            out["Team_Final"].astype(str).str.lower().str.strip() == team.lower().strip()
        ]

    if season:
        if isinstance(season, list):
            out = out[out["Season"].isin(season)]
        else:
            out = out[out["Season"] == season]

    if out.empty:
        print(f"❌ No data for {player_name}")
        return pd.DataFrame()

    cols = [
        "Season", "Player", "Team_Final", "Previous_Season_Team", "Transfer_Flag",
        "League", "Main_Position", "Age", "Minutes",
        "Player Score", "Player Impact", "Player Impact Raw",
        "Player Impact Positive", "Player Impact Negative", "Impact Reliability"
    ]
    cols = [c for c in cols if c in out.columns]

    out = out[cols].copy()
    out = out.sort_values(["Season", "Minutes"], ascending=[True, False])

    return out.reset_index(drop=True)
```

### Def #2 — line 11488

```python
def player_transfer_history(
    df,
    player_name,
    season=None,
    team=None
):
    """
    Full player history with:
    - Team_Final
    - Previous team
    - Transfer signal
    - Impact
    """

    work_df = df.copy()

    # Ensure transfer logic exists
    if "Team_Final" not in work_df.columns:
        work_df = prepare_team_and_transfer_signal(work_df)

    # Ensure impact exists
    if "Player Impact" not in work_df.columns:
        work_df = add_player_impact(work_df)

    # Minutes fallback
    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break

    # Position fallback
    if "Main_Position" not in work_df.columns and "Position" in work_df.columns:
        work_df["Main_Position"] = work_df["Position"]

    # Filter player
    out = work_df[
        work_df["Player"].astype(str).str.lower().str.strip()
        == player_name.lower().strip()
    ].copy()

    if team:
        out = out[
            out["Team_Final"].astype(str).str.lower().str.strip()
            == team.lower().strip()
        ]

    if season:
        if isinstance(season, list):
            out = out[out["Season"].isin(season)]
        else:
            out = out[out["Season"] == season]

    if out.empty:
        print(f"❌ No data for {player_name}")
        return pd.DataFrame()

    cols = [
        "Season",
        "Player",
        "Team_Final",
        "Previous_Season_Team",
        "Transfer_Flag",
        "League",
        "Main_Position",
        "Age",
        "Minutes",
        "Player Score",
        "Player Impact",
        "Player Impact Raw",
        "Player Impact Positive",
        "Player Impact Negative",
        "Impact Reliability"
    ]

    cols = [c for c in cols if c in out.columns]

    out = out[cols].copy()

    # Sort
    out = out.sort_values(["Season", "Minutes"], ascending=[True, False])

    return out.reset_index(drop=True)
```

**Diff vs #1:** DOES NOT include the final `if "Minutes" not in work_df.columns: work_df["Minutes"] = 0`
fallback (same divergence pattern as `prepare_team_and_transfer_signal` def #2 at 11427 — this
confirms both "second" definitions come from the same editing pass that temporarily dropped the
0-default). Otherwise identical filtering/column-selection/sort logic to #1; the extra length is
signature style + docstring + list formatting, not new behavior.

### Def #3 — line 11870

```python
def player_transfer_history(df, player_name, season=None, team=None):
    work_df = df.copy()

    if "Team_Final" not in work_df.columns:
        work_df = prepare_team_and_transfer_signal(work_df)

    if "Player Impact" not in work_df.columns:
        work_df = add_player_impact(work_df)

    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break

    if "Minutes" not in work_df.columns:
        work_df["Minutes"] = 0

    if "Main_Position" not in work_df.columns and "Position" in work_df.columns:
        work_df["Main_Position"] = work_df["Position"]

    out = work_df[
        work_df["Player"].astype(str).str.lower().str.strip()
        == player_name.lower().strip()
    ].copy()

    if team:
        out = out[
            out["Team_Final"].astype(str).str.lower().str.strip()
            == team.lower().strip()
        ]

    if season:
        if isinstance(season, list):
            out = out[out["Season"].isin(season)]
        else:
            out = out[out["Season"] == season]

    if out.empty:
        print(f"❌ No data for {player_name}")
        return pd.DataFrame()

    cols = [
        "Season",
        "Player",
        "Team_Final",
        "Previous_Season_Team",
        "Transfer_Flag",
        "League",
        "Main_Position",
        "Age",
        "Minutes",
        "Player Score",
        "Player Impact",
        "Player Impact Raw",
        "Player Impact Positive",
        "Player Impact Negative",
        "Impact Reliability"
    ]

    cols = [c for c in cols if c in out.columns]
    out = out[cols].copy()

    out = out.sort_values(["Season", "Minutes"], ascending=[True, False])

    return out.reset_index(drop=True)
```

**Diff vs #1:** functionally identical to #1 (re-adds the `Minutes` → 0 fallback that #2
dropped); only cosmetic difference is the `cols` list reformatted one-per-line (matching #2's
style) rather than #1's packed multi-per-line style.

### Def #4 — line 12329

```python
def player_transfer_history(df, player_name, season=None, team=None):
    work_df = df.copy()

    if "Team_Final" not in work_df.columns:
        work_df = prepare_team_and_transfer_signal(work_df)

    if "Player Impact" not in work_df.columns:
        work_df = add_player_impact(work_df)

    if "Minutes" not in work_df.columns:
        for alt in ["Minutes played", "Mins played", "Time Played"]:
            if alt in work_df.columns:
                work_df["Minutes"] = work_df[alt]
                break

    if "Minutes" not in work_df.columns:
        work_df["Minutes"] = 0

    if "Main_Position" not in work_df.columns and "Position" in work_df.columns:
        work_df["Main_Position"] = work_df["Position"]

    out = work_df[
        work_df["Player"].astype(str).str.lower().str.strip()
        == player_name.lower().strip()
    ].copy()

    if team:
        out = out[
            out["Team_Final"].astype(str).str.lower().str.strip()
            == team.lower().strip()
        ]

    if season:
        if isinstance(season, list):
            out = out[out["Season"].isin(season)]
        else:
            out = out[out["Season"] == season]

    if out.empty:
        print(f"❌ No data for {player_name}")
        return pd.DataFrame()

    cols = [
        "Season",
        "Player",
        "Team_Final",
        "Previous_Season_Team",
        "Transfer_Flag",
        "League",
        "Main_Position",
        "Age",
        "Minutes",
        "Player Score",
        "Player Impact",
        "Player Impact Raw",
        "Player Impact Positive",
        "Player Impact Negative",
        "Impact Reliability"
    ]

    cols = [c for c in cols if c in out.columns]
    out = out[cols].copy()
    out = out.sort_values(["Season", "Minutes"], ascending=[True, False])

    return out.reset_index(drop=True)
```

**Diff vs #1/#3:** byte-for-byte logic match with #3 (and functionally identical to #1); no
new behavior versus either.

**Claude's recommendation (non-binding):** last-wins would pick **def #4 (12329)**. As with
Section A, defs #1, #3, and #4 are functionally identical (single-line signature, packed/
one-per-line `cols` formatting aside, and — critically — all three retain the `Minutes` → 0
fallback). Def #2 (11488) is the outlier: despite being the longest by raw line count, that
extra length is almost entirely signature style, a docstring, and list formatting — not added
functionality — and it is actually *missing* the `Minutes` → 0 fallback the other three share
(mirroring Section A's def #2 exactly, reinforcing that 11427/11488 come from the same
editing pass). So "longer" here does not mean "more complete." Last-wins (def #4 / 12329) is
a reasonable pick on functional grounds. As in Section A, def #4 still carries the `Minutes` →
0 silent default that falls under `03-CONTEXT.md`'s fix-threshold and should be corrected
during the Phase 4 port regardless of which duplicate is chosen as the base.

DECISION: 12329
REASON: Same reasoning: matches the 3-way majority (7093/11870/12329); the outlier at 11488 was traced to docstring/formatting length, not additional logic, so it isn't a stronger claim to authoritativeness.

---

## Handoff

Once both `DECISION:`/`REASON:` pairs above are filled in by the user, this file's outcome
feeds `get-scouted-be/scoring/docs/DUPLICATE_FUNCTIONS.md` (the master mechanical-resolution
map for the other 18 duplicated names, produced by Plan 02) so that Plan 07 can merge all 20
duplicate-name resolutions — 18 mechanical + these 2 human-decided — into a single master
curation map for Phase 4's port.
