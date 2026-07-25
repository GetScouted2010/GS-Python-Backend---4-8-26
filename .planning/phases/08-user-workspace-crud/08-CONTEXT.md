# Phase 8: User Workspace CRUD - Context

**Gathered:** 2026-07-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Authenticated users can build and manage their own personal scouting workspace on top of the real Player/Club data Phase 7 exposed: a Watchlist, named Shortlists tied to a club, Squad Plans with simulated (not-yet-committed) changes, an automatically-recorded Recent Activity log, and CSV export of a Shortlist or Club report. This is the first phase in the project that writes new user-owned data, not just reads existing scouting data. No AI features (Phase 9-10), no actual squad-change *simulation math* (Phase 11 — this phase only stores the proposed-change data structure, doesn't compute recalculated squad metrics from it), no cross-user visibility (directors/admins don't get to browse other users' workspaces — not asked for by any ROADMAP success criterion).

All decisions below were made by Claude on the user's standing instruction ("make all necessary and important decisions considering trade-offs and execute") rather than through interactive discussion. Rationale is spelled out for each so downstream agents (and the user, on review) can see why.

</domain>

<decisions>
## Implementation Decisions

### App structure: one `workspace` app, not four
- **Decision:** A single new Django app, `workspace/`, houses all 4 new models (`Watchlist`, `Shortlist` + `ShortlistEntry`, `SquadPlan`, `RecentActivity`). Not four separate near-empty apps.
- **Why:** These are four small, tightly-related "personal workspace" concepts, all owned by `accounts.User`, all delivered in one phase, with no independent lifecycle from each other. This project's existing convention is one app per clear domain noun (`players`, `clubs`, `transfers`, `scoring`, `accounts`) — "a user's personal workspace" is itself a coherent single domain, closer in spirit to `accounts` than to four unrelated entities.

### Ownership & permissions — object-level ownership, not role hierarchy
- **Decision:** Every workspace endpoint requires authentication (project-wide deny-by-default, unchanged) plus a new `IsOwner` object-level permission: a user may only read/write their **own** Watchlist/Shortlists/Squad Plans/Activity, full stop. No `MinimumRole` hierarchy gating is used here, and no director/admin cross-user visibility is built.
- **Why:** ROADMAP's 5 success criteria for this phase are all phrased as "User can..." over their own data — none describe a director/admin oversight capability, unlike Phase 2's `/api/auth/admin/users/`. `MinimumRole("scout")` would be a no-op in practice (scout is the lowest rank; every authenticated role already clears it), so the primitive that actually matters here is ownership, not hierarchy. This does NOT contradict PROJECT.md's note that `MinimumRole` was "built... ready for Phase 7/8 reuse" — that note describes the primitive being *available*, not a requirement that every phase must use hierarchy gating specifically; object-level ownership is the correct tool for "manage your own stuff," matching the existing `accounts.permissions.IsSelfOrAdmin` precedent's shape (adapted here to drop the admin-override clause, since nothing asks for it).

### Watchlist model shape
- **Decision:** `Watchlist` is a single row per `(user, player)` pair — not a JSON blob, not a single "Watchlist" object with an M2M field. `unique_together = ("user", "player")` prevents duplicate saves; `added_at` timestamp for ordering.
- **Why:** Matches CRUD-06's exact phrasing ("save and remove players from a personal Watchlist") — save/remove are naturally per-player row operations (`POST` to add, `DELETE` to remove), and a per-row model gives a free `added_at` for "most recently saved" ordering without extra bookkeeping.

### Shortlist model shape
- **Decision:** Two models: `Shortlist` (`user` FK, `name`, `club` FK — "tied to a specific club context" per CRUD-07 — `created_at`) and `ShortlistEntry` (`shortlist` FK, `player` FK, `added_at`, optional `note` text field). A user can have multiple Shortlists, each scoped to one club, each containing multiple players.
- **Why:** "Create, name, and manage" (CRUD-07) implies multiple named lists, not a single list — a through-model (`ShortlistEntry`) mirrors the `Watchlist` shape and lets entries carry their own metadata (when added, optional scouting note) without overloading `Shortlist` itself.

### SquadPlan: don't duplicate the live squad, only store proposed changes
- **Decision:** `SquadPlan` stores `user` FK, `club` FK, `name`, `formation` (string), `created_at`/`updated_at`, and a `proposed_changes` `JSONField` — a list of `{"action": "add"|"remove"|"swap", "player_id": ..., "incoming_player_id": ...}`-shaped entries. It does **NOT** store a duplicated/frozen copy of the "current squad" — that's always derived live from `Player.objects.filter(club=squad_plan.club)` (reusing Phase 7's `PlayerListSerializer`, the exact same pattern Phase 7's own Club-detail squad overview already uses), exactly the way Phase 6 chose not to denormalize things that can be read live at negligible cost.
- **Why:** Freezing a "current squad" snapshot at creation time would immediately go stale the moment a real transfer happens, and nothing in CRUD-08 asks for historical squad snapshots — it asks for "current squad" (implying live) and "proposed changes" (implying a delta, not a full alternate roster). This also sets up Phase 11 correctly: Phase 11's "simulate a squad change... see recalculated aggregate squad metrics... not persisted until committed" needs exactly this shape — live current squad + a change delta — to compute against. Phase 8 stores the delta; Phase 11 is what actually *simulates* against it (out of this phase's scope, deliberately).

