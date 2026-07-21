# Phase 3: Scoring Engine Curation & Correctness Oracle - Context

**Gathered:** 2026-07-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Identify and characterize the authoritative logic inside the untested, duplicated 15,747-line `impact_model_v4.1.py` before a single line is ported to Django. Produces: (1) a written curation map showing which functions/columns feed each of the 4 scores, (2) a versioned correctness-oracle snapshot of real script output, (3) a trained/versioned Transfer Probability model artifact. No Django porting, no API endpoints, no live scoring service — that's Phase 4. This phase carries no directly-owned requirement; it exists to de-risk Phases 4-6 (SCORE-01 through SCORE-07).

</domain>

<decisions>
## Implementation Decisions

### Duplicate-Function Resolution Policy

- **Default rule (locked):** for any duplicated function name, the LAST definition in the file is authoritative — cross-checked against `get_export_columns_for_position()` (the actual Excel export columns), since that reflects what was actually "shipped" when the script last ran successfully. This applies mechanically to every duplicated name with exactly 2 definitions.
- **Escalation trigger:** any function name with **more than 2 definitions** (3 or more) must be escalated to the user for review before locking in which version is authoritative — regardless of how similar or different the versions look at a glance. From the verified duplicate-count scan, this currently means `prepare_team_and_transfer_signal` (4 definitions) and `player_transfer_history` (4 definitions) MUST be escalated; do not resolve these via the mechanical last-wins rule without user review.
- **Curation map must record BOTH the kept version and every rejected version, with a reason** — even if the reason is just "identical to kept version, redundant." This creates an audit trail for debugging any future scoring discrepancy.

### Handling Bugs/Quirks Found During Curation

- **The oracle is "corrected ground truth," not a bit-for-bit copy of the original script.** Where curation finds an obviously-wrong silent default, fix it now rather than faithfully preserving broken behavior into the port.
- **Fix threshold (narrow, deliberately):** only fix cases where MISSING/ABSENT data gets silently defaulted in a way that mathematically distorts a score — e.g., a missing `Minutes` column defaulting to `0` (implying zero playing time / zero performance) instead of excluding the player from that calculation or nulling the field. This is the CONCERNS.md-flagged pattern class.
- **Everything else is preserved and documented, not touched** — odd thresholds, hardcoded weights (e.g. the `league_weights` dict), unusual formulas. These may be deliberate tuning choices, not bugs, even if they look debatable. Do not "improve" them during characterization.
- **Every fix applied must be documented in the curation map:** what was wrong, what changed, why. No silent fixes.

### Transfer Probability / sklearn Component

- Verified: no pre-trained model file exists anywhere in the codebase. `RandomForestRegressor` trains at runtime via `train_test_split(..., random_state=42)` + `RandomForestRegressor(..., random_state=42)` — both seeded, so the trained model IS reproducible given identical input data (impact_model_v4.1.py lines ~5638-5652).
- **Train fresh on Phase 1's real migrated dataset** — this is the only available and correct baseline; there is no prior trained artifact or historical reference output to match instead.
- **Save the fitted model as a versioned artifact** (joblib) as part of this phase's deliverables. Phase 4+ loads this artifact; it is NOT retrained per request or on-demand later — matches ARCHITECTURE.md's `ml_artifacts/` design (serialized, versioned, not retrained per request).
- **Record model quality metrics (MAE, R² on the held-out test split) for reference only — no minimum quality bar enforced in this phase.** This is characterization, not model improvement. Flag the actual numbers in the curation map as a known-risk area feeding Phase 5's parity-tolerance decision (this resolves the "not purely deterministic" hedge in STATE.md's blockers — it IS deterministic given fixed seed + fixed data, but its *accuracy* is a separate, unaddressed question left to later phases).

### Oracle Snapshot Scope

- **Full population** — snapshot every real player's RMM/CS/TFM/Transfer Probability output (all ~41,708 players from Phase 1), not a stratified sample. Maximizes Phase 5 parity-testing coverage; storage cost is modest (a handful of numeric columns × 41,708 rows). Consistent with the project's "real data, not approximated" core value.
- **Format: flat file (CSV/Parquet), versioned in the repo** — NOT a Postgres table/Django model. The oracle is a one-time comparison baseline for Phase 5's test suite to diff against; it doesn't need to be live-queryable by the application itself.

### Claude's Discretion

