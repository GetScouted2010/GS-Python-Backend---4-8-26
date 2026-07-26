# Phase 7: Core CRUD - Players & Clubs - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can browse, filter, sort, and paginate real Player and Club data (including scores), retrieve full single-entity detail, and fetch multiple entities by ID for comparison — through a read-only API surface. No writes (Watchlist/Shortlist/Squad Plans are Phase 8), no new scoring logic (Phases 3-6 already own that), no AI/NL search (Phase 9). This phase is the read/browse layer on top of everything built so far.

All decisions below were made by Claude on the user's standing instruction from Phase 5/6 ("make all necessary and important decisions considering trade-offs and execute") rather than through interactive discussion. Rationale is spelled out for each so downstream agents (and the user, on review) can see why.

</domain>

<decisions>
## Implementation Decisions

### Filtering, sorting, and pagination stack
- **Decision:** Adopt `django-filter` for `FilterSet`-based query-param filtering (exact match on position/league/country/playing-style; range filters via `gte`/`lte` on age/market_value/the 4 score fields), DRF's built-in `OrderingFilter` for `?ordering=-impact_score`-style sorting, and DRF's `PageNumberPagination` (default page size 25, client-adjustable via `page_size` up to a capped max of 100) for pagination.
- **Why a new dependency here, unlike Phase 6's Redis-avoidance:** `django-filter` is the de facto standard DRF companion for exactly this shape of problem (list/filter/sort/paginate over a queryset) — low-risk, single-purpose, doesn't commit the project to an infrastructure decision the way Redis would have. Not currently installed; this phase adds it.
- **Why range filters, not just exact match:** CRUD-01 explicitly requires filtering by age, market value, and score *thresholds* — inherently range queries ("age between 18 and 23," "impact_score >= 80"), not exact-match lookups.

### List vs. detail response depth
- **Decision:** Two-tier serializers per entity.
  - **List** (`GET /api/players/`, `GET /api/clubs/`): lightweight — identity fields, position/league/club, market value, and the 4 denormalized own-club scores (`impact_score`/`compatibility_score`/`financial_fit_score`/`transfer_probability_score`) already built in Phase 6. No stat breakdown, no full 99-column stat block — keeps list responses small and fast across 41,708 rows.
  - **Detail** (`GET /api/players/{id}/`, `GET /api/clubs/{id}/`): full profile — every stat field, plus score **breakdowns**, not just the 4 scalar values.
- **Why detail calls the existing scoring service instead of re-deriving breakdowns:** `scoring.services.summary.get_summary(player_id, club_id)` already composes all 4 scores + full breakdowns for the own-club case, and Phase 6's gap closure made it genuinely fast (~0.2s, verified against real data) specifically so call sites like this could use it inline. Player detail calls it directly rather than reimplementing breakdown assembly a second time.

### "Season-by-season stats" — scoped to match the real data model
- **Decision:** Player detail exposes the single season snapshot that actually exists for that player (labeled with the real `season` field value: `"2024-2025"`, `"2023-2024"`, `"2022-2023"`, or `"Last Calendar Year"`), not a fabricated multi-season history.
- **Why:** Verified directly against the live dev DB — every one of the 41,708 players has exactly **one** row (0 players with duplicate rows by `unique_id`), each tagged with one `season` label. The migrated dataset never contained true per-player multi-season history; different players' single rows just happen to be drawn from different season windows. ROADMAP's "season-by-season" phrasing doesn't match what Phase 1 actually migrated. Silently pretending otherwise (e.g., fabricating a fake history array) would violate the project's core "real data, not approximated" value. The honest fix is exposing the one real season clearly labeled, not inventing structure that isn't there.

### Club detail: squad overview & transfer behaviour aggregates
- **Decision:** Both computed live via Django ORM aggregation at request time, not precomputed/cached — this is NOT a Phase-6-style problem, because these aggregates are bounded to one club's data (one club's squad, one club's transfer history), not a whole-population scan.
  - **Squad overview:** `Player.objects.filter(club=club)`, using the existing lightweight list serializer.
  - **Transfer behaviour aggregates:** computed from `Transfer.market_value_at_transfer` (a clean `BigIntegerField`) and count/movement/window breakdowns — **not** from `Transfer.fee`, which is a free-text field (`"Free"`, `"loan"`, or a currency string) that isn't safely aggregatable without a parsing layer this phase doesn't build. `fee` stays available as a raw display field on individual transfer records; only `market_value_at_transfer` feeds the aggregate numbers.

### Multi-fetch comparison endpoint (CRUD-05)
- **Decision:** Reuse the same list endpoints with an `ids` filter rather than building bespoke comparison endpoints — e.g. `GET /api/players/?ids=<uuid1>,<uuid2>,<uuid3>` returns those specific players through the existing list serializer (unpaginated when `ids` is present, since the caller already named an exact, bounded set). Same pattern for `/api/clubs/?ids=...`.
- **Why:** The comparison use case is just "list filtering, but by ID instead of by attribute" — it fits the same `FilterSet`/serializer machinery already being built, rather than introducing a third response shape and a separate endpoint to maintain.

