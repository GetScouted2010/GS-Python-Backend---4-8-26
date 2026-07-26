# Roadmap: GetScouted Backend

## Overview

The backend is built along the hard dependency chain the domain imposes: real data must exist before scores can be validated against anything, the untested 15,700-line scoring engine must be characterized and proven correct before anything downstream trusts its numbers, and the CRUD/AI/matching surfaces are only as credible as the scores and data beneath them. Twelve phases carry this chain from an empty Postgres schema to a full API surface: data migration and auth first (Phases 1-2), then the scoring engine split into its own four-phase arc — curation, port, parity testing, caching — because a 15,700-line untested port is the single highest-risk piece of this project and deserves to be characterized, built, and proven correct as distinct, separately-verifiable steps (Phases 3-6), then the CRUD surface split into core browse/detail data vs. user workspace data (Phases 7-8), then the AI layer split into search parsing vs. grounded report generation (Phases 9-10), and finally squad planning split into needs/simulation vs. bidirectional matching (Phases 11-12). Every phase carries its own correctness check in its success criteria rather than deferring verification to the end.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Data Foundation** - Real player, club, stats, and transfer data migrated into Postgres with a reviewed import report (completed 2026-07-21)
- [x] **Phase 2: Auth & Access Control** - One Django system of record for identity, gating every write endpoint by role (completed 2026-07-21)
- [x] **Phase 3: Scoring Engine Curation & Correctness Oracle** - The authoritative logic in the untested scoring script is characterized and snapshotted before any porting begins (completed 2026-07-22)
- [x] **Phase 4: Scoring Engine Port** - Curated calculators for RMM, CS, TFM, and Transfer Probability run as real Django services with component breakdowns (completed 2026-07-23)
- [x] **Phase 5: Scoring Parity Testing** - The Django port is proven numerically faithful to the original script within tolerance, for every position group (completed 2026-07-24)
- [x] **Phase 6: Scoring Performance & Caching Layer** - Live per-entity scoring runs in O(1) time against precomputed, cached aggregates (completed 2026-07-24)
- [ ] **Phase 7: Core CRUD - Players & Clubs** - Users can browse, filter, inspect, and compare real player and club data including scores
- [x] **Phase 8: User Workspace CRUD** - Users can manage Watchlist, Shortlists, Squad Plans, Recent Activity, and CSV export (completed 2026-07-25)
- [x] **Phase 9: AI Provider Interface & Natural-Language Search** - Users can search in plain language against a provider-agnostic LLM interface (completed 2026-07-25)
- [ ] **Phase 10: AI Grounded Report Generation** - Users can request AI-written scouting reports and club insights grounded in real computed scores
- [ ] **Phase 11: Position Needs & Squad Simulation** - Users can see squad weaknesses and simulate changes before committing
- [ ] **Phase 12: Bidirectional Matching - Replacements & Player-Club Fit** - Users can get ranked replacement players and ranked club fits off one shared ranking primitive

## Phase Details

### Phase 1: Data Foundation
**Goal**: Real player, club, stats, and transfer data live in Postgres, accurately reflecting the legacy CSVs, with mismatches surfaced rather than hidden.
**Depends on**: Nothing (first phase)
**Requirements**: DATA-01, DATA-02, DATA-03, DATA-04, DATA-05
**Success Criteria** (what must be TRUE):
  1. Querying the Player table returns real profile data (position, age, nationality, foot, height, contract, market value) for every player in the source CSVs.
  2. Querying the Club table returns real club data (league, country, manager, formation, squad size, playing style) for every club in the source CSVs.
  3. A Player's season-by-season, position-aware performance stats (goals, assists, tackles, interceptions, passing, duels, xG/xA) are stored and queryable.
  4. Transfer history records (fee, date, source/destination club, market value at transfer time) are stored and queryable.
  5. Running the migration produces a written import report listing every field-mapping mismatch or dropped/defaulted value found, instead of migrating silently.