- Exact file/module layout for curation deliverables (curation map as Markdown table vs. structured JSON/YAML; where the training/snapshot scripts live)
- Exact CSV/Parquet schema for the oracle snapshot (one file per position group vs. one combined file; exact column naming)
- Specific feature-engineering/hyperparameter details beyond what's already in the original script's Transfer Probability recipe — must faithfully reproduce the original recipe, per the "train fresh but faithful" decision, not redesign it
- Mechanics of how escalation to the user actually happens during research/planning/execution for the >2-version duplicate cases (e.g., inline questions during planning vs. a consolidated review doc) — the policy (escalate) is locked, the workflow mechanics are not

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture guidance for this phase
- `.planning/research/ARCHITECTURE.md` — the duplicate-function heuristic (last-wins + export-column cross-check), the "no function scores a single player in isolation" finding that drives the whole caching strategy Phase 6 will build on, and Anti-Pattern 3 ("porting all 15,747 lines verbatim, including duplicate/superseded function definitions")

### The actual script being curated
- `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` — 15,747 lines. Specific locations already verified this session:
  - Lines ~4666-4672: sklearn imports (`RandomForestRegressor`, `train_test_split`, etc.)
  - Lines ~4677+: hardcoded `league_weights` dict (league-name → strength-weight mapping) — feeds RMM league normalization, port as-is per the "don't touch non-bug quirks" decision
  - Lines ~5638-5652: `RandomForestRegressor(random_state=42, ...)` and `train_test_split(..., random_state=42)` — confirms Transfer Probability is reproducible given fixed input
  - 20 duplicated function names total; `prepare_team_and_transfer_signal` and `player_transfer_history` each have 4 definitions and MUST be escalated per the policy above

### Known risks and prior findings
- `.planning/codebase/CONCERNS.md` §"Fragile Area: Complex Python Scoring Engine" — defensive column-checking pattern (e.g. missing `Minutes` silently defaulting to `0`), the exact bug class this phase's narrow fix-threshold targets
- `.planning/STATE.md` §"Blockers/Concerns" — prior note flagging Transfer Probability as "sklearn-trained, not purely deterministic"; this phase's research confirmed it IS deterministic given fixed seed, but accuracy/quality remains an open, deliberately-unaddressed question for Phase 5

### Product context
- `GetScouted PRD.docx` — defines the 4 core scores (Player Score/RMM, Compatibility Score/CS, Financial Fit/TFM, Transfer Probability) this curation map must account for

### Roadmap context
- `.planning/ROADMAP.md` §"Phase 3: Scoring Engine Curation & Correctness Oracle" — goal, 4 success criteria, explicit "no directly-owned requirement" note (prerequisite work for SCORE-01 through SCORE-07 in Phases 4-6)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- The 8 position-specific `_calc_*_impact_raw` functions (`_calc_gk_impact_raw`, `_calc_cb_impact_raw`, `_calc_fb_impact_raw`, `_calc_cmf_impact_raw`, `_calc_dmf_impact_raw`, `_calc_amf_impact_raw`, `_calc_winger_impact_raw`, `_calc_cf_impact_raw`) are the one genuinely clean, non-duplicated part of the script per ARCHITECTURE.md — good candidates to characterize first since they're not tangled in the duplicate-resolution problem.
- Phase 1's `get-scouted-be/` Django project has the real migrated dataset (Player, Club, PlayerRoleScore, PlayerClubCompatibility, Transfer — all UUID-keyed) that this phase's snapshot generation will run against.

### Established Patterns
- No function in the script computes a single player's score in isolation — every meaningful function takes a precomputed whole-dataset lookup (`std_lookup`, `team_styles_df`, `build_team_position_reference()`) as an argument. This isn't a Phase 3 concern directly (Phase 6 handles caching), but it means the snapshot-generation script for this phase will itself need to build these lookups once over the full dataset, not per-player.
- Project testing convention: pytest + pytest-django, fixture-based (see Phase 1/2's `conftest.py` patterns) — though this phase's work is closer to a data-science characterization script than typical Django app code, so exact test shape is Claude's discretion.

### Integration Points
- Downstream: Phase 4 (Scoring Engine Port) consumes this phase's curation map and trained Transfer Probability artifact directly — the port must NOT retrain the model or re-derive the duplicate-resolution decisions from scratch.
- Downstream: Phase 5 (Scoring Parity Testing) consumes the oracle snapshot file(s) as its comparison baseline.

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this phase is entirely code-archaeology and data-science characterization work, not a user-facing feature.

</specifics>

<deferred>
## Deferred Ideas

- Improving the Transfer Probability model's actual predictive quality (feature engineering, hyperparameter tuning) — explicitly deferred; this phase only characterizes and versions what already exists, quality improvement is not in scope
- Fixing non-bug quirks (odd thresholds, hardcoded weights) even if they look debatable — deferred indefinitely unless a future phase explicitly revisits scoring methodology
- A "raw/unfixed" parallel oracle snapshot — considered and explicitly rejected in favor of a single "corrected ground truth" oracle

</deferred>

---

*Phase: 03-scoring-engine-curation-correctness-oracle*
*Context gathered: 2026-07-21*
