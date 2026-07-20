# Requirements: GetScouted Backend

**Defined:** 2026-07-20
**Core Value:** The backend must serve accurate, real scouting data and real (not approximated) Impact RMM scoring — the product's credibility rests on the scores being right, not just on the API being reachable.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Data Foundation

- [ ] **DATA-01**: Real player profile data (position, age, nationality, foot, height, contract, market value) is migrated from legacy CSVs/Mongo into Postgres
- [x] **DATA-02**: Real club data (league, country, manager, formation, squad size, playing style) is migrated into Postgres
- [ ] **DATA-03**: Position-aware, multi-season player performance stats (goals, assists, tackles, interceptions, passing, duels, xG/xA) are migrated and queryable
- [ ] **DATA-04**: Real transfer history (fee, date, source/destination club, market value at transfer time) is migrated and queryable
- [x] **DATA-05**: Migration produces a reviewed import report surfacing field-mapping mismatches instead of silently dropping/defaulting data

### Authentication & Access

- [ ] **AUTH-01**: User can register and log in with role-based access (scout, analyst, director, admin)
- [ ] **AUTH-02**: All write endpoints (watchlist, shortlist, squad plan, profile) are gated by role-based permissions
- [ ] **AUTH-03**: The 3 conflicting legacy auth models (JWT, disabled API-key, Supabase Auth) are reconciled into one Django system of record; existing Supabase-authenticated users are not migrated (clean re-registration)

### Scoring Engine

- [ ] **SCORE-01**: Player Score (RMM) is computed via a curated, faithful port of `impact_model_v4.1.py`'s per-position calculators, exposed via API
- [ ] **SCORE-02**: Compatibility Score (CS) between a player and a specific club is computed and exposed via API
- [ ] **SCORE-03**: Financial Fit (TFM) between a player's value/cost and a club's spending profile is computed and exposed via API
- [ ] **SCORE-04**: Transfer Probability is computed and exposed via API
- [ ] **SCORE-05**: All four scores return a breakdown of contributing components, not just a final number
- [ ] **SCORE-06**: The Django port passes a numerical parity test suite against the original script's real output, within an agreed tolerance, for every position group
- [ ] **SCORE-07**: Live per-entity scoring runs in O(1) time against precomputed/cached aggregates — no full-dataset pandas operations inside a request cycle

### Core CRUD & Data Access

- [ ] **CRUD-01**: User can list/filter/sort/paginate Players by position, age, market value, league, score thresholds
- [ ] **CRUD-02**: User can list/filter Clubs by league, country, playing style
- [ ] **CRUD-03**: User can retrieve a single Player's full profile, season-by-season stats, and score breakdowns
- [ ] **CRUD-04**: User can retrieve a single Club's full profile, squad overview, and transfer behaviour aggregates
- [ ] **CRUD-05**: User can fetch multiple players/clubs by ID in one request for side-by-side comparison
- [ ] **CRUD-06**: User can save/remove players to/from a personal Watchlist
- [ ] **CRUD-07**: User can create, name, and manage Shortlists tied to a club context
- [ ] **CRUD-08**: User can create and manage Squad Plans (formation, current squad, proposed changes)
- [ ] **CRUD-09**: User's Recent Activity (searches, viewed players) is recorded and retrievable
- [ ] **CRUD-10**: User can export a Shortlist or Club report as CSV

### AI Features

- [ ] **AI-01**: User can submit a natural-language query parsed into structured filters (position, age, value, league, style) against a fixed whitelist of real fields
- [ ] **AI-02**: NL query parsing gracefully falls back (partial parse / keyword fallback) when input is ambiguous or unparseable
- [ ] **AI-03**: User can request an AI-generated scouting report for a player (strengths, weaknesses, tactical fit, financial fit, best use case), strictly grounded in already-computed scores/stats
- [ ] **AI-04**: User can request AI-generated club insights (recruitment gaps, over-aged positions, financial constraints), grounded in Position Needs and Transfer Behaviour aggregates
- [ ] **AI-05**: The LLM integration is built behind a provider-agnostic interface so the concrete provider can be swapped without touching calling code

### Squad Planning & Matching