**Plans**: 9 plans (6 waves)
- [x] 01-01-PLAN.md — Django project scaffolding + FIELD_MAPPING.md deliverable (wave 1)
- [x] 01-02-PLAN.md — pytest-django test infra + seeded fixture CSVs (wave 2)
- [x] 01-03-PLAN.md — Club/Player/RoleScore/Compatibility/Transfer models + migrations (wave 2)
- [x] 01-04-PLAN.md — Shared import utils + ImportReport + Club derivation import (wave 3)
- [x] 01-05-PLAN.md — Player import (idempotent, club FK, extended_stats, outlier flagging) (wave 4)
- [x] 01-06-PLAN.md — Position role-score import (wide->long normalization) (wave 5)
- [x] 01-07-PLAN.md — Compatibility-score import (~8.1M rows normalized) (wave 5)
- [x] 01-08-PLAN.md — Transfer import (UniqueID-is-club trap guarded) (wave 5)
- [x] 01-09-PLAN.md — import_all orchestrator + reconciliation + combined report (wave 6)

### Phase 2: Auth & Access Control
**Goal**: A single Django system of record for identity and permissions replaces the 3 conflicting legacy auth models, gating every write endpoint by role.
**Depends on**: Phase 1
**Requirements**: AUTH-01, AUTH-02, AUTH-03
**Success Criteria** (what must be TRUE):
  1. A user can register and log in and is assigned a role of scout, analyst, director, or admin.
  2. Attempting a write (watchlist, shortlist, squad plan, profile) without the correct role returns a permission-denied response, not a silent success.
  3. No write endpoint defaults to allow-by-default; every write path has an explicit, testable permission check.
  4. Legacy Supabase-authenticated users are not carried forward — new registration under Django auth is the only path in.
**Plans**: 3 plans
- [x] 02-01-PLAN.md — Custom accounts.User model, DRF/JWT settings, AUTH_USER_MODEL dev-DB reset + re-import, test fixtures
- [x] 02-02-PLAN.md — Registration, login, password reset
- [x] 02-03-PLAN.md — Role-based permissions, admin user management

### Phase 3: Scoring Engine Curation & Correctness Oracle
**Goal**: The authoritative logic inside the untested, duplicated 15,700-line scoring script is identified and characterized against real data before a single line is ported, so the port has a ground truth to be checked against.
**Depends on**: Phase 1
**Requirements**: (none directly — prerequisite risk-mitigation work that Phases 4-6 depend on to satisfy SCORE-01 through SCORE-07)
**Success Criteria** (what must be TRUE):
  1. Every function defined more than once in impact_model_v4.1.py is catalogued, with the authoritative (final) definition identified and documented.
  2. Running the original script against the real migrated dataset (Phase 1) produces a stored, versioned snapshot of its output (RMM, CS, TFM, Transfer Probability) for every position group, saved as the correctness oracle Phase 5 checks the port against.
  3. Non-deterministic or sklearn-trained components (e.g. Transfer Probability) are identified and separated from purely deterministic calculators, with their handling documented for the port.
  4. A written curation map exists showing, per score, which original functions and columns feed it.
**Plans**: 7 plans (3 waves)
- [x] 03-01-PLAN.md — Foundation: scikit-learn/joblib deps, scoring app skeleton, ORM→script DataFrame reconstruction (wave 1)
- [x] 03-02-PLAN.md — Duplicate-function catalogue (20 names, last-wins resolution of 18, flag 2) (wave 2)
- [x] 03-03-PLAN.md — Escalation review + human decision for the 2 four-definition functions (wave 2, checkpoint)
- [x] 03-04-PLAN.md — RMM (Player Impact) calculator characterization (wave 2)
- [x] 03-05-PLAN.md — CS role-fit + deterministic Transfer Probability characterization (wave 2)
- [x] 03-06-PLAN.md — TFM sklearn model training + versioned joblib artifact (wave 3)
- [x] 03-07-PLAN.md — Full-population oracle snapshot + master curation map finalization (wave 4)

### Phase 4: Scoring Engine Port
**Goal**: The curated, authoritative calculators for all four scores run as real Django/Python services and are reachable via API with full component breakdowns.
**Depends on**: Phase 3
**Requirements**: SCORE-01, SCORE-02, SCORE-03, SCORE-04, SCORE-05
**Success Criteria** (what must be TRUE):
  1. Requesting a Player's score via API returns a real computed Player Score (RMM) from the curated port, not an approximation.
  2. Requesting a Player-Club pairing via API returns a real computed Compatibility Score (CS).
  3. Requesting a Player-Club pairing via API returns a real computed Financial Fit (TFM).
  4. Requesting a Player via API returns a real computed Transfer Probability.
  5. Every score response includes a breakdown of its contributing components, not just a final number.
