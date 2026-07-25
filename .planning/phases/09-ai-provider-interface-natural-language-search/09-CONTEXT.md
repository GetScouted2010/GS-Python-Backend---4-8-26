# Phase 9: AI Provider Interface & Natural-Language Search - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Authenticated users can submit a plain-language query (e.g. "young left-backs under €5M who play for possession-based clubs") and get back real, structured Player results — filtered against a fixed whitelist of real fields, never an LLM-fabricated answer. An ambiguous or unparseable query degrades gracefully (partial filters or keyword fallback) rather than erroring or returning nothing. The LLM call itself goes through a provider-agnostic interface so the concrete provider can be swapped later with zero changes to calling code. This phase does NOT build AI-generated scouting reports or club insights (Phase 10 — those consume already-computed scores/stats, a different capability), does not build a free-form multi-turn conversational agent (explicitly out of scope per REQUIREMENTS.md), and does not let the LLM compute or influence any score (scores stay 100% deterministic, per this project's core value).

All decisions below were made by Claude on the user's standing instruction ("make all necessary and important decisions considering trade-offs and execute") rather than through interactive discussion. Rationale is spelled out for each so downstream agents (and the user, on review) can see why.

</domain>

<decisions>
## Implementation Decisions

### Concrete provider: Anthropic Claude (Messages API + tool-use), behind a swappable interface
- **Decision:** The first concrete implementation calls Anthropic's Messages API using tool-use / a forced JSON schema to extract structured filters, via a small `NLQueryParser` abstract interface (one method: `parse(query: str) -> ParsedQuery`). A `get_nl_query_parser()` factory reads `LLM_PROVIDER` from settings/env (django-environ, matching `EMAIL_BACKEND`'s existing pattern) and returns the configured implementation. Swapping providers later means adding one new class + one env var change — zero changes to the search view/service that calls `get_nl_query_parser()`.
- **Why:** AI-05 requires provider-agnosticism, but a concrete phase still needs *a* real implementation to prove the interface actually works end-to-end (an interface with zero implementations proves nothing). Anthropic's tool-use gives reliable structured/schema-constrained output, which is exactly what's needed to keep parsed filters restricted to the fixed real-field whitelist — the same reason function-calling/tool-use exists as a pattern, not a brand preference. No LLM SDK exists yet anywhere in this codebase (verified via grep) — this is genuinely greenfield.

