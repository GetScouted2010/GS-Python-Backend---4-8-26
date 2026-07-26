# Phase 11: Position Needs & Squad Simulation - Context

**Gathered:** 2026-07-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Authenticated users can view a real Position Needs analysis for a club's squad — per-position strong/weak/at-risk classification based on depth, contract expiry, and age — and can simulate a squad change (add/remove/swap) against a Squad Plan to see recalculated aggregate metrics (avg age, avg score, budget impact), entirely without persisting anything until the user separately saves it. This phase does NOT build AI-suggested replacement players (Phase 12's `PLAN-02`) or Player→Club matching (Phase 12's `PLAN-04`) — both reuse this phase's scoring/aggregation primitives but are their own ranking features, out of this phase's scope.

All decisions below were made by Claude on the user's standing instruction ("make all necessary and important decisions considering trade-offs and execute") rather than through interactive discussion. Rationale is spelled out for each so downstream agents (and the user, on review) can see why.

</domain>

<decisions>
## Implementation Decisions

### Position Needs extends Phase 10's existing aggregation, not a rebuild
- **Decision:** `PLAN-01`'s Position Needs feature extends `clubs/services.py::position_needs_aggregate(club)` (built in Phase 10 as a deliberately narrow, internal-only helper for AI-04's club-insights grounding) rather than writing a second, parallel aggregation. The same bounded, single-club `.values("position").annotate(...)` ORM query (squad depth, avg age, contracts-expiring-within-12-months per position) is reused as-is; this phase adds a classification layer on top (`strong`/`weak`/`at-risk` per position) and a new public, user-facing endpoint that exposes it.
- **Why:** Phase 10's docstring already documents itself as narrower than "Phase 11's full canonical Position Needs feature" and anticipates this reuse. Recomputing the same numbers a second way would risk the two aggregations silently disagreeing — the exact class of bug this project has caught and fixed multiple times before (Phase 4's TFM log-scale bug, Phase 6's compatibility-score merge collision).