**Plans**: 6 plans (4 waves)
- [x] 04-01-PLAN.md — Foundation: population reconstruction + RMM-first scoring sequence, memoized TFM loader, club-name resolver, null+reason envelope (wave 1)
- [x] 04-02-PLAN.md — RMM (Player Impact) service + full component breakdown (wave 2)
- [x] 04-03-PLAN.md — Compatibility Score + deterministic Transfer Probability services + breakdowns (wave 2)
- [x] 04-04-PLAN.md — Financial Fit (TFM) service: club-context override + np.expm1 money-scale unwrap + value verdict (wave 2)
- [x] 04-05-PLAN.md — Combined summary orchestrator (all 4 scores, single reconstruction) + serializers contract (wave 3)
- [x] 04-06-PLAN.md — 5 authenticated DRF endpoints under /api/scoring/ + integration tests (wave 4)

### Phase 5: Scoring Parity Testing
**Goal**: The Django port is proven numerically faithful to the original script, not just "runs without crashing."
**Depends on**: Phase 3, Phase 4
**Requirements**: SCORE-06
**Success Criteria** (what must be TRUE):
  1. An automated parity test suite runs the Django port against the Phase 3 oracle snapshot for every position group and reports pass/fail within an agreed numerical tolerance.
  2. The full parity suite passes for all position groups before the port is considered done.
  3. Edge cases (missing stats, boundary ages, zero-appearance players) are covered by the parity suite and pass.
**Plans**: 4 plans (2 waves)
- [x] 05-01-PLAN.md — Shared parity helpers: version-agnostic oracle discovery, 10-group bucketing, both-null-aware tolerance comparator, mismatch-report writer (wave 1)
- [x] 05-02-PLAN.md — Tier-1 full-population bulk parity (RMM/CS/TP/TFM) parametrized over the 10 real position groups (wave 2)
- [x] 05-03-PLAN.md — Tier-2 API-sample parity: seeded stratified ~30-player sample through the real per-request services + DRF endpoints (wave 2)
- [x] 05-04-PLAN.md — Edge-case parity: zero-minutes, missing stats, boundary ages, invalid position (dynamically mined) (wave 2)

### Phase 6: Scoring Performance & Caching Layer
**Goal**: Live scoring is fast and safe under real concurrency — no full-dataset pandas operation ever runs inside a request.
**Depends on**: Phase 4, Phase 5
**Requirements**: SCORE-07
**Success Criteria** (what must be TRUE):
  1. Requesting any single player's or club's score returns in O(1) time against precomputed/cached aggregates, not a full-dataset recomputation.
  2. Precomputed aggregates (std_lookup, team-style vectors, team-position references) are rebuilt on data change, not per request.
  3. Final scores are denormalized onto model fields so list/browse/sort endpoints never invoke scoring math directly.
  4. A timing check confirms per-entity score retrieval stays flat as dataset size grows, rather than scaling linearly with player count.
**Plans**: 7 plans (3 original waves + gap closure 06-05..06-07 wiring the live API to the caching layer)
- [x] 06-01-PLAN.md — Denormalize 4 final scores onto Player (nullable indexed FloatFields) + migration (wave 1)
- [x] 06-02-PLAN.md — In-process aggregate caching: memoize reconstruct_population + get_scored_population + clear_scoring_caches (wave 1)
- [x] 06-03-PLAN.md — recompute_scores management command: atomic bulk_update of the 4 denormalized fields, money-scale TFM, cache clear (wave 2)
- [x] 06-04-PLAN.md — Timing verification test: O(1) denormalized read + warm cache vs cold recompute, order-of-magnitude assertion (wave 3)
- [x] 06-05-PLAN.md — GAP CLOSURE: wire RMM/Compatibility/Transfer-Probability live services to the memoized get_scored_population() own-club fast path (wave 1)
- [x] 06-06-PLAN.md — GAP CLOSURE: Financial Fit O(1) denormalized-field read + Summary own-club fast path; arbitrary-club live fallback preserved (wave 2)
- [x] 06-07-PLAN.md — GAP CLOSURE: warm-process sub-second regression test for the 5 live services + live-wiring design decisions doc (wave 3)

