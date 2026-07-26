# Phase 12: Bidirectional Matching - Replacements & Player-Club Fit - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Authenticated users can get ranked matches in two directions off the same underlying scoring primitives: replacement players for a weak position at a club (ranked by RMM/CS/TFM), and clubs that fit a given player (ranked by CS/TFM). This is the final phase of the project. It does NOT build a squad-plan-integration ("add this suggested replacement to my Squad Plan" in one click) — that would touch Phase 8/11's `SquadPlan`, a different capability not asked for by either success criterion. It does NOT involve any LLM call — despite `PLAN-02`'s "AI-suggested" phrasing, ROADMAP's own success criteria for this phase are purely deterministic ("ranked by RMM/CS/TFM fit," "scored by CS/TFM") with zero mention of AI/LLM/narrative generation, consistent with this project's explicit, repeated principle that scores stay 100% deterministic.

All decisions below were made by Claude on the user's standing instruction ("make all necessary and important decisions considering trade-offs and execute") rather than through interactive discussion. Rationale is spelled out for each so downstream agents (and the user, on review) can see why.

</domain>

<decisions>
## Implementation Decisions

### "AI-suggested" (PLAN-02's wording) means algorithmically ranked, not an LLM call
- **Decision:** Replacement-player suggestions are computed entirely via existing deterministic scoring (RMM/CS/TFM) — no `ReportGenerator`, no Anthropic call, no narrative text. `PLAN-02`'s "AI-suggested" is read as informal language for "produced by the platform's scoring engine," not a literal requirement for LLM involvement.
- **Why:** ROADMAP's actual Phase 12 goal and all 3 success criteria never mention AI, LLM, or narrative generation once — they describe a ranking service scored by RMM/CS/TFM. REQUIREMENTS.md's own Out-of-Scope table is explicit: "LLM directly computing scores | Scores must stay deterministic — an LLM-guessed score is the exact crude heuristic this project replaces." A ranking is fundamentally a sort-by-score operation; running it through an LLM would contradict this project's core value, not fulfill it.

