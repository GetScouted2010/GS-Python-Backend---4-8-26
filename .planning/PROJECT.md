# GetScouted Backend

## What This Is

A Django/DRF backend for GetScouted, an AI-powered football recruitment and scouting platform (built for World In Motion Ltd) used by agents, recruitment analysts, and club decision-makers. This backend replaces the Supabase layer currently behind the `pixel-perfect-clone-60729` frontend prototype, serving real player/club/transfer data and computing the platform's core scores for real — including natural-language search and AI-generated scouting insights.

## Core Value

The backend must serve accurate, real scouting data and real (not approximated) Impact RMM scoring — the product's credibility rests on the scores being right, not just on the API being reachable.

## Requirements

### Validated

- ✓ Real dataset migration: Players, Clubs/Playstyles, per-position role scores, Compatibility Scores, and transfer history CSVs (from `API-Updated-/dataset/`) imported into the new Postgres schema, with a reviewed combined import report — Phase 1 (41,708 players, 1,060 clubs, 230,139 role scores, 8,188,712 compatibility rows, 47,201 transfers)

### Active

- [ ] Django + DRF backend on Postgres, designed to serve `pixel-perfect-clone-60729` (replacing its current Supabase backend)
- [ ] Auth with roles (scout, analyst, director, admin) — replacing Supabase Auth, reconciling the 3 conflicting legacy auth models (JWT, disabled API-key middleware, Supabase Auth)
- [ ] Full CRUD API for core entities: Players, Clubs, Transfers, Watchlist, Shortlists, Squad Plans, Recent Activity, Profiles
- [ ] Full port of `impact_model_v4.1.py` (~15,700 lines) as the live Django scoring engine — Player Score (RMM), Compatibility Score (CS), Financial Fit (TFM), Transfer Probability
- [ ] AI features in v1: natural-language search parsing (query → structured filters) and AI-generated scout reports / club insights, built behind an LLM-provider-agnostic interface
- [ ] Data model and endpoints support the PRD's 6 pages: AI Dashboard, AI Shortlist, Player Profile, Club Intelligence, Squad Planner, Player → Club Matching

### Out of Scope

- Rewiring `pixel-perfect-clone-60729`'s frontend to call the new API — deferred as a separate, later effort once the backend is proven; this project is backend-only
- Concrete hosting/deployment target — deferred; build Docker/12-factor-friendly so the decision doesn't block backend work
- Concrete LLM provider selection — abstracted behind an interface now; picked when that phase is actually planned
- Legacy `RT-Tool-Frontend` — not the target consumer, not extended or rebuilt
- Legacy `API-Updated-` Node/Mongo API — not maintained or extended going forward; only mined as a source of reference logic and real data for migration

## Context

- **Existing codebase** (`/Users/MAC/Desktop/getScouted/`) has 3 separate sub-projects, each its own git repo:
  - `API-Updated-/` — legacy Node/Express + MongoDB REST API (JWT auth; API-key middleware currently disabled). Real CSV datasets live under `API-Updated-/dataset/` (Players, Playstyles, per-position stats with leagues, Compatibility Scores, transfer history).
  - `RT-Tool-Frontend/` — legacy React/Vite client of `API-Updated-`. Not the target frontend for this backend.
  - `pixel-perfect-clone-60729/` — newer Lovable-generated React/TanStack Start prototype implementing the PRD's 6-page vision, currently backed by Supabase (see `supabase/migrations/`). Contains `docs/impact_model_v4.1.py`, a ~15,700-line pandas-based scoring engine ("Impact RMM 4.1") that is currently **unused in production** — the frontend instead approximates scoring with a crude client-side heuristic in `src/lib/domain.ts`.
- `GetScouted PRD.docx` (Jan 2026, World In Motion Ltd) defines the 6-page platform and 4 core scores: Player Score (RMM), Compatibility Score (CS), Financial Fit (TFM), Transfer Probability, plus AI-generated insights/search/scout reports.
- A full codebase map exists at `.planning/codebase/` (STACK, ARCHITECTURE, STRUCTURE, CONVENTIONS, TESTING, INTEGRATIONS, CONCERNS) covering all 3 sub-projects.
- **Known risks surfaced during mapping** (see `.planning/codebase/CONCERNS.md`):
  - 3 conflicting auth models across the legacy pieces (JWT, disabled API-key middleware, Supabase Auth) need reconciling into one Django approach
  - Field-naming mismatches across MongoDB / CSVs / Supabase / the Python scoring model — though the Python model already uses consistent snake_case, which aligns naturally with Django/Postgres conventions
  - Zero test coverage anywhere in the existing codebase, most notably on the ~15,700-line untested scoring logic that now needs porting
- Existing Supabase migrations show a workable reference schema (clubs, players with jsonb attributes, profiles, user_roles enum, watchlist, squad_plans, recent_activity) — useful as a reference, not a mandate, for the new Django schema.

## Constraints

- **Tech stack**: Django + Django REST Framework, Postgres — replaces both MongoDB (legacy) and Supabase (prototype)
- **Timeline**: 4-day demo/deadline target — treated as a *soft* target. The user explicitly chose to keep full scope rather than cut it to fit 4 days; progress will be reported realistically against the deadline instead of force-fitting scope.
- **Scope boundary**: backend-only — no frontend rewiring of `pixel-perfect-clone-60729` in this project
- **LLM integration**: must be built behind a provider-agnostic interface; concrete provider (Claude, OpenAI, etc.) is an explicit later decision, not locked in now
- **Hosting**: undecided; backend should be Docker/12-factor-friendly so this doesn't block development

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Backend serves `pixel-perfect-clone-60729` (new PRD platform), not legacy `RT-Tool-Frontend` | New platform reflects the current product direction; the legacy Node API already adequately serves the old frontend | — Pending |
| Port `impact_model_v4.1.py` in full as the real scoring engine | It's already Python/pandas — Django is a natural fit; the current JS heuristic in the frontend is not the real methodology | — Pending |
| Migrate real datasets (CSVs from `API-Updated-`) into Postgres rather than starting empty | Real scouting data already exists and is valuable; avoids building and demoing against fake data | ✓ Good — Phase 1 imported all 5 real datasets successfully; surfaced and fixed 3 real data-quality bugs (player import TypeError, blank rows in 3 position CSVs, 51 duplicate transfer rows) that synthetic data would have hidden |
| AI features (NL search, AI-generated reports/insights) are in scope for v1 | The PRD treats these as core to the product's value proposition, not an optional add-on | — Pending |
| Backend-only scope; frontend rewiring explicitly deferred | Keeps this project focused and shippable; frontend integration is a distinct, separately-scoped effort | — Pending |
| LLM provider abstracted, not chosen yet | Avoids premature lock-in; decide with real requirements when that phase is actually planned | — Pending |
| Hosting/deployment target deferred | Not yet decided; building cleanly (Docker/12-factor) means this doesn't block backend development | — Pending |
| Keep full scope despite the 4-day soft deadline | User explicitly chose realism over force-fitting scope into an unrealistic window | — Pending |
| Existing Supabase-authenticated users in `pixel-perfect-clone-60729` are not migrated | Clean re-registration under the new Django auth system; product is still at prototype/demo stage, not a live user base | — Pending |

---
*Last updated: 2026-07-21 after Phase 1 (Data Foundation) completion*
