# Phase 3: Scoring Engine Curation & Correctness Oracle - Research

**Researched:** 2026-07-21
**Domain:** Code archaeology + data-science characterization of a 15,747-line flattened-Jupyter-notebook Python scoring script (`impact_model_v4.1.py`); no Django porting in this phase.
**Confidence:** HIGH (all structural/line-number findings below are from direct inspection of the actual file in this repo, 2026-07-21) — MEDIUM/LOW flagged explicitly where the script's intent is ambiguous and requires curation-time judgment or user escalation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Duplicate-Function Resolution Policy**
- Default rule (locked): for any duplicated function name, the LAST definition in the file is authoritative — cross-checked against `get_export_columns_for_position()` (the actual Excel export columns), since that reflects what was actually "shipped" when the script last ran successfully. This applies mechanically to every duplicated name with exactly 2 definitions.
- Escalation trigger: any function name with more than 2 definitions (3 or more) must be escalated to the user for review before locking in which version is authoritative — regardless of how similar or different the versions look at a glance. From the verified duplicate-count scan, this currently means `prepare_team_and_transfer_signal` (4 definitions) and `player_transfer_history` (4 definitions) MUST be escalated; do not resolve these via the mechanical last-wins rule without user review.
- Curation map must record BOTH the kept version and every rejected version, with a reason — even if the reason is just "identical to kept version, redundant." This creates an audit trail for debugging any future scoring discrepancy.

**Handling Bugs/Quirks Found During Curation**
- The oracle is "corrected ground truth," not a bit-for-bit copy of the original script. Where curation finds an obviously-wrong silent default, fix it now rather than faithfully preserving broken behavior into the port.
- Fix threshold (narrow, deliberately): only fix cases where MISSING/ABSENT data gets silently defaulted in a way that mathematically distorts a score — e.g., a missing `Minutes` column defaulting to `0` (implying zero playing time / zero performance) instead of excluding the player from that calculation or nulling the field. This is the CONCERNS.md-flagged pattern class.
- Everything else is preserved and documented, not touched — odd thresholds, hardcoded weights (e.g. the `league_weights` dict), unusual formulas. These may be deliberate tuning choices, not bugs, even if they look debatable. Do not "improve" them during characterization.
- Every fix applied must be documented in the curation map: what was wrong, what changed, why. No silent fixes.

**Transfer Probability / sklearn Component**
- Verified: no pre-trained model file exists anywhere in the codebase. `RandomForestRegressor` trains at runtime via `train_test_split(..., random_state=42)` + `RandomForestRegressor(..., random_state=42)` — both seeded, so the trained model IS reproducible given identical input data (impact_model_v4.1.py lines ~5638-5652).
- Train fresh on Phase 1's real migrated dataset — this is the only available and correct baseline; there is no prior trained artifact or historical reference output to match instead.
- Save the fitted model as a versioned artifact (joblib) as part of this phase's deliverables. Phase 4+ loads this artifact; it is NOT retrained per request or on-demand later — matches ARCHITECTURE.md's `ml_artifacts/` design (serialized, versioned, not retrained per request).
- Record model quality metrics (MAE, R² on the held-out test split) for reference only — no minimum quality bar enforced in this phase. This is characterization, not model improvement. Flag the actual numbers in the curation map as a known-risk area feeding Phase 5's parity-tolerance decision.
- **IMPORTANT — this research found a discrepancy that must be resolved before this decision can be executed as literally stated.** See `## Critical Finding: "Transfer Probability" Is Not What It Was Assumed To Be` below — the RandomForestRegressor at lines ~5638-5652 does NOT predict transfer probability; it predicts transfer fee (`log_fee`). The output column literally named `"Transfer Probability %"` is produced elsewhere by a hand-weighted, non-ML formula. This must be escalated per the same policy spirit as the duplicate-function escalation, before Phase 3 execution treats "the RandomForestRegressor artifact" as "the Transfer Probability model."

**Oracle Snapshot Scope**
- Full population — snapshot every real player's RMM/CS/TFM/Transfer Probability output (all ~41,708 players from Phase 1), not a stratified sample. Maximizes Phase 5 parity-testing coverage; storage cost is modest.
- Format: flat file (CSV/Parquet), versioned in the repo — NOT a Postgres table/Django model. The oracle is a one-time comparison baseline for Phase 5's test suite to diff against; it doesn't need to be live-queryable by the application itself.

### Claude's Discretion
- Exact file/module layout for curation deliverables (curation map as Markdown table vs. structured JSON/YAML; where the training/snapshot scripts live)
- Exact CSV/Parquet schema for the oracle snapshot (one file per position group vs. one combined file; exact column naming)
- Specific feature-engineering/hyperparameter details beyond what's already in the original script's Transfer Probability recipe — must faithfully reproduce the original recipe, per the "train fresh but faithful" decision, not redesign it
- Mechanics of how escalation to the user actually happens during research/planning/execution for the >2-version duplicate cases

### Deferred Ideas (OUT OF SCOPE)
- Improving the Transfer Probability model's actual predictive quality (feature engineering, hyperparameter tuning) — explicitly deferred
- Fixing non-bug quirks (odd thresholds, hardcoded weights) even if they look debatable — deferred indefinitely
- A "raw/unfixed" parallel oracle snapshot — considered and explicitly rejected in favor of a single "corrected ground truth" oracle

</user_constraints>

<phase_requirements>
## Phase Requirements

No requirement IDs are directly owned by Phase 3 (confirmed in REQUIREMENTS.md's traceability note and ROADMAP.md). This phase is prerequisite risk-mitigation work: its curation map and oracle snapshot are consumed by Phase 4 (SCORE-01 through SCORE-05, the actual port), Phase 5 (SCORE-06, parity testing against this phase's oracle), and Phase 6 (SCORE-07, caching strategy built on the "no isolated per-player scoring" finding this research reconfirms).

| ID | Description | Research Support |
|----|-------------|-----------------|
| (none — see above) | Prerequisite work for SCORE-01..07 | Findings below (duplicate-function inventory, score-computation map, sklearn recipe, data-reconstruction guidance) directly enable Phase 4's port tasks and Phase 5's tolerance decisions |

</phase_requirements>

## Summary

`impact_model_v4.1.py` (15,747 lines, confirmed by `wc -l`) is a flattened Jupyter notebook (`# In[N]:` cell markers, 108 of them; `import pandas`/`import numpy` re-imported 21 times) with 20 top-level function names defined more than once — verified by direct `grep -n "^def "` + line-number extraction, matching CONTEXT.md's "~20 duplicated names" figure exactly. Of these, 18 have exactly 2 definitions (mechanical last-wins + export-column cross-check applies) and 2 have 4 definitions each (`prepare_team_and_transfer_signal`, `player_transfer_history` — both MUST be escalated per the locked policy). The full line-number inventory for all 20 names is below.

The script cannot be executed top-to-bottom as a plain `.py` file: it reads three hardcoded absolute paths on the original author's machine (`/Users/oluquadri/Downloads/*.xlsx`, none of which exist in this repo) via `pd.read_excel(...)` at line ~742-748 (and two more at 11415/12725), and it calls Jupyter's `display()` 18 times starting at line 728 while `from IPython.display import display` isn't imported until line 14361 — i.e. it only ever worked as a notebook (where `display` is a kernel-provided global), never as a linear script. **This confirms the phase's approach must be "extract and call specific curated functions against a reconstructed DataFrame," not "run the whole file."**

