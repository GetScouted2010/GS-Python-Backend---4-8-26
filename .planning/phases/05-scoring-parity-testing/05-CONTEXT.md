# Phase 5: Scoring Parity Testing - Context

**Gathered:** 2026-07-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the Django scoring port (Phase 4) is numerically faithful to the Phase 3 correctness oracle — not just "runs without crashing." An automated, repeatable pytest suite compares every score (RMM, CS, TFM, Transfer Probability) for every real player against the oracle snapshot, reports pass/fail per position group, and covers named edge cases. No new scoring logic, no performance/caching work (Phase 6), no re-characterization of the original script (Phase 3 is done).

All decisions below were made by Claude on the user's explicit instruction ("make all necessary and important decisions considering trade offs and execute" — user is not confident evaluating implementation trade-offs directly) rather than through interactive discussion. Rationale is spelled out for each so downstream agents (and the user, on review) can see why.

</domain>

<decisions>
## Implementation Decisions

### Computation strategy at scale
- **Decision:** Two-tier approach.
  1. **Full-population numeric parity** (all ~41,708 players) runs via the same bulk path `generate_scoring_oracle.py` used: `reconstruct_population()` + `score_population()` / `compute_cs_tp_for_pairs` called once over the whole DataFrame, not per-player. This is the only feasible way to check the full population — each Phase 4 per-request service call (`get_compatibility`, etc.) does its own ~80s population reconstruction, so 41,708 individual calls is on the order of days, not viable for a repeatable test suite.
  2. **Small API/service-layer sample** (~30 players, stratified to include at least a few from each position group) is run through the *real* per-request service functions (`get_rmm`, `get_compatibility`, `get_financial_fit`, `get_transfer_probability`, `get_summary`) and, for at least a handful, the actual DRF endpoints — compared against the same oracle rows. This exists specifically to catch wiring bugs in the per-request path (Phase 4 already had one real bug here: the CS breakdown's `role_scores_wide` merge) that the bulk path alone cannot detect, since the bulk path and the per-request path are separately-written orchestration code calling the same underlying characterization functions.
- **Why not pure bulk-only:** would miss exactly the class of bug Phase 4 already proved can happen (per-request wiring diverging from the bulk path) — misses the actual highest-risk surface.
- **Why not full per-request replay:** ~80s × 41,708 ≈ 38 days of wall-clock time. Not a suite anyone would ever rerun.

### Tolerance & missing-value policy
- **Decision:** Tight numeric tolerance, since both the oracle and the port call the exact same `scoring/characterization/*.py` functions (Phase 3's curated modules) — this suite is not re-verifying the underlying math (Phase 3 did that), it's verifying Phase 4's orchestration reproduces the same result as Phase 3's orchestration.
  - RMM, CS, Transfer Probability (0-100 scale scores): absolute tolerance `0.01` (matches the oracle CSV's own 2-decimal display precision).
  - TFM (money-scale, `np.expm1`-unwrapped): relative tolerance `0.1%` — small float differences in the log-scale prediction amplify after the exponential unwrap, so a relative bound is more meaningful than an absolute one here.
  - **Null/missing handling is a correctness check, not an exemption:** wherever the oracle has NaN (e.g. 26,657 players with `unresolved_role_fit` for CS/TP), the port must also return null/`None` for that field. A non-null port value where the oracle is null (or vice versa) is a **hard failure**, not skipped — silently fabricating a value where the oracle correctly abstained would be exactly the kind of bug this phase exists to catch.

### Position-group reporting shape
- **Decision:** `pytest.mark.parametrize` over position groups, so pytest's own test report gives one real pass/fail per group natively (satisfies ROADMAP's literal "reports pass/fail... for every position group"). On top of that, any failing group writes a small mismatch-detail CSV/markdown (player_id, score, oracle value, port value, diff) to make debugging a failure fast, rather than just a bare assertion error.
- **Correction from Phase 5 research (05-RESEARCH.md):** the real position groups are **10, not 8** — `add_player_impact`'s percentile logic keys LB/RB and LW/RW separately (`normalise_position()` groups: `GK, CB, LB, RB, CM, DMF, AMF, LW, RW, CF`), never merging into "FB"/"Winger" buckets. Parametrize on these 10 real groups, not the 8 assumed during discussion.
- **Research also found:** GK, LB, and RB have zero non-null CS/Transfer Probability across all 41,708 players (a role-column normalization gap upstream of this phase, not a bug to fix here) — the stratified API sample and any "pass for every group" assertion must account for these 3 groups having no non-null CS/TP rows to compare.
- **Why not a single suite-wide result:** roadmap explicitly requires per-position-group granularity; a single pass/fail would hide which position's calculators regressed.

### Edge case selection
- **Decision:** Mine genuine edge cases from the real 41,708-player dataset rather than constructing synthetic fixtures — consistent with the project's "real data, not approximated" core value and every prior phase's approach:
  - Missing stats: players where key input columns used by their position's calculator are null/absent in the source data.
  - Boundary ages: youngest and oldest players actually present in the dataset per position group.
  - Zero-appearance players: players with `Minutes` / `Minutes played` = 0 or absent (the exact silent-zero-fill risk class Phase 3's curation already fixed once — this is the regression guard for that fix).
  - Each edge case gets an explicit test asserting the expected behavior (correct null propagation or correct non-crashing score), not just "doesn't throw."

### Oracle versioning & repeatability
- **Decision:** The parity suite locates the oracle CSV by globbing for the latest `scoring_oracle_v*_*.csv` in `scoring/oracle/` (the same pattern `scoring/tests/test_oracle_snapshot.py::_find_latest_oracle_csv` already uses), never a hardcoded filename. This makes the whole Phase 5 flow repeatable: when the team's data scientist updates the underlying dataset, regenerating a new oracle via `manage.py generate_scoring_oracle` and rerunning `pytest scoring/tests/test_parity*.py` is the entire re-validation flow — no test code changes needed.
- Confirmed with the user this is exactly the intended recurring flow, not a one-off check.

### Claude's Discretion
- Exact test file naming/structure (single `test_parity.py` vs one file per score) — must live under `scoring/tests/` following the existing pytest + pytest-django + `real_data_available` fixture convention.
- Exact mismatch-report file format/location for failed position groups.
- Whether the ~30-player API-sample set is chosen randomly (seeded, for reproducibility) or hand-picked — seeded random stratified sample is the default assumption.
- Whether this suite is wired into any CI-equivalent beyond `pytest` (no CI system currently established in this project per prior phases).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 5: Scoring Parity Testing" — goal, 3 success criteria, `SCORE-06`, depends on Phase 3 + Phase 4
- `.planning/REQUIREMENTS.md` — `SCORE-06`: "The Django port passes a numerical parity test suite against the original script's real output, within an agreed tolerance, for every position group"

### The oracle (ground truth this phase checks against)
- `get-scouted-be/scoring/oracle/scoring_oracle_v1_2026-07-22.csv` — 41,708-row snapshot: `player_id, player_name, main_position, rmm, cs, tfm, transfer_probability`
- `get-scouted-be/scoring/oracle/MANIFEST.md` — per-score population/context notes: RMM is context-free per player; CS/TFM/Transfer Probability are each computed **vs. the player's own current club**, not an arbitrary club — the parity suite must call the port the same way (own-club context) to compare apples to apples
- `get-scouted-be/scoring/docs/CURATION_MAP.md` — which curated functions feed each score, the RMM-first wiring order, and the documented bug-fixes from Phase 3 (informs edge-case selection)

### The port being validated
- `get-scouted-be/scoring/services/population.py` — `reconstruct_population()`, `score_population(pop, club_name)` (the bulk path this phase's full-population check reuses), `resolve_club_name()`
- `get-scouted-be/scoring/services/{rmm,compatibility,financial_fit,transfer_probability,summary}.py` — the per-request service functions the API-sample check exercises
- `get-scouted-be/scoring/management/commands/generate_scoring_oracle.py` — the exact bulk orchestration + column-merge order (`player_impact` merged before `compute_cs_tp_for_pairs`) the full-population parity check must replicate faithfully
- `get-scouted-be/scoring/tests/test_oracle_snapshot.py` — existing `_find_latest_oracle_csv()` glob pattern to reuse for oracle-version-agnostic lookup

### Prior phase context
- `.planning/phases/03-scoring-engine-curation-correctness-oracle/03-CONTEXT.md` — oracle scope decisions (full population, flat-file format, "corrected ground truth not bit-for-bit copy")
- `.planning/phases/04-scoring-engine-port/04-CONTEXT.md` — API surface shape, the CS `role_scores_wide` merge bug and fix (the concrete precedent for why the API-sample check exists)
- `.planning/PROJECT.md` — Key Decisions table, esp. "Phase 4 ships correct but slow" and the TFM buying-club-context decision

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scoring/services/population.py::score_population()` — the exact bulk scoring path to call for full-population parity checking; already proven correct (it's what Phase 4's own services and `generate_scoring_oracle.py` both build on).
- `scoring/tests/conftest.py::real_data_available` fixture — existing pattern for real-data tests that skip cleanly when the dev DB is empty; reuse for parity tests.
- `scoring/tests/test_oracle_snapshot.py::_find_latest_oracle_csv()` — oracle-file discovery pattern to reuse verbatim (or extract to a shared helper) so the parity suite never hardcodes a filename/version.

### Established Patterns
- pytest + pytest-django, real-data tests gated behind `real_data_available`, following every prior phase (1-4) in this project.
- "Never zero-fill, NaN propagates" is a hard invariant already enforced throughout Phase 3/4 — the parity suite's null-mismatch-is-a-failure decision extends this invariant into testing.

### Integration Points
- This suite reads (doesn't modify) `scoring/oracle/*.csv` and calls into `scoring/services/*.py` and `scoring/characterization/*.py` — no new production code paths, purely a new `scoring/tests/test_parity*.py` (plus possibly a small report-writing helper).

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this is a backend correctness-verification phase with no user-facing surface.

</specifics>

<deferred>
## Deferred Ideas

- Wiring the parity suite into a CI pipeline — no CI system exists yet in this project; noted for whenever hosting/CI is decided (see PROJECT.md Constraints).
- Improving TFM model accuracy if parity testing surfaces it as weak — out of scope; Phase 3 already flagged R²/MAE as "reference only, no quality bar enforced," and any tuning work is a separate future decision.

</deferred>

---

*Phase: 05-scoring-parity-testing*
*Context gathered: 2026-07-24*