### Recent Activity — logged automatically by existing views, not a separate manual-log endpoint
- **Decision:** `RecentActivity` (`user` FK, `activity_type` — `"viewed_player"` / `"viewed_club"` / `"searched"` — `target_id` nullable UUID, `query_text` nullable, `created_at`). Phase 7's already-built `PlayerDetailView`/`ClubDetailView` are modified in this phase to write a `RecentActivity` row automatically on every authenticated GET, rather than requiring a caller to separately POST "log this view." The `"searched"` type is defined now (structurally ready) but nothing populates it yet — Phase 9 (NL search, not yet built) is the only future producer of that event type, and this phase does not fabricate search history that doesn't exist.
- **Why:** "Frontend integration is explicitly out of scope" per PROJECT.md — there is no separate client this project controls that could reliably call a manual "log this activity" endpoint. The only way "viewed players" tracking actually works, without depending on a future frontend team remembering to wire it up correctly, is for the backend's own view code to record it. This is a small, surgical modification to two already-shipped, already-tested Phase 7 views (adding one write after the existing read logic, not changing their response contract).

### CSV export — synchronous streaming, no new async infra
- **Decision:** `GET /api/workspace/shortlists/{id}/export/` and `GET /api/clubs/{id}/export/` (or equivalent) return `text/csv` directly using Django's `StreamingHttpResponse` + Python's stdlib `csv` module — no Celery/background task, no new dependency. Shortlist export columns reuse `PlayerListSerializer`'s field set (identity, position, club, market value, the 4 scores). Club report export flattens the club profile + the same transfer aggregate numbers Phase 7's Club detail already computes (`market_value_at_transfer`-based, never `fee`).
- **Why:** Matches Phase 6's established precedent of not introducing new infrastructure (Celery, in that case) without a real forcing reason — CSV generation for a bounded list (one shortlist's players, one club's squad/transfers) is fast enough to do synchronously in the request/response cycle, no background job needed. `StreamingHttpResponse` avoids buffering a potentially large CSV entirely in memory, cheap insurance for negligible extra code.