### Phase 7: Core CRUD - Players & Clubs
**Goal**: Users can browse, filter, and inspect real player and club data, including their scores, through a full API surface.
**Depends on**: Phase 1, Phase 6
**Requirements**: CRUD-01, CRUD-02, CRUD-03, CRUD-04, CRUD-05
**Success Criteria** (what must be TRUE):
  1. User can list/filter/sort/paginate Players by position, age, market value, league, and score thresholds.
  2. User can list/filter Clubs by league, country, and playing style.
  3. User can retrieve a single Player's full profile, season-by-season stats, and score breakdowns.
  4. User can retrieve a single Club's full profile, squad overview, and transfer behaviour aggregates.
  5. User can fetch multiple players or clubs by ID in one request for side-by-side comparison.
**Plans**: 3/3 plans executed
- [x] 07-01-PLAN.md — Foundation: django-filter dependency + REST_FRAMEWORK filter/pagination wiring, shared capped/ids-bypass pagination classes, Wave-0 real_data_available test fixtures (wave 1)
- [x] 07-02-PLAN.md — Players read API: list filter/sort/paginate, detail (profile + season + score breakdowns, club=None branch), ?ids= multi-fetch (wave 2)
- [x] 07-03-PLAN.md — Clubs read API: list filter/paginate, detail (profile + squad overview + transfer aggregates from market_value_at_transfer), ?ids= multi-fetch (wave 3)

### Phase 8: User Workspace CRUD
**Goal**: Authenticated users can build and manage their own scouting workspace on top of real player/club data.
**Depends on**: Phase 2, Phase 7
**Requirements**: CRUD-06, CRUD-07, CRUD-08, CRUD-09, CRUD-10
**Success Criteria** (what must be TRUE):
  1. User can save and remove players from a personal Watchlist.
  2. User can create, name, and manage Shortlists tied to a specific club context.
  3. User can create and manage Squad Plans (formation, current squad, proposed changes).
  4. User's Recent Activity (searches, viewed players) is recorded and retrievable.
  5. User can export a Shortlist or Club report as CSV.
**Plans**: 6 plans (6 waves — sequential; all workspace features share workspace/views.py, serializers.py, urls.py so cannot run in parallel)
- [ ] 08-01-PLAN.md — Foundation: workspace app scaffold + 5 models + migration + IsOwner permission + test conftest (wave 1)
- [ ] 08-02-PLAN.md — Watchlist read/write API (save/remove, per-user uniqueness, list scoping) (wave 2)
- [ ] 08-03-PLAN.md — Shortlists + nested entries (named, club-tied, @action nested routes) (wave 3)
- [ ] 08-04-PLAN.md — Squad Plans (list/detail split, live current_squad, proposed_changes validation) (wave 4)
- [x] 08-05-PLAN.md — Recent Activity (auto-logged by Player/Club detail views + scoped list endpoint) (wave 5)
- [ ] 08-06-PLAN.md — CSV export (Shortlist + Club report via StreamingHttpResponse) (wave 6)

### Phase 9: AI Provider Interface & Natural-Language Search
**Goal**: Users can search using plain language and get real, structured results, with the underlying LLM provider swappable without touching calling code.
**Depends on**: Phase 7
**Requirements**: AI-01, AI-02, AI-05
**Success Criteria** (what must be TRUE):
  1. User can submit a natural-language query and receive results filtered by structured fields (position, age, value, league, style) drawn from a fixed whitelist of real fields.
  2. An ambiguous or unparseable query still returns a graceful partial-parse or keyword-fallback result, never an error or empty crash.
  3. The LLM call for parsing goes through a provider-agnostic interface — swapping the underlying provider requires no changes to search-calling code.
**Plans**: 4 plans (3 waves)
- [x] 09-01-PLAN.md — Foundation: anthropic dep + LLM_PROVIDER/ANTHROPIC_* settings + NLQueryParser interface contract + pytest anthropic-call safety-net (wave 1) (completed 2026-07-25)
- [x] 09-02-PLAN.md — AnthropicNLQueryParser (forced tool-use + whitelist validation) + get_nl_query_parser() factory (wave 2) (completed 2026-07-25)
- [x] 09-03-PLAN.md — Tier-2 keyword fallback extractor + search_players() service (PlayerFilter + manual club__ style step + pagination) (wave 2) (completed 2026-07-25)
- [x] 09-04-PLAN.md — POST /api/players/search/ view: 3-tier degradation + RecentActivity "searched" logging + integration tests (wave 3) (completed 2026-07-25)

