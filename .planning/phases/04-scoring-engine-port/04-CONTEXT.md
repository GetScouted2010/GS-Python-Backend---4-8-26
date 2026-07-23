# Phase 4: Scoring Engine Port - Context

**Gathered:** 2026-07-23
**Status:** Ready for planning

<domain>
## Phase Boundary

The curated, authoritative calculators for all four scores (Player Score/RMM, Compatibility Score/CS, Financial Fit/TFM, Transfer Probability) run as real Django/Python services and are reachable via API with full component breakdowns. This phase wraps Phase 3's already-characterized, faithfully-ported logic (`scoring/characterization/*.py`) in a request-facing service + API layer — it does NOT re-derive or re-characterize scoring logic, and it does NOT build the O(1) caching layer (that's Phase 6/SCORE-07). Numerical parity testing against Phase 3's oracle is Phase 5's job, not this phase's.

</domain>

<decisions>
## Implementation Decisions

### RMM & CS Source Disambiguation (resolves Phase 3's Open Questions 2 & 3)

- **RMM = `add_player_impact()`'s "Player Impact" output — context-free, not the club-dependent "Performance Score".** Matches the PRD's wording exactly ("an overall, position-aware performance score") and is the clean, non-duplicated function Phase 3 fully characterized. "Performance Score" is explicitly OUT of Phase 4's scope — its team/target-percentile terms were left as unwired NaN placeholders in Phase 3 (needs league-wide `POSITION_METRICS` machinery not yet built); finishing it is new characterization work, not a port, and does not belong in this phase.
- **CS = the fresh role-fit computation (`deterministic_scores.compute_cs_tp_for_pairs`), not the legacy `PlayerClubCompatibility.score`.** Matches PRD wording ("how well a player fits a specific club's tactical system") and is what ARCHITECTURE.md's `role_fit.py` service is already designed around. The legacy 8.19M-row `PlayerClubCompatibility` table is NOT queried by this phase's CS endpoint — it remains in Postgres from Phase 1 but is not the v1 API's source of truth for CS.
- **When a club has no playing-style data (~77% of clubs, confirmed by Phase 3), CS returns `null` with a reason flag** — e.g. `{"compatibility_score": null, "reason": "club_style_data_unavailable"}` — never a fabricated/estimated substitute. Matches Phase 3's "never silently zero-fill" policy.

### API Surface Shape

- **Nested resource paths** for player-vs-club scores: `GET /api/scoring/players/{id}/clubs/{club_id}/compatibility/`, `.../financial-fit/`, `.../transfer-probability/`. RESTful, cacheable by URL, consistent with this project's UUID-PK convention.
- **RMM is a plain player-scoped endpoint** (no club needed): `GET /api/scoring/players/{id}/impact/` (or equivalent — exact URL name is Claude's discretion).
- **A combined summary endpoint also exists**, in addition to the 4 per-score endpoints: `GET /api/scoring/players/{id}/summary/?club_id={club_id}` returning RMM + CS + TFM + Transfer Probability together. Matches the PRD's Player Profile page, which shows all scores at once — avoids the (out-of-scope) frontend needing 4 round-trips for one page load.
- **Transfer Probability also requires a club** (`.../transfer-probability/` under the same nested path as CS/TFM), NOT a standalone `/players/{id}/transfer-probability/` endpoint. Its formula (`0.30×compatibility + 0.20×performance + 0.20×financial + 0.30×contract_fit`) needs club-dependent `compatibility_score` and `financial_score` inputs — it cannot actually be computed for "just a player" the way ROADMAP.md's SCORE-04 phrasing alone might suggest. This nested shape satisfies SCORE-04's intent (a real computed Transfer Probability, reachable via API) without contradicting what the formula actually needs.
- **One shared null+reason envelope for missing-data cases across all 4 scores** — same `{"score_field": null, "reason": "..."}` pattern applies uniformly whether the cause is missing club style data, missing transfer history, missing market value, etc. One predictable shape for callers to handle everywhere, not a different convention per score.

### TFM Buying-Club Context (escalated during research, resolved 2026-07-23)

- **Research finding:** direct inspection of `tfm_model.py`/`generate_scoring_oracle.py` surfaced a genuine unresolved fork CONTEXT.md's original TFM section didn't address — does the requested `club_id` in `/players/{id}/clubs/{club_id}/financial-fit/` actually change the TFM prediction (override the buying-club context before feature-building), or is it purely a display label alongside a prediction that's always computed against the player's own current club (matching the Phase 3 oracle exactly)?
- **Resolution (locked): `club_id` DOES change the prediction.** Override the buying-club context (`players_df["Team"]` equivalent / whatever `build_oracle_player_features` uses as the buying club) with the requested club's name before calling into the TFM feature-engineering + prediction pipeline. This makes the nested URL computationally meaningful, not decorative, and matches the PRD's literal wording ("realistic for a **given club's** spending profile").
- **Why this matters beyond Phase 4:** Phase 12 (Bidirectional Matching, PLAN-04 "Player → Club Matching") is planned to rank clubs for a given player by CS/TFM fit. If `club_id` didn't change TFM, every club would return an identical number and that ranking feature would be meaningless — Option B was rejected specifically because it would defer this decision rather than avoid it.
- **Known, accepted consequence:** TFM predictions from this endpoint will diverge from Phase 3's oracle CSV whenever `club_id` is not the player's actual current club — this is expected and fine, since Phase 5's parity testing is against own-club predictions only (the oracle's methodology), not against every possible (player, arbitrary club) pairing.