### Claude's Discretion
- Exact URL structure under `/api/workspace/` (e.g. `/api/workspace/watchlist/`, `/api/workspace/shortlists/`, `/api/workspace/squad-plans/`) vs nesting exports under `players`/`clubs`.
- Exact `proposed_changes` JSON schema validation strictness (e.g. whether malformed entries are rejected at write time vs stored permissively) — validate at write time is the natural default given the project's "never fabricate, catch problems early" pattern, but exact serializer-level validation depth is an implementation detail.
- Whether `RecentActivity` gets a retention cap (e.g. only keep the last N entries per user) — not required by CRUD-09's "recorded and retrievable" wording; unbounded is fine at this project's scale unless the planner finds a concrete reason otherwise.
- Exact CSV column ordering/headers.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & requirements
- `.planning/ROADMAP.md` §"Phase 8: User Workspace CRUD" — goal, 5 success criteria, `CRUD-06` through `CRUD-10`, depends on Phase 2 + Phase 7
- `.planning/REQUIREMENTS.md` — `CRUD-06` through `CRUD-10` definitions

### Permission precedent to adapt
- `get-scouted-be/accounts/permissions.py` — `MinimumRole` factory (available but not the right tool here, per decision above) and `IsSelfOrAdmin` (the shape to adapt into this phase's new `IsOwner`, dropping the admin-override clause)

### Models/patterns this phase builds on
- `get-scouted-be/players/serializers.py::PlayerListSerializer` — reused verbatim for Squad Plan's live "current squad" view and Shortlist CSV export columns
- `get-scouted-be/players/views.py::PlayerDetailView`, `get-scouted-be/clubs/views.py::ClubDetailView` — the two existing views this phase modifies to log `RecentActivity`
- `get-scouted-be/clubs/serializers.py::ClubDetailSerializer` — the transfer-aggregate computation (`market_value_at_transfer`-based) Club report CSV export reuses
- `get-scouted-be/core/pagination.py` — existing shared-utility app precedent for where cross-cutting workspace helpers (if any) could live

### Prior phase context
- `.planning/phases/07-core-crud-players-clubs/07-CONTEXT.md` — the read-layer this phase's writes sit on top of
- `.planning/PROJECT.md` — Key Decisions table (esp. the `MinimumRole` note and Phase 6's "don't add infra without a forcing reason" pattern this phase's CSV-export decision follows)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `PlayerListSerializer` — directly reusable for Squad Plan's current-squad view and Shortlist export, no new serializer needed for that shape.
- `IsSelfOrAdmin` — structural template for the new `IsOwner` permission class.

### Established Patterns
- No Django signals anywhere in this codebase (confirmed in Phase 6's research) — `RecentActivity` logging is a direct, explicit write inside the view method, not a signal handler, consistent with this project's explicit-over-implicit convention.
- UUID PKs throughout; every new model in this phase follows suit.
- "Never fabricate, null means null" — `RecentActivity.target_id` is null for a `"searched"` event (no player/club target), not defaulted to some sentinel.

### Integration Points
- Downstream: Phase 11 (Position Needs & Squad Simulation) directly consumes `SquadPlan.proposed_changes` — the schema decided here is a real contract Phase 11 must not have to migrate away from.
- Downstream: Phase 9 (NL search) will be the first real producer of `RecentActivity`'s `"searched"` event type.

</code_context>

<specifics>
## Specific Ideas

No specific product/UI references — this phase is a backend read/write API surface with no UI of its own (frontend integration is explicitly out of this project's scope per PROJECT.md).

</specifics>

<deferred>
## Deferred Ideas

- Actually computing recalculated squad metrics (avg age, avg score, budget/wage impact) from `SquadPlan.proposed_changes` — that's Phase 11's job explicitly; this phase only stores the delta.
- Director/admin visibility into other users' workspaces — not asked for by any Phase 8 success criterion; would be a new capability if ever wanted, its own future decision.
- CSV export format alternatives (XLSX, PDF) — ROADMAP's CRUD-10 explicitly says CSV; the legacy script's `export_team_shortlist_xlsx` (found during Phase 3's characterization) is not being revived here.
- Retention/pruning policy for `RecentActivity` — left as Claude's Discretion for the planner, not a locked requirement.

</deferred>

---

*Phase: 08-user-workspace-crud*
*Context gathered: 2026-07-25*
