# Phase 6: Scoring Performance & Caching Layer - Context

**Gathered:** 2026-07-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Make live scoring fast and safe under real concurrency. Right now every score computation reconstructs and re-scores the entire 41,708-player population from Postgres (~75-115s), because RMM/CS/TP/TFM are all population-relative by construction. This phase does NOT change any scoring math (Phases 3-5 already proved it correct) — it only changes how fast the already-correct answer is produced. No new scores, no new endpoints beyond what Phase 4 already exposed, no UI.

All decisions below were made by Claude on the user's explicit standing instruction from Phase 5 ("make all necessary and important decisions considering trade-offs and execute" — user is not confident evaluating implementation trade-offs directly) rather than through interactive discussion. Rationale is spelled out for each so downstream agents (and the user, on review) can see why.

</domain>

<decisions>
## Implementation Decisions

### Denormalization target for "own club" final scores
- **Decision:** Add 4 new nullable, indexed `FloatField`s directly onto the existing `Player` model: `impact_score` (RMM), `compatibility_score`, `financial_fit_score` (TFM, money-scale via `np.expm1`, not the raw log-scale model output), `transfer_probability_score`. Each computed **against the player's own current club** — the exact same context the Phase 3 oracle and Phase 4's services already default to when no `club_id` is given, and the same context Phase 5 already proved correct. No new model.
- **Why not a separate `PlayerScore` model:** Phase 7's CRUD-01 requirement is literally "filter/sort/paginate Players by... score thresholds" — that needs `Player.objects.filter(impact_score__gte=80).order_by('-impact_score')` to work as a plain indexed column query. A separate model forces a join (or a denormalized copy anyway) on every single list/browse request, undermining the exact performance goal this phase exists for.
- **Why not overload `legacy_total_score`:** that field is explicitly documented as "the OLD (pre-Django) system... NOT the Impact RMM" — reusing it would silently conflate two different scoring systems the project has gone to considerable lengths (Phases 3-5) to keep distinct.
- Player-vs-*arbitrary*-other-club scores (used by Phase 4's live `/api/scoring/*?club_id=` params and Phase 12's future "rank clubs for this player") are **not** denormalized — there are 41,708 × 1,060 possible pairs, far too many to precompute and store. Those stay live-computed, but faster (see next decision).

### Precomputed aggregate caching (the O(1) mechanism for live/arbitrary-club computation)
- **Decision:** Extend the exact in-process memoization pattern this codebase already established in `scoring/services/population.py::get_tfm_pipeline()` (an `lru_cache`-wrapped module-level singleton for the joblib artifact) to also memoize `reconstruct_population()`'s output and `score_population()`'s expensive intermediates (`std_lookup`, `team_styles_df`, team-position reference). A live request for an arbitrary player-club pairing then reuses the cached population/aggregates instead of re-querying and re-scoring all 41,708 players from Postgres every time.
- **Why not Redis / Django's generic cache framework:** neither exists anywhere in this codebase today (verified: no `CACHES` setting, no `redis`/`celery` package installed). PROJECT.md's own Constraints explicitly defer the hosting/deployment target ("Docker/12-factor-friendly... decision doesn't block backend work") and the timeline is a soft 4-day target — introducing a new infrastructure dependency (a Redis instance, cross-process cache invalidation) is exactly the kind of premature architecture commitment the project has been deliberately avoiding elsewhere (see PROJECT.md's LLM-provider and hosting decisions, both explicitly deferred). The in-process pattern needs zero new infra and directly extends code Phase 4 already wrote and proved reliable.
- **Trade-off accepted:** in-process caching means each server *process* (e.g. each gunicorn worker, if/when one is chosen) rebuilds its own copy once, not a single shared cache across processes. Acceptable given hosting/process-model isn't decided yet; flagged as a Deferred Idea below for whenever Redis or a shared-cache layer becomes relevant.

### Rebuild trigger — management command, not Django signals
- **Decision:** A new management command (e.g. `recompute_scores`, following the exact naming/structure precedent of `generate_scoring_oracle.py`/`train_tfm_model.py`) recomputes and writes the 4 denormalized `Player` fields, and clears the in-process aggregate cache so the next live request rebuilds fresh. This is the same "repeatable regeneration flow" pattern Phase 5 already established and confirmed with the user (data scientist updates data → rerun the relevant command).
- **Why not `post_save` signals:** verified directly — **no signals exist anywhere in this codebase today**, and more importantly, Phase 1's real data-import commands use `bulk_create`/`bulk_update` throughout (confirmed in STATE.md's Phase 1 decisions), which **does not fire Django's `post_save` signal** per Django's own documented behavior. A signal-based "rebuild on save" design would silently never fire during the exact bulk data-refresh flow this project actually uses — a real correctness bug, not just a stylistic preference.
- The command must be safe to run against the live dev DB while the app is serving requests (read the old denormalized values until the new ones are written, no partial-write window a live request could observe as a broken intermediate state) — left as an implementation detail for the planner/executor, not re-litigated here.