### Auth (carried forward, not re-decided)
- All Phase 7 endpoints require authentication, matching the project-wide deny-by-default posture locked in Phase 2 (`DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]`, `DEFAULT_AUTHENTICATION_CLASSES = [JWTAuthentication]`) and followed by every Phase 4 scoring endpoint. No role restriction beyond "logged in" — browsing isn't a write action, so `MinimumRole` gating isn't needed here (that primitive is reserved for Phase 8's Watchlist/Shortlist/Squad Plan writes per its original design intent).

### Claude's Discretion
- Exact `FilterSet` field names and filter-class choices (e.g. `NumberFilter` vs `RangeFilter` for age/market_value/scores).
- Exact URL structure under `/api/players/` and `/api/clubs/` (e.g. whether `/api/players/{id}/transfers/` is a separate nested route or embedded in detail).
- Whether `ids` multi-fetch has a sane upper bound (e.g. reject more than ~100 ids) to prevent an accidentally enormous unpaginated response.
- Exact set of orderable/filterable fields beyond the ones ROADMAP explicitly names — reasonable additions (e.g. ordering by `market_value`) are fine; wholesale new filter dimensions are not (see Deferred Ideas).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 7: Core CRUD - Players & Clubs" — goal, 5 success criteria, `CRUD-01` through `CRUD-05`, depends on Phase 1 + Phase 6
- `.planning/REQUIREMENTS.md` — `CRUD-01` through `CRUD-05` definitions

### The models being exposed
- `get-scouted-be/players/models.py::Player` — ~99 stat FloatFields (exact CSV casing, see `FIELD_MAPPING.md`), `season` field (single value per row, not a history — see decision above), the 4 Phase 6 denormalized score fields, `club` FK
- `get-scouted-be/clubs/models.py::Club` — `league`, `country`, `manager`, `formation`, 8 playing-style FloatFields (only ~22.6% coverage, nulls expected)
- `get-scouted-be/transfers/models.py::Transfer` — `market_value_at_transfer` (clean numeric, use for aggregates) vs `fee` (free-text, display-only, do not aggregate); `club`/`player` FKs, `movement`, `window`

### Established API/service patterns to follow
- `get-scouted-be/scoring/views.py`, `scoring/urls.py` — the thin-views-call-services-directly pattern this phase's `players`/`clubs` views should match (no business logic in views)
- `get-scouted-be/scoring/services/summary.py::get_summary(player_id, club_id)` — the fast (~0.2s post-Phase-6) own-club composed-score+breakdown call Player detail should reuse directly
- `get-scouted-be/config/urls.py` — add `path("api/players/", include("players.urls"))` and `path("api/clubs/", include("clubs.urls"))` alongside the existing `api/auth/` and `api/scoring/` includes

### Prior phase context
- `.planning/phases/06-scoring-performance-caching-layer/06-CONTEXT.md`, `06-live-wiring-DECISIONS.md` — why/how the 4 denormalized score fields exist and are fast to read
- `.planning/PROJECT.md` — Constraints (hosting deferred, 4-day soft deadline) and Key Decisions table

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Phase 6's 4 denormalized `Player` score fields — already indexed, already O(1) to read, directly usable in `django-filter` range filters and `OrderingFilter` without any new plumbing.
- `scoring.services.summary.get_summary()` — reusable wholesale for Player detail's breakdown data.

### Established Patterns
- Thin views, UUID PKs throughout, deny-by-default auth, "never fabricate/zero-fill — null means null" (the same invariant Phases 3-6 enforced for scores applies here too: don't invent squad/transfer aggregate numbers for clubs with no data, return them as null/empty instead).
- No app currently has `views.py`/`serializers.py`/`urls.py` for `players`/`clubs` — this phase creates that scaffolding from scratch, following `scoring/`'s existing shape as the template.

### Integration Points
- Downstream: Phase 8 (User Workspace CRUD) depends on this phase's Player/Club read endpoints existing (Watchlist/Shortlist entries reference these entities).
- Downstream: Phase 9's NL search depends on this phase's filterable field set being the "fixed whitelist of real fields" it parses queries against.

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this phase is a read-only API surface with no UI of its own (frontend integration is explicitly out of this project's scope per PROJECT.md).

</specifics>

<deferred>
## Deferred Ideas

- Parsing/normalizing `Transfer.fee`'s free-text values ("Free", "loan", currency strings) into a clean numeric field for richer aggregates — deferred; `market_value_at_transfer` already covers the aggregate use case this phase needs, and fee-parsing is a distinct, non-trivial data-cleaning task not required by CRUD-04.
- True multi-season player history (would require a schema/migration change to store more than one snapshot per player) — deferred; out of scope for a read-layer phase, and not something Phase 1's migrated data supports today regardless.
- CSV export (mentioned in the broader CRUD-10 requirement) — that's explicitly Phase 8's requirement, not this phase's.

</deferred>

---

*Phase: 07-core-crud-players-clubs*
*Context gathered: 2026-07-25*
