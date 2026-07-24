# Phase 5: Scoring Parity Testing - Research

**Researched:** 2026-07-24
**Domain:** Django/pandas numerical parity testing against a CSV oracle snapshot (pytest + pytest-django, real migrated data)
**Confidence:** HIGH (all claims below verified directly against the actual codebase and a live run against the real 41,708-player dev DB, not training-data assumptions)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Computation strategy at scale — Two-tier approach:**
1. **Full-population numeric parity** (all ~41,708 players) runs via the same bulk path `generate_scoring_oracle.py` used: `reconstruct_population()` + `score_population()` / `compute_cs_tp_for_pairs` called once over the whole DataFrame, not per-player. This is the only feasible way to check the full population — each Phase 4 per-request service call (`get_compatibility`, etc.) does its own ~80s population reconstruction, so 41,708 individual calls is on the order of days, not viable for a repeatable test suite.
2. **Small API/service-layer sample** (~30 players, stratified to include at least a few from each position group) is run through the *real* per-request service functions (`get_rmm`, `get_compatibility`, `get_financial_fit`, `get_transfer_probability`, `get_summary`) and, for at least a handful, the actual DRF endpoints — compared against the same oracle rows. This exists specifically to catch wiring bugs in the per-request path (Phase 4 already had one real bug here: the CS breakdown's `role_scores_wide` merge) that the bulk path alone cannot detect.
- **Why not pure bulk-only:** would miss exactly the class of bug Phase 4 already proved can happen (per-request wiring diverging from the bulk path).
- **Why not full per-request replay:** ~80s × 41,708 ≈ 38 days of wall-clock time. Not a suite anyone would ever rerun.

**Tolerance & missing-value policy:**
- RMM, CS, Transfer Probability (0-100 scale scores): absolute tolerance `0.01` (matches the oracle CSV's own 2-decimal display precision).
- TFM (money-scale, `np.expm1`-unwrapped): relative tolerance `0.1%` — small float differences in the log-scale prediction amplify after the exponential unwrap, so a relative bound is more meaningful than an absolute one here.
- **Null/missing handling is a correctness check, not an exemption:** wherever the oracle has NaN, the port must also return null/`None` for that field. A non-null port value where the oracle is null (or vice versa) is a **hard failure**, not skipped.

**Position-group reporting shape:**
- `pytest.mark.parametrize` over position groups so pytest's own test report gives one real pass/fail per group natively. On top of that, any failing group writes a small mismatch-detail CSV/markdown (player_id, score, oracle value, port value, diff) to make debugging fast.
- CONTEXT.md's own working assumption was **8 groups (GK, CB, FB, CMF, DMF, AMF, Winger, CF)** — **this research found the actual code computes 10 distinct percentile groups, not 8. See "Position-Group Representation" finding below — this is a correction the planner MUST apply, not just a restatement.**

**Edge case selection — mine genuine edge cases from the real 41,708-player dataset, not synthetic fixtures:**
- Missing stats: players where key input columns used by their position's calculator are null/absent in the source data.
- Boundary ages: youngest and oldest players actually present in the dataset per position group.
- Zero-appearance players: players with `Minutes`/`Minutes played` = 0 or absent (the exact silent-zero-fill risk class Phase 3's curation already fixed once).
- Each edge case gets an explicit test asserting the expected behavior (correct null propagation or correct non-crashing score), not just "doesn't throw."

**Oracle versioning & repeatability:**
- The parity suite locates the oracle CSV by globbing for the latest `scoring_oracle_v*_*.csv` in `scoring/oracle/` (the same pattern `scoring/tests/test_oracle_snapshot.py::_find_latest_oracle_csv` already uses), never a hardcoded filename.
- Confirmed with the user this is the intended recurring flow (regenerate oracle → rerun `pytest scoring/tests/test_parity*.py`), not a one-off check.

### Claude's Discretion
- Exact test file naming/structure (single `test_parity.py` vs one file per score) — must live under `scoring/tests/` following the existing pytest + pytest-django + `real_data_available` fixture convention.
- Exact mismatch-report file format/location for failed position groups.
- Whether the ~30-player API-sample set is chosen randomly (seeded, for reproducibility) or hand-picked — seeded random stratified sample is the default assumption.
- Whether this suite is wired into any CI-equivalent beyond `pytest` (no CI system currently established in this project per prior phases).

### Deferred Ideas (OUT OF SCOPE)
- Wiring the parity suite into a CI pipeline — no CI system exists yet in this project.
- Improving TFM model accuracy if parity testing surfaces it as weak — Phase 3 already flagged R²/MAE as "reference only, no quality bar enforced," any tuning is a separate future decision.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SCORE-06 | The Django port passes a numerical parity test suite against the original script's real output, within an agreed tolerance, for every position group | This document's "Architecture Patterns" (bulk + API-sample two-tier design), "Position-Group Representation" (the corrected 10-group finding, which position-group `pytest.mark.parametrize` must actually use), "Edge Cases" (concrete, verified real-data edge-case candidates), and "Code Examples" (exact function calls/output-column mapping to wire the test suite against `scoring/services/*.py` and the oracle CSV) directly enable implementing SCORE-06's pass/fail-per-position-group parity suite. |
</phase_requirements>

## Summary

Phase 5 does not need any new production code — it needs a new `scoring/tests/test_parity*.py` suite that diffs two already-built things: the Phase 3 oracle CSV (`scoring/oracle/scoring_oracle_v1_2026-07-22.csv`, 41,708 rows) and the Phase 4 port (`scoring/services/*.py`, backed by `scoring/services/population.py`'s `reconstruct_population()`/`score_population()`). The bulk-path half of the suite is a near-verbatim replay of `generate_scoring_oracle.py`'s own orchestration (RMM first, merged onto `players_df` as `player_impact`, then `compute_cs_tp_for_pairs` with `club_context=None`), so getting that half right is mostly "read `generate_scoring_oracle.py`'s Steps 2-4 and call the exact same functions in the exact same order over `score_population(pop, None)`'s output," plus mapping `add_player_impact`'s `"Player Impact"`/`compatibility_score`/`transfer_probability` columns and the TFM pipeline's `np.expm1`-unwrapped prediction back onto the oracle's `rmm`/`cs`/`tfm`/`transfer_probability` columns.

Two corrections to CONTEXT.md's working assumptions surfaced during this research, both load-bearing for planning:

1. **Position groups are 10, not 8.** `add_player_impact`'s final percentile loop (`impact.py` line ~1008) computes RMM's position-relative percentile *separately* for `LB` vs `RB` and separately for `LW` vs `RW` — never merged into a combined "FB"/"Winger" bucket. The oracle's raw `main_position` column (`RCB`, `LCMF`, `RWB`, etc.) must be passed through `impact.normalise_position()` to get the actual 10 canonical groups the RMM calculator itself groups by: `GK, CB, LB, RB, CM, DMF, AMF, LW, RW, CF`. `pytest.mark.parametrize` must use these 10, or the parity suite's per-group buckets will not match what `add_player_impact` actually computed groupings over.
2. **CS/TP are structurally 100%-null for 3 of those 10 groups.** A live query against the oracle CSV shows `GK`, `LB`, and `RB` have **zero** non-null `cs`/`transfer_probability` values across the entire 41,708-player population (root cause: `build_role_scores_wide`'s role-column-name normalization gap — 18/45 `ROLE_COLUMNS_BY_POSITION` role names, disproportionately GK/full-back roles like "Goalkeeper (Defend)", "Full-Back", "Wing-Back", "Inverted Full-Back", never match a real `PlayerRoleScore` column, so `calculate_subjective_role_fit_for_player_to_team`'s Role Fit Score is NaN for every player in those 3 groups, which `compute_cs_tp_for_pairs` correctly forces to a NaN `compatibility_score`). This is NOT a Phase 5 bug to fix — it is the real, correct current state of both the oracle and the port. The parity suite's CS/TP tests for GK/LB/RB groups will legitimately assert "both sides are null" rather than "values match within tolerance," and the ~30-player API sample cannot include any GK/LB/RB player with a non-null CS/TP (there are none) — the sample-selection logic must not assume every position group will yield a non-null CS/TP example.

**Primary recommendation:** Build the bulk-path parity check as a single `score_population(pop, None)` call (verified ~74s wall-clock against the real dev DB) compared row-by-row against the oracle CSV, parametrized over the 10 real `normalise_position()` groups; build the API-sample check by reusing `test_views.py`'s existing module-scope reconstruction/scoring memoization pattern (keyed by distinct club name) to avoid the ~75-110s-per-distinct-club cost of naively calling each per-request service function 30 times.

## Standard Stack

### Core
| Library | Version (verified in this env) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 8.3.2 | Test runner, `pytest.mark.parametrize` for per-position-group reporting | Already the project's test runner (every prior phase) |
| pytest-django | 4.8.0 | `@pytest.mark.django_db`, `db` fixture | Already used throughout `scoring/tests/` |
| pandas | 2.3.2 | Oracle CSV read, DataFrame diffing, `.groupby` for position-group buckets | Already the substrate every characterization/service module is built on |
| numpy | 2.2.3 | `np.isclose`/`np.allclose` for tolerance comparison, `np.expm1` (TFM unwrap, already used by the port) | Same |

No new packages need to be added — this phase is pure test code against existing production code.

**Version verification:** versions above were read directly from the project's active virtualenv (`python3 -c "import pandas; print(pandas.__version__)"` etc.), not training-data assumptions — confirmed 2026-07-24.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `np.isclose(a, b, atol=0.01)` for RMM/CS/TP tolerance | `pandas.testing.assert_series_equal(..., atol=...)` | Either works; `assert_series_equal` gives a nicer diff on failure but pytest's own per-position-group parametrize + a custom mismatch-CSV (per CONTEXT.md) already covers the debugging need — plain `np.isclose` is simpler and gives full control over the "both-null-is-a-pass, one-null-one-not-is-a-fail" logic that a generic `assert_series_equal` doesn't natively express |
| Comparing oracle CSV rows directly | Re-running `generate_scoring_oracle.py`'s command inside the test | Re-running the oracle generator inside the parity suite would test the port against itself if the port and the oracle generator both changed together — the whole point of a *snapshot* oracle (CONTEXT.md's locked decision) is a frozen, independently-generated ground truth; always read the committed CSV, never regenerate it as part of the parity test run |

## Architecture Patterns

### Recommended Test File Structure
```
scoring/tests/
├── conftest.py                    # existing: real_data_available fixture (reuse, no changes needed)
├── test_oracle_snapshot.py        # existing: _find_latest_oracle_csv() -- reuse or extract to a shared helper
├── test_parity_bulk.py            # NEW: full-population bulk-path parity (Tier 1)
├── test_parity_api_sample.py      # NEW: ~30-player per-request service + DRF endpoint sample (Tier 2)
└── test_parity_edge_cases.py      # NEW: named edge-case players (missing stats / boundary ages / zero minutes)
```
(Claude's Discretion per CONTEXT.md — single-file vs split is open; the split above keeps the ~75-110s bulk pass isolated from the API-sample tests' own per-distinct-club cost so a developer can run just one file while iterating.)

### Pattern 1: Oracle discovery — reuse `_find_latest_oracle_csv`

**What:** Never hardcode the oracle CSV filename/version.
**When to use:** Every parity test module that reads the oracle.
**Example (verified pattern already in the codebase, `scoring/tests/test_oracle_snapshot.py` lines 38-42):**
```python
from pathlib import Path

ORACLE_DIR = Path(__file__).resolve().parents[1] / "oracle"

def _find_latest_oracle_csv() -> Path | None:
    if not ORACLE_DIR.exists():
        return None
    candidates = sorted(ORACLE_DIR.glob("scoring_oracle_v1_*.csv"))
    return candidates[-1] if candidates else None
```
Recommendation: extract this into `scoring/tests/conftest.py` (or a small `scoring/tests/_oracle_helpers.py`) as a shared fixture/function so `test_oracle_snapshot.py` and the new parity files import one copy, not two independently-maintained copies of the same glob.

### Pattern 2: Bulk-path parity — replicate `generate_scoring_oracle.py`'s exact sequence via `score_population`

**What:** The oracle's `rmm`/`cs`/`transfer_probability` columns were produced by `generate_scoring_oracle.py` calling `compute_rmm_column` then `compute_cs_tp_for_pairs` in a specific merge order. The port's bulk-equivalent is `population.score_population()`, which the code's own docstring states "Replicates `generate_scoring_oracle.py`'s proven order EXACTLY." Confirmed by direct comparison of both functions' source (`scoring/services/population.py` lines 69-114 vs `scoring/management/commands/generate_scoring_oracle.py` lines 138-226): both call `add_player_impact`/`compute_rmm_column` first, merge the result onto `players_df` as `player_impact`, then call `compute_cs_tp_for_pairs` with that series. The ONLY structural difference: the oracle uses `compute_rmm_column` (a thin wrapper) while `score_population` uses `add_player_impact` directly and reads `scored["Player Impact"]` off it — **these are the same underlying function** (`compute_rmm_column` literally calls `add_player_impact` internally, `impact.py` lines 1027-1039), so the RMM values are byte-for-byte the same computation, not just "close."

**When to use:** Tier 1 (full-population) parity check.
**Example:**
```python
# Source: scoring/services/population.py + scoring/management/commands/generate_scoring_oracle.py
from scoring.services.population import reconstruct_population, score_population

pop = reconstruct_population()
scored, cs_tp = score_population(pop, None)  # club_context=None == "each player vs their own current club" == the oracle's methodology (MANIFEST.md)

# Map port outputs -> oracle columns:
port_rmm = scored.set_index("player_id")["Player Impact"]                 # -> oracle "rmm"
port_cs = cs_tp["compatibility_score"]                                    # -> oracle "cs"
port_tp = cs_tp["transfer_probability"]                                   # -> oracle "transfer_probability"
# "tfm" has NO bulk-path equivalent in score_population -- see Pattern 3.
```

**Verified timing (live run against the real 41,708-player dev DB, 2026-07-24):**
| Call | Wall-clock |
|------|-----------|
| `reconstruct_population()` | 3.55s |
| `score_population(pop, None)` | 73.98s |
| `score_population(pop, "Real Madrid")` (a specific single club) | 111.33s |

The cost is dominated by `compute_cs_tp_for_pairs`'s per-row Python loop over all ~41,708 players (both `impact.add_player_impact` and `deterministic_scores.compute_cs_tp_for_pairs` iterate row-by-row, not vectorized) — this is unrelated to which `club_context` is passed; it costs roughly the same (~75-115s) whether comparing every player to their own club (`None`) or to one fixed club. **Tier 1 needs exactly ONE `score_population(pop, None)` call** (~75-115s total, a one-time cost per full suite run) since `club_context=None` already evaluates every player against their own current club in a single pass — this matches the oracle's methodology exactly (MANIFEST.md: "per player vs. their OWN CURRENT club").

### Pattern 3: TFM (Financial Fit) bulk-path — no `score_population` shortcut; replicate the oracle command's Step 4 directly

**What:** Unlike RMM/CS/TP, `score_population()` does NOT compute TFM — there is no bulk TFM helper in `scoring/services/`. The oracle's `tfm` column came directly from `generate_scoring_oracle.py`'s Step 4 (`build_oracle_player_features` + the joblib pipeline's `np.expm1`-unwrapped `.predict()`). The parity suite's bulk TFM check must call the same two functions directly, not go through any `scoring/services/financial_fit.py` per-request wrapper (that wrapper is Tier 2's concern — it prices ONE player against a SPECIFIC requested club, overriding `Team`, which is a different, per-request contract than the oracle's "everyone vs. their own club" bulk methodology).
**Example (mirrors `generate_scoring_oracle.py` lines 189-210 — the exact steps the parity check must replicate):**
```python
# Source: scoring/management/commands/generate_scoring_oracle.py Step 4
import numpy as np
from scoring.characterization.tfm_model import build_oracle_player_features
from scoring.services.population import get_tfm_pipeline

# players_df here MUST already carry player_impact/compatibility_score/performance_score/role_pct
# merged on (score_population's `scored`/`cs_tp` outputs, same as generate_scoring_oracle.py does
# via its own separate merge -- see Pitfall 1 below).
pipeline, feature_cols = get_tfm_pipeline()
features = build_oracle_player_features(players_df, pop.transfers_df)
X = features[feature_cols]
predicted_fee = pd.Series(np.expm1(pipeline.predict(X)), index=features.index)
predicted_fee = predicted_fee.where(features["_has_club_context"], np.nan)  # never fabricate a fee with no club context
```

### Pattern 4: API-sample check — reuse `test_views.py`'s memoization pattern (CRITICAL for feasibility)

**What:** The ~30-player API-sample check calls the REAL per-request service functions (`get_rmm`, `get_compatibility`, `get_financial_fit`, `get_transfer_probability`, `get_summary`), each of which independently calls `reconstruct_population()` + `score_population()` internally. `reconstruct_population()` is cheap (3.55s) but `score_population()` costs ~75-115s **per distinct `club_name` argument**. Since the parity sample must compare each player against their OWN current club (matching oracle methodology per MANIFEST.md), and 30 different sampled players will likely have 15-30 different own-clubs, naively calling `get_compatibility(player_id, club_id)` 30 times could cost 30 × ~90s ≈ 45 minutes.
**When to use:** Tier 2 (API-sample) check — mandatory pattern, not optional, or the suite becomes impractically slow to rerun.
**Example (the exact pattern `scoring/tests/test_views.py` and `test_services_summary.py` already establish and that this phase should copy verbatim):**
```python
# Source: scoring/tests/test_views.py lines 82-150 (existing, already-proven pattern)
from unittest.mock import patch
from scoring.services.population import reconstruct_population, score_population

_CACHE: dict = {}

def _real_pop():
    if "pop" not in _CACHE:
        _CACHE["pop"] = reconstruct_population()
    return _CACHE["pop"]

def _real_scored(club_name):
    scored_cache = _CACHE.setdefault("scored", {})
    if club_name not in scored_cache:
        scored_cache[club_name] = score_population(_real_pop(), club_name)
    return scored_cache[club_name]

# Then patch each service module's imported reconstruct_population/score_population names
# to the cached results before calling the REAL service function -- the service function body
# itself (cs_breakdown_from_row, tp_breakdown_from_row, etc.) still runs unmocked end-to-end.
with patch("scoring.services.compatibility.reconstruct_population", return_value=_real_pop()), \
     patch("scoring.services.compatibility.score_population", return_value=_real_scored(club_name)):
    result = get_compatibility(player_id, club_id)
```
This reduces the ~30-player sample's cost to "one `score_population` call per DISTINCT own-club among the sample" rather than one per player — still potentially 15-30 calls if every sampled player has a different club, so **the sample-selection strategy should actively favor picking multiple players from the SAME small set of clubs** (e.g., pick ~30 players from ~8-10 clubs, a few players per club) to bound the number of distinct `score_population` calls the suite needs, rather than picking 30 players from 30 different clubs.

### Pattern 5: Position-group bucketing — apply `normalise_position()`, don't trust raw `main_position`

**What:** Both the oracle CSV's `main_position` column and the live `Player.main_position` DB field hold RAW, ungrouped position strings (`RCB`, `LCMF`, `RWB`, `LWF`, etc. — verified via a live DB query, 21 distinct raw values across 41,708 players). Grouping must go through `scoring.characterization.impact.normalise_position()` (or the byte-identical copy in `role_fit.py` — confirmed identical via diff) to get the 10 canonical groups the RMM calculator's percentile loop actually uses.
**Example:**
```python
# Source: scoring/characterization/impact.py normalise_position()
import pandas as pd
from scoring.characterization.impact import normalise_position

oracle_df = pd.read_csv(oracle_csv_path)
oracle_df["position_group"] = oracle_df["main_position"].apply(normalise_position)
# position_group now in {"GK","CB","LB","RB","CM","DMF","AMF","LW","RW","CF"} (+ possibly "0" for 1 garbage row -- see Edge Cases)
```

### Anti-Patterns to Avoid
- **Grouping LB+RB into one "FB" bucket or LW+RW into one "Winger" bucket for the parity report:** `add_player_impact`'s percentile computation (`impact.py` ~line 1008) runs its `_position_percentile()` separately per exact `normalise_position()` output — an LB player's RMM percentile is computed only against other LB players, never against RB players too. A parity test that merges LB+RB before comparing would be checking a mathematically different quantity than what the port (and oracle) actually computed. Use the 10 real groups.
- **Assuming every position group will have a non-null CS/TP example to sample:** GK/LB/RB have zero non-null `cs`/`transfer_probability` values in the real data (verified). Sample-selection code that asserts/requires ">=1 non-null CS example per group" will hang or error for these 3 groups — design the sampler to accept "both oracle and port agree it's null" as the valid, expected outcome for GK/LB/RB's CS/TP checks.
- **Re-running `generate_scoring_oracle.py` inside the parity test:** defeats the point of a frozen snapshot oracle (CONTEXT.md's locked decision) — always read the committed CSV.
- **Calling `get_compatibility`/`get_transfer_probability`/`get_financial_fit` unmemoized in a loop over the 30-player sample:** ~75-115s × up to 30 ≈ tens of minutes; use Pattern 4's memoization.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Oracle CSV file discovery | A new hardcoded-filename read, or a new glob pattern | `test_oracle_snapshot.py::_find_latest_oracle_csv()`'s exact glob (`scoring_oracle_v1_*.csv`), extracted to a shared helper if reused across files | Already proven, already exactly what CONTEXT.md's locked decision specifies |
| Bulk RMM/CS/TP computation | A new standalone RMM/CS/TP calculator for the test suite | `scoring.services.population.score_population(pop, None)` | It IS the already-proven bulk path (`generate_scoring_oracle.py`'s own methodology, verified identical) — writing a second implementation would itself need its own parity check against the first, an infinite regress |
| Position normalization | A new position-group mapping dict for the test suite | `scoring.characterization.impact.normalise_position()` (or `role_fit.py`'s identical copy) | Verified byte-identical between the two existing copies; a third copy in test code risks a THIRD source of truth that could silently drift from whichever one the port actually uses |
| Auth for DRF endpoint sample tests | A new auth-setup helper | `test_views.py`'s `auth_client` fixture pattern (`APIClient` + `force_authenticate` against a real `accounts.User`) | Already the established, working pattern for scoring's DRF tests; the global `IsAuthenticated` + `JWTAuthentication` DRF defaults apply identically |

**Key insight:** Nearly everything Phase 5 needs already exists somewhere in the Phase 3/4 codebase (the bulk scoring path, the oracle glob, the position normalizer, the auth fixture, the module-scope memoization pattern) — the actual net-new work is almost entirely comparison/reporting logic (tolerance checks, per-position-group `pytest.mark.parametrize`, mismatch-CSV writer), not new computation.

## Common Pitfalls

### Pitfall 1: TFM's bulk path needs a THIRD merge step the RMM/CS/TP bulk path doesn't
**What goes wrong:** Someone builds the TFM bulk parity check by calling `build_oracle_player_features` directly on `pop.players_df` (unmerged), producing wrong/degraded predictions that "run without crashing" but don't match the oracle.
**Why it happens:** `build_oracle_player_features` reads `player_impact`/`compatibility_score`/`performance_score`/`role_pct` straight off DataFrame columns (per `financial_fit.py`'s own docstring, "fact 2") — these are NOT present on `pop.players_df` until explicitly merged from `scored`/`cs_tp`'s output, exactly as `generate_scoring_oracle.py` Step 3 (lines 177-181) and `financial_fit.py`'s `_merge_tfm_feature_columns` (lines 47-62) both do.
**How to avoid:** Before calling `build_oracle_player_features` for the bulk TFM check, merge `player_impact` (from `scored`) and `compatibility_score`/`performance_score`/`role_pct` (from `cs_tp`) onto a copy of `pop.players_df` first — reuse `financial_fit.py`'s existing `_merge_tfm_feature_columns` helper if it's importable, or replicate the 2-line merge `generate_scoring_oracle.py` does.
**Warning signs:** TFM parity failures that are large and systematic (not small float-precision drift) across nearly every player, not just a handful — a sign the whole feature set was silently NaN/imputed rather than genuinely wrong on a case-by-case basis.

### Pitfall 2: `np.expm1` unwrap is easy to forget and silently "passes" a broken comparison
**What goes wrong:** Comparing the raw `pipeline.predict()` output (log-scale, range ~13-17 for real players) against the oracle's `tfm` column (money-scale, e.g. €597K-1.29M) — both are just floats, so a badly-chosen tolerance check might not obviously crash, it'll just always fail (or, worse, if compared against a stale/wrong oracle column, silently mismatch in a way that's hard to diagnose).
**Why it happens:** `financial_fit.py`'s own module docstring calls this out explicitly as "the confirmed log-scale bug" that Phase 4 already had to guard against with a dedicated regression test (`test_predicted_fee_is_money_scale_not_log_scale`).
**How to avoid:** Always `np.expm1(pipeline.predict(X))`, never raw `.predict()` output, when computing the bulk TFM comparison values.
**Warning signs:** Every TFM mismatch in the failure report shows the port's value in the 10-20 range while the oracle's value is in the millions.

### Pitfall 3: Confusing "financial_score" (inside `compute_cs_tp_for_pairs`) with "TFM" (the oracle's `tfm` column)
**What goes wrong:** `cs_tp["financial_score"]` (from `compute_cs_tp_for_pairs`) is a DIFFERENT number from the oracle's `tfm` column — they're two genuinely different scores (`deterministic_scores.py`'s module docstring: "its ML sibling (RandomForestRegressor -> log_fee) is the actual TFM artifact"). A parity test that accidentally diffs `cs_tp["financial_score"]` against the oracle's `tfm` column will show large, consistent "failures" that are actually a test-code bug, not a real port defect.
**Why it happens:** Both are plausibly named "financial ___" and both feed into Transfer Probability's weighted formula, but only `tfm` (from the sklearn pipeline) is what the oracle's `tfm` column and `SCORE-03`/`financial_fit.py` mean by "Financial Fit."
**How to avoid:** `oracle["tfm"]` maps ONLY to `np.expm1(pipeline.predict(...))` (Pattern 3) — never to `cs_tp["financial_score"]`, which has no oracle column at all (it's an internal-only term of the TP formula).
**Warning signs:** Every single player shows a "TFM mismatch," with port values in the 0-100 range vs oracle values in the millions.

### Pitfall 4: Sampling a stratified 30-player set that requires non-null CS for GK/LB/RB
**What goes wrong:** A stratified-sample selector that does something like `for group in ALL_10_GROUPS: pick 3 players with non-null cs from that group` will loop forever or error for GK/LB/RB, since zero such players exist.
**Why it happens:** Not obvious without directly querying the oracle CSV first (verified in this research — see Summary).
**How to avoid:** Either (a) sample GK/LB/RB players specifically to exercise the "correct null propagation" path (their non-null RMM and null CS/TP is itself a valid, useful assertion), or (b) document explicitly that the CS/TP-focused stratification only meaningfully covers 7 of 10 groups and GK/LB/RB are covered by the RMM-focused sampling + the explicit "both null" assertion instead.
**Warning signs:** Sample-selection code timing out, raising `IndexError`/`ValueError` on an empty filtered DataFrame for GK/LB/RB, or (worse) silently skipping those 3 groups entirely without anyone noticing the coverage gap.

### Pitfall 5: `Minutes_played=0` and `age=0` are extremely rare in this dataset — don't build a sample-selection strategy assuming dozens of candidates
**What goes wrong:** Assuming "zero-appearance players" is a common, easy-to-sample-many-of edge case.
**Why it happens:** In principle it sounds like a common data-quality issue; in this specific real dataset it verified as exactly **1** player (`Minutes_played=0`, `T. Franssen`, `RW`) out of 41,708.
**How to avoid:** Treat the zero-minutes edge case as a single named-player regression test (this exact player, or whichever one exists after any future oracle regeneration), not a "pick N random zero-minute players" strategy — there may only ever be 0-2 such players in the real data. `age=0` similarly only has 22 matches (likely a data-quality placeholder, not a genuine "youngest real player" — see Edge Cases section below for the distinction the planner should make explicitly).
**Warning signs:** A sample-selection filter that expects `>= 5` zero-minutes players and gets an empty or near-empty DataFrame.

## Code Examples

### Exact service function signatures (verified against `scoring/services/*.py`)
```python
# Source: scoring/services/rmm.py, compatibility.py, financial_fit.py, transfer_probability.py, summary.py
from scoring.services.rmm import get_rmm                              # get_rmm(player_id) -> dict
from scoring.services.compatibility import get_compatibility          # get_compatibility(player_id, club_id) -> dict
from scoring.services.financial_fit import get_financial_fit          # get_financial_fit(player_id, club_id) -> dict
from scoring.services.transfer_probability import get_transfer_probability  # get_transfer_probability(player_id, club_id) -> dict
from scoring.services.summary import get_summary                      # get_summary(player_id, club_id) -> dict

# All 4 club-scoped functions REQUIRE a club_id. To match the oracle's "vs. own current club"
# methodology, the API-sample test must resolve each sampled player's OWN club and pass its id:
club_id = Player.objects.get(id=player_id).club_id  # own current club, matching oracle's club_context=None semantics
```

### Output-to-oracle-column mapping (verified against each service's return dict shape)
```python
# get_rmm(player_id) -> {"rmm": float|None, "positive": ..., "negative": ..., "components": {...}, "reliability": ...}
port_rmm = get_rmm(player_id)["rmm"]                                    # compare to oracle["rmm"]

# get_compatibility(player_id, own_club_id) -> {"compatibility_score": float|None, "components": {...}} 
#                                             or {"compatibility_score": None, "reason": "..."} when null
port_cs = get_compatibility(player_id, own_club_id).get("compatibility_score")  # compare to oracle["cs"]

# get_financial_fit(player_id, own_club_id) -> {"predicted_fee": float|None, "market_value": ..., ...}
port_tfm = get_financial_fit(player_id, own_club_id).get("predicted_fee")       # compare to oracle["tfm"]

# get_transfer_probability(player_id, own_club_id) -> {"transfer_probability": float|None, "components": {...}}
port_tp = get_transfer_probability(player_id, own_club_id).get("transfer_probability")  # compare to oracle["transfer_probability"]
```
Note: `get_transfer_probability`'s returned value is already `round(float(tp), 1)` (one decimal), while the oracle's `transfer_probability` column also comes from the same `round(..., 1)` call inside `deterministic_scores.transfer_probability()` — so this particular comparison is comparing two already-rounded-to-1-decimal values; CONTEXT.md's `0.01` absolute tolerance for TP is comfortably looser than that rounding, so no special-casing needed.

### Null-envelope shape (verified against `scoring/exceptions.py`)
```python
# Source: scoring/exceptions.py
def null_with_reason(field: str, code: str) -> dict:
    return {field: None, "reason": code}
# Every score service returns this exact shape when a score cannot be honestly computed --
# parity comparison code should treat `result.get(<field>) is None` as "port says null" uniformly,
# whether checking the per-request dict shape or the bulk DataFrame's NaN.
```

### DRF auth pattern for the API-sample's endpoint checks (verified, `scoring/tests/test_views.py` lines 47-59)
```python
# Source: scoring/tests/test_views.py
import pytest
from rest_framework.test import APIClient

@pytest.fixture
def auth_client():
    from accounts.models import User
    user = User.objects.create_user(email="parity-tester@example.com", password="testpass123")
    client = APIClient()
    client.force_authenticate(user=user)
    return client

# Endpoint paths (scoring/urls.py, verified):
# GET /api/scoring/players/<uuid:player_id>/impact/
# GET /api/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/compatibility/
# GET /api/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/financial-fit/
# GET /api/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/transfer-probability/
# GET /api/scoring/players/<uuid:player_id>/summary/?club_id=<uuid>   (club_id is a QUERY param here, not a path segment)
```
No bespoke permission class exists or is needed — the project's global `DEFAULT_PERMISSION_CLASSES` (`IsAuthenticated`) + `DEFAULT_AUTHENTICATION_CLASSES` (`JWTAuthentication`) already gate every endpoint; `force_authenticate` is the established equivalent of a real Bearer token for tests.

## State of the Art

Not applicable in the usual "library version churn" sense — this phase's "state of the art" is entirely intra-project: Phase 4 (completed 2026-07-24 per STATE.md) is the most current state of the port, and Phase 3 (completed 2026-07-22, oracle generated 2026-07-22) is the most current oracle. No external library upgrade concerns apply; the risk surface is entirely "does the port's orchestration match the oracle's orchestration," which this research directly verified function-by-function above.

## Open Questions

1. **Should the "0" garbage `main_position` row (1 player, likely a data-import artifact) get its own edge-case test, or be explicitly excluded/ignored?**
   - What we know: exactly 1 player across 41,708 has `main_position` literally `"0"` (not a valid position label). `normalise_position("0")` returns `"0"` unchanged (falls through `POSITION_NORMALISATION`'s `.get()` default), and `add_player_impact`'s dispatch `if/elif` chain has no branch for `"0"`, so this player gets `raw=NaN` → RMM is NaN for them (1 of the 2 real NaN RMM cases MANIFEST.md's "Non-null for 41707/41708" note refers to).
   - What's unclear: whether the planner should scope this in as a formal "invalid/unrecognized position" edge case (CONTEXT.md's edge-case list doesn't explicitly name this category — it names missing stats/boundary ages/zero-appearance) or treat it as out-of-scope noise.
   - Recommendation: treat it as a bonus/opportunistic edge case if convenient (it's a single named player, cheap to test — "both oracle and port report NaN RMM for this player"), but don't block phase completion on it since CONTEXT.md's locked edge-case categories don't explicitly require it.

2. **Is `age=0` (22 players) a genuine "boundary age" or a data-quality placeholder that should be excluded from "youngest player per position group" edge-case selection?**
   - What we know: `Player.age` ranges 0-44 across the real data; exactly 22 players show `age=0`, which is implausible for a professional footballer roster (likely an unparsed/placeholder value from the original CSV import, not a real 0-year-old).
   - What's unclear: whether Phase 1's import already flagged these (worth checking `Player.objects.filter(age=0)` against Phase 1's import report / `extended_stats` for a flag) before treating them as genuine "youngest player" edge cases.
   - Recommendation: the planner should decide whether "boundary ages" means "youngest/oldest AFTER excluding `age=0`/other obviously-invalid placeholder values" (more defensible as a genuine edge-case test) or "youngest/oldest literally, including age=0" (tests the port's raw NaN-propagation/no-crash behavior on a clearly bad input, which is also a legitimate thing to verify) — either is reasonable, but should be a conscious choice, not an accident of `.sort_values("age").iloc[0]`.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3.2 + pytest-django 4.8.0 |
| Config file | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`; `DJANGO_SETTINGS_MODULE = "config.settings.local"`, `testpaths` includes `scoring`) |
| Quick run command | `pytest scoring/tests/test_parity_edge_cases.py -x` (named-player edge cases only, seconds) |
| Full suite command | `pytest scoring/tests/test_parity_bulk.py scoring/tests/test_parity_api_sample.py scoring/tests/test_parity_edge_cases.py` (bulk pass ~75-115s + API-sample pass; run against a dev DB with real migrated data, `real_data_available` fixture skips cleanly otherwise) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SCORE-06 | Full-population RMM/CS/TP/TFM parity within tolerance, reported per position group | integration (real DB + real oracle CSV) | `pytest scoring/tests/test_parity_bulk.py -x` | ❌ Wave 0 |
| SCORE-06 | Per-request service function (`get_rmm`/`get_compatibility`/`get_financial_fit`/`get_transfer_probability`/`get_summary`) + DRF endpoint parity on a ~30-player stratified sample | integration | `pytest scoring/tests/test_parity_api_sample.py -x` | ❌ Wave 0 |
| SCORE-06 | Named edge cases (missing stats, boundary ages, zero-minutes) pass with correct null propagation or correct non-crashing score | integration | `pytest scoring/tests/test_parity_edge_cases.py -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** run the specific new test file being built (e.g., `pytest scoring/tests/test_parity_bulk.py -x`)
- **Per wave merge:** `pytest scoring/tests/test_parity_bulk.py scoring/tests/test_parity_api_sample.py scoring/tests/test_parity_edge_cases.py`
- **Phase gate:** full parity suite green before `/gsd:verify-work`, against the real dev DB with the committed oracle CSV (`scoring/oracle/scoring_oracle_v1_2026-07-22.csv` or whichever is latest per the glob pattern)

### Wave 0 Gaps
- [ ] `scoring/tests/test_parity_bulk.py` — full-population bulk parity, covers SCORE-06's "every position group" clause
- [ ] `scoring/tests/test_parity_api_sample.py` — per-request service + DRF endpoint sample, covers the wiring-bug-detection half of SCORE-06
- [ ] `scoring/tests/test_parity_edge_cases.py` — named real-data edge cases
- [ ] Shared oracle-discovery helper (extract `_find_latest_oracle_csv` from `test_oracle_snapshot.py` into `conftest.py` or a small shared module) — small refactor, not a new framework
- [ ] Shared tolerance/mismatch-report helper (`np.isclose`-based comparator + CSV/markdown writer for failing position groups, per CONTEXT.md's locked reporting shape) — new, small utility module, e.g. `scoring/tests/_parity_helpers.py`

No test framework installation gap — pytest/pytest-django/pandas/numpy are all already installed and in active use by the existing `scoring/tests/` suite.

## Sources

### Primary (HIGH confidence — direct code read + live execution against the real dev DB, 2026-07-24)
- `get-scouted-be/scoring/services/population.py` — `reconstruct_population`, `score_population`, `resolve_club_name`, `get_tfm_pipeline` (full source read)
- `get-scouted-be/scoring/management/commands/generate_scoring_oracle.py` — full source read, the exact bulk orchestration the parity check must replicate
- `get-scouted-be/scoring/characterization/impact.py` — full source read, `add_player_impact`, `normalise_position`, `POSITION_NORMALISATION`, `compute_rmm_column`
- `get-scouted-be/scoring/characterization/deterministic_scores.py` — full source read, `compute_cs_tp_for_pairs`, `financial_score`, `transfer_probability`, `contract_fit`
- `get-scouted-be/scoring/characterization/reconstruct.py` — full source read, `build_players_df`/`build_role_scores_wide`/`build_team_styles_df`/`build_transfers_df`, confirmed raw (unnormalized) `main_position` values pass through unchanged
- `get-scouted-be/scoring/services/{rmm,compatibility,financial_fit,transfer_probability,summary}.py` — full source read, exact function signatures + return dict shapes
- `get-scouted-be/scoring/exceptions.py` — `null_with_reason` envelope shape
- `get-scouted-be/scoring/tests/test_oracle_snapshot.py` — `_find_latest_oracle_csv` pattern
- `get-scouted-be/scoring/tests/test_views.py`, `test_services_summary.py`, `test_services_financial_fit.py` — existing auth fixture pattern + module-scope memoization pattern
- `get-scouted-be/scoring/tests/conftest.py` — `real_data_available` fixture
- `get-scouted-be/scoring/urls.py`, `views.py` — exact endpoint paths
- `get-scouted-be/scoring/oracle/MANIFEST.md`, `scoring_oracle_v1_2026-07-22.csv` — read directly (41,708 rows), confirmed null counts (`cs`/`transfer_probability`: 26,657 null; `rmm`: 1 null; `tfm`: 0 null)
- `get-scouted-be/scoring/docs/CURATION_MAP.md` — RMM's whole-dataset (position-group percentile) dependency, confirmed
- Live `python manage.py shell` queries against the real dev DB (2026-07-24): `main_position` distinct values (21 raw labels + 1 garbage `"0"` row), `Minutes_played` null/zero counts, `age` min/max/distribution, `market_value`/`contract_expires` null counts, position-group non-null CS breakdown (GK/LB/RB = 0 non-null), and a live timed `reconstruct_population()`/`score_population()` run (3.55s / 73.98s / 111.33s)
- Live `pip`/`python -c` version checks in the project's active virtualenv: pandas 2.3.2, numpy 2.2.3, pytest 8.3.2, Django 4.2.13, pytest-django 4.8.0
- `.planning/phases/05-scoring-parity-testing/05-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md` — locked decisions, SCORE-06 text, prior-phase decision log

### Secondary / Tertiary
None used — every claim in this document was verified directly against the actual codebase or a live run against the real dev database rather than external search or training-data recall, since this phase's entire risk surface is intra-project code, not an external library/ecosystem question.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions read directly from the active virtualenv, no new packages needed
- Architecture (bulk path, API-sample memoization, TFM merge steps): HIGH — every function signature and call sequence verified by reading the actual source, cross-checked between `generate_scoring_oracle.py` and `population.py`, and timing verified by a live run
- Position-group representation (10 groups, not 8; GK/LB/RB zero non-null CS/TP): HIGH — verified by both static code read (`impact.py`'s percentile loop) AND a live query against the actual oracle CSV and live DB
- Edge cases (rarity of zero-minutes/age=0 candidates): HIGH — verified by live DB queries; the *interpretation* of whether age=0 counts as a genuine boundary case is flagged as an Open Question, not a confidence gap
- Pitfalls: HIGH — each one traces to an explicit warning already written into the existing Phase 3/4 code's own docstrings (not speculative)

**Research date:** 2026-07-24
**Valid until:** Until the oracle CSV is regenerated or `scoring/services/*.py`/`scoring/characterization/*.py` change — this is intra-project research tied to a specific commit state, not time-decaying external-ecosystem research. Re-verify the position-group null-coverage numbers and timing figures if either the oracle or the port changes materially before Phase 5 planning happens.
