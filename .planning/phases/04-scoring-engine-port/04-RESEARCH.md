# Phase 4: Scoring Engine Port - Research

**Researched:** 2026-07-23
**Domain:** Django/DRF service-layer wrapping of already-ported pandas/sklearn scoring code (`scoring/characterization/*.py`) into a request-facing API
**Confidence:** HIGH (all claims below are grounded in direct reads of the actual Phase 3 code, not training-data assumptions about what it "probably" does)

## Summary

Phase 4 is pure plumbing over four already-faithful, already-tested Phase 3 modules (`impact.py`, `role_fit.py`, `deterministic_scores.py`, `tfm_model.py`) plus one bridge module (`reconstruct.py`). None of the four score-producing entry points Phase 4 needs to call (`compute_rmm_column`, `compute_cs_tp_for_pairs`, the TFM joblib `pipeline.predict`, `add_value_labels`) can be invoked for a single player/pair without first reconstructing population- or club-scale DataFrames via `reconstruct.py`'s `build_*` functions — **every one of those functions pulls the full table from Postgres with zero filtering support**. This is not a Phase 4 defect to fix; it is the exact "ship correct-but-slow" reality CONTEXT.md already locked in. Every one of Phase 4's service functions will, in the general case, look like a thin wrapper around the same reconstruct → compute → merge → slice-to-one-player sequence `generate_scoring_oracle.py` (Plan 07) already established as the canonical wiring order — reuse that ordering exactly, don't re-derive it.

The one genuinely new design decision Phase 4 must make that CONTEXT.md does **not** resolve: whether TFM's `predicted_fee` is priced using the **player's actual current club** as buying-club context (matching the oracle's methodology exactly, `Team` column unmodified) or the **requested `club_id` from the URL** as buying-club context (overriding `Team` before feature-building, matching the PRD's literal wording "realistic for a **given club's** spending profile" and giving the nested `/clubs/{club_id}/financial-fit/` URL actual computational meaning rather than just a display label). See "Open Questions" below — this needs an explicit, documented choice in the plan, not silent resolution either way.

**Primary recommendation:** Build one `scoring/services/` module per score (`rmm.py`, `compatibility.py`, `financial_fit.py`, `transfer_probability.py`, `summary.py`), each following the exact reconstruct→compute→merge→slice pattern documented below, wrapping `scoring/characterization/*.py` unmodified. Load the TFM joblib artifact via a lazy, `functools.lru_cache`-memoized module-level getter (not `AppConfig.ready()` — see rationale below). Mirror `accounts/`'s serializers.py/views.py/urls.py/permissions.py file layout and its `IsAuthenticated`-by-default posture; no new permission classes needed (base auth only, per CONTEXT.md's canonical refs).

## User Constraints

### Locked Decisions (from CONTEXT.md — copied verbatim)