### Phase 10: AI Grounded Report Generation
**Goal**: Users can request AI-written scouting reports and club insights that are narratively generated but numerically grounded in real, already-computed scores.
**Depends on**: Phase 6, Phase 9
**Requirements**: AI-03, AI-04
**Success Criteria** (what must be TRUE):
  1. User can request an AI-generated scouting report for a player covering strengths, weaknesses, tactical fit, financial fit, and best use case, with every number in the report traceable to an already-computed score/stat.
  2. User can request AI-generated club insights (recruitment gaps, over-aged positions, financial constraints) grounded in real Position Needs and Transfer Behaviour aggregates.
  3. No report ever contains an LLM-invented number — all figures originate from the scoring/CRUD layers.
**Plans**: 5 plans (4 waves)
- [ ] 10-01-PLAN.md — Foundation: ANTHROPIC_REPORT_MODEL config + ReportGenerator interface contract + grounding validator (wave 1)
- [ ] 10-02-PLAN.md — AnthropicReportGenerator (plain generation + section parse + grounding + retry-once) + get_report_generator() factory (wave 2)
- [ ] 10-03-PLAN.md — Player scouting-report slice (AI-03): generate_scouting_report service + POST /api/players/{id}/scouting-report/ + clean-error path (wave 3)
- [ ] 10-04-PLAN.md — Club-insights slice (AI-04): clubs/tests conftest safety-net port + position_needs_aggregate + generate_club_insights + POST /api/clubs/{id}/insights/ (wave 3)
- [ ] 10-05-PLAN.md — Full-suite regression check + Phase-10 collection verify + live real-LLM spot-check/deferral (wave 4)

### Phase 11: Position Needs & Squad Simulation
**Goal**: Users can see where a club's squad is weak and simulate changes before committing to them.
**Depends on**: Phase 6, Phase 8
**Requirements**: PLAN-01, PLAN-03
**Success Criteria** (what must be TRUE):
  1. User can view a Position Needs analysis (strong/weak/at-risk) for a club's squad, based on depth, contract expiry, and age profile.
  2. User can simulate a squad change (add/remove/swap) and see recalculated aggregate squad metrics (avg age, avg score, budget/wage impact).
  3. A simulated change is not persisted to the real Squad Plan until the user explicitly commits it.
**Plans**: TBD

### Phase 12: Bidirectional Matching - Replacements & Player-Club Fit
**Goal**: Users can get ranked matches in both directions — replacement players for a weak position, and clubs that fit a given player.
**Depends on**: Phase 6, Phase 11
**Requirements**: PLAN-02, PLAN-04
**Success Criteria** (what must be TRUE):
  1. User can get a ranked list of suggested replacement players for a weak position, ordered by RMM/CS/TFM fit.
  2. User can get a ranked list of clubs that fit a given player (Player → Club Matching), scored by CS/TFM.
  3. Both ranking directions reuse one shared underlying "rank the other side by fit" service rather than duplicated logic.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 → 12

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Data Foundation | 9/9 | Complete    | 2026-07-21 |
| 2. Auth & Access Control | 3/3 | Complete    | 2026-07-21 |
| 3. Scoring Engine Curation & Correctness Oracle | 7/7 | Complete    | 2026-07-22 |
| 4. Scoring Engine Port | 6/6 | Complete   | 2026-07-23 |
| 5. Scoring Parity Testing | 4/4 | Complete   | 2026-07-24 |
| 6. Scoring Performance & Caching Layer | 7/7 | Complete   | 2026-07-24 |
| 7. Core CRUD - Players & Clubs | 3/3 | In Progress | - |
| 8. User Workspace CRUD | 6/6 | Complete   | 2026-07-25 |
| 9. AI Provider Interface & Natural-Language Search | 4/4 | Complete   | 2026-07-25 |
| 10. AI Grounded Report Generation | 4/5 | In Progress|  |
| 11. Position Needs & Squad Simulation | 0/TBD | Not started | - |
| 12. Bidirectional Matching - Replacements & Player-Club Fit | 0/TBD | Not started | - |

---
*Roadmap created: 2026-07-20*
*Granularity: fine (12 phases)*