### Timing verification (Success Criterion 4)
- **Decision:** The "stays flat as dataset size grows" check is a real, automated test — not a manual/eyeballed claim. Time a single-player score retrieval (both the denormalized-field read path AND a live arbitrary-club computation path) before and after the aggregate cache is warm, and assert the warm-cache path is at least an order of magnitude faster than the cold/no-cache baseline (which Phase 5's research already measured concretely: ~74-115s cold). Exact assertion thresholds are Claude's Discretion for the planner to set based on what's actually measured.

### Claude's Discretion
- Exact field names for the 4 new `Player` columns, exact DB index definitions.
- Exact management command name/flags, and how it batches the 41,708-player recompute (single bulk pass vs chunked) to keep memory reasonable.
- Whether to also warm the in-process cache automatically at process startup (e.g. Django `AppConfig.ready()`) versus only on first live request — a nice-to-have, not required by any success criterion.
- Exact timing-test thresholds/methodology (see above).
- Whether `financial_fit_score`'s money-scale conversion happens at write time (store money-scale directly) or read time — store money-scale directly is the natural default given Phase 5 already established `np.expm1` is applied once per comparison, but this is an implementation detail.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 6: Scoring Performance & Caching Layer" — goal, 4 success criteria, `SCORE-07`, depends on Phase 4 + Phase 5
- `.planning/REQUIREMENTS.md` — `SCORE-07`: "Live per-entity scoring runs in O(1) time against precomputed/cached aggregates — no full-dataset pandas operations inside a request cycle"

### The existing memoization precedent this phase extends
- `get-scouted-be/scoring/services/population.py::get_tfm_pipeline()` — the `lru_cache`-wrapped singleton pattern to replicate for `reconstruct_population()`/`score_population()`'s aggregates
- `get-scouted-be/scoring/services/population.py::reconstruct_population()`, `score_population()` — the expensive whole-population operations being cached; confirmed live-timed at ~3.5s (reconstruct alone) / ~74-115s (full scoring) in Phase 5's research

### The management-command precedent this phase follows
- `get-scouted-be/scoring/management/commands/generate_scoring_oracle.py` — naming/structure precedent, and the exact bulk column-merge order (`player_impact` before `compute_cs_tp_for_pairs`, then TFM last) the new recompute command must replicate faithfully
- `get-scouted-be/scoring/management/commands/train_tfm_model.py` — second precedent for this codebase's management-command conventions

### The models being denormalized onto
- `get-scouted-be/players/models.py::Player` — read the existing field conventions (FloatField usage, the `legacy_total_score` field's docstring explicitly distinguishing it from the new Impact RMM system) before adding the 4 new score fields
- `get-scouted-be/players/models.py::PlayerRoleScore`, `PlayerClubCompatibility` — existing precedent for `models.Index(fields=["club", "-score"])`-style indexes to replicate for the new denormalized fields

### Prior phase context
- `.planning/phases/04-scoring-engine-port/04-CONTEXT.md`, `.planning/phases/05-scoring-parity-testing/05-CONTEXT.md` — established conventions: "own current club" as the default context, `np.expm1` money-scale unwrap, never zero-fill/always NaN-propagate
- `.planning/PROJECT.md` — Constraints section (hosting deferred, 4-day soft deadline, Docker/12-factor-friendly) and Key Decisions table

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scoring/services/population.py`'s existing `lru_cache` pattern (`get_tfm_pipeline`) — direct precedent to extend, not invent from scratch.
- `scoring/services/{rmm,compatibility,financial_fit,transfer_probability}.py` — the 4 `get_*` functions whose "own club" computation this phase's denormalized fields must match exactly (same inputs, same defaults).
- `scoring/management/commands/generate_scoring_oracle.py` — nearly the exact computation this phase's recompute command needs, already proven correct against real data; largely a matter of reusing its orchestration and writing to `Player` fields instead of a CSV.

### Established Patterns
- No Django signals anywhere in this codebase; all data mutation flows through explicit management commands using `bulk_create`/`bulk_update`. Phase 6's rebuild trigger must follow this same explicit-command convention, not introduce signals as a new pattern.
- "Never zero-fill, NaN propagates" — the new denormalized fields must stay `null=True` and genuinely null where the live computation would be null (e.g. GK/LB/RB's structurally-null CS/TP, confirmed in Phase 5), not defaulted to 0.

### Integration Points
- Downstream: Phase 7 (Core CRUD) directly depends on this phase and will query the 4 new denormalized fields for `CRUD-01`'s "filter/sort/paginate... by score thresholds."
- Downstream: Phase 10, 11, 12 also formally depend on Phase 6 per ROADMAP.md — they need fast score access for AI report grounding, squad simulation, and bidirectional matching, respectively.

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this is backend performance infrastructure with no user-facing surface of its own (it makes Phase 4's existing surface fast, nothing new is exposed).

</specifics>

<deferred>
## Deferred Ideas

- A real shared cache layer (Redis or similar) across multiple server processes — deferred until hosting/process-model is actually decided (PROJECT.md already defers this explicitly); the in-process `lru_cache` approach is a deliberate stepping stone, not a permanent architecture decision.
- Incremental/signal-based rebuild (recompute only the changed player/club instead of the whole population) — deferred; the current data-refresh flow is already batch-oriented (Phase 1's `import_all`, Phase 5's oracle regeneration), so a full-recompute-on-demand command matches how data actually changes in practice. Worth revisiting only if incremental single-player edits become a real workflow.
- Background/async task queue (Celery) for running the recompute command without blocking — deferred; no async infra exists yet and the recompute is an operator-triggered, infrequent operation (matching Phase 5's "rerun whenever the data scientist refreshes data" cadence), not a per-request concern.

</deferred>

---

*Phase: 06-scoring-performance-caching-layer*
*Context gathered: 2026-07-24*