### Strong/weak/at-risk classification: a concrete, documented 3-signal heuristic
- **Decision:** Per position, per club: **weak** if `squad_depth < 2` (fewer than 2 recognized players — real risk of no fit cover); **at-risk** if depth is adequate (`>= 2`) but either `avg_age > 30` (an aging cohort) or `contracts_expiring_within_12mo >= squad_depth / 2` (half or more of the position's players are out of contract within a year); **strong** otherwise (adequate depth, not aging, not facing mass contract expiry). A position can only receive one label — checked in the order weak → at-risk → strong.
- **Why:** ROADMAP specifies the 3 input signals (depth, contract expiry, age) and the 3 output labels, but not the exact thresholds — a real product judgment call with no single objectively-correct formula. These specific numbers (2, 30, 50%) are reasonable, explainable defaults for a football squad-planning context, documented explicitly here so the planner/executor doesn't have to invent unstated thresholds mid-implementation, and so the user can adjust them on review if they don't match domain expectations.

### Squad simulation reuses Phase 8's `proposed_changes` schema and Phase 8's own SquadPlan update endpoint for "commit" — no new commit endpoint
- **Decision:** `POST /api/workspace/squad-plans/{id}/simulate/` accepts an OPTIONAL `proposed_changes` override in the request body (same `[{"action": "add"|"remove"|"swap", "player_id": ..., "incoming_player_id": ...}]` shape Phase 8 already defined on the `SquadPlan` model) — if omitted, simulates the SquadPlan's own currently-stored `proposed_changes`. It computes recalculated metrics by applying the changes to the live current squad **entirely in memory** and returns them; it **never writes to the database**. "Committing" a simulated change (ROADMAP's success criterion #3) means the user separately calls Phase 8's existing `PATCH /api/workspace/squad-plans/{id}/` to persist the `proposed_changes` they want to keep — no new dedicated "commit" endpoint is built, since that would duplicate Phase 8's already-existing, already-tested update path.
- **Why:** Accepting an optional override lets a user experiment with several hypothetical variants before deciding which one (if any) to actually save, without needing to PATCH-then-simulate-then-PATCH-again for every experiment. Reusing Phase 8's PATCH endpoint as the literal "commit" action is the simplest interpretation of "not persisted until committed" that doesn't invent a second, parallel persistence mechanism.

### Simulation metrics use `impact_score` (RMM) for "avg score," never the club-context scores, for incoming/outgoing players
- **Decision:** "Avg score" in recalculated squad metrics means the squad's average `Player.impact_score` (RMM) — never `compatibility_score`, `financial_fit_score`, or `transfer_probability_score`. "Budget impact" is computed as the net `Player.market_value` delta of the proposed changes (sum of incoming players' market values minus outgoing players' market values) — there is no wage/salary field anywhere in the migrated dataset (confirmed: `Player` has `market_value` and `contract_expires`, no wage/salary column), so market-value delta is the only real financial signal available to approximate "budget/wage impact."
- **Why:** `Player.impact_score` is confirmed club-independent (its model comment reads plainly "RMM (Player Impact)," unlike the other three fields which are explicitly documented "vs own club"). This matters concretely for simulation: an "add"/"swap" can bring in a player who currently plays for a *different* real club — their denormalized `compatibility_score` would be relative to that other club, not the club being simulated into, and using it would silently produce a wrong number. `impact_score` has no such trap. Market-value delta as a wage proxy is an honest data-driven substitute, not a fabricated number — it's a real, already-migrated field, just not literally "wage."

### Claude's Discretion
- Exact response JSON shape for both new endpoints (field names, nesting) beyond what's locked above.
- Whether the Position Needs endpoint also returns the raw per-position numbers alongside the classification label (recommended: yes, for transparency, matching this project's established "never hide the numbers behind a label" pattern from Phase 10's grounding-echo design) — exact inclusion is left to the planner.
- Whether simulation validates that referenced `player_id`/`incoming_player_id` values in an ad-hoc override actually exist before computing (recommended: yes, clean 400 on an invalid ID, matching this project's "never fabricate, catch problems early" convention) — exact error-shape details left to the planner.
- Any additional squad-composition metrics beyond avg age/avg score/budget impact (e.g. position-balance counts) — not required by PLAN-03's literal wording, may be added if low-cost.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 11: Position Needs & Squad Simulation" — goal, 3 success criteria, `PLAN-01`/`PLAN-03`, depends on Phase 6 + Phase 8
- `.planning/REQUIREMENTS.md` — `PLAN-01`, `PLAN-03` definitions; `PLAN-02`/`PLAN-04` (Phase 12, explicitly NOT this phase's scope)

### Aggregation this phase extends, not duplicates
- `get-scouted-be/clubs/services.py::position_needs_aggregate(club)` — the exact bounded ORM aggregation (squad depth/avg age/contracts-expiring-within-12mo per position) built in Phase 10, to be extended with classification labels, not reimplemented

### Squad Plan model/schema this phase builds on
- `get-scouted-be/workspace/models.py::SquadPlan` — `proposed_changes` `JSONField(default=list)`, the exact `[{"action": ..., "player_id": ..., "incoming_player_id": ...}]` shape simulation must parse
- `get-scouted-be/workspace/views.py` — existing `SquadPlanViewSet` (CRUD-08, Phase 8) — the PATCH endpoint this phase's "commit" flow reuses; also the existing `current_squad` `SerializerMethodField` pattern (live-derived via `PlayerListSerializer(obj.club.players.all(), ...)`) simulation's "current squad" baseline should match

### Score fields this phase must use correctly
- `get-scouted-be/players/models.py` — `Player.impact_score` (club-independent, use for avg-score) vs. `compatibility_score`/`financial_fit_score`/`transfer_probability_score` (own-club context, do NOT use for squad-average metrics involving incoming players from other clubs); `Player.market_value` (the only financial field — no wage/salary exists); `Player.age`, `Player.contract_expires`, `Player.position`

### Prior phase context
- `.planning/phases/10-ai-grounded-report-generation/10-CONTEXT.md` — the original Phase-10-vs-Phase-11 Position Needs scoping decision this phase now fulfills
- `.planning/PROJECT.md` — Key Decisions table (own-club-context score fields, denormalization rationale)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `position_needs_aggregate()` — directly extensible for the classification layer, no new aggregation query needed.
- `SquadPlanViewSet`'s existing `current_squad` live-derivation pattern — the exact baseline-squad-fetch logic simulation should mirror.
- `PlayerListSerializer` — likely reusable for representing simulated squad membership in the response, consistent with every prior phase's serializer-reuse pattern.

### Established Patterns
- No wage/salary field exists anywhere in the migrated dataset — `market_value` is the only financial signal.
- `impact_score` is club-independent; the other 3 denormalized score fields are own-club-context only — a real correctness trap for any feature (like this one) that reasons about players relative to a club other than their current one.
- This project consistently reuses existing serializers/services across app boundaries (`clubs/services.py` already imports from `players/ai/`, `clubs/serializers.py` already imports `PlayerListSerializer` from `players/`) rather than duplicating logic — this phase should follow suit.

### Integration Points
- Downstream: Phase 12's `PLAN-02` (AI-suggested replacements) and `PLAN-04` (Player→Club matching) will likely reuse this phase's scoring primitives (`impact_score`-based ranking) and possibly the Position Needs classification (to identify which positions need suggestions for).

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this phase is a backend API surface with no UI of its own (frontend integration is explicitly out of this project's scope per PROJECT.md).

</specifics>

<deferred>
## Deferred Ideas

- AI-suggested replacement players ranked by RMM/CS/TFM fit — `PLAN-02`, Phase 12 explicitly.
- Player → Club matching (ranked list of clubs that fit a player) — `PLAN-04`, Phase 12 explicitly.
- A dedicated "commit simulation" endpoint distinct from Phase 8's existing SquadPlan PATCH — deliberately not built; PATCH already serves this role.
- Wage/salary as a distinct financial dimension from market value — not available in the migrated dataset; would require a new data source, a future decision if ever wanted.

</deferred>

---

*Phase: 11-position-needs-squad-simulation*
*Context gathered: 2026-07-26*