- **RMM = `add_player_impact()`'s "Player Impact" output — context-free, not the club-dependent "Performance Score".** Matches the PRD's wording exactly ("an overall, position-aware performance score") and is the clean, non-duplicated function Phase 3 fully characterized. "Performance Score" is explicitly OUT of Phase 4's scope.
- **CS = the fresh role-fit computation (`deterministic_scores.compute_cs_tp_for_pairs`), not the legacy `PlayerClubCompatibility.score`.** The legacy 8.19M-row table is NOT queried by this phase's CS endpoint.
- **When a club has no playing-style data (~77% of clubs), CS returns `null` with a reason flag** — e.g. `{"compatibility_score": null, "reason": "club_style_data_unavailable"}` — never a fabricated/estimated substitute.
- **Nested resource paths** for player-vs-club scores: `GET /api/scoring/players/{id}/clubs/{club_id}/compatibility/`, `.../financial-fit/`, `.../transfer-probability/`.
- **RMM is a plain player-scoped endpoint** (no club needed): `GET /api/scoring/players/{id}/impact/` (or equivalent — exact URL name is Claude's discretion).
- **A combined summary endpoint also exists**: `GET /api/scoring/players/{id}/summary/?club_id={club_id}` returning RMM + CS + TFM + Transfer Probability together.
- **Transfer Probability also requires a club** (`.../transfer-probability/` under the same nested path as CS/TFM), NOT a standalone `/players/{id}/transfer-probability/` endpoint.
- **One shared null+reason envelope for missing-data cases across all 4 scores** — same `{"score_field": null, "reason": "..."}` pattern applies uniformly.
- **RMM breakdown**: full positive/negative components dict, exactly as produced by `add_player_impact()` / the 8 `_calc_*_impact_raw` functions' `components_dict`.
- **CS breakdown**: all 3 source components — `role_fit_score`, `similarity_pct` (flagged `null` / "requires target-player comparison pool, not characterized in Phase 3"), and `bonus`.
- **TFM breakdown**: `predicted_fee`, the actual/market-value comparison, and the `Bargain`/`Fair Value`/`Overpay` label — exactly what `add_value_labels()` produces. Do NOT expose the raw 33-feature list or per-feature importances.
- **Transfer Probability breakdown**: all 4 weighted terms individually, each with its raw value, its weight, and its resulting contribution.
- **Ship correct-but-slow. Phase 4 does NOT build caching.** No O(1) work, no demo speed ceiling — Phase 6's job (SCORE-07).

### Claude's Discretion (from CONTEXT.md)

- Exact URL naming for the RMM endpoint and the combined summary endpoint (e.g. `/impact/` vs `/rmm/` vs `/score/`)
- Whether `scoring/characterization/*.py` gets promoted/refactored directly into `scoring/services/*.py` or wrapped by a thin new `services/` layer that imports `characterization/` as-is
- Whether the TFM joblib artifact is loaded once at Django startup/module import vs lazily on first request
- Exact DRF serializer/viewset structure, pagination (not needed), and error-response status codes beyond the null+reason envelope
- Whether the combined summary endpoint internally calls the 4 per-score service functions separately or reconstructs the underlying DataFrames once and reuses them across all 4

### Deferred Ideas (OUT OF SCOPE)

- Finishing "Performance Score" (RMM's club-context-dependent variant) — needs league-wide `POSITION_METRICS` percentile machinery not yet built
- Exposing TFM's full 33-feature list / per-feature importances
- Cross-checking fresh CS against the legacy `PlayerClubCompatibility.score`
- Any O(1) caching, precomputed aggregates, Redis, or materialized tables — entirely Phase 6's scope (SCORE-07)
- Numerical parity testing against Phase 3's oracle — entirely Phase 5's scope (SCORE-06)

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| SCORE-01 | Player Score (RMM) computed via curated port, exposed via API | `impact.compute_rmm_column(players_df)` signature/shape documented below; exact wiring pattern from `generate_scoring_oracle.py` step 2 |
| SCORE-02 | Compatibility Score (CS) between player and club, exposed via API | `deterministic_scores.compute_cs_tp_for_pairs(..., club_context=<club name>)` documented below, including the null+reason case (`club_style_data_unavailable`) |
| SCORE-03 | Financial Fit (TFM), exposed via API | `tfm_model.build_oracle_player_features` + joblib `pipeline.predict` + `add_value_labels` documented below, including the confirmed log-scale unwrap and the unresolved buying-club-context fork flagged in Open Questions |
| SCORE-04 | Transfer Probability, exposed via API | Row-local `deterministic_scores.transfer_probability()` formula documented below; confirmed NOT ML (no sklearn import in that module) |
| SCORE-05 | All four scores return component breakdowns | Exact breakdown shapes for all 4 scores documented per-score below, matching CONTEXT.md's locked depth decisions |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| Django | (already pinned in project) | Web framework | Already in use project-wide |
| djangorestframework | (already pinned, `rest_framework` in `INSTALLED_APPS`) | API layer | Already the project's only API framework (`accounts/` precedent) |
| djangorestframework-simplejwt | 5.5.1 (pinned, per Phase 2) | Auth | Already the sole `DEFAULT_AUTHENTICATION_CLASSES` entry — scoring endpoints inherit this for free via `REST_FRAMEWORK`'s global `IsAuthenticated` default, no new permission class needed |
| pandas | (already installed, used throughout `scoring/characterization/`) | DataFrame plumbing | Required by every `characterization/` function signature — Phase 4 cannot avoid it |
| joblib | (already installed, Phase 3) | Load the trained TFM `Pipeline` | `scoring/ml_artifacts/tfm_value_model_v1.joblib` was written with `joblib.dump()` in `train_tfm_model.py`; `joblib.load()` is the only correct counterpart |
| scikit-learn | 1.9.0 (recorded in `.metrics.json`, must match or be compatible with the version the artifact was pickled under) | `Pipeline.predict()` for TFM | Verify installed version matches or is forward-compatible with 1.9.0 — a scikit-learn version mismatch on unpickling is a common, easy-to-miss failure mode |

**Version verification:** No new packages are needed for Phase 4 — everything it needs (`djangorestframework`, `pandas`, `joblib`, `scikit-learn`) is already installed per Phase 2/3. Before starting, confirm the installed scikit-learn version still matches (or is compatible with) `1.9.0` (the version recorded in `tfm_value_model_v1.metrics.json`'s `sklearn_version` field) — run:
```bash
python -c "import sklearn; print(sklearn.__version__)"
```
If it has drifted, either re-pin or re-run `manage.py train_tfm_model` to regenerate the artifact under the current version before Phase 4 relies on it (do NOT retrain as part of this phase otherwise — CONTEXT.md is explicit that Phase 4 loads, never retrains).

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `functools.lru_cache` (stdlib) | n/a | Memoize the loaded joblib `Pipeline` singleton | See "Architecture Patterns" below — recommended over `AppConfig.ready()` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Loading joblib artifact lazily (`lru_cache`) | Loading in `ScoringConfig.ready()` | `ready()` runs on **every** `manage.py` invocation (migrate, shell, test collection, makemigrations) — would crash every unrelated command if the artifact file is ever absent/mid-retrain, and wastes load time on commands that never touch scoring. Lazy loading defers both cost and failure to actual first use. |
| Promoting `characterization/*.py` into `services/*.py` (rename/move) | Thin `services/` wrapper importing `characterization/` unchanged | ARCHITECTURE.md's suggested structure names the directory `services/`, but CONTEXT.md explicitly leaves this to discretion. Recommend the thin-wrapper approach (below) — it keeps Phase 3's audit trail (`APPLIED_FIXES`, docstrings citing exact source line numbers) intact and undisturbed, and keeps Phase 5's parity tests importing from a stable, unmoved location. |

**Installation:** None required — all dependencies already present.

## Architecture Patterns

### Recommended Project Structure

```
scoring/
├── characterization/          # UNCHANGED — Phase 3's audit-trailed ports (do not move/rename)
│   ├── impact.py
│   ├── role_fit.py
│   ├── deterministic_scores.py
│   ├── tfm_model.py
│   └── reconstruct.py
├── services/                  # NEW — Phase 4's thin request-facing wrappers
│   ├── __init__.py
│   ├── population.py          # single place that calls reconstruct.build_* + memoizes the TFM pipeline load
│   ├── rmm.py                 # wraps impact.compute_rmm_column / add_player_impact
│   ├── compatibility.py       # wraps deterministic_scores.compute_cs_tp_for_pairs (CS half)
│   ├── transfer_probability.py# wraps deterministic_scores.compute_cs_tp_for_pairs (TP half)
│   ├── financial_fit.py       # wraps tfm_model.build_oracle_player_features + pipeline.predict + add_value_labels
│   └── summary.py             # orchestrates the above 4 for the combined endpoint
├── serializers.py              # NEW — output shape only, no computation
├── views.py                    # NEW — thin: parse params -> call services/ -> serialize
├── urls.py                     # NEW
├── exceptions.py                # NEW (optional) — shared NullWithReason envelope helper
├── ml_artifacts/                # UNCHANGED
├── docs/                        # UNCHANGED (CURATION_MAP.md etc.)
├── oracle/                      # UNCHANGED
├── management/commands/         # UNCHANGED (train_tfm_model.py, generate_scoring_oracle.py)
└── tests/
    ├── conftest.py               # UNCHANGED (real_data_available fixture)
    ├── test_impact.py            # UNCHANGED (Phase 3)
    ├── test_deterministic_scores.py  # UNCHANGED (Phase 3)
    ├── test_tfm_model.py         # UNCHANGED (Phase 3)
    ├── test_reconstruct.py       # UNCHANGED (Phase 3)
    ├── test_curation_map.py      # UNCHANGED (Phase 3)
    ├── test_oracle_snapshot.py   # UNCHANGED (Phase 3)
    ├── test_services_rmm.py      # NEW
    ├── test_services_compatibility.py  # NEW
    ├── test_services_financial_fit.py  # NEW
    ├── test_services_transfer_probability.py  # NEW
    ├── test_services_summary.py  # NEW
    └── test_views.py              # NEW — DRF APIClient-level tests for all 5 endpoints
```

### Pattern 1: The canonical reconstruct → compute → merge → slice sequence

**What:** Every one of `reconstruct.py`'s four `build_*` functions (`build_players_df`, `build_role_scores_wide`, `build_team_styles_df`, `build_transfers_df`) queries the **entire** corresponding Postgres table with **no filtering parameters at all** — confirmed by direct inspection: `build_players_df()` calls `Player.objects.select_related("club").values(*field_names, "club__name")` unconditionally, `build_transfers_df()` calls `Transfer.objects.values(...)` unconditionally, etc. There is no `player_id=` kwarg anywhere in `reconstruct.py`. Combined with `impact._build_std_lookup`'s `df.groupby(position_col)` (RMM's percentile ranking is meaningless without the full position-group population) and `compute_cs_tp_for_pairs`'s `merged.groupby("Team")[[...]].mean()` (Financial Score's squad baseline needs the full target-club roster), **every score computation Phase 4 exposes is, at minimum, an O(position-group-size) or O(club-roster-size) operation, and RMM/CS are effectively O(whole-player-population) per request** unless a future phase (6) adds caching. This is exactly what CONTEXT.md's "ship correct-but-slow" decision anticipates — do not attempt to "fix" this in Phase 4.

**When to use:** Every one of the 4 score services, and the summary orchestrator.

**Example — the exact wiring order already established and proven correct by `generate_scoring_oracle.py`** (reuse this order verbatim, just compute for the whole population and then slice to the one requested `player_id` instead of writing a CSV):

```python
# scoring/services/population.py (illustrative — not literal code to copy verbatim,
# but the sequencing below IS load-bearing and must not be reordered)
from scoring.characterization.deterministic_scores import compute_cs_tp_for_pairs
from scoring.characterization.impact import compute_rmm_column
from scoring.characterization.reconstruct import (
    build_players_df, build_role_scores_wide, build_team_styles_df, build_transfers_df,
)

def score_player(player_id, club_name: str | None):
    players_df = build_players_df()
    role_scores_wide = build_role_scores_wide()
    team_styles_df = build_team_styles_df()

    # STEP 1 — RMM must be computed and merged BEFORE compute_cs_tp_for_pairs,
    # because Performance Score (20% of Transfer Probability) requires it as
    # a required, non-optional argument (deterministic_scores.py raises
    # ValueError if player_impact is None).
    rmm = compute_rmm_column(players_df)
    players_df["player_impact"] = players_df["player_id"].map(rmm)

    # STEP 2 — club_context=<resolved club NAME string>, not the club's UUID.
    # team_styles_df["Team"] matching is by Club.name (case/whitespace-
    # insensitive per calculate_subjective_role_fit_for_player_to_team).
    cs_tp = compute_cs_tp_for_pairs(
        players_df, team_styles_df, role_scores_wide,
        club_context=club_name,   # None => each player scored vs their OWN club
        player_impact=rmm,
    )
    # STEP 3 — slice to the one requested player_id; cs_tp is indexed by player_id.
    row = cs_tp.loc[player_id] if player_id in cs_tp.index else None
    return rmm.get(player_id), row
```

### Pattern 2: club_id resolution — pass a NAME, not a UUID, into `characterization/`

**What:** Nothing in `role_fit.py` / `deterministic_scores.py` accepts a club UUID. `calculate_subjective_role_fit_for_player_to_team(player_row, target_team: str, team_styles_df)` matches on `team_styles_df["Team"].str.strip().str.lower() == target_team.strip().lower()`, and `team_styles_df["Team"]` is populated from `Club.name` (see `reconstruct._CLUB_STYLE_RENAME = {"name": "Team", ...}`). `compute_cs_tp_for_pairs`'s `club_context` parameter is the same string-keyed contract.

**When to use:** Every service function that takes a `club_id` URL kwarg must first do `club = Club.objects.get(id=club_id)` (raising 404 via DRF's standard `get_object_or_404` if not found) and pass `club.name` as the string into `characterization/` functions — never the UUID.

### Pattern 3: RMM breakdown extraction — read `Impact Comp - *` columns, don't recompute

**What:** `add_player_impact(df)` (called internally by `compute_rmm_column`) already attaches a `components_df` (the position-specific `_calc_*_impact_raw`'s 4th return value, `components_dict`) to the scored DataFrame with an `"Impact Comp - "` column prefix (see `impact.py` lines 1015-1019: `components_df.add_prefix("Impact Comp - ")` then `pd.concat`). It also carries `"Player Impact Positive"` and `"Player Impact Negative"` (the two top-level positive/negative sums each `_calc_*_impact_raw` returns). **`compute_rmm_column` itself discards all of this** — its return contract is a bare `pd.Series` of just the final `"Player Impact"` value, per its own docstring ("Thin wrapper... just player_id -> RMM"). **Phase 4's RMM service must NOT call `compute_rmm_column`** if it needs the breakdown — it must call `add_player_impact(players_df)` directly (the full DataFrame-returning function) and read the `"Player Impact Positive"`, `"Player Impact Negative"`, and every `"Impact Comp - *"` column for the target player's row. Component names differ per position (e.g. GK has `shot_stopping`/`command`/`distribution`/`buildup_support`; CB has `defensive_actions`/`duel_dominance`/`aerial`/`reading`/`buildup`) — the breakdown response shape is inherently position-dependent, which is faithful to the source, not a Phase 4 invention.

**When to use:** RMM endpoint and the RMM portion of the summary endpoint.

**Example — position-keyed component names (from direct inspection of `impact.py`), for the planner's awareness when shaping the RMM breakdown serializer:**

| Position | `return_components` dict keys |
|----------|-------------------------------|
| GK | `shot_stopping`, `command`, `distribution`, `buildup_support` |
| CB | `defensive_actions`, `duel_dominance`, `aerial`, `reading`, `buildup` |
| LB/RB | `defending`, `progression`, `chance_creation`, `control`, `duel_work` |
| CM | `ball_progression`, `control`, `creation`, `ball_winning`, `carrying` |
| DMF | `ball_winning`, `control`, `progression`, `distribution`, `creation` |
| AMF | `creation`, `final_third_progression`, `scoring_threat`, `carrying`, `connection` |
| LW/RW | `dribbling`, `creation`, `threat`, `progression`, `duel_value` |
| CF | `finishing`, `box_threat`, `chance_creation`, `progression`, `duel_value` |

These sub-components are themselves weighted sums of raw std-lookup percentiles (0-100 scale each), not final 0-100 scores — the "breakdown" the API exposes is these named intermediate values plus the top-level `positive`/`negative` totals, matching CONTEXT.md's "full positive/negative breakdown" instruction.

### Pattern 4: TFM feature-column contract comes from `.metrics.json`, AND the raw prediction is log-scale (CONFIRMED)

**What:** `train_transfer_value_model`'s `feature_cols` list in `tfm_model.py` names 33 nominal features, but the **actually-fitted** pipeline only used the subset that survived `build_transfer_value_dataset`'s merges (some, like `club_avg_in_fee`/`to_league_weight`/`domestic_move`/`best_role`/`squad_role`, were dropped — either absent from real data or lost to the source's own documented `_x`/`_y` merge-suffix collision, per `tfm_model.py`'s docstring). The **authoritative, must-match-exactly** feature list actually used by the fitted `Pipeline.predict()` is recorded in `scoring/ml_artifacts/tfm_value_model_v1.metrics.json`'s `"feature_cols"` array (23 entries, verified by direct read): `age, age_squared, u23_flag, prime_age_flag, older_flag, minutes_played, market_value, contract_years_left, performance_score, compatibility_score, player_impact, role_pct, from_league_weight, mv_to_fee_ratio, is_loan, seller_hist_avg_out_fee, seller_hist_max_out_fee, seller_hist_median_out_fee, seller_hist_count_out, seller_hist_avg_out_age, club_pos_avg_in_fee, club_pos_avg_out_fee, position`.

**CONFIRMED (verified against real data, not just inferred from code):** `pipeline.predict(X)` returns a **log-scale** value (`log1p(fee)`), matching how `train_transfer_value_model` fit against `y = np.log1p(actual_fee)`. This was verified directly by reading `scoring/oracle/scoring_oracle_v1_2026-07-22.csv`'s `tfm` column (the exact output of the same `pipeline.predict(X)` call this phase must replicate): across all 41,708 real players, `tfm` ranges from **13.11 to 17.09** with a median of **14.25** — these are not plausible Euro transfer fees (which would be in the thousands-to-hundreds-of-millions range); they are exactly the magnitude `np.log1p(fee)` produces for realistic fees (e.g. `np.log1p(3_000_000) ≈ 14.9`, `np.log1p(50_000_000) ≈ 17.7`). **`generate_scoring_oracle.py`'s oracle-generation code stores this log-scale value directly with no `np.expm1()` unwrap — meaning the committed oracle CSV's `tfm` column is itself log-scale, not money-scale.** Phase 4's API contract, per CONTEXT.md, must return `predicted_fee` as a monetary figure (for direct comparison against `Market value` and to produce a sensible `Bargain`/`Fair Value`/`Overpay` verdict) — **Phase 4's service code MUST apply `np.expm1()` to `pipeline.predict(X)`'s raw output before treating it as `predicted_fee`**, even though the existing oracle CSV does not do this. This is a deliberate, documented divergence from the oracle's literal column values (the oracle's `tfm` is log-scale; Phase 4's API `predicted_fee` is money-scale) — flag this for Phase 5's parity-testing plan to be aware of (it will need its own `np.expm1()` or `np.log1p()` conversion when diffing Phase 4's production values against the oracle's `tfm` column, not a direct value comparison).

**When to use:** Any TFM prediction call.

**Example — verbatim pattern already proven in `generate_scoring_oracle.py`, WITH the required `np.expm1()` fix applied:**
```python
# Source: get-scouted-be/scoring/management/commands/generate_scoring_oracle.py lines 111-136, 190-210
# (feature-loading and prediction plumbing is verbatim-reusable; the np.expm1()
# unwrap below is Phase 4's own addition -- the oracle generator does NOT do this)
pipeline = joblib.load(artifact_path)
with open(metrics_path) as f:
    tfm_metrics = json.load(f)
feature_cols = tfm_metrics.get("feature_cols", [])

oracle_features = build_oracle_player_features(players_df, transfers_df)
missing_feature_cols = [c for c in feature_cols if c not in oracle_features.columns]
for c in missing_feature_cols:
    oracle_features[c] = np.nan

X = oracle_features[feature_cols]
predicted_log_fee = pd.Series(pipeline.predict(X), index=oracle_features.index)
predicted_fee = np.expm1(predicted_log_fee)  # REQUIRED unwrap -- confirmed via oracle CSV inspection
# Never fabricate a fee for a player with no resolvable club context:
predicted_fee = predicted_fee.where(oracle_features["_has_club_context"], np.nan)
```

### Anti-Patterns to Avoid

- **Calling `compute_rmm_column` when a breakdown is needed:** loses the components entirely — call `add_player_impact(players_df)` directly instead (Pattern 3).
- **Passing club UUIDs into `characterization/` functions:** they only understand `Club.name` strings (Pattern 2).
- **Recomputing scoring math inline in `views.py` or `serializers.py`:** ARCHITECTURE.md's Anti-Pattern 1 — applies unchanged to Phase 4; views parse/delegate/serialize only.
- **Re-deriving TFM's feature list from `train_transfer_value_model`'s nominal 33-name list instead of the fitted artifact's `.metrics.json`:** will silently pass columns the fitted pipeline's `ColumnTransformer` was never fit on, causing either a `sklearn` error or (worse) silently-wrong predictions depending on sklearn version behavior for unseen columns.
- **Treating `pipeline.predict(X)`'s raw output as already money-scale:** confirmed false — see Pattern 4. Skipping the `np.expm1()` unwrap produces a `predicted_fee` in the 13-17 range instead of millions of Euros.
- **Loading the joblib artifact inside the request-handling `views.py`/`services/` function body itself, every call:** wastes real deserialization time per request. Even without full O(1) caching (Phase 6's job), memoizing the *artifact load itself* (a pure I/O/deserialization cost, not a "cache the computed score" concern) is squarely within Phase 4's own scope and not something CONTEXT.md's "no caching" decision forbids — it forbids caching *computed scores/aggregates*, not basic "don't re-deserialize a 300-tree RandomForest on every HTTP request" hygiene.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Null/reason envelope shape | A bespoke per-score "missing data" response format | One shared serializer/mixin producing `{"<field>": null, "reason": "<code>"}` | CONTEXT.md explicitly locks one shared shape across all 4 scores — a bespoke-per-score shape would violate this and burden the frontend with 4 different conventions |
| Club name resolution for `characterization/` calls | Ad-hoc string matching per service module | One shared `resolve_club_name(club_id) -> str` helper (thin `Club.objects.get(id=...).name` wrapper, 404 via `get_object_or_404`) | Every one of the 3 club-paired endpoints (CS/TFM/TP) needs the identical UUID→name resolution; duplicating it 3x invites drift |
| TFM feature-column filtering + log-scale unwrap | Hardcoding the 23 (or 33) feature names inline in a service module, or forgetting the `np.expm1()` unwrap | Read `feature_cols` from `tfm_value_model_v1.metrics.json` at load time (Pattern 4); always unwrap `pipeline.predict()`'s output with `np.expm1()` before treating it as a monetary value | The feature list is an artifact of what actually survived training's merges — hardcoding it duplicates a fact that already lives in a versioned sidecar file and will drift if the artifact is ever retrained; the log-scale unwrap is easy to miss since the existing oracle generator doesn't do it either (it doesn't need to for parity purposes; Phase 4's API contract does) |

**Key insight:** Nearly everything Phase 4 needs already exists in `characterization/*.py` or `reconstruct.py` — the entire phase is about correct sequencing/wiring (population reconstruct → RMM → CS/TP → TFM, in that exact order) and correct extraction (which DataFrame columns carry the breakdown, and which scale they're on), not new algorithmic work.

## Common Pitfalls

### Pitfall 1: Forgetting the RMM-before-CS/TP merge-order dependency

**What goes wrong:** Calling `compute_cs_tp_for_pairs` before `player_impact` has been merged onto `players_df` raises `ValueError: compute_cs_tp_for_pairs: player_impact is required` (the function explicitly guards this — it will not silently proceed).
**Why it happens:** It's tempting to treat the 4 scores as 4 independent, parallelizable service calls since they're 4 separate API endpoints — but Performance Score (used inside Transfer Probability) has a hard, enforced dependency on RMM being computed first.
**How to avoid:** Every service function that needs CS, Performance Score, or Transfer Probability must compute RMM first (even the standalone CS endpoint, if it wants Financial Score / Performance Score-dependent Transfer Probability alongside it) — reuse the `population.py` helper's step ordering (Pattern 1) everywhere, never reimplement this sequencing per-endpoint.
**Warning signs:** A `ValueError` raised from deep inside `compute_cs_tp_for_pairs` on any CS/TP-touching endpoint.

### Pitfall 2: Treating `compute_cs_tp_for_pairs`'s `club_context` as per-row instead of global-to-the-call

**What goes wrong:** `compute_cs_tp_for_pairs(players_df, ..., club_context=X)` evaluates **every row in `players_df`** against the **same** club `X` when `club_context` is not `None` (see the loop: `target_team = club_context if club_context is not None else row.get("Team")`). It is not possible to ask "player A vs club X, player B vs club Y" in one call.
**Why it happens:** The function signature reads like a generic "pairs" batch API, but it's actually "one club, N players" (a shortlist-generation primitive), not "N arbitrary pairs."
**How to avoid:** For a single player-vs-single-club API request this is fine — call once with `club_context=<the one club>`, then slice to the one `player_id`. Do not try to batch multiple *different* player-club pairs through one call.
**Warning signs:** None directly (this will just silently produce a working-but-wasteful call unless someone tries to misuse it for a batch-of-mixed-pairs use case).

### Pitfall 3: NaN Role Fit Score must force `compatibility_score` to NaN, not fall through to the bonus-only average

**What goes wrong:** `role_fit.compatibility_score(role_fit_score, similarity_pct, bonus)` is a pure `_avg_non_null([...])` — if `role_fit_score` is `NaN` and `similarity_pct` is always `NaN` (Phase 3's documented scope gap), a naive call would silently average just `bonus` (70.0 or 100.0), producing a confident-looking-but-meaningless CS value for a club with no style data.
**Why it happens:** `compute_cs_tp_for_pairs` already guards this correctly (`if pd.isna(role_fit_info.get("Role Fit Score", np.nan)): compat_val = np.nan`) — the risk is only if Phase 4's service code bypasses `compute_cs_tp_for_pairs` and calls `role_fit.compatibility_score` directly without replicating this guard.
**How to avoid:** Always go through `compute_cs_tp_for_pairs` for CS, never call `role_fit.compatibility_score` directly from `services/`.
**Warning signs:** A CS value returned for a club known (from `Club.objects` inspection) to have all-NaN `STYLE_COLUMNS`.

### Pitfall 4: `predicted_fee` log-scale vs money-scale mismatch (CONFIRMED real risk, not hypothetical)

**What goes wrong:** Returning `pipeline.predict(X)`'s raw log-scale output (typically 13-17, per the confirmed oracle CSV range) directly as `predicted_fee`, instead of applying `np.expm1()` first — producing a nonsensical "€14.25 predicted fee" instead of a realistic multi-million-Euro figure.
**Why it happens:** The existing, precedent-setting `generate_scoring_oracle.py` does NOT apply `np.expm1()` at its `pipeline.predict()` call site, and it's the most obvious code to copy from — but its `tfm` oracle column is legitimately log-scale (fine for a raw data snapshot; Phase 5 can convert as needed for parity comparisons), whereas Phase 4's API response must be money-scale per CONTEXT.md's breakdown spec (`predicted_fee`, compared directly against `Market value`).
**How to avoid:** Always wrap `pipeline.predict(X)`'s output in `np.expm1()` before naming it `predicted_fee` in any Phase 4 service/response. Add a unit test asserting `predicted_fee` values are in a realistic money range (e.g. `> 1000`) for a known real player, not a 0-20 range.
**Warning signs:** A `predicted_fee` field with values clustered between roughly 10 and 20 in test output.

### Pitfall 5: `assert_columns_present` raising `ValueError` is a feature, not a bug to work around

**What goes wrong:** A developer catches/suppresses the `ValueError` from `assert_columns_present` (used throughout `reconstruct.py` and `impact.py`'s `_ensure_minutes`) thinking it's a transient error, silently degrading the response instead.
**Why it happens:** DRF views conventionally want to return a clean 4xx/5xx instead of an unhandled 500 traceback, tempting a broad `try/except Exception`.
**How to avoid:** Let `ValueError` from the `characterization/`/`reconstruct/` layer propagate as a genuine 500 (or map it explicitly and loudly to a 503/500 with a clear message) — these exceptions exist specifically so a reconstruction bug fails loudly (per `reconstruct.py`'s own module docstring: "so a reconstruction bug... surfaces as a loud `ValueError`, not a silently zero-filled/NaN score"). Do not convert this into a null+reason envelope response — the null+reason envelope is for legitimate **missing input data** (no club style, no transfer history), not for **reconstruction bugs**.
**Warning signs:** Any test asserting a 200 response with a null+reason envelope for a scenario that should actually be a hard error (e.g., a genuinely broken DB state).

## Code Examples

### RMM with breakdown, single player

```python
# Source: derived from scoring/characterization/impact.py's add_player_impact
# (lines 916-1039) and reconstruct.build_players_df — NOT copy-paste ready,
# illustrates the required call shape.
from scoring.characterization.impact import add_player_impact
from scoring.characterization.reconstruct import build_players_df

def get_rmm_with_breakdown(player_id):
    players_df = build_players_df()
    scored = add_player_impact(players_df)   # NOT compute_rmm_column -- need components
    row = scored[scored["player_id"] == player_id]
    if row.empty:
        raise Http404
    row = row.iloc[0]
    comp_cols = [c for c in scored.columns if c.startswith("Impact Comp - ")]
    return {
        "rmm": row["Player Impact"] if pd.notna(row["Player Impact"]) else None,
        "positive": row["Player Impact Positive"],
        "negative": row["Player Impact Negative"],
        "components": {
            c.removeprefix("Impact Comp - "): row[c] for c in comp_cols if pd.notna(row[c])
        },
        "reliability": row["Impact Reliability"],
    }
```

### Compatibility Score with null+reason envelope

```python
# Source: derived from scoring/characterization/deterministic_scores.compute_cs_tp_for_pairs
def get_compatibility(player_id, club_id):
    club = get_object_or_404(Club, id=club_id)
    players_df = build_players_df()
    role_scores_wide = build_role_scores_wide()
    team_styles_df = build_team_styles_df()

    rmm = compute_rmm_column(players_df)
    players_df["player_impact"] = players_df["player_id"].map(rmm)

    cs_tp = compute_cs_tp_for_pairs(
        players_df, team_styles_df, role_scores_wide,
        club_context=club.name, player_impact=rmm,
    )
    if player_id not in cs_tp.index or pd.isna(cs_tp.loc[player_id, "compatibility_score"]):
        return {"compatibility_score": None, "reason": "club_style_data_unavailable"}
    row = cs_tp.loc[player_id]
    return {
        "compatibility_score": row["compatibility_score"],
        "components": {
            "role_fit_score": None,  # re-derive from calculate_subjective_role_fit_for_player_to_team if breakdown needs the raw pre-average value
            "similarity_pct": None,  # ALWAYS None -- Phase 3 scope gap, per CONTEXT.md
            "bonus": None,           # same caveat -- compute_cs_tp_for_pairs doesn't expose bonus on its return DataFrame; must call role_fit functions directly if the raw 3 components are required in the breakdown
        },
    }
```
**Important gap surfaced by writing this example:** `compute_cs_tp_for_pairs`'s returned DataFrame only exposes the final `compatibility_score`, **not** the 3 raw pre-average components (`role_fit_score`, `similarity_pct`, `bonus`) CONTEXT.md's breakdown decision requires. To get those 3 raw values, the CS service must **also** call `calculate_subjective_role_fit_for_player_to_team` and `get_player_own_best_role` directly (both already imported by `deterministic_scores.py`, so they're available), replicating the same `bonus` computation logic `compute_cs_tp_for_pairs` does internally (lines 380-388 of `deterministic_scores.py`) rather than being able to read it off `compute_cs_tp_for_pairs`'s output. This is straightforward (both functions are pure, cheap, row-local given the already-reconstructed `team_styles_df`) but is not a "just read a column" operation — flag this for the plan's task breakdown.

### Transfer Probability full breakdown

```python
# Source: scoring/characterization/deterministic_scores.py's transfer_probability
# formula (0.30/0.20/0.20/0.30 weights) -- reconstructing the breakdown requires
# reading compute_cs_tp_for_pairs's row AND reapplying the same weights, since
# transfer_probability() itself only returns the final float, not per-term contributions.
WEIGHTS = {"compatibility": 0.30, "performance": 0.20, "financial": 0.20, "contract_fit": 0.30}

def build_tp_breakdown(row):
    raw = {
        "compatibility": row["compatibility_score"],
        "performance": row["performance_score"],
        "financial": row["financial_score"],
        "contract_fit": row["contract_fit"] * 100,  # contract_fit is 0-1 scale; others are 0-100
    }
    return {
        term: {
            "raw": raw[term],
            "weight": WEIGHTS[term],
            "contribution": round(raw[term] * WEIGHTS[term], 2) if pd.notna(raw[term]) else None,
        }
        for term in WEIGHTS
    }
```
Note `contract_fit` is on a 0-1 scale (per `contract_fit()`'s own docstring: `1.0`/`0.7`/`0.4`/`0.1`/`0.5`) while `compatibility_score`/`performance_score`/`financial_score` are 0-100 — the formula itself (`transfer_probability()`) already accounts for this scale difference internally (`0.30 * contract_fit_value` with no `/100.0`, vs `0.30 * (compatibility_score_value / 100.0)` for the others). A breakdown that shows "raw value, weight, contribution" per CONTEXT.md's spec must decide whether to display `contract_fit`'s raw value as `0.1-1.0` (matching the function's actual internal scale) or `x100` for visual consistency with the other 3 terms (as illustrated above) — either is defensible; document the choice.

## State of the Art

Not directly applicable — this is an internal-code-wrapping phase, not a "pick the current best library" research question. No external library version churn is relevant; `characterization/*.py` is a locked, already-tested Phase 3 artifact that Phase 4 must not modify.

## Open Questions

1. **Does the requested `club_id` in `/players/{id}/clubs/{club_id}/financial-fit/` change the TFM prediction, or only annotate it?**
   - What we know: `build_oracle_player_features` (the oracle's TFM feature-engineering function) keys all club-aggregate features (`club_pos_avg_in_fee`, `seller_hist_avg_out_fee`, etc.) off `players_df["Team"]` — the player's **actual current club** from Postgres, always used as both buying- and selling-club context (documented rationale: "there is no real transfer event for a player who isn't actually moving"). Nothing in `tfm_model.py` accepts an override "evaluate as if buying club were X."
   - What's unclear: CONTEXT.md's TFM section doesn't explicitly say whether `club_id` should override this buying-club context (pricing "what would THIS club pay for this player") or be purely informational (just echoing the oracle's own-club prediction alongside a club label). The PRD wording in canonical_refs — "whether a player's market value and transfer cost are realistic for a **given club's** spending profile" — leans toward `club_id` being computationally meaningful, not decorative.
   - Recommendation: the plan should make an **explicit choice and document it**. Two defensible options: (a) override `players_df["Team"]` = the requested club's name before calling `build_oracle_player_features`, so the club-aggregate features reflect the *target* club's historical buy profile — this makes `club_id` meaningful and matches the PRD's literal wording, but will diverge from the Phase 3 oracle's own-club-context values whenever `club_id != player's actual club` (acceptable — Phase 5's parity testing is presumably against own-club predictions only); or (b) always use the player's actual club (matching the oracle exactly for guaranteed future parity, treating `club_id` as informational only). **Recommend (a)** given the PRD wording and the nested-URL shape's clear "pairing" intent, but this is a genuine judgment call for the plan to make explicitly, not silently default either way.

2. **TFM log-scale unwrap — RESOLVED during this research pass (not left open).** Verified directly against `scoring/oracle/scoring_oracle_v1_2026-07-22.csv`: the `tfm` column ranges 13.11-17.09 (median 14.25) across all 41,708 real players — definitively log-scale (`log1p(fee)`), not money-scale. Phase 4's service code must apply `np.expm1()` to `pipeline.predict(X)`'s output before treating it as `predicted_fee`. See Pattern 4 / Pitfall 4 above. Flagged here only so the plan explicitly assigns a task/acceptance-criterion to this unwrap (it's easy to silently omit by copy-pasting `generate_scoring_oracle.py`'s pattern verbatim, which does NOT do this unwrap).

3. **Does the CS/TP breakdown need the raw `role_fit_score`/`bonus` components, requiring a second call beyond `compute_cs_tp_for_pairs`?**
   - What we know: `compute_cs_tp_for_pairs`'s returned DataFrame only carries the final `compatibility_score`, not the 3 raw pre-average terms. CONTEXT.md's locked breakdown decision requires showing `role_fit_score`, `similarity_pct` (always null), and `bonus` individually.
   - What's unclear: whether the plan should modify `compute_cs_tp_for_pairs`'s return contract to also expose these (touching a Phase 3 file, which CONTEXT.md/ARCHITECTURE.md both discourage re-deriving) versus having the CS service call `calculate_subjective_role_fit_for_player_to_team` + `get_player_own_best_role` a second time (redundant computation, but zero changes to Phase 3's tested code).
   - Recommendation: call the two underlying functions a second time from `services/compatibility.py` rather than modifying `deterministic_scores.py` — the redundant computation is cheap (both are row-local given already-reconstructed `team_styles_df`) and keeps Phase 3's characterization modules byte-for-byte unmodified, which both CONTEXT.md ("do not re-derive scoring logic") and Phase 5's future parity-testing needs favor.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django (already configured) |
| Config file | `get-scouted-be/pyproject.toml` `[tool.pytest.ini_options]` — `DJANGO_SETTINGS_MODULE = "config.settings.local"`, `testpaths` includes `"scoring"` |
| Quick run command | `cd get-scouted-be && python -m pytest scoring/tests/test_services_rmm.py -x` (per-file, fast synthetic-fixture tests) |
| Full suite command | `cd get-scouted-be && python -m pytest scoring -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|-------------|
| SCORE-01 | RMM returned via API with real computed value | integration (DRF `APIClient`, real or synthetic DB data) | `python -m pytest scoring/tests/test_views.py::test_rmm_endpoint_returns_real_score -x` | ❌ Wave 0 |
| SCORE-01 | RMM service function returns correct breakdown shape | unit (synthetic fixture, no DB) | `python -m pytest scoring/tests/test_services_rmm.py -x` | ❌ Wave 0 |
| SCORE-02 | CS returned via API for a player-club pair | integration | `python -m pytest scoring/tests/test_views.py::test_compatibility_endpoint -x` | ❌ Wave 0 |
| SCORE-02 | CS null+reason envelope for club with no style data | unit/integration | `python -m pytest scoring/tests/test_services_compatibility.py::test_null_reason_for_missing_club_style -x` | ❌ Wave 0 |
| SCORE-03 | TFM returned via API with predicted_fee (money-scale) + value verdict | integration | `python -m pytest scoring/tests/test_views.py::test_financial_fit_endpoint -x` | ❌ Wave 0 |
| SCORE-03 | TFM feature_cols match `.metrics.json` sidecar exactly; predicted_fee is money-scale (`np.expm1` applied) | unit | `python -m pytest scoring/tests/test_services_financial_fit.py::test_feature_cols_match_artifact_sidecar test_services_financial_fit.py::test_predicted_fee_is_money_scale_not_log_scale -x` | ❌ Wave 0 |
| SCORE-04 | Transfer Probability returned via API with all 4 weighted terms | integration | `python -m pytest scoring/tests/test_views.py::test_transfer_probability_endpoint -x` | ❌ Wave 0 |
| SCORE-05 | Every score response includes a breakdown (not just a final number) | unit, one assertion per score service | `python -m pytest scoring/tests/test_services_*.py -k breakdown -x` | ❌ Wave 0 |
| (cross-cutting) | Unauthenticated requests to any scoring endpoint are rejected | integration | `python -m pytest scoring/tests/test_views.py::test_endpoints_require_authentication -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** run the specific new `scoring/tests/test_services_*.py` / `test_views.py` file touched by that task
- **Per wave merge:** `python -m pytest scoring -x` (full suite, including Phase 3's existing characterization tests — Phase 4 must not regress them)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `scoring/tests/test_services_rmm.py` — covers SCORE-01, SCORE-05 (RMM breakdown)
- [ ] `scoring/tests/test_services_compatibility.py` — covers SCORE-02, SCORE-05 (CS breakdown + null+reason envelope)
- [ ] `scoring/tests/test_services_financial_fit.py` — covers SCORE-03, SCORE-05 (TFM breakdown, feature_cols contract test against `.metrics.json`, money-scale unwrap regression test)
- [ ] `scoring/tests/test_services_transfer_probability.py` — covers SCORE-04, SCORE-05 (4-term weighted breakdown)
- [ ] `scoring/tests/test_services_summary.py` — covers the combined summary endpoint's service orchestration
- [ ] `scoring/tests/test_views.py` — DRF `APIClient`-level integration tests for all 5 endpoints, plus the shared "requires authentication" cross-cutting test
- [ ] No new pytest fixtures/framework install needed — `scoring/tests/conftest.py`'s `real_data_available` fixture (Phase 3) is directly reusable for any Phase 4 test that needs a real migrated player/club; synthetic-fixture-only tests (most of the breakdown/shape assertions) don't need it at all, following `test_deterministic_scores.py`'s existing pattern of hand-built `pd.Series`/`pd.DataFrame` fixtures requiring no DB access

## Sources

### Primary (HIGH confidence — direct code/data inspection)
- `get-scouted-be/scoring/characterization/impact.py` — full file read; `add_player_impact`, `compute_rmm_column`, all 8 `_calc_*_impact_raw` signatures/returns, component-column naming
- `get-scouted-be/scoring/characterization/role_fit.py` — full file read; `calculate_subjective_role_fit_for_player_to_team`, `compatibility_score`, `get_player_own_best_role` signatures/returns
- `get-scouted-be/scoring/characterization/deterministic_scores.py` — full file read; `compute_cs_tp_for_pairs`, `transfer_probability`, `financial_score`, `performance_score`, `contract_fit` signatures/returns, confirmed zero sklearn import
- `get-scouted-be/scoring/characterization/tfm_model.py` — full file read; `build_transfer_value_dataset`, `train_transfer_value_model`, `build_oracle_player_features`, `add_value_labels` signatures/returns, feature-column handling
- `get-scouted-be/scoring/characterization/reconstruct.py` — full file read; confirmed zero filtering parameters on any `build_*` function
- `get-scouted-be/scoring/management/commands/generate_scoring_oracle.py` — full file read; the canonical reconstruct→RMM→CS/TP→TFM wiring order, confirmed authoritative by direct execution precedent
- `get-scouted-be/scoring/management/commands/train_tfm_model.py` — full file read; confirms identical merge-order pattern
- `get-scouted-be/scoring/ml_artifacts/tfm_value_model_v1.metrics.json` — full file read; authoritative 23-entry `feature_cols` list, `sklearn_version: 1.9.0`
- `get-scouted-be/scoring/oracle/scoring_oracle_v1_2026-07-22.csv` — directly queried (Python/csv) the full `tfm` column across all 41,708 rows (min 13.11, max 17.09, median 14.25) — definitively confirmed the log-scale-vs-money-scale question rather than leaving it a guess
- `get-scouted-be/accounts/urls.py`, `views.py`, `permissions.py` — full file reads; DRF wiring conventions (thin views, `AllowAny` overrides, router pattern) this phase should mirror
- `get-scouted-be/config/settings/base.py` — full file read; confirmed `REST_FRAMEWORK` global `IsAuthenticated`+`JWTAuthentication` defaults apply automatically to any new scoring view with no extra permission class needed
- `get-scouted-be/config/urls.py` — confirmed current state (`accounts.urls` only), Phase 4 must add the `scoring.urls` include
- `get-scouted-be/players/models.py`, `clubs/models.py` — confirmed UUID primary keys on both `Player` and `Club`
- `get-scouted-be/scoring/tests/conftest.py`, `test_impact.py`, `test_deterministic_scores.py` — full/partial reads; existing Phase 3 test patterns (synthetic-fixture unit tests + `real_data_available`-gated DB tests) Phase 4's new tests should follow
- `get-scouted-be/pyproject.toml` — confirmed pytest configuration and test command
- `.planning/research/ARCHITECTURE.md` — full file read; service-layer pattern, hybrid caching pattern (Phase 6, NOT this phase), anti-patterns, recommended `scoring/` structure
- `.planning/phases/03-scoring-engine-curation-correctness-oracle/03-.../CURATION_MAP.md` — full file read; master per-score function/column map, cross-score data-flow dependencies, resolved TFM/Transfer-Probability mapping
- `.planning/phases/04-scoring-engine-port/04-CONTEXT.md` — full file read; all locked decisions and discretion areas

### Secondary (MEDIUM confidence)
None needed — this phase's research was entirely groundable in direct code/config/data inspection; no external web sources were required or consulted.

### Tertiary (LOW confidence)
None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, everything already installed and pinned by Phase 2/3
- Architecture: HIGH — every pattern is grounded in direct reads of the actual functions being wrapped, not inferred
- Pitfalls: HIGH — each pitfall traces to a specific, quoted line/behavior in the actual Phase 3 code; the log-scale pitfall is additionally confirmed against real oracle data, not just code inspection
- Open Questions (club_id's computational meaning for TFM, CS breakdown's second-call requirement): MEDIUM — these are real, unresolved forks correctly surfaced rather than guessed at, requiring an explicit product/planning decision as the next step

**Research date:** 2026-07-23
**Valid until:** No expiry concern — this research is grounded in this repository's own already-committed, stable Phase 3 code and data, not external library versions that could drift. Re-validate only if `scoring/characterization/*.py` or the TFM artifact are regenerated/retrained before Phase 4 planning begins.