The single most important and previously-unverified finding from this research: **the sklearn `RandomForestRegressor` (lines 5638-5652) does not compute "Transfer Probability."** It trains to predict `log_fee` (a player's transfer fee in money terms — `train_transfer_value_model()`, feeding `predicted_fee` / Bargain-Fair-Overpay `value_verdict` labels). The literal `"Transfer Probability %"` output column is produced entirely differently: a hand-weighted, non-ML formula (`0.30*compatibility + 0.20*performance + 0.20*financial + 0.30*contract_fit`) inside `external_target_shortlist_absolute_vectorized()` at line 3809-3814. There is no `RandomForestClassifier`, `LogisticRegression`, `.predict_proba(`, or any other probability-of-transfer model anywhere in the file (verified: `pipeline.fit(` at line 5655 is the *only* `.fit()` call in the whole script). This directly affects how CONTEXT.md's locked Transfer Probability decision should be executed and must be resolved (see Critical Finding section and Open Questions).

**Primary recommendation:** Treat this phase as three parallel-but-sequenced workstreams — (1) duplicate-function curation driven off the confirmed 20-name inventory below, (2) a from-Django-ORM DataFrame-reconstruction step that leans heavily on the already-existing `get-scouted-be/docs/FIELD_MAPPING.md` (Phase 1 deliverable) rather than re-deriving column mappings from scratch, and (3) sklearn artifact training using the exact feature/target recipe extracted below from `train_transfer_value_model()` — but do not wire that artifact to "Transfer Probability" until the Critical Finding is escalated and resolved, since it may actually belong to Financial Fit (TFM) instead.

## Critical Finding: "Transfer Probability" Is Not What Prior Research Assumed

This is escalation-worthy under the spirit of CONTEXT.md's policy (high-impact ambiguity affecting which artifact feeds which of the 4 PRD scores), even though it isn't a duplicate-function-name case. Flagging prominently because Phase 4-6 planning depends on getting this right.

**What the PRD says (`GetScouted PRD.docx` §1.4):**
- Financial Fit (TFM) — "whether a player's market value and transfer cost are realistic for a given club's spending profile."
- Transfer Probability — "the modelled likelihood of a transfer occurring, used across shortlist, matching, and risk views."

**What the script actually contains, verified by direct inspection:**

| Script artifact | Line(s) | What it actually computes | Best PRD-score match |
|---|---|---|---|
| `train_transfer_value_model()` + `RandomForestRegressor` | 5569-5670 (model def), 4666-4672 (imports), 5638-5652 (RF + `train_test_split`, both `random_state=42`) | Regresses `log_fee` (a transfer's money value) against ~33 features (age, performance/compat/impact scores, league weights, club buy/sell fee history, position/role categoricals). Outputs `predicted_fee`, `fee_diff`, `fee_ratio_actual_to_pred`, and a `value_verdict` label (`"Bargain"` / `"Fair Value"` / `"Overpay"`) via `add_value_labels()` (line 5676). | **Financial Fit (TFM)** — this is a "is the transfer cost realistic" model, matching the PRD's TFM definition almost verbatim. It is NOT a probability. |
| `"Transfer Probability %"` column | Computed at 3809-3814, inside `external_target_shortlist_absolute_vectorized()` (top-level def at 3275) | `tp = (0.30*compatibility_score/100 + 0.20*performance_score/100 + 0.20*financial_score/100 + 0.30*contract_fit) * 100`. Pure weighted average of already-computed component scores + a contract-expiry-derived `contract_fit` (1.0/0.7/0.4/0.1 banded by years left). No ML, no historical transfer outcomes used as training signal. | **Transfer Probability** by literal column name and PRD wording ("likelihood... used across shortlist... views" matches this being computed per-player-per-shortlist-row) — but it is a heuristic score, not a "modelled likelihood," and it exists in only ONE function in the whole 15,747-line file (confirmed: `grep -n "Transfer Probability"` returns exactly 3 hits — 2 are the `get_export_columns_for_position()` column-name string, 1 is this assignment). |
| `"Sell Probability %"` | 4527 (`build_sell_probability_list`, def at 4015) | A separate heuristic (age/contract/minutes/step-up-score band) predicting how likely a club is to *sell* a player, distinct from a buying-club "will this transfer happen" probability. Not one of the 4 PRD scores; likely irrelevant to SCORE-04 but could be confused with it by name similarity. | Neither — a different concept (sell-side risk signal), not player-to-club transfer likelihood. |
| `build_club_requirement_prediction_model()` | 14884+ | Predicts which *positions* a club needs (not player-level transfer probability), includes its own `requirement_probability_label()` (Very Likely/Likely/Possible/Unlikely bands from a 0-100 score) — feeds PLAN-01 (Position Needs), not SCORE-04. | Neither — belongs to Phase 11's Position Needs analysis, unrelated to SCORE-04. |

**Why this matters for CONTEXT.md's locked decision:** "Save the fitted model as a versioned artifact... Phase 4+ loads this artifact... Record model quality metrics... feeding Phase 5's parity-tolerance decision" was written assuming the RandomForestRegressor produces Transfer Probability. Based on this research, the RandomForestRegressor's natural home is **Financial Fit (TFM)**, and the actual "Transfer Probability" the port must faithfully reproduce is the **deterministic heuristic formula** at 3809-3814 (which is fully deterministic — no sklearn involved, no train/test split, trivially reproducible, arguably *lower* curation risk than previously assumed since there's no model-quality question at all for it).

This does not remove work — it likely *relabels* it: the RF artifact is still worth training/versioning/joblib-saving exactly as CONTEXT.md describes, just as the TFM-feeding artifact, not the Transfer-Probability-feeding one. Recommend the planner insert an explicit early task in Phase 3 to confirm this mapping (cross-check against `get_export_columns_for_position()`'s column ordering — `"Performance Score", "Compatibility Score", "Financial Score", "Recommendation", "Transfer Probability %"` — and against the PRD text) and, if this research's reading is confirmed, update the curation map's score-to-function assignment accordingly before Phase 4 consumes it. Given CONTEXT.md frames escalation as necessary for "any... ambiguity" with downstream impact, treat this the same way as the 4-definition duplicate-function cases: surface it explicitly rather than silently resolving it either direction.

## Related, Lower-Stakes Ambiguities (also flag, lower priority)

- **"Player Score (RMM)" candidate mapping:** The one clean, single-definition, population-wide, position-aware, 0-100-percentile function is `add_player_impact(df)` (line 2725) → sets `df["Player Impact"]` via `_position_percentile()` per position group (line 2822), built from the 8 non-duplicated `_calc_*_impact_raw` functions (lines 1413-2007) + `_build_std_lookup()` (line 1392). This does NOT require a target-club context — matches PRD's RMM description ("overall, position-aware performance score out of 100") most cleanly and is ARCHITECTURE.md's own recommended reusable asset. By contrast, `"Performance Score"` (set at line 3836, inside the same 3275 shortlist function as the Transfer-Probability heuristic) is a *further* blend of Player Impact + team-target-relative percentiles (`perf_team_pct`, `perf_target_pct`, `perf_own`) — i.e. it's contextual to a specific target-club shortlist run, not a standalone player attribute. Recommend `add_player_impact()`'s `"Player Impact"` as the RMM candidate for a context-free `/players/{id}/impact` endpoint; keep `"Performance Score"` as a documented, secondary, club-context-dependent quantity if Phase 4 needs it for shortlist-style views. This is lower-stakes than the Transfer Probability finding because `add_player_impact()` is unambiguous and non-duplicated — the risk is only in choosing which of two real, already-computed quantities the port calls "RMM."
- **"Compatibility Score (CS)" — recompute vs. already-imported legacy data:** Phase 1 already imported 8,188,712 `PlayerClubCompatibility` rows (one score per player×club, from legacy `Compatibility Scores/*.csv` files — see STATE.md's Phase 1 decisions). Separately, the script computes a fresh `"Compatibility Score"` at line 3798-3802 (`_avg_non_null([role_fit_score, similarity_pct, 100_or_70_bonus])`), itself dependent on `calculate_subjective_role_fit_for_player_to_team()` (line 2446) and `team_styles_df`/Club playing-style fields. It is not yet established whether SCORE-02 should be served from the already-migrated legacy `PlayerClubCompatibility.score` field or freshly computed via the script's role-fit logic (or both, cross-checked). Recommend the curation map explicitly note this fork and let the user/Phase 4 planner decide — this phase should still characterize `calculate_subjective_role_fit_for_player_to_team()` regardless, since ARCHITECTURE.md's `scoring/services/role_fit.py` already assumes it gets ported.

## Script Structure & Execution Model

Verified by direct inspection (`wc -l`, `grep -n "^# In\["`, `grep -n "^import pandas"`, `grep -n "__main__"`, `grep -n "pd.read_excel\|pd.read_csv"`, `grep -n "IPython"`).

| Fact | Detail |
|---|---|
| Total lines | 15,747 |
| Notebook cell markers | 108 (`# In[N]:`), confirming flattened-notebook origin, not an authored module |
| `import pandas as pd` occurrences | 21 separate re-imports scattered through the file (lines 439, 734, 1212, 4663, 6557, 6610, 6817, 8232, 8293, 8469, 8987, 9031, 11070, 11409, 11695, 12185, 12770, 13257, 13621, 14357, 14880) |
| `if __name__ == "__main__"` | None. No CLI, no argparse, no main() function of any kind. |
| Data ingestion | 5 total `pd.read_excel(...)` calls, ALL to hardcoded absolute paths on the original author's machine, none of which exist in this repo or any accessible filesystem: `/Users/oluquadri/Downloads/Wyscout_ALL_SEASONS_TM_updated_2526_league_club_player_match3.xlsx` (players_df, line 742), `/Users/oluquadri/Downloads/Main Clean Transfers Data updated 18 - 24.new.xlsx` (transfers_df, line 745), `/Users/oluquadri/Downloads/Teams.xlsx` (team_styles_df, line 748), plus 2 more later re-reads of a differently-named file at lines 11415 and 12725. Zero `pd.read_csv`, zero DB connections, zero API/network calls anywhere in the file (verified via grep for `requests.`, `urllib`, `psycopg`, `pymongo`). |
| Output/export | 41 `.to_excel(`/`.to_csv(` calls, all writing to more `/Users/oluquadri/Downloads/*.xlsx` paths — none are readable inputs for this phase, only demonstrate what the original author manually inspected. |
| Jupyter-only calls | `display(...)` called 18 times, first use at line 728 — but `from IPython.display import display` isn't imported until line 14361. Running this file with plain `python impact_model_v4.1.py` top-to-bottom would `NameError` at the first `display()` call long before reaching that import. This is additional, independent confirmation (beyond the hardcoded paths) that **the file was only ever executed as a Jupyter/IPython notebook**, never as a linear script — the phase's snapshot-generation approach must call extracted/curated functions directly, not `exec()`/`runpy` the whole file. |
| Column-naming convention the script expects | Original Wyscout/Excel-export style: spaces, commas, `%` signs, mixed case (e.g. `"Successful defensive actions per 90"`, `"Accurate passes, %"`, `"PAdj Interceptions"`, `"Market value"`) — NOT the Django `Snake_Case_With_Caps` field names Phase 1 used. See "Data Reconstruction" section below — `get-scouted-be/docs/FIELD_MAPPING.md` already documents this exact Django-field ↔ script-internal-name mapping. |

## Full Duplicate-Function Inventory (verified, all 20 names)

Extracted via `grep -n "^def "` + `awk`-based name/count aggregation, then per-name line-number lookup — all line numbers below are exact, directly verified against the file in this repo on 2026-07-21.

| Function name | Definition count | Line numbers | Escalation required? | Notes |
|---|---|---|---|---|
| `prepare_team_and_transfer_signal` | **4** | 7041, 11427, 11702, 12192 | **YES — escalate** | Body lengths diverge (51/60/58/64 lines) — genuine content differences across versions, not just whitespace. All 4 share an identical first ~9 lines (Team_within_selected_timeframe → Team_Final fallback logic) then diverge. |
| `player_transfer_history` | **4** | 7093, 11488, 11870, 12329 | **YES — escalate** | Body lengths diverge (57/89/71/70 lines); the 2nd definition (11488) has a different signature style (`def player_transfer_history(\n    df, player_name, season=None, team=None\n):` — multi-line) vs. the other 3 (single-line signature) — worth noting in the escalation review as a possible signal of a more substantially reworked version. |
| `season_to_year` | 2 | 4783, 13705 | No — mechanical last-wins (13705) + export-column cross-check | |
| `safe_div` | 2 | 4762, 13699 | No — mechanical (13699) | Used by the sklearn feature-engineering step (`mv_to_fee_ratio`) — verify the kept version's zero/NaN-division handling carefully since it feeds a model feature. |
| `player_transfer_summary` | 2 | 11577, 12399 | No — mechanical (12399) | |
| `pick_first_existing` | 2 | 4768, 13733 | No — mechanical (13733) | **Signature differs between versions:** first def has `required=True` default, second has `required=False` default. Since this helper is used throughout column-resolution logic (including inside `build_transfer_value_dataset`), confirm which default is actually in effect at each call site during curation — a default-flip here is exactly the class of subtle bug CONTEXT.md's "fix threshold" section is about. |
| `parse_money_to_numeric` | 2 | 4738, 13668 | No — mechanical (13668) | Feeds the sklearn model's fee-cleaning step — verify both versions produce identical output before assuming interchangeable. |
| `get_role_scores_from_dataset` | 2 | 1055, 3133 | No — mechanical (3133) | Second version (3133) confirmed reads `ROLE_COLUMNS_BY_POSITION`-keyed wide columns off the row — needs a `PlayerRoleScore` long→wide pivot when reconstructing input (see Data Reconstruction section). |
| `get_position_target_avg_cols` | 2 | 13, 104 | No — mechanical (104) | Both located near the very top of the file (within the first 155 lines) — confirmed byte-identical logic; this is the "EXPORT HELPERS" cell pasted twice back-to-back, not an old/new revision pair. Good example of a "trivial redundant duplicate" per CONTEXT.md's "identical to kept version" reason. |
| `get_position_delta_cols` | 2 | 16, 107 | No — mechanical (107) | Same trivial-duplicate cell as above. |
| `get_position_component_cols` | 2 | 10, 101 | No — mechanical (101) | Same trivial-duplicate cell as above. |
| `get_export_columns_for_position` | 2 | 19, 110 | No — mechanical (110) | **Verified byte-for-byte identical body** (diffed directly) except one extra blank line in the second copy — the canonical "trivial redundant duplicate, no behavior difference" example for the curation map. This is also the function CONTEXT.md's cross-check policy anchors on — both copies list the same column order, so the cross-check is unaffected by which copy is "kept." |
| `get_2425_transfers` | 2 | 11598, 12412 | No — mechanical (12412) | |
| `format_financial` | 2 | 1305, 13742 | No — mechanical (13742) | **Signature differs:** first def is `format_financial(value, currency="€")`, second is `format_financial(x, currency="€")` — parameter rename only (positional-call-safe), but confirm no keyword-argument call sites break. |
| `export_team_shortlist_xlsx` | 2 | 67, 158 | No — mechanical (158) | Large function (~90 lines each); not diffed line-by-line in this research pass — recommend the curation task actually diff these two bodies since it's the main shortlist-export orchestrator and not a trivial helper. |
| `contract_to_years_left` | 2 | 4793, 13716 | No — mechanical (13716) | Feeds sklearn feature `contract_years_left`. |
| `classify_age_fit` | 2 | 1325, 2698 | No — mechanical (2698) | Used directly in the shortlist scoring block (line 3719) that also computes `"Transfer Probability %"` — verify which of the 2 definitions is actually in scope at that call site (both are pre-3719 in file order, so 2698's version is in effect there, consistent with last-wins-by-position). |
| `build_wim_player_list_from_players_df` | 2 | 10406, 10670 | No — mechanical (10670) | |
| `build_transfer_value_dataset` | 2 | 4887, 4935 | No — mechanical (4935) | **The first definition (4887) is truncated/orphaned** — it's cut off mid-body by the second `def` statement at 4935 without ever reaching a `return`, i.e. it's dead, broken code if ever called (would hit the second function's body as if it were the first's, then never return from the first because Python simply treats it as two independent top-level defs — the first one's incomplete body just silently does nothing useful if invoked, since it has no `return` and Python functions without a `return` implicitly return `None`). This is strong direct evidence for why last-wins is the correct default policy, and a good concrete example for the curation map's "why rejected" column. |
| `build_general_market_shortlist` | 2 | 12776, 13263 | No — mechanical (13263) | |

**Important scope clarification for the curation task:** the count above (20 names, all top-level `def` statements at column 0) is what CONTEXT.md's "~20 duplicated names" and the escalation policy refer to. Separately, this research found **nested/local helper functions** with duplicate names across *different* outer functions — e.g. a local `def financial_fit_label(age_fit, mv_fit):` is independently defined inside 3 different outer functions (`validate_transfer_impact_with_style` at 7454, `predict_player_move_to_club` at 8473, `validate_all_transfers_with_style_and_team_penalty` at 9108), each a closure scoped to its own outer function — not a name-collision/last-wins ambiguity at all, since each is scoped independently and correctly used within its own function. **Do not apply the duplicate-function escalation policy to these** — they're a different (much lower-risk) kind of code duplication (copy-pasted logic across differently-named outer functions), worth noting in the curation map as "duplicated logic, not duplicated definition," but not something requiring the last-wins/escalation machinery. If the curation task wants to also catalogue these for completeness, `grep -n "    def " impact_model_v4.1.py` (4-space-indented `def`) surfaces the nested ones separately from the top-level `grep -n "^def "` inventory above.

## Core Score Computation Map

Concrete function/line references for each of the 4 PRD scores, established by direct grep + read of surrounding code. Use this as the starting skeleton for the phase's required curation map (Success Criterion 4).

| Score | Primary candidate function(s) | Line(s) | Whole-dataset dependency? | Confidence |
|---|---|---|---|---|
| **RMM (Player Score)** | `add_player_impact(df)` → `"Player Impact"` column, via the 8 `_calc_*_impact_raw` functions + `_build_std_lookup()` | `add_player_impact`: 2725; `_build_std_lookup`: 1392; `_calc_gk_impact_raw`: 1413; `_calc_cb_impact_raw`: 1473; `_calc_fb_impact_raw`: 1539; `_calc_cmf_impact_raw`: 1616; `_calc_dmf_impact_raw`: 1694; `_calc_amf_impact_raw`: 1773; `_calc_winger_impact_raw`: 1851; `_calc_cf_impact_raw`: 1928 | Yes — `_build_std_lookup(df, metrics_needed, position_col="Main_Position")` needs the full player population once, then per-row scoring is O(1) against that lookup (confirms ARCHITECTURE.md's "no isolated per-player scoring" finding directly) | HIGH — single, non-duplicated definition; also `add_player_impact` itself is not one of the 20 duplicated names |
| **Compatibility Score (CS)** | Two candidates, unresolved — see "Related Ambiguities" above: (a) already-imported `PlayerClubCompatibility.score` (legacy, Phase 1), or (b) fresh `calculate_subjective_role_fit_for_player_to_team()` feeding the `"Compatibility Score"` column at line 3798-3802 | `calculate_subjective_role_fit_for_player_to_team`: 2446; `"Compatibility Score"` assignment: 3798-3802 (inside `external_target_shortlist_absolute_vectorized`, def at 3275) | Yes — role-fit needs `team_styles_df` (Club playing-style vectors) built once per club, not per-player | MEDIUM — function itself is clean/non-duplicated, but which-quantity-is-CS is an open question |
| **Financial Fit (TFM)** | Two overlapping candidates: (a) simple `"Financial Score"` = avg(age_fit_score, mv_fit_score) at line 3804-3807 (cheap, deterministic, no ML); (b) the sklearn `train_transfer_value_model()` fee-value-prediction pipeline (see Critical Finding — this research recommends TFM as this model's true home, not Transfer Probability) | Simple version: 3804-3807; sklearn version: `build_transfer_value_dataset` (4935), `train_transfer_value_model` (5569), `add_value_labels` (5676) | Simple version: no (row-local + 2 precomputed averages); sklearn version: yes — trains once on the full historical transfer dataset, then the fitted pipeline scores are O(1) per player-transfer-candidate row | MEDIUM — two real, different-fidelity computations both plausibly "TFM"; curation must decide if TFM = the cheap heuristic, the ML-fee-prediction, or a documented combination |
| **Transfer Probability** | `"Transfer Probability %"` heuristic formula (deterministic, NOT sklearn) | 3809-3814, inside `external_target_shortlist_absolute_vectorized` (def at 3275) | No — pure row-local weighted average of already-computed component scores + contract-band lookup; trivially O(1), no whole-dataset dependency at all | MEDIUM-HIGH on "this is what the column is called and how it's computed" (verified directly); LOW on "this is definitely what SCORE-04 should port" pending the Critical Finding's escalation |

All 4 candidate functions above live inside (or are called from) `external_target_shortlist_absolute_vectorized()` (top-level, non-duplicated, def at line 3275) EXCEPT `add_player_impact()`, which is the one truly standalone, context-free calculator. This function is the single richest characterization target in the whole file — recommend the curation task read it in full (3275 through roughly 3959, based on the `pd.DataFrame` construction pattern observed) as the anchor for documenting how CS/Financial/Transfer-Probability all actually get computed together in one code path.

## sklearn Transfer-Value Model — Exact Reproduction Recipe

Faithful-reproduction inputs for whichever score curation ultimately assigns this artifact to (see Critical Finding — likely TFM, not Transfer Probability). All details below verified directly from `train_transfer_value_model()` (line 5569) and `build_transfer_value_dataset()` (line 4935).

**Imports (lines 4666-4672):**
```python
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder
```
(Currently NOT installed in `get-scouted-be/.venv` — verified via `pip list`. Needs adding to `requirements/base.txt`. Latest available on PyPI as of this research: `scikit-learn==1.9.0`.)

**Target variable:** `log_fee = np.log1p(actual_fee)`, where `actual_fee` comes from parsing the `Fee` column of the transfers dataset via `parse_money_to_numeric()` (line 4738/13668), filtered to `actual_fee.notna() & actual_fee > 0` (line 5573-5574).

**Training-data filtering (in `build_transfer_value_dataset`, before any model code runs):**
1. `transfers = transfers[transfers["Year"].isin([2023, 2024])]` (line 4947-4949) — only 2 transfer years used.
2. Season mapping: `{2023: "2022-2023", 2024: "2023-2024"}` (line 4955-4958) used to join transfer rows to the matching player-season row.
3. `actual_fee = Fee.apply(parse_money_to_numeric)`, then drop rows where `actual_fee` is NaN or ≤ 0 (line 4969-4980).
4. Merge transfers ↔ players on `(Player, mapped_season)` ↔ `(Player, Season)`, left join (line 4273-4289 region — confirmed pattern, not fully re-verified byte-for-byte in this pass).
5. Club-level aggregate features computed via groupby on `Club` (buy side) and `Dealing_Club` (sell side): mean/max/median fee, count, avg age (lines 5004-5045 and a symmetric departures block).

**Full feature list actually used (line 5577-5611, filtered to `[c for c in feature_cols if c in model_df.columns]` — some may be absent depending on merge success):**
```
age, age_squared, u23_flag, prime_age_flag, older_flag,
minutes_played, market_value, contract_years_left,
performance_score, compatibility_score, player_impact, role_pct,
from_league_weight, to_league_weight, league_jump_ratio, mv_to_fee_ratio,
is_loan, domestic_move,
club_avg_in_fee, club_max_in_fee, club_median_in_fee, club_count_in, club_avg_in_age,
seller_hist_avg_out_fee, seller_hist_max_out_fee, seller_hist_median_out_fee,
seller_hist_count_out, seller_hist_avg_out_age,
club_pos_avg_in_fee, club_pos_avg_out_fee,
position, best_role, squad_role
```
Engineered flags verified directly (line 5341-5367): `age_squared = age**2`; `u23_flag = age<=23`; `prime_age_flag = 24<=age<=28`; `older_flag = age>=29`. `mv_to_fee_ratio = safe_div(market_value, actual_fee)` (5373-5384). `is_loan` coerced to int via `pd.to_numeric(...).fillna(0).astype(int)` (5390-5401).

**Preprocessing pipeline (lines 5619-5636):**
- Categorical columns (`dtype == "object"`, i.e. `position`, `best_role`, `squad_role`): `SimpleImputer(strategy="most_frequent")` → `OneHotEncoder(handle_unknown="ignore")`.
- Numeric columns (everything else): `SimpleImputer(strategy="median")`.
- Combined via `ColumnTransformer`.

**Model + split (lines 5638-5653, both seeded):**
```python
model = RandomForestRegressor(n_estimators=300, max_depth=12, min_samples_leaf=3, random_state=42, n_jobs=-1)
pipeline = Pipeline([("preprocessor", preprocessor), ("model", model)])
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.20, random_state=42)
pipeline.fit(X_train, y_train)
```

**Evaluation (lines 5657-5665):** predictions inverse-transformed via `np.expm1`; `mean_absolute_error(actual_fee, pred_fee)` (money-scale MAE) and `r2_score(y_test, pred_log)` (log-scale R²) — both printed, not asserted against any threshold (matches CONTEXT.md's "record for reference only, no minimum quality bar").

**Post-fit labeling (`add_value_labels`, line 5676-5692):** `fee_ratio_actual_to_pred = actual_fee / predicted_fee`; ≤0.80 → `"Bargain"`, ≥1.20 → `"Overpay"`, else `"Fair Value"`.

**Reproduction note:** the *pipeline object itself* (imputer + one-hot encoder + RF, all fit together) is what should be joblib-serialized, not just the raw `RandomForestRegressor` — the `ColumnTransformer`'s fitted imputer statistics and one-hot categories are required at inference time and are part of the same `Pipeline` object returned by `train_transfer_value_model()`.

## Data Reconstruction: Django ORM → Script-Shaped DataFrames

This is the concrete answer to "how does a snapshot-generation task get data OUT of Django INTO the shape this script expects."

**Player data (`players_df`):** `get-scouted-be/docs/FIELD_MAPPING.md` (Phase 1 deliverable, already exists and is comprehensive — 326 lines) is the canonical reference. It documents, for every one of the 121 identifier/stat columns migrated from `Players.csv`, both the Django field name AND the exact literal string `impact_model_v4.1.py` expects internally (e.g. Django `Successful_defensive_actions_per_90` ↔ script `"Successful defensive actions per 90"`; Django `Market_value` ↔ script `"Market value"`). Building `players_df` is therefore: `Player.objects.values(...)` (or `.values_list`) → `pandas.DataFrame` → `.rename(columns=<reverse of FIELD_MAPPING.md's table>)`. Do not re-derive this mapping from scratch; §5 of FIELD_MAPPING.md also documents already-resolved mismatches (the `Team_within_selected_timeframe`→`Team` rename the script performs internally via `_rename_columns_safe()` at line 1191-1197 is independently confirmed by this research to match FIELD_MAPPING.md's §1a note exactly).

**Role scores (`ROLE_COLUMNS_BY_POSITION`-keyed wide columns, feeding `get_role_scores_from_dataset()` at line 3133):** the script expects each player row to carry one column per role name (e.g. `"Deep-Lying Forward"`, `"Target Forward"`, `"Poacher"`...) with a numeric score. Django's `PlayerRoleScore` (230,139 rows, long format — one row per player×role, confirmed in STATE.md's Phase 1 decisions) must be **pivoted wide** (`role_name` → columns, `score` → values) per player before merging into `players_df`. `ROLE_COLUMNS_BY_POSITION` (defined starting line 824) gives the exact expected role-name-per-position lists to validate the pivot's column coverage against.

**Club / team style data (`team_styles_df`):** Django's `Club` model already has 8 flat playing-style `FloatField`s (`control_possession`, `gegenpressing`, `direct_play`, `defensive_counter_attack`, `tiki_taka`, `counter_attack`, `wing_play`, `low_block` — `get-scouted-be/clubs/models.py`), confirmed to only be populated for 239/1,059 clubs (22.6% coverage, per FIELD_MAPPING.md §3) — the other ~77% will have nulls, which the reconstruction script must not silently zero-fill (matches the phase's own "don't distort scores with silent defaults" policy). Straightforward `Club.objects.values(...)` → DataFrame → rename to whatever column names `team_styles_df`-consuming functions expect (needs direct verification against `calculate_subjective_role_fit_for_player_to_team`, line 2446, and `build_team_position_reference`-style helpers during curation — not fully traced in this research pass).

**Transfer data (`transfers_df`):** `build_transfer_value_dataset()` expects specific literal column names — `Player`, `Year`, `Position`, `Age`, `Fee`, `Dealing_Club` (selling), `Club` (buying), `League`, `is_loan` (lines 4895-4903). Django's `Transfer` model (per FIELD_MAPPING.md §4) already has fields named `Year`, `Fee`, `dealing_club` (lowercase — note the casing difference from the script's `Dealing_Club`), `League_Name` (not `League` — needs a rename), `is_loan`, `Age`, `Position`. Reconstruction needs a small explicit rename map for the 2-3 fields where Django's casing/naming diverges from the script's literal expectations; FIELD_MAPPING.md §4 has all the source names, just cross-reference against the specific column names `build_transfer_value_dataset` reads (verified list above).

**Compatibility data:** if CS ends up sourced from the legacy-imported `PlayerClubCompatibility` (8,188,712 rows, keyed by `player` + `club_name_raw`) rather than recomputed, no DataFrame reconstruction against the script is needed for that path at all — it's a direct Django query. If CS is recomputed via the script's role-fit logic instead, no separate reconstruction is needed beyond `players_df` + `team_styles_df` above (role-fit reads role-score columns + `team_styles_df`, not `PlayerClubCompatibility` directly).

## Standard Stack

### Core
| Library | Version (verified via `pip index versions`, 2026-07-21) | Purpose | Currently installed in `get-scouted-be/.venv`? |
|---|---|---|---|
| pandas | 2.3.3 (already pinned `>=2.2,<3.0` in `requirements/base.txt`) | DataFrame reconstruction, all curated scoring functions | Yes |
| numpy | 2.5.1 | Underlying array math used throughout the script | Yes (pandas dependency) |
| scikit-learn | 1.9.0 latest; recommend pinning `>=1.5,<2.0` for stability | `RandomForestRegressor`, `train_test_split`, `Pipeline`, `ColumnTransformer`, `SimpleImputer`, `OneHotEncoder` — all required to faithfully reproduce `train_transfer_value_model()` | **No — not installed, not in requirements. Must be added this phase.** |
| joblib | 1.5.3 latest | Serializing the fitted sklearn `Pipeline` as a versioned artifact (CONTEXT.md's locked decision) | **No — not installed. Must be added.** (Note: scikit-learn depends on joblib transitively, but pin it explicitly since this phase's deliverable directly calls `joblib.dump`/`joblib.load`.) |

### Supporting
| Library | Version | Purpose | When to Use |
|---|---|---|---|
| pyarrow | latest stable (verify at install time) | Only needed if the oracle snapshot format is chosen as Parquet (CONTEXT.md leaves CSV-vs-Parquet to Claude's discretion) | Not currently installed; add only if Parquet is chosen. CSV needs no new dependency and is simpler given "Claude's discretion" doesn't mandate compactness — recommend CSV unless the 41,708-row × handful-of-numeric-columns file size becomes an actual git-repo-size concern (it won't; back-of-envelope this is well under 10MB even with several score columns per position group). |
| openpyxl | 3.1.5 latest | Only needed if any characterization/debugging step reads the original `.xlsx` files the script expects — not needed for the actual snapshot-generation pipeline, since Player/Club/Transfer data comes from the Django ORM, not from re-reading Excel files that don't exist in this repo anyway | Not installed; likely not needed at all for this phase given the ORM-based reconstruction approach above. |

**Installation:**
```bash
# add to get-scouted-be/requirements/base.txt
scikit-learn>=1.5,<2.0
joblib>=1.4,<2.0
```

### Alternatives Considered
| Instead of | Could use | Tradeoff |
|---|---|---|
| Reconstructing DataFrames from Django ORM | Re-reading the CSVs directly from `API-Updated-/dataset/` and bypassing Django entirely | Rejected implicitly by CONTEXT.md ("run against Phase 1's real migrated dataset") — the whole point of Phase 1 having run is that Postgres is now the source of truth; re-reading raw CSVs would validate the *original script's* correctness against source data, not validate that the *migrated Postgres data* produces the right oracle Phase 5 needs. |
| joblib for artifact serialization | `pickle` directly | joblib is what CONTEXT.md explicitly names and is the sklearn-ecosystem standard for numpy-array-heavy objects (more efficient than raw pickle for large arrays); no reason to deviate. |

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---|---|---|---|
| Deciding which of 2 duplicate-definition versions is "correct" by re-deriving from first principles | A fresh re-implementation "improving" on both versions | The mechanical last-wins rule + `get_export_columns_for_position()` cross-check (already locked in CONTEXT.md) | The rule already exists and is verified sound by direct evidence in this research (e.g. `build_transfer_value_dataset`'s first definition is provably dead/broken code — last-wins is not just a convenient heuristic, it's demonstrably correct here) |
| Re-deriving the CSV↔Django↔script column-name mapping | A new mapping document from scratch | `get-scouted-be/docs/FIELD_MAPPING.md` (already exists, Phase 1 deliverable, verified comprehensive and accurate against the actual script in this research pass) | Avoids re-doing already-completed, carefully-verified work; also keeps the single-source-of-truth property FIELD_MAPPING.md's own header claims |
| Reproducing sklearn's `RandomForestRegressor` training loop "close enough" from memory/general knowledge | Approximating hyperparameters or feature list | The exact recipe extracted above (line-verified: `n_estimators=300, max_depth=12, min_samples_leaf=3, random_state=42`, exact 33-feature list, exact preprocessing pipeline) | CONTEXT.md explicitly requires "faithfully reproduce the original recipe... not redesign it" — any deviation (even a "reasonable-looking" hyperparameter choice) breaks that faithfulness requirement and produces a different, non-reproducible artifact |

**Key insight:** almost everything this phase needs is already either directly extractable from the script (verified above) or already documented by a prior phase (FIELD_MAPPING.md). The actual net-new work is judgment calls (duplicate-version review, score-to-function assignment) and mechanical extraction/execution, not new algorithm design.

## Common Pitfalls

### Pitfall 1: Assuming the script can be run end-to-end as a script
**What goes wrong:** A snapshot-generation task tries `exec(open("impact_model_v4.1.py").read())` or similar, expecting it to "just work" against substituted DataFrames.
**Why it happens:** The file looks like a normal `.py` file at a glance; the notebook artifacts (cell markers, scattered re-imports, `display()` calls) are easy to miss without directly grepping for them.
**How to avoid:** Extract only the specific curated function definitions (plus their direct helper dependencies) into a clean characterization module; never attempt a full top-to-bottom exec of the original file. Confirmed necessary by two independent pieces of evidence: hardcoded absolute paths to files that don't exist (`pd.read_excel` at line 742+), and `display()` used before its only import (line 728 vs. 14361).
**Warning signs:** `FileNotFoundError` on `/Users/oluquadri/Downloads/...` or `NameError: name 'display' is not defined` if anyone tries a naive full-file execution.

### Pitfall 2: Treating "sklearn-trained" and "Transfer Probability" as synonyms
**What goes wrong:** Wiring the RandomForestRegressor artifact to a `/scoring/transfer-probability` endpoint in Phase 4 because CONTEXT.md's Transfer Probability section mentions sklearn and `random_state=42`.
**Why it happens:** Prior research (recorded in STATE.md/CONTEXT.md) reasonably assumed the one ML model in the file must be "the" ML-flavored score (Transfer Probability, per the "not purely deterministic" framing) — but direct inspection shows the RF model predicts fee/value, and the actual `"Transfer Probability %"` column is a separate, fully deterministic, non-ML formula.
**How to avoid:** See "Critical Finding" section above — escalate and confirm the RF artifact's correct score assignment (likely TFM) before Phase 4 wiring.
**Warning signs:** If Phase 5's parity test for "Transfer Probability" ever needs `train_test_split` reproducibility/tolerance reasoning, that's a signal the mapping was applied incorrectly, since the actual `"Transfer Probability %"` formula has zero randomness or model-fit variance to reason about.

### Pitfall 3: The defensive-column-checking silent-default bug class (CONCERNS.md-flagged)
**What goes wrong:** A column expected by a calculator (e.g. `Minutes`) is missing from the reconstructed DataFrame (because of a Django-field-name mismatch, a pivot that didn't cover every position, or genuinely missing source data), and the script's existing `if "Minutes" not in df.columns: df["Minutes"] = 0` pattern (documented in CONCERNS.md) silently zero-fills it, distorting every score that depends on `Minutes` for every affected player.
**Why it happens:** The script was written defensively against genuinely-optional input shapes (different Excel exports having different columns available), but "column truly absent from this run" and "column present with legitimately low/zero minutes" get conflated by a blanket `= 0` default.
**How to avoid:** Per CONTEXT.md's locked fix-threshold: during curation, any instance of this exact pattern (missing/absent → silently defaulted in a way that mathematically distorts a score) should be fixed to either exclude the player from that calculation or null the field, not preserved as-is. Document every such fix in the curation map (what was wrong, what changed, why) — do not silently fix.
**Warning signs:** A DataFrame-reconstruction bug (e.g. an incomplete `FIELD_MAPPING.md`-driven rename) could masquerade as "the script's fault" if this pattern isn't watched for — verify reconstructed `players_df`/`transfers_df`/`team_styles_df` column coverage explicitly (e.g. assert every column each curated calculator reads is actually present) before trusting any score output as "the oracle."

### Pitfall 4: Conflating nested-function name duplication with top-level duplicate-definition ambiguity
**What goes wrong:** Applying the escalate-if->2-definitions policy to the 3 independently-scoped local `financial_fit_label()` closures (found inside `validate_transfer_impact_with_style`, `predict_player_move_to_club`, `validate_all_transfers_with_style_and_team_penalty`) as if they were part of the same 20-name top-level inventory.
**Why it happens:** A naive `grep -n "def financial_fit_label"` (without anchoring to line-start `^def`) would find all 3 and could be mistaken for a "3-definition, must-escalate" case.
**How to avoid:** Only top-level (column-0, `^def `) function names are subject to the last-wins/escalation ambiguity — verified 20 names, listed exhaustively above. Nested/local functions are correctly scoped to their own outer function and never silently "win" over each other; they're a separate (lower-risk) code-duplication concern, not a name-collision one.
**Warning signs:** If a curation task's duplicate count comes out higher than 20 for top-level definitions, the grep pattern used probably isn't anchored correctly.

## Curation Map — Recommended Format

CONTEXT.md leaves the exact format to Claude's discretion; given the audit-trail requirement ("record BOTH the kept version and every rejected version, with a reason"), recommend a structured format over free-form prose so Phase 4/5 can programmatically or reliably manually cross-reference it:

- A Markdown table per duplicated function name: columns `Line`, `Kept? (Y/N)`, `Reason`, `Body length (lines)`, `Escalated? (Y/N)`.
- A separate section per PRD score (RMM / CS / TFM / Transfer Probability) listing: which function(s) feed it, their line numbers, whether they need whole-dataset context, and which columns they read/write (the "curation map... showing which functions/columns feed it" success criterion).
- The two escalation items (both 4-definition functions, plus this research's Transfer-Probability/TFM mapping finding) should get their own clearly flagged subsection, not buried in the per-name table, since they need explicit user sign-off before Phase 4 can proceed safely.

## Oracle Snapshot — Recommended Format

CONTEXT.md locks "flat file (CSV/Parquet), full population, versioned in repo" but leaves the exact schema to discretion.

- **Format: CSV.** No new dependency (pyarrow) required; 41,708 rows × a handful of numeric score columns per position group is trivially small (low-single-digit MB), so Parquet's compactness/dtype-preservation advantages aren't decisive here. If float-precision round-tripping through CSV becomes a real parity-testing concern in Phase 5 (e.g. `1.0` vs `1.00000000001` string-formatting drift), Parquet can be revisited then — but starting simple avoids an unnecessary new dependency in a phase that already needs to add scikit-learn/joblib.
- **One combined file, not one-per-position-group**, with a `position_group` column — simplifies Phase 5's parity-test tooling (one file to load) at negligible cost given the row count is modest either way. Recommend columns: `player_id` (Django UUID, the actual join key back to Postgres — critical, since the script itself has no stable player ID, only the `Player` name string, which per FIELD_MAPPING.md's own findings is NOT guaranteed unique), `player_name`, `main_position`, `rmm` (Player Impact), `cs`, `tfm`, `transfer_probability`, plus a `snapshot_version`/`generated_at` metadata column or a separate small manifest file recording the git commit / script version the snapshot was generated from.
- **Versioning:** given CONTEXT.md says "versioned in the repo," recommend a filename or subfolder pattern like `scoring_oracle_v1_<date>.csv` (or a `CHANGELOG`-style manifest) so Phase 5 can pin its parity test to a specific, immutable snapshot rather than "whatever's currently in the file."

## Validation Architecture

### Test Framework
| Property | Value |
|---|---|
| Framework | pytest 9.1.1 + pytest-django 4.12.0 (already installed and configured — `get-scouted-be/pyproject.toml` sets `DJANGO_SETTINGS_MODULE`, `testpaths = ["clubs", "players", "transfers", "core", "accounts"]`) |
| Config file | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`) — `testpaths` will need a new entry (e.g. `"scoring"` or wherever this phase's characterization tests live) once this phase's deliverables land |
| Quick run command | `cd get-scouted-be && .venv/bin/pytest <new-phase-3-test-path> -x -q` |
| Full suite command | `cd get-scouted-be && .venv/bin/pytest -q` |

### Phase Requirements → Test Map

This phase owns no SCORE-* requirement IDs directly, but its 4 success criteria are independently verifiable and should each have a concrete automated check:

| Success Criterion | Behavior | Test Type | Automated Command | File Exists? |
|---|---|---|---|---|
| SC-1: Every duplicated function catalogued with authoritative version identified | Curation map contains all 20 names with line numbers, kept/rejected status, reasons | unit/data-check | `pytest scoring/tests/test_curation_map.py::test_all_20_names_present -x` | ❌ Wave 0 |
| SC-2: Oracle snapshot exists, versioned, covers full population per position group | Snapshot file has 41,708 rows (or documented deviation), all position groups represented, all 4 score columns populated (non-100%-null) | integration | `pytest scoring/tests/test_oracle_snapshot.py::test_snapshot_coverage -x` | ❌ Wave 0 |
| SC-3: Non-deterministic/sklearn components identified and separated, artifact versioned | joblib artifact file exists and loads; MAE/R² recorded in curation map | unit | `pytest scoring/tests/test_transfer_value_model.py::test_artifact_loads_and_predicts -x` | ❌ Wave 0 |
| SC-4: Written curation map exists, shows functions/columns per score | Curation map document exists and has the required per-score sections | manual-only (doc-existence check can be automated trivially; content quality is a review, not an assertion) | `test -f .planning/phases/03-.../CURATION_MAP.md` (or equivalent path decided at plan time) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** run the specific new test file for that task (`pytest <file> -x -q`)
- **Per wave merge:** `pytest scoring/tests/ -q` (or wherever this phase's tests land)
- **Phase gate:** full suite green before `/gsd:verify-work`, plus manual review of the curation map's escalation items (the 2 four-definition functions + the Transfer-Probability/TFM mapping finding) since those are judgment calls no automated test can fully verify

### Wave 0 Gaps
- [ ] `scoring/` Django app (or equivalent location) doesn't exist yet — needs at minimum a `tests/` dir and `__init__.py` before any of the above tests can be written; confirm with the planner whether this phase creates a minimal `scoring/` app skeleton now (used properly starting Phase 4) or keeps characterization scripts/tests outside the Django app structure entirely (e.g. a standalone `scripts/` + `tests/` pair, given this phase does no Django porting) — CONTEXT.md leaves this to Claude's discretion ("where the training/snapshot scripts live")
- [ ] `requirements/base.txt` needs `scikit-learn` and `joblib` added, then `pip install -r requirements/base.txt` re-run in `.venv`
- [ ] No existing fixtures/conftest for scoring-domain tests — will need player/club/transfer factory fixtures or direct real-data queries (given CONTEXT.md's "full population, real data" oracle requirement, tests here likely query real migrated Phase 1 data rather than using `factory_boy`-built synthetic fixtures, unlike Phase 1/2's pattern)

## Open Questions

1. **Which artifact does the sklearn RandomForestRegressor actually feed — TFM or Transfer Probability?**
   - What we know: The RF model regresses `log_fee` (transfer fee/value), not a probability. The literal `"Transfer Probability %"` column is a separate, fully deterministic heuristic formula with no ML involved.
   - What's unclear: Whether CONTEXT.md's Transfer Probability decisions (train fresh, joblib-version, feed Phase 4+) should be re-targeted at Financial Fit (TFM) instead, and what — if anything — should replace "Transfer Probability" as the thing needing ML-artifact treatment (this research's answer: nothing does; the deterministic formula needs no ML/artifact treatment at all, just a faithful port of the arithmetic).
   - Recommendation: Escalate to the user before Phase 3 execution begins wiring the sklearn artifact to a specific PRD score name. This is a planning-blocking ambiguity, not a mid-execution judgment call — get it resolved before the phase's plan is written, so tasks are named/scoped correctly from the start.

2. **Is Compatibility Score (CS) the already-migrated legacy `PlayerClubCompatibility.score`, the script's freshly-computed role-fit score, or both?**
   - What we know: Both exist and are real, non-trivial quantities. The legacy one is already in Postgres (8.19M rows, Phase 1). The script's fresh computation needs `team_styles_df` + role-score columns and produces its own `"Compatibility Score"`.
   - What's unclear: Product intent — is CS meant to reflect "how well does this player's role-fit match this club's tactical system" (the script's fresh computation, matching ARCHITECTURE.md's `role_fit.py` service plan) or is the already-imported legacy score considered authoritative/sufficient?
   - Recommendation: Lower urgency than #1 (both paths are viable and this phase should characterize the script's role-fit logic regardless, since ARCHITECTURE.md already plans to port it), but flag in the curation map for Phase 4 planning to resolve explicitly rather than defaulting silently to one or the other.

3. **Which quantity is "RMM" for a context-free `/players/{id}/impact` endpoint — `"Player Impact"` or `"Performance Score"`?**
   - What we know: `"Player Impact"` (from `add_player_impact()`) is context-free, population-relative, non-duplicated, and matches the PRD's RMM description most directly. `"Performance Score"` is a club-target-context-dependent blend computed only inside the shortlist function.
   - What's unclear: Whether the PRD's single-number "Player Score (RMM)" shown on Player Profile / AI Shortlist pages is meant to always be context-free (this research's recommendation) or whether it's expected to already reflect shortlist/target-club context when one is selected.
   - Recommendation: Recommend `"Player Impact"` as the RMM primitive; document `"Performance Score"` as a secondary, target-club-contextual refinement available when a shortlist/matching context exists. Low urgency for Phase 3 itself (both functions should be characterized either way) but worth flagging for Phase 4's endpoint design.

4. **Exact literal `team_styles_df` column names the role-fit functions expect, vs. what Django's `Club` model currently provides.**
   - What we know: `Club` has 8 flat playing-style FloatFields with lowercase-snake names (`control_possession`, etc.); `calculate_subjective_role_fit_for_player_to_team()` (line 2446) is the consumer.
   - What's unclear: This research did not fully trace `calculate_subjective_role_fit_for_player_to_team()`'s internals or confirm its exact expected `team_styles_df` column names/shape (e.g. does it expect one row per club with 8 numeric columns, or a different structure like per-role weighted vectors built from those 8 numbers via `build_team_style_vector()`, referenced in ARCHITECTURE.md but not directly verified here).
   - Recommendation: A concrete Phase 3 planning/execution task should read lines ~2400-2726 of the script in full (the `weighted_overlap_score`/`calculate_subjective_role_fit_for_player_to_team` region) before writing the `team_styles_df` reconstruction code — this research establishes the location and the Club-model data source but doesn't fully resolve the exact shape needed.

## Sources

### Primary (HIGH confidence — direct inspection, 2026-07-21)
- `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` — full 15,747-line file; `grep -n "^def "` for the top-level duplicate inventory; targeted `Read` calls for RMM/CS/TFM/Transfer-Probability computation sites, sklearn training block, data-ingestion calls, `IPython`/`display` import ordering, `_rename_columns_safe`, `add_player_impact`, `_calc_*_impact_raw`, `get_role_scores_from_dataset`, `ROLE_COLUMNS_BY_POSITION`, `build_transfer_value_dataset`, `train_transfer_value_model`, `add_value_labels`
- `get-scouted-be/docs/FIELD_MAPPING.md` — Phase 1 deliverable, verified accurate and directly reusable for this phase's DataFrame-reconstruction step
- `get-scouted-be/players/models.py`, `get-scouted-be/clubs/models.py`, `get-scouted-be/transfers/models.py` — direct field-name verification for Player/PlayerRoleScore/PlayerClubCompatibility/Club/Transfer
- `get-scouted-be/pyproject.toml`, `get-scouted-be/requirements/base.txt`, `get-scouted-be/requirements/dev.txt`, `.venv` `pip list` output — confirmed current test framework, confirmed scikit-learn/joblib/pyarrow/openpyxl are NOT currently installed
- `pip index versions scikit-learn/joblib/openpyxl` — confirmed current PyPI versions as of 2026-07-21 (scikit-learn 1.9.0, joblib 1.5.3, openpyxl 3.1.5)
- `GetScouted PRD.docx` (converted via `textutil`) — §1.4 "Core Scoring Concepts," the authoritative product definitions of RMM/CS/TFM/Transfer Probability used to evaluate the script's candidate functions against

### Secondary (MEDIUM confidence)
- `.planning/research/ARCHITECTURE.md` — duplicate-function heuristic, no-isolated-scoring finding, Anti-Pattern 3, reusable `_calc_*_impact_raw` assets — cross-checked against and confirmed consistent with this research's direct re-verification
- `.planning/codebase/CONCERNS.md` — "Fragile Area: Complex Python Scoring Engine" section, defensive-column-checking bug class — confirmed the exact code pattern still exists in the current file (not independently re-verified line-by-line in this pass, taken as accurate given it matches this research's own observations of the script's general defensive style)
- `.planning/STATE.md` — Phase 1 decisions (PlayerRoleScore long-format row count, PlayerClubCompatibility import scale) used to inform the data-reconstruction guidance

### Tertiary (LOW confidence)
- None — all findings in this document are traceable to direct file inspection or existing verified project documents; no unverified web-search-only claims were needed for this phase's domain (it's entirely internal-codebase archaeology, not an external-library research question).

## Metadata

**Confidence breakdown:**
- Duplicate-function inventory (20 names, line numbers, def-counts): HIGH — directly verified via grep/read against the actual file, cross-checked line counts for divergence
- Script execution model (no CLI, notebook-only, hardcoded paths, display()-ordering bug): HIGH — directly verified
- Core score computation map (RMM/CS/TFM/Transfer-Probability candidate functions): MEDIUM-HIGH on "where the code is," LOW-MEDIUM on "which is definitively correct for each PRD score" — genuine ambiguities exist in the source material itself, not a research gap; flagged explicitly as Open Questions for user/planner resolution
- sklearn reproduction recipe: HIGH — every hyperparameter, feature name, and preprocessing step directly read from the file
- Data-reconstruction guidance (Django → script DataFrame shape): HIGH for Player (leans on verified FIELD_MAPPING.md), MEDIUM for Club/team_styles_df (location confirmed, exact expected shape not fully traced — Open Question 4), MEDIUM for Transfer (source columns confirmed, exact rename map not fully enumerated)
- Pitfalls: HIGH — each is either directly observed in the file or is the CONCERNS.md-flagged pattern class this phase already exists to address

**Research date:** 2026-07-21
**Valid until:** This research is tied to a specific, static, non-changing artifact (`impact_model_v4.1.py` is legacy code, not an actively-developed library) — line numbers and findings remain valid indefinitely unless the file itself is modified. Re-verify only if `impact_model_v4.1.py` changes before Phase 3 execution begins. The sklearn/joblib version pins (PyPI-latest-as-of-2026-07-21) should be re-checked if Phase 3 execution happens more than ~30 days after this research.

---
*Phase: 03-scoring-engine-curation-correctness-oracle*
*Researched: 2026-07-21*