- [ ] **PLAN-01**: User can view Position Needs analysis (strong/weak/at-risk) for a club's squad, based on depth, contract expiry, and age profile
- [ ] **PLAN-02**: User can get AI-suggested replacement players for a weak position, ranked by RMM/CS/TFM fit
- [ ] **PLAN-03**: User can simulate a squad change (add/remove/swap) and get recalculated aggregate squad metrics (avg age, avg score, budget/wage impact) without persisting until committed
- [ ] **PLAN-04**: User can get a ranked list of clubs that fit a given player (Player → Club Matching), scored by CS/TFM

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Reliability & Cost

- **REL-01**: Report caching/regeneration with data-version-aware invalidation (ship "always regenerate" first)
- **REL-02**: NL search clarification UX for ambiguous input (v1 uses simple graceful fallback)
- **REL-03**: Transfer Probability trust-tuning against real known outcomes, once initial version ships

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Frontend rewiring of `pixel-perfect-clone-60729` | Backend-only per PROJECT.md; separate later effort once API is proven |
| Concrete hosting/deployment target | Deferred; build Docker/12-factor-friendly so this doesn't block backend work |
| Concrete LLM provider selection | Abstracted behind a provider-agnostic interface; picked when that phase is planned |
| Free-form multi-turn conversational AI agent | PRD asks for bounded query→filter parsing, not an open agent loop |
| Real-time match/event data ingestion (live tracking) | Different, much larger data-engineering problem, not in PRD scope |
| LLM directly computing scores | Scores must stay deterministic — an LLM-guessed score is the exact crude heuristic this project replaces |
| Transfer marketplace/negotiation/messaging layer | Different product surface entirely, not in the PRD's 6 pages |
| Multi-tenant white-labeling / cross-club data isolation | No PRD requirement; single-org role model (scout/analyst/director/admin) only |
| Real-time collaborative squad editing | Disproportionate infra for what the PRD describes as single-user planning workflows |
| Training/fine-tuning a custom ML model for scoring | Port the existing deterministic model faithfully instead of replacing it |
| Video/footage storage and clip-tagging | Separate, much larger product category; nothing in the PRD references it |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 1 | In Progress (Plan 4/9 done) |
| DATA-02 | Phase 1 | Complete (Plan 04) |
| DATA-03 | Phase 1 | In Progress (Plan 4/9 done) |
| DATA-04 | Phase 1 | In Progress (Plan 4/9 done) |
| DATA-05 | Phase 1 | Complete (Plan 04) |
| AUTH-01 | Phase 2 | Pending |
| AUTH-02 | Phase 2 | Pending |
| AUTH-03 | Phase 2 | Pending |
| SCORE-01 | Phase 4 | Pending |
| SCORE-02 | Phase 4 | Pending |
| SCORE-03 | Phase 4 | Pending |
| SCORE-04 | Phase 4 | Pending |
| SCORE-05 | Phase 4 | Pending |
| SCORE-06 | Phase 5 | Pending |
| SCORE-07 | Phase 6 | Pending |
| CRUD-01 | Phase 7 | Pending |
| CRUD-02 | Phase 7 | Pending |
| CRUD-03 | Phase 7 | Pending |
| CRUD-04 | Phase 7 | Pending |
| CRUD-05 | Phase 7 | Pending |
| CRUD-06 | Phase 8 | Pending |
| CRUD-07 | Phase 8 | Pending |
| CRUD-08 | Phase 8 | Pending |
| CRUD-09 | Phase 8 | Pending |
| CRUD-10 | Phase 8 | Pending |
| AI-01 | Phase 9 | Pending |
| AI-02 | Phase 9 | Pending |
| AI-03 | Phase 10 | Pending |
| AI-04 | Phase 10 | Pending |
| AI-05 | Phase 9 | Pending |
| PLAN-01 | Phase 11 | Pending |
| PLAN-02 | Phase 12 | Pending |
| PLAN-03 | Phase 11 | Pending |
| PLAN-04 | Phase 12 | Pending |

**Coverage:**
- v1 requirements: 34 total
- Mapped to phases: 34
- Unmapped: 0 ✓

**Phase note:** Phase 3 (Scoring Engine Curation & Correctness Oracle) is prerequisite risk-mitigation work with no directly-owned requirement — it enables Phases 4-6 to satisfy SCORE-01 through SCORE-07.

---
*Requirements defined: 2026-07-20*
*Last updated: 2026-07-20 after roadmap creation (34/34 requirements mapped across 12 phases)*
