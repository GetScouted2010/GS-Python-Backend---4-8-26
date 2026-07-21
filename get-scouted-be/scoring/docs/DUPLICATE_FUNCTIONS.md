# Duplicate-Function Catalogue

Source file: `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` (15,747 lines).
Verified 2026-07-21 via:

```
grep -n "^def " pixel-perfect-clone-60729/docs/impact_model_v4.1.py \
  | sed 's/(.*//;s/^[0-9]*:def //' | sort | uniq -d
```

which lists exactly **20 top-level function names** defined more than once, and

```
... | sort | uniq -c | awk '$1>2'
```

which shows exactly two names with **4** definitions each: `prepare_team_and_transfer_signal`
and `player_transfer_history`.

## Policy in force

Per `03-CONTEXT.md` "Duplicate-Function Resolution Policy" (locked):

- **Default rule (last-wins):** for any duplicated name with **exactly 2 definitions**, the
  **LAST** definition in the file is authoritative. This is not an arbitrary convention — it is
  cross-checked against `get_export_columns_for_position()` (line 110, the second/last copy),
  which lists the actual Excel export column order that reflects what the script last shipped
  successfully. Both copies of `get_export_columns_for_position` are byte-identical (see below),
  so the cross-check is copy-invariant: whichever copy is "last" produces the same column order,
  confirming last-wins does not silently change shipped behavior for the anchor case.
- **Escalation trigger:** any name with **more than 2 definitions (3+)** is escalated to a human
  for review, never mechanically resolved. Exactly two names meet this bar:
  `prepare_team_and_transfer_signal` (4 defs) and `player_transfer_history` (4 defs). Both are
  marked `ESCALATION PENDING` below and handed off to Plan 03 / `ESCALATION_REVIEW.md`.
- **Audit trail requirement:** every kept version AND every rejected version is recorded here
  with a reason, even when the reason is simply "identical to kept version, redundant."

## The 20-name catalogue