### Score Breakdown Depth (satisfies SCORE-05)

- **RMM**: full breakdown — positive and negative contributing components with their raw values, exactly as already produced by `add_player_impact()` / the 8 `_calc_*_impact_raw` functions' `components_dict`. No new computation, no truncation/ranking logic invented.
- **CS**: all 3 source components shown — `role_fit_score`, `similarity_pct` (explicitly flagged `null` / "requires target-player comparison pool, not characterized in Phase 3" since that machinery is genuinely out of Phase 3's scope), and `bonus`. Do not silently drop the two partially-characterized components from the breakdown.
- **TFM**: `predicted_fee`, the actual/market-value comparison, and the `Bargain`/`Fair Value`/`Overpay` label — exactly what `add_value_labels()` already produces. Do NOT expose the raw 33-feature list or per-feature importances — that's new work Phase 3 didn't characterize, and given the earlier finding that MAE is large relative to typical transfer fees, feature-importance numbers risk being more misleading than clarifying without dedicated care outside this phase's scope.
- **Transfer Probability**: all 4 weighted terms individually, each with its raw value, its weight, and its resulting contribution — e.g. `{"compatibility": {"raw": 72, "weight": 0.30, "contribution": 21.6}, ...}`. This is pure arithmetic already in the ported formula, so showing the full breakdown is nearly free and makes the score fully explainable, unlike TFM's ML-based prediction.

### Performance Scope Boundary vs. Phase 6

- **Ship correct-but-slow. Phase 4 does NOT build caching.** Phase 3's characterization code rebuilds whole-population lookups (`std_lookup` for RMM, team-style vectors for CS) fresh from the ORM on every call — acceptable for Phase 4, since its own success criteria are about correctness ("a real computed score, not an approximation"), not speed. O(1) caching against precomputed aggregates is explicitly Phase 6's job (SCORE-07) — building it now would duplicate Phase 6's work and blur the two phases' boundaries the roadmap deliberately drew.
- **No hard response-time ceiling for this phase**, even for demo purposes — consistent with the project-level decision to treat the 4-day deadline as a soft target rather than force-fitting scope. Endpoints may be slow (multi-second, possibly longer for the full population) until Phase 6 lands; that's expected, not a Phase 4 defect.

### Claude's Discretion

- Exact URL naming for the RMM endpoint and the combined summary endpoint (e.g. `/impact/` vs `/rmm/` vs `/score/`)
- Whether `scoring/characterization/*.py` gets promoted/refactored directly into `scoring/services/*.py` (per ARCHITECTURE.md's suggested structure) or wrapped by a thin new `services/` layer that imports `characterization/` as-is — both keep the Phase 3 audit-trail modules intact; the mechanics of how services/views/serializers wrap them is an implementation choice
- Whether the TFM joblib artifact is loaded once at Django startup/module import vs lazily on first request (a technical performance/architecture detail, not a product decision)
- Exact DRF serializer/viewset structure, pagination (not needed for single-entity score endpoints), and error-response status codes beyond the null+reason envelope already decided
- Whether the combined summary endpoint internally calls the 4 per-score service functions separately or reconstructs the underlying DataFrames once and reuses them across all 4 — an efficiency detail within the "ship correct-but-slow" scope boundary, not something requiring new caching infrastructure

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements this phase satisfies
- `.planning/REQUIREMENTS.md` §"Scoring Engine" — SCORE-01 (RMM via API), SCORE-02 (CS via API), SCORE-03 (TFM via API), SCORE-04 (Transfer Probability via API), SCORE-05 (component breakdowns on all 4 scores). SCORE-06 (parity testing) and SCORE-07 (O(1) caching) are explicitly OUT of this phase's scope — Phases 5 and 6 respectively.

### The ported, characterized logic this phase wraps (do not re-derive)
- `get-scouted-be/scoring/characterization/impact.py` — `add_player_impact()`, `compute_rmm_column()`, the 8 `_calc_*_impact_raw` functions, `components_dict` shape for RMM's breakdown
- `get-scouted-be/scoring/characterization/role_fit.py` — `calculate_subjective_role_fit_for_player_to_team()`, `compatibility_score()` for CS
- `get-scouted-be/scoring/characterization/deterministic_scores.py` — `compute_cs_tp_for_pairs()`, `transfer_probability()`, `financial_score()`, `contract_fit()`, `performance_score()` (the club-context RMM variant explicitly NOT exposed this phase)
- `get-scouted-be/scoring/characterization/tfm_model.py` — `build_transfer_value_dataset()`, `train_transfer_value_model()`, `add_value_labels()` (predicted_fee/fee_diff/value_verdict)
- `get-scouted-be/scoring/characterization/reconstruct.py` — the ORM→DataFrame reconstruction bridge every score calculator needs as input
- `get-scouted-be/scoring/ml_artifacts/tfm_value_model_v1.joblib` + `.metrics.json` — the versioned, already-trained TFM artifact (load, do not retrain)
- `get-scouted-be/scoring/docs/CURATION_MAP.md` — master per-score function/column/dependency map from Phase 3
- `get-scouted-be/scoring/docs/DUPLICATE_FUNCTIONS.md` + `ESCALATION_REVIEW.md` — authoritative-version decisions for every duplicated function in the source script

### Architecture guidance
- `.planning/research/ARCHITECTURE.md` §"Recommended Project Structure" — the `scoring/services/`, `scoring/views.py`, `scoring/serializers.py`, `scoring/models.py` (denormalized cache fields), `scoring/ml_artifacts/` layout this phase should follow
- `.planning/research/ARCHITECTURE.md` §"Pattern 1: Service Layer" — views parse/delegate/serialize only; all scoring logic lives in plain-Python `services/` functions with zero DRF/HTTP imports
- `.planning/research/ARCHITECTURE.md` §"Pattern 2: Hybrid Caching" — describes the FULL caching design (Redis/materialized aggregates); this phase implements NONE of the caching parts of this pattern (that's Phase 6) but should still follow the service-layer shape it describes
- `.planning/research/ARCHITECTURE.md` §"Anti-Pattern 1" (scoring math inline in views/serializers) and §"Anti-Pattern 3" (porting all 15,747 lines verbatim including dead duplicate definitions) — both directly apply; Phase 3 already resolved the duplicate-definition problem, this phase must not reintroduce it by porting from the raw script instead of from `scoring/characterization/`

### Product context for score definitions and display
- `GetScouted PRD.docx` §1.4 "Core Scoring Concepts" — RMM ("overall, position-aware performance score"), CS ("how well a player fits a specific club's tactical system, shown out of 100 with a breakdown"), TFM ("whether a player's market value and transfer cost are realistic for a given club's spending profile"), Transfer Probability ("modelled likelihood of a transfer occurring, used across shortlist, matching, and risk views")
- `GetScouted PRD.docx` §"Player Profile" (§3.0-3.1 and surrounding) — the page that consumes the combined summary endpoint; shows scoring breakdowns alongside player overview/performance metrics

### Prior phase precedent
- `.planning/phases/03-scoring-engine-curation-correctness-oracle/03-CONTEXT.md` §"Score-to-Artifact Mapping Resolution" — the locked TFM (RandomForestRegressor) vs Transfer Probability (deterministic formula) mapping this phase must not reverse
- `.planning/phases/03-scoring-engine-curation-correctness-oracle/03-RESEARCH.md` §"Related, Lower-Stakes Ambiguities" — the original RMM/CS open questions this session's discussion resolved
- `.planning/phases/02-auth-access-control/02-CONTEXT.md` — UUID PK convention, DRF/simplejwt already wired; scoring endpoints should require authentication like every other write/read endpoint in this project (role gating specifics are Phase 7/8's concern for CRUD, but base authentication applies now)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scoring/characterization/*.py` (Phase 3) — all four scores' core math already faithfully ported and tested; this phase wraps, does not rewrite
- `scoring/ml_artifacts/tfm_value_model_v1.joblib` — trained, versioned, loadable via `joblib.load()` immediately
- `accounts/` app — established DRF patterns to mirror (serializers.py, views.py, urls.py, permissions.py structure) even though scoring's actual logic differs substantially from auth's simple CRUD shape

### Established Patterns
- UUID primary keys on every model (`Player`, `Club`, `Transfer`, etc.) — score endpoints' path parameters follow this (`/players/{uuid}/...`)
- Django apps organized by domain, settings split `base.py`/`local.py`/`production.py` with `django-environ`
- `scoring/` app currently has NO `models.py`, `views.py`, `serializers.py`, or `urls.py` — this phase is the first to add them. `config/urls.py` currently only wires `accounts.urls`; this phase adds `path("api/scoring/", include("scoring.urls"))` or equivalent.

### Integration Points
- This is the FIRST API surface in the whole project besides auth — `players/`, `clubs/`, `transfers/` apps have models from Phase 1 but zero views/serializers/urls yet. Phase 4's scoring endpoints will be the first place those models get read via API.
- Downstream: Phase 5 (Parity Testing) will call these same service-layer functions (not necessarily the HTTP endpoints) and diff their output against Phase 3's oracle CSV.
- Downstream: Phase 6 (Caching) wraps this phase's service-layer calls with the precomputed-aggregate cache Pattern 2 describes, without needing to change this phase's API contract.
- Downstream: Phase 7 (Core CRUD) will likely surface these same scores as fields on Player/Club list/detail responses — this phase's denormalized-field decision (if any) affects how cheap that later read is.

</code_context>

<specifics>
## Specific Ideas

No specific visual/product references — this phase is entirely API contract and service-layer design. The PRD's Player Profile page description ("scoring breakdowns" shown alongside player overview) is the closest thing to a concrete reference, already reflected in the combined summary endpoint decision above.

</specifics>

<deferred>
## Deferred Ideas

- Finishing "Performance Score" (RMM's club-context-dependent variant) — needs league-wide `POSITION_METRICS` percentile machinery not yet built; revisit only if a future phase's product need requires it
- Exposing TFM's full 33-feature list / per-feature importances — new characterization work, not in scope
- Cross-checking fresh CS against the legacy `PlayerClubCompatibility.score` — no clear product need identified; legacy data stays in Postgres unused by this phase
- Any O(1) caching, precomputed aggregates, Redis, or materialized tables — entirely Phase 6's scope (SCORE-07)
- Numerical parity testing against Phase 3's oracle — entirely Phase 5's scope (SCORE-06)

</deferred>

---

*Phase: 04-scoring-engine-port*
*Context gathered: 2026-07-23*