### Fixed field whitelist, including how "style" resolves
- **Decision:** NL search targets **Players only** (not a combined Player+Club search — that would be scope creep beyond this phase's boundary). The whitelist is exactly Phase 7's existing `PlayerFilter` query params: `position`, `league`, `age_min`/`age_max`, `market_value_min`/`market_value_max`, plus the 4 score thresholds. "Style" (mentioned in ROADMAP's success criteria) resolves through the player's **club's** playing-style fields (`club__control_possession`, `club__gegenpressing`, etc. — the same 8 fields `ClubFilter` already exposes), since `Player` itself has no style field (verified directly against `players/models.py` — style is Club-only, confirmed in `clubs/filters.py`). The LLM's job is to map free text onto this exact whitelist; it never invents new filter dimensions.
- **Why:** Reusing Phase 7's already-tested, already-correct filter fields (not reinventing a parallel filter set) means the NL layer is a thin translation step on top of proven filtering logic, not a new source of correctness bugs. The "style through club" resolution is the only way to make ROADMAP's literal field list ("position, age, value, league, style") actually map onto real, existing, non-null-heavy data.

### Endpoint shape: `POST /api/players/search/`, returns parsed filters + fallback flag + paginated results
- **Decision:** New endpoint `POST /api/players/search/` (added to `players/urls.py`), body `{"query": "<free text>"}`. Response: `{"query": "...", "parsed_filters": {...}, "fallback_used": bool, "results": {<same paginated envelope as GET /api/players/, reusing PlayerListSerializer + IdsBypassPagination>}}`. POST (not GET) because this triggers a non-idempotent, cost-bearing external LLM call — matching the existing `@action`-style semantics already used for Shortlist's `export` action in Phase 8, not the plain-GET semantics of the already-existing structured-filter list endpoint.
- **Why:** Exposing `parsed_filters` back to the caller makes the "graceful degradation" requirement (AI-02) verifiable and debuggable — a caller/tester can see exactly what was understood vs. what fell back, rather than a black box. Reusing `PlayerListSerializer`/pagination from Phase 7 keeps result shape consistent with every other player-listing surface in this API, rather than inventing a third results shape.

### Fallback behavior (AI-02): partial-filter application, then keyword regex, then unfiltered — never an error
- **Decision:** Three-tier degradation, in order: (1) If the LLM returns a full or partial structured filter set, apply whatever it confidently extracted and ignore terms it couldn't map — response includes `fallback_used: false` if a full parse succeeded on all mappable terms, or the partial filters still applied with `fallback_used: false` (still "the LLM's real answer," just partial). (2) If the LLM call itself fails (timeout, API error, malformed/empty response), fall back to a lightweight keyword/regex extractor (position synonyms — "centre back"/"CB", "striker"/"FWD" — a number-plus-suffix parser for "under €5M"/"5m", a substring match against real league names) — response has `fallback_used: true`. (3) If even the keyword fallback extracts nothing usable, return the full unfiltered (but still paginated) player list with `parsed_filters: {}` and `fallback_used: true` — always HTTP 200, never a 4xx/5xx or empty-crash response.
- **Why:** ROADMAP's success criterion #2 is explicit: "never an error or empty crash." A 3-tier fallback (real parse → cheap deterministic parse → show-everything) guarantees a response at every tier while being honest via `fallback_used` about which tier actually served the request — critical for a demo where an LLM API hiccup shouldn't ever be visible as a broken endpoint.

### RecentActivity integration: NL search populates the `"searched"` event type Phase 8 built for it
- **Decision:** Every call to `POST /api/players/search/` (success or fallback) writes a `RecentActivity` row with `activity_type="searched"`, `query_text=<raw query>`, `target_id=None` — using the exact model/pattern `workspace/models.py::RecentActivity` already defines.
- **Why:** Phase 8's `08-CONTEXT.md` explicitly built `"searched"` as "structurally ready... Phase 9 is the only future producer of that event type" and deliberately didn't fabricate search history it didn't have yet. This phase is that producer — wiring it up is completing a contract Phase 8 already committed to, not a new decision with real ambiguity.

### Claude's Discretion
- Exact Anthropic model choice for the parsing call (a small/fast model is sufficient for structured extraction against a fixed whitelist — this isn't open-ended generation).
- Exact prompt/tool-schema wording sent to the LLM.
- Whether parsed-but-unmappable terms are surfaced back to the caller as an `unparsed_terms` list (nice-to-have transparency, not required by AI-01/AI-02's literal wording) — planner may include if low-cost.
- Retry/timeout tuning for the Anthropic API call before falling back to tier 2.
- Exact regex/synonym dictionary shape for the keyword-fallback tier.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 9: AI Provider Interface & Natural-Language Search" — goal, 3 success criteria, `AI-01`/`AI-02`/`AI-05`, depends on Phase 7
- `.planning/REQUIREMENTS.md` — `AI-01`, `AI-02`, `AI-05` definitions; Out of Scope table (free-form conversational agent, LLM-computed scores, concrete-provider-lock-in are all explicitly excluded)

### Filter fields this phase must reuse, not reinvent
- `get-scouted-be/players/filters.py::PlayerFilter` — the exact field set (`position`, `league`, `age_min/max`, `market_value_min/max`, 4 score thresholds) the NL parser must map onto
- `get-scouted-be/clubs/filters.py::ClubFilter` — the 8 playing-style fields ("style" resolves through `club__<style_field>`)
- `get-scouted-be/players/serializers.py::PlayerListSerializer` — reused verbatim for search results
- `get-scouted-be/core/pagination.py::IdsBypassPagination` — reused for the search endpoint's paginated results

### Config/secrets pattern to follow
- `get-scouted-be/config/settings/base.py` — `EMAIL_BACKEND = env("EMAIL_BACKEND", default=...)` is the established django-environ pattern `LLM_PROVIDER`/API-key settings must follow
- `get-scouted-be/.env.example` — existing convention for documenting required env vars without committing secrets

### RecentActivity contract this phase completes
- `get-scouted-be/workspace/models.py::RecentActivity` — the `"searched"` `activity_type`, `query_text` field Phase 8 built for this phase to populate
- `.planning/phases/08-user-workspace-crud/08-CONTEXT.md` — the explicit forward-looking note: "Phase 9 (NL search, not yet built) is the only future producer of that event type"

### Prior phase context
- `.planning/PROJECT.md` — Constraints section: "LLM integration must be built behind a provider-agnostic interface; concrete provider... is an explicit later decision" (this phase IS that later decision) + Key Decisions table

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PlayerFilter`/`ClubFilter` — the parser's structured output must be valid input to these, not a parallel filtering mechanism.
- `PlayerListSerializer` + `IdsBypassPagination` — directly reusable for search results, no new serializer/pagination class needed.
- `django-environ` (`env()`) — already the project's config pattern; `LLM_PROVIDER`/`ANTHROPIC_API_KEY` should follow it exactly.

### Established Patterns
- No LLM/AI SDK dependency exists anywhere in the codebase yet (verified via grep across `get-scouted-be`) — this phase adds the first one.
- Global `IsAuthenticated` default (deny-by-default) already covers this endpoint; no new permission class is needed — any authenticated user may search.
- `Shortlist.export` `@action` (Phase 8) is the precedent for a POST-triggered, non-idempotent read-like operation on an otherwise RESTful resource.

### Integration Points
- Downstream: Phase 10 (AI scouting reports/club insights) will likely reuse this phase's provider-agnostic interface pattern (`NLQueryParser`-style abstraction) for its own LLM calls, though with a different concrete task (generation, not extraction).
- Upstream: Phase 8's `RecentActivity` model already has the `"searched"` event type waiting for this phase to populate it.

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this phase is a backend API surface with no UI of its own (frontend integration is explicitly out of this project's scope per PROJECT.md).

</specifics>

<deferred>
## Deferred Ideas

- Combined Player+Club dual-entity NL search (e.g. "find clubs that need a striker") — not asked for by AI-01's field whitelist, which matches Player fields; would be its own future decision if ever wanted.
- AI-generated scouting reports / club insights consuming this phase's parser — that's Phase 10 explicitly, a generation task not an extraction task.
- Caching/memoizing repeated identical NL queries to reduce LLM cost — not required by AI-01/AI-02's wording; REL-01 (v2 requirement) already flags "report caching... ship always regenerate first" as the project's general stance on this class of optimization.
- Multi-turn conversational refinement of a search ("no, cheaper than that") — explicitly out of scope per REQUIREMENTS.md's "Free-form multi-turn conversational AI agent" exclusion.

</deferred>

---

*Phase: 09-ai-provider-interface-natural-language-search*
*Context gathered: 2026-07-25*