| Function | Def count | Line numbers | Kept line | Rejected line(s) | Reason | Escalated? |
|---|---|---|---|---|---|---|
| `prepare_team_and_transfer_signal` | 4 | 7041, 11427, 11702, 12192 | ESCALATION PENDING | ESCALATION PENDING | 4 definitions exceeds the 2-definition mechanical-resolution threshold; requires human review of all 4 bodies before locking an authoritative version. | Y |
| `player_transfer_history` | 4 | 7093, 11488, 11870, 12329 | ESCALATION PENDING | ESCALATION PENDING | 4 definitions exceeds the 2-definition mechanical-resolution threshold; requires human review of all 4 bodies before locking an authoritative version. | Y |
| `season_to_year` | 2 | 4783, 13705 | 13705 | 4783 | Last-wins (default rule); no signature or behavioral difference noted in research. | N |
| `safe_div` | 2 | 4762, 13699 | 13699 | 4762 | Last-wins (default rule). Feeds the sklearn `mv_to_fee_ratio` feature — verify zero/NaN-division handling explicitly when porting, since a silent div-by-zero here would distort a training feature. | N |
| `player_transfer_summary` | 2 | 11577, 12399 | 12399 | 11577 | Last-wins (default rule); no signature or behavioral difference noted in research. | N |
| `pick_first_existing` | 2 | 4768, 13733 | 13733 | 4768 | Last-wins (default rule). **SIGNATURE DIFFERS between the two copies:** the 4768 copy defaults `required=True`; the 13733 (kept) copy defaults `required=False`. This is exactly the subtle-default bug class the fix-threshold targets — callers relying on implicit `required=` at call sites now get the `required=False` behavior (missing column silently returns `None` instead of raising) because the last definition is authoritative. Flagged for explicit verification during the Phase 4 port. | N |
| `parse_money_to_numeric` | 2 | 4738, 13668 | 13668 | 4738 | Last-wins (default rule). Feeds the sklearn fee-cleaning pipeline; no signature difference noted. | N |
| `get_role_scores_from_dataset` | 2 | 1055, 3133 | 3133 | 1055 | Last-wins (default rule). The 3133 (kept) copy reads the wide `ROLE_COLUMNS_BY_POSITION` columns directly, differing in data-shape assumption from the 1055 copy — confirm the wide-column read path is what Phase 4's port should replicate. | N |
| `get_position_target_avg_cols` | 2 | 13, 104 | 104 | 13 | Last-wins (default rule). Byte-identical body — the "EXPORT HELPERS" code cell was pasted twice verbatim. | N |
| `get_position_delta_cols` | 2 | 16, 107 | 107 | 16 | Last-wins (default rule). Trivial redundant duplicate — identical body. | N |
| `get_position_component_cols` | 2 | 10, 101 | 101 | 10 | Last-wins (default rule). Trivial redundant duplicate — identical body. | N |
| `get_export_columns_for_position` | 2 | 19, 110 | 110 | 19 | Last-wins (default rule). **Cross-check anchor for the whole last-wins policy** — diffed both bodies (lines 19-61 vs 110-153): byte-identical except one blank line; both list the identical column order. This confirms last-wins does not change shipped Excel export behavior for the anchor case. | N |
| `get_2425_transfers` | 2 | 11598, 12412 | 12412 | 11598 | Last-wins (default rule); no signature or behavioral difference noted in research. | N |
| `format_financial` | 2 | 1305, 13742 | 13742 | 1305 | Last-wins (default rule). **SIGNATURE DIFFERS between the two copies:** the 1305 copy's first positional parameter is named `value=`; the 13742 (kept) copy renames it `x=`. Positional call sites are unaffected, but any call site using the keyword form (`value=...`) would break against the kept definition. Flagged for explicit verification during the Phase 4 port — same subtle-default bug class as `pick_first_existing`. | N |
| `export_team_shortlist_xlsx` | 2 | 67, 158 | 158 | 67 | Last-wins (default rule). Diffed both ~90-line bodies directly (research had not diffed them): the first definition (67) is **truncated/dead code** — its body ends at line 97 (`writer = pd.ExcelWriter(...)`) with no `return` statement, immediately interrupted by a module-level "EXPORT HELPERS" comment block and the second copies of `get_position_component_cols`/`get_position_target_avg_cols`/`get_position_delta_cols`/`get_export_columns_for_position` (lines 98-153), before the second, complete `export_team_shortlist_xlsx` definition begins at 158 and runs to completion. The first copy is provably never a working function body — last-wins is not just convention here, it is demonstrably correct. | N |
| `contract_to_years_left` | 2 | 4793, 13716 | 13716 | 4793 | Last-wins (default rule). Feeds the sklearn `contract_years_left` feature; no signature difference noted. | N |
| `classify_age_fit` | 2 | 1325, 2698 | 2698 | 1325 | Last-wins (default rule). The 2698 (kept) copy is the one in effect at the shortlist scoring block (line 3719), since Python module execution order means the later definition shadows the earlier one by the time that call site runs. | N |
| `build_wim_player_list_from_players_df` | 2 | 10406, 10670 | 10670 | 10406 | Last-wins (default rule); no signature or behavioral difference noted in research. | N |
| `build_transfer_value_dataset` | 2 | 4887, 4935 | 4935 | 4887 | Last-wins (default rule). Read and confirmed directly: the first definition (4887) is **truncated/orphaned** — its body ends at line 4930 (`p_squad_role_col = pick_first_existing(...)`) with no `return` statement, cut off mid-body by a module-level "HISTORICALLY CORRECT TRANSFER VALUE DATASET" comment block before the second, complete definition begins at 4935. The first copy never reaches a `return` and cannot be a working function — strong direct evidence that last-wins is correct, not just convention. | N |
| `build_general_market_shortlist` | 2 | 12776, 13263 | 13263 | 12776 | Last-wins (default rule); no signature or behavioral difference noted in research. | N |

## Nested duplicates (out of scope for last-wins)

The following is **duplicated logic, not a duplicated top-level definition**, and is explicitly
excluded from the last-wins/escalation machinery above:

- **`financial_fit_label`** — defined locally (nested) inside three different outer functions, at
  lines 7454, 8473, and 9108. Each is a correctly-scoped closure local to its enclosing function;
  none of them collide as top-level names (the anchored `^def ` grep used to build the 20-name
  catalogue above does not even see them, since they are indented, not top-level). This is
  duplicated *logic* across three call sites, not a name-collision requiring kept/rejected
  resolution. No action required here; Phase 4's port should port each closure in place within
  its enclosing function, not attempt to hoist/dedupe them into a single shared helper (that would
  be an architectural change out of scope for this characterization phase).

## Escalation handoff

`prepare_team_and_transfer_signal` (4 defs: 7041, 11427, 11702, 12192) and
`player_transfer_history` (4 defs: 7093, 11488, 11870, 12329) are **not resolved by this plan**.
Both are deliberately left `ESCALATION PENDING` per the locked policy (any name with 3+
definitions requires human review, never mechanical last-wins). See Plan 03 /
`ESCALATION_REVIEW.md` for the human-reviewed resolution of these two names.