### The two ranking directions have genuinely asymmetric computational cost — reconcile "one shared service" against that reality, don't force symmetry that doesn't exist
- **Decision:** Both directions share one underlying scoring primitive (`compute_cs_tp_for_pairs` + RMM's club-independent `player_impact`), invoked through a single service module — but NOT via the same call pattern, because the two directions are not computationally symmetric:
  - **Replacements for a weak position** (`PLAN-02`, many-players × one-club): reuses `scoring/services/population.py::score_population(pop, club_name)` directly — the exact "arbitrary-other-club" live path Phase 6 explicitly deferred to this phase (`PROJECT.md`: "Arbitrary-other-club scoring... intentionally still computes live, deferred to Phase 12"). This scores the whole ~41,708-player population against one target club in a single pass, then filters to the weak position and ranks by RMM/CS/TFM — accepted as a multi-second live operation (not a hot path), bounded to a top-N result.
  - **Club fit for a player** (`PLAN-04`, one-player × many-clubs): does **NOT** call `score_population` once per candidate club (that would replay the expensive full-population pass ~1,060 times — completely infeasible). Instead it slices the population down to the single target player's row, then loops `compute_cs_tp_for_pairs` (or an equivalent thin wrapper) once per candidate club against that one-row slice — verified directly against the function's real implementation: its internal cost scales with the number of *player rows* processed (`for _, row in merged.iterrows()`), not with which club is targeted, so a single-player slice makes each per-club call cheap regardless of club count.
  - "One shared underlying service" (success criterion 3) is satisfied at the level of the actual scoring math (both directions call into the same `compute_cs_tp_for_pairs`/RMM primitives, no duplicated scoring logic, no two independently-maintained CS/TFM formulas) — not by forcing both directions through an identical, direction-blind code path that would make one of them absurdly slow for no reason.
- **Why:** This asymmetry is a direct, verified consequence of how the existing scoring code is actually structured (read directly from `scoring/characterization/deterministic_scores.py::compute_cs_tp_for_pairs` and `scoring/services/population.py::score_population`), not a guess. Forcing symmetric code paths would either make Player→Club matching catastrophically slow (replaying the full population scan per club) or silently wrong (trying to reuse a memoized whole-population result that was never computed for the right club context). The "shared service" requirement is about not duplicating the *scoring logic* — which this design honors — not about using literally identical code for two operations with different real-world cost profiles.

### Both endpoints exclude the "already there" case and return a bounded top-N, not a full paginated list
- **Decision:** Replacement suggestions exclude players already on the target club's current squad (a "replacement" is by definition someone not already there). Club-fit suggestions exclude the player's own current club (matching a player to their existing club isn't a transfer suggestion). Both return a bounded top-N (e.g., top 10) ranked list, not a full paginated browse — this is a "suggestions" surface, not a general list/filter endpoint like Phase 7's `/api/players/`.
- **Why:** Literal correctness — suggesting a club's own current player as their own replacement, or a player's own current club as their best-fit match, would be a nonsensical result that also happens to be the trivially-highest-scoring one in most cases (a player already fits their own club by construction in many of the scoring formulas), so excluding the "already there" case isn't just cosmetic, it prevents a systematically misleading top result. Top-N (not full pagination) matches the "suggestion" framing of both success criteria ("get a ranked list," not "browse all N results").

### Reuses Phase 11's Position Needs classification to identify "weak" — doesn't re-derive it
- **Decision:** The replacement-suggestion endpoint takes an explicit `position` parameter (not an automatic "find my weakest position for me" behavior) — the caller is expected to have already consulted Phase 11's `GET /api/clubs/{id}/position-needs/` to identify which position is weak/at-risk, then requests replacements for that specific position. This phase does not re-implement or wrap Phase 11's classification logic.
- **Why:** `PLAN-02`'s wording is "replacement players for a weak position" (singular, specific), not "replacement players for whichever position is weakest" — the caller already has Phase 11's classification available as a separate, already-built call. Auto-selecting "the weakest position" on the caller's behalf would be a product decision this phase's success criteria don't ask for, and would silently couple this endpoint's behavior to Phase 11's exact classification thresholds in a way that's harder to test/reason about independently.

### Claude's Discretion
- Exact top-N bound for both ranked lists (10 is a reasonable default; exact number is a display/UX detail with no functional consequence).
- Exact response JSON shape (field names, whether score breakdowns are included alongside the final ranking numbers, matching this project's established "never hide the numbers" transparency pattern from Phase 10).
- Whether replacement suggestions apply any additional guard (e.g., minimum RMM threshold to avoid suggesting clearly unsuitable players) beyond the position filter — not required by PLAN-02's literal wording, may be added if it improves suggestion quality without adding real complexity.
- Exact candidate-club set for Player→Club matching (all ~1,060 real clubs vs. some reasonable subset/league filter) — default to all real clubs unless the performance numbers found during research indicate a real reason to bound it further.

### Resolutions from 12-RESEARCH.md (post-research, pre-planning — locked)

Research verified this design against the real code and surfaced two issues requiring an explicit resolution before task-level plans are written. Both are resolved here rather than left open for the planner, per the standing "decide and execute" instruction.

- **PLAN-04's literal "single-row slice into `compute_cs_tp_for_pairs`" design is corrected to Pattern 2.** Verified: a one-row slice makes `compute_cs_tp_for_pairs`'s internal `groupby("Team")` squad-stats baseline blank (`NaN`) for every candidate club except the player's own current one — a real correctness bug, not a style choice. **Locked fix:** `rank_clubs_for_player` reuses the low-level pure functions directly (`calculate_subjective_role_fit_for_player_to_team`, `compatibility_score`, `classify_age_fit`, `classify_fit`, `financial_score`, `contract_fit`, `transfer_probability` from `role_fit.py`/`deterministic_scores.py`), with `squad_stats` (avg age/market value per club) computed ONCE over the full population and reused per candidate club — exactly 12-RESEARCH.md's "Pattern 2". This still satisfies success criterion 3 (shared scoring primitives, no re-derived formulas) — it just doesn't call the monolithic `compute_cs_tp_for_pairs` entry point directly for this direction.
- **"TFM" means the real ML Financial Fit pipeline (`scoring/services/financial_fit.py::get_financial_fit`, `predicted_fee`/`value_verdict`), not `compute_cs_tp_for_pairs`'s internal `financial_score` label.** Confirmed via `REQUIREMENTS.md` (SCORE-03), `PROJECT.md`'s Key Decisions table (Phase 4 entry explicitly: club-context TFM override "Required for Phase 12's planned 'rank clubs by fit for this player' feature to make sense at all") — this project uses "TFM" consistently for the trained pipeline everywhere else, and PROJECT.md was written anticipating this exact feature using the real one. **Locked design:** both endpoints rank candidates cheaply first using RMM/CS/`transfer_probability` (already-cheap deterministic scores, no ML call), bound to top-N, THEN call `get_financial_fit` (with the candidate club as context override) only for those top-N results to attach the real `predicted_fee`/`value_verdict`. `build_oracle_player_features` is verified fully vectorized (no per-row Python loop), so N calls (N=10-ish) stays cheap even though full-population candidates were filtered first. Never call the real TFM pipeline for the full unranked candidate set (thousands for PLAN-02, ~1,060 for PLAN-04) — cost would be unacceptable and unnecessary.
- **Ranking/sort key: `transfer_probability` is the primary sort key for both directions**, with RMM (`Player Impact`)/CS (`compatibility_score`)/real TFM (`predicted_fee`, attached post-ranking per above) exposed as visible breakdown fields on each ranked entry — not folded into a new invented composite score. `transfer_probability` is already this project's existing deterministic "how good a fit, blended" formula (combines compatibility, performance, financial label-fit, and contract fit) — reusing it as the sort key avoids inventing an unproven new weighting scheme for what "RMM/CS/TFM fit" means when combined.
- **PLAN-04's per-club loop (Pattern 2) has no existing latency benchmark** (it's new orchestration, not existing code) — the plan MUST include an early/Wave 0 task that live-times this loop against the real ~41,708-player/~1,060-club dev DB via `manage.py shell`, per this project's consistent "live-verify against real data, don't trust estimates" pattern (matches every prior phase, e.g. Phase 6's 44.6s/92.04s benchmarks).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 12: Bidirectional Matching - Replacements & Player-Club Fit" — goal, 3 success criteria, `PLAN-02`/`PLAN-04`, depends on Phase 6 + Phase 11
- `.planning/REQUIREMENTS.md` — `PLAN-02`, `PLAN-04` definitions; Out of Scope table ("LLM directly computing scores" — the reason this phase has zero LLM involvement despite `PLAN-02`'s "AI-suggested" phrasing)

### Scoring primitives this phase must reuse, not duplicate
- `get-scouted-be/scoring/services/population.py::score_population(pop, club_name)` — the many-players × one-club primitive `PLAN-02` reuses directly; also `reconstruct_population()` (memoized) and `resolve_club_name()`
- `get-scouted-be/scoring/characterization/deterministic_scores.py::compute_cs_tp_for_pairs` — the per-row scoring function whose cost scales with player-row count, not club count — the mechanism `PLAN-04`'s one-player × many-clubs direction must exploit via a single-row slice, verified directly against its real `for _, row in merged.iterrows()` implementation
- `get-scouted-be/scoring/services/compatibility.py`, `financial_fit.py`, `rmm.py` — existing single-pair (`get_compatibility`, `get_financial_fit`, `get_rmm`) service patterns for response-shape/breakdown conventions to follow

### Phase 11 classification this phase consumes, doesn't re-derive
- `get-scouted-be/clubs/services.py::classify_position_needs`/`position_needs_aggregate` — the "weak" classification the replacement endpoint's caller is expected to have already consulted; this phase does not wrap or re-implement it

### Existing filter/serializer conventions to follow
- `get-scouted-be/players/filters.py::PlayerFilter` — the clean 10-value `position` field this phase's position parameter must match
- `get-scouted-be/players/serializers.py::PlayerListSerializer` — likely reusable for representing ranked player results
- `get-scouted-be/clubs/serializers.py::ClubDetailSerializer`/list equivalents — likely reusable for representing ranked club results

### Prior phase context
- `.planning/PROJECT.md` — Key Decisions table: "Arbitrary-other-club scoring... intentionally still computes live, deferred to Phase 12" (Phase 6's decision this phase now fulfills) and "Requesting Financial Fit (TFM) for a specific club actually changes the prediction... required for Phase 12's planned 'rank clubs by fit for this player' feature to make sense at all" (Phase 4's decision this phase now depends on being true)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `score_population(pop, club_name)` — directly reusable for the replacement-players direction, no new bulk-scoring logic needed.
- `compute_cs_tp_for_pairs` — directly reusable (sliced to one player) for the club-matching direction.
- `PlayerListSerializer`/club serializers — likely reusable for ranked-result representation, consistent with every prior phase's serializer-reuse pattern.

### Established Patterns
- `Player.impact_score` (RMM) is club-independent — confirmed again relevant here: a player's RMM doesn't need recomputing per candidate club, only their CS/TFM does.
- This project has consistently deferred performance optimization until a real forcing reason exists (Phase 6's caching was scoped exactly to what SCORE-07 required) — this phase should follow suit rather than pre-building caching infrastructure for the replacement-players direction unless research finds the live cost is actually unacceptable for a non-hot-path "suggestions" feature.

### Integration Points
- This is the final phase of the v1 roadmap — no downstream phase consumes this phase's output.
- Upstream: depends on Phase 6 (the RMM-first scoring sequence, memoized `reconstruct_population()`) and Phase 11 (Position Needs classification, consumed but not re-derived).

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this phase is a backend API surface with no UI of its own (frontend integration is explicitly out of this project's scope per PROJECT.md).

</specifics>

<deferred>
## Deferred Ideas

- One-click "add this suggested replacement to my Squad Plan" integration — touches Phase 8/11's `SquadPlan`, not asked for by either success criterion; a future decision if ever wanted.
- Caching/precomputing replacement-player rankings per club — not built unless research finds the live `score_population` cost is actually unacceptable for this non-hot-path feature; matches this project's consistent "don't add infra without a forcing reason" pattern.
- Bounding the Player→Club candidate-club set below "all real clubs" — default is the full set; narrowing (e.g., by league) is a future decision if the unbounded set proves genuinely too broad to be useful.

</deferred>

---

*Phase: 12-bidirectional-matching-replacements-player-club-fit*
*Context gathered: 2026-07-26*
