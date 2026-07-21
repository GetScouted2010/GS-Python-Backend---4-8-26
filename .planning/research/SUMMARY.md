# Project Research Summary

**Project:** GetScouted Backend
**Domain:** Django/DRF backend for an AI-powered football scouting/recruitment platform — CRUD data layer + a ported deterministic pandas scoring engine + LLM-driven search/report generation
**Researched:** 2026-07-20
**Confidence:** MEDIUM-HIGH

## Executive Summary

GetScouted's backend is a Django 5.2 LTS + DRF service that must do three structurally different things well: serve conventional CRUD (Players, Clubs, Transfers, Watchlist, Shortlists, Squad Plans, Profiles) on Postgres; run a genuinely correct port of a 15,747-line, untested, notebook-derived pandas scoring engine (`impact_model_v4.1.py`) that produces the platform's core credibility asset (Player Impact/RMM, Compatibility, Financial Fit, Transfer Probability scores); and expose LLM-backed natural-language search and AI-generated scouting reports/insights behind a provider-agnostic interface. Every research track converges on the same conclusion: this is a well-trodden Django/DRF CRUD problem wrapped around one genuinely hard, high-risk core — the scoring engine port — and the project succeeds or fails on whether that port is verifiably correct, not on whether the API surface is broad.

The recommended approach is layered and conservative given the risk profile: Django 5.2 LTS + DRF + psycopg3 + Postgres for the CRUD surface; a strictly isolated `scoring/` service layer with zero DRF imports, following a hybrid caching pattern (precompute whole-dataset aggregates like `std_lookup`/team-reference vectors on data change, do O(1) row-level math on demand, denormalize final scores onto model fields for cheap list/browse reads); Celery + Redis for anything that touches an LLM or scores in bulk; and `pydantic-ai` behind a thin adapter interface so search-query parsing and report generation share one provider-agnostic seam. Pandas should be pinned to `<3.0` for the port given the engine is untested and pandas 3.0 shipped real breaking changes in Jan 2026.

The dominant risk, repeated across STACK, ARCHITECTURE, and PITFALLS research independently, is silent correctness failure, not crashes: porting the scoring engine by "reading and rewriting" instead of characterizing it first, field-mapping drift during CSV migration that the engine's own defensive fallbacks mask rather than surface, and running full-dataset pandas operations synchronously inside request cycles. All three produce systems that "look done" while being subtly wrong or unusably slow under real concurrency — the worst outcome for a product whose entire value proposition is "the scores are real, not approximated." Mitigation is procedural as much as architectural: snapshot the original script's output before porting a single line, build a numerical parity test suite as the acceptance criterion, reconcile auth into one system of record with a role×endpoint permission matrix, and never let "endpoint exists" count as "phase done" without its correctness check attached.

## Key Findings

### Recommended Stack

Django 5.2 LTS is the correct default over Django 6.0 for a project meant to become the real production backend — 5.2 has the longest support runway and doesn't force Python ≥3.12. DRF (not Django Ninja) is right here because this project is CRUD-dominant with mature role-permission needs, and the codebase already has zero test coverage — adding an unfamiliar API framework on top of an untested port compounds risk for no real benefit. Postgres via psycopg3 (not psycopg2, maintenance-only) is a hard project constraint replacing Mongo/Supabase. pandas must be pinned `>=2.2,<3.0` during the port specifically because pandas 3.0 (Jan 2026) shipped real breaking changes and the 15,700-line source script was never written against it. Celery + Redis covers both scheduled batch recompute and ad-hoc LLM calls. `pydantic-ai` is the recommended LLM interface because the project needs both structured extraction (NL search → filters) and general text generation (reports) under one provider-agnostic seam.

**Core technologies:**
- Django 5.2 LTS — web framework/ORM; longest support window, matches CRUD-heavy shape
- Django REST Framework 3.17.x — REST layer; mature role-permission ecosystem (simplejwt, filter, spectacular)
- PostgreSQL 16/17 + psycopg 3.2.x — datastore/driver; project constraint, native connection pooling via Django 5.1+
- pandas `>=2.2,<3.0` + numpy 2.x — scoring engine runtime; pin below 3.0 until the port has test coverage; numpy (not pandas) for the live per-request hot path
- Celery 5.6.x + Redis + django-redis — background jobs and aggregate/vector caching for LLM calls and bulk scoring
- pydantic-ai 2.13.x — provider-agnostic LLM interface for NL search parsing and report generation, behind a thin service seam

### Expected Features

The feature landscape splits into table-stakes data-platform features (present in every competitor: Wyscout, InStat, TransferRoom) and AI-driven differentiators that make GetScouted distinct from a plain scouting database. The PRD already fixes full v1 scope (not being cut for the 4-day soft deadline), so "MVP" means "what must exist to be a credible v1," not a reduced feature set.

**Must have (table stakes):**
- Player/Club CRUD with rich profile schema, position-aware multi-season stats, transfer history
- Filter/sort/pagination on all list endpoints; role-based auth (scout/analyst/director/admin)
- Watchlist, Shortlist/Squad Plan persistence, player/club comparison, CSV/PDF export
- Deterministic scoring engine (RMM/CS/TFM/Transfer Probability) exposed via API with score breakdown/explainability, not just a final number

**Should have (differentiators):**
- Natural-language search → structured filter parsing (bounded single-call, not an open agent loop)
- AI-generated scouting reports and club insights, strictly grounded in already-computed scores (LLM narrates, never invents numbers)
- Bidirectional Player↔Club matching and AI-suggested squad replacements — both share one underlying "rank the other side by fit" primitive worth building axis-agnostically once
- Report caching/regeneration (near-term, not indefinitely deferred, given LLM cost/latency)

**Defer (v2+):**
- Multi-tenant data isolation, video/footage integration, marketplace/negotiation/messaging layer, real-time collaborative squad editing, conversational multi-turn AI agent, custom ML model training (port the existing deterministic model faithfully first)

### Architecture Approach

The backend is organized as one Django project with per-entity CRUD apps (`players/`, `clubs/`, `transfers/`, `watchlist/`, `shortlists/`, `squad_plans/`, `accounts/`), a cross-cutting `scoring/` app that owns the ported engine as a pure-Python service layer (zero DRF/HTTP imports, directly unit-testable), and a cross-cutting `ai/` app that separates *what to ask* (`services/`) from *how to talk to a vendor* (`providers/`, behind an `LLMProvider` ABC). The most important architectural fact — discovered by direct inspection of the source file — is that almost no function in `impact_model_v4.1.py` computes a single player's score in isolation: nearly everything depends on a precomputed whole-dataset lookup (`std_lookup` z-scores, team style vectors, team position references). This means "per-entity scoring" in Django requires hybrid caching: precompute and cache whole-dataset aggregates on data change (Redis or a materialized table), do O(1) row-level math on demand against those cached aggregates, and denormalize final scores onto model fields so list/browse/sort pages never invoke scoring math at all. The file is also a flattened Jupyter notebook with the same function names defined 3-4 times at different points (only the last definition is authoritative) and embedded sklearn model training mixed with deterministic math — so the port phase must start with a de-duplication/curation pass, not a blind copy.

**Major components:**
1. `scoring/` — ported engine as a service layer (position-keyed strategy pattern over the 8 clean `_calc_*_impact_raw` calculators), owns the hybrid cache and denormalized score fields
2. `ai/` — LLM-provider-agnostic layer; `services/` builds grounded prompts from real `scoring/` output, `providers/` implements the vendor adapter interface (stub provider unblocks dev before a provider is chosen)
3. Per-entity CRUD apps — thin views delegating to querysets and, where scores are involved, to `scoring/` services — no scoring math lives here
4. Cache/precomputed-aggregate layer (Django cache API, LocMem→Redis) — holds `std_lookup`, team-style vectors, team-position references, rebuilt on data change, never inline per request
5. ETL/migration layer — idempotent Django management commands per domain app, reusing legacy field-mapping knowledge as reference, not a bespoke separate service

### Critical Pitfalls

1. **Porting by "read and rewrite" instead of characterizing first** — snapshot the original script's real output before writing any Django scoring code; treat that snapshot as the oracle; port function-by-function with diffs, not model-by-model with one test at the end.
2. **No numerical parity test between the pandas original and the Django port** — build an explicit tolerance-based parity suite covering every position group and edge cases; this is the acceptance criterion for "the port is done," not optional QA.
3. **Running full-dataset pandas scoring synchronously inside a DRF request** — compute at data-load/import time or via Celery; cap live single-entity math to O(1) row-level operations against pre-cached aggregates.
4. **Silent CSV/Mongo import data loss** — write an explicit FIELD_MAPPING before import code exists, specify dtypes explicitly, log a pre-import data-quality pass, and produce a reviewed import report rather than trusting "the script ran without crashing."
5. **Field-mapping mismatches surfacing silently inside scoring via defensive fallbacks** — add a schema-conformance check that fails loudly at the migration boundary, and a smoke test asserting defensive fallbacks aren't firing on real imported data.
6. **Auth reconciliation treated as "pick one and migrate later"** — three conflicting legacy trust models exist; make Django the explicit single system of record for identity, never carry forward a disabled/default-allow security check, and write a role×endpoint permission matrix test early.

## Implications for Roadmap

Based on combined research, the phase structure should mirror the hard dependency chain surfaced independently by ARCHITECTURE.md (build order) and FEATURES.md (feature dependency graph): data model/migration must be real before scoring can be validated against anything, scoring must be real before AI features can ground their output, and auth must be settled before any write path ships. The single biggest roadmap risk (Pitfall 8) is treating "endpoint returns 200" as done — each phase below must carry its own correctness/verification step as part of its definition of done.

### Phase 1: Foundation — Data Model, Migration, and Auth
**Rationale:** Every other phase depends on real data existing in Postgres shaped correctly, and role-based auth gates all subsequent write endpoints; retrofitting auth later is more error-prone than building it in from the start.
**Delivers:** Django project skeleton, Player/Club/Transfer/Playstyle/CompatibilityScore models, idempotent CSV import management commands with explicit FIELD_MAPPING and dtype handling, an import report, `accounts/` with Profile/UserRole models and DRF permission classes wired to a secure-by-default setting.
**Addresses:** Player/Club/Transfer CRUD table stakes, role-based auth table stake
**Avoids:** Pitfall 5 (silent CSV import data loss), Pitfall 7 (auth reconciliation without a transition plan)

### Phase 2: Scoring Engine Curation and Port
**Rationale:** The scoring engine cannot be meaningfully validated without real migrated data (Phase 1), and every downstream AI/matching feature requires real scores to exist first. This is the highest-risk phase and must not be rushed or parallelized away.
**Delivers:** A curated (de-duplicated, sklearn-isolated) port of the position-keyed impact calculators, standardization/team-reference cache-building services, a snapshot-vs-port parity test suite across all position groups and edge cases, denormalized score fields, and the hybrid cache layer.
**Uses:** pandas `<3.0`, numpy, Django cache API, Celery for batch recompute
**Implements:** `scoring/` service layer, hybrid caching pattern
**Avoids:** Pitfall 1 (port-by-rewrite drift), Pitfall 2 (no parity test), Pitfall 3 (sync heavy compute), Pitfall 6 (silent field-mapping drift inside scoring)

### Phase 3: CRUD API Surface (Watchlist, Shortlists, Squad Plans, Filtering)
**Rationale:** With real data and real scores in place, the remaining CRUD apps and filter/search surface can be built against genuine model fields. This phase also establishes the filterable-field whitelist that NL search (Phase 4) needs to target.
**Delivers:** Full DRF ViewSet/router surface for all remaining entities, django-filter FilterSets, pagination conventions, query-count regression tests, CSV export.
**Addresses:** Watchlist, Shortlist/Squad Plan persistence, filter/sort/pagination, comparison, export table stakes
**Avoids:** Pitfall 4 (N+1 query patterns from per-row score access in serializers)

### Phase 4: AI Layer — NL Search and Grounded Report Generation
**Rationale:** Both AI features are explicit consumers of the CRUD filter surface (Phase 3) and the scoring layer (Phase 2). The provider adapter interface itself is cheap and should be scaffolded early against a stub so `ai/` isn't blocked on a provider decision.
**Delivers:** LLM provider adapter interface + stub provider, NL search (query → structured filter JSON via pydantic-ai), grounded report generator reading only real computed scores, report caching keyed on entity/context/prompt-version/data-version.
**Addresses:** NL search, AI-generated scout reports/club insights, report caching/regeneration differentiators
**Implements:** Adapter/Interface pattern for LLM provider abstraction

### Phase 5: Matching, Squad Simulation, and Polish
**Rationale:** Bidirectional Player↔Club matching and AI-suggested squad replacements share one underlying "rank the other side by fit" primitive with the scoring/AI layers already built — sequencing them last lets them reuse a proven, axis-agnostic ranking service.
**Delivers:** Player→Club matching endpoints, squad simulation "what-if" endpoints, AI-suggested replacements tied to Position Needs analysis, PDF export if time allows.
**Addresses:** Bidirectional matching, squad simulation, AI-suggested replacements differentiators

### Phase Ordering Rationale

- Data migration is a hard blocker for scoring — the scoring engine's inputs are specific real columns and cannot be validated against synthetic fixtures alone.
- Scoring must precede AI features because AI reports are required to ground their narrative in real computed scores, not invented ones.
- Auth is sequenced early but in parallel with data-model work since DRF permission classes are cheap to build in from the start but easy to forget if deferred onto existing endpoints.
- CRUD surface is placed after scoring so filterable-field definitions are grounded in real schema, and so NL search has a concrete filter surface to target.
- This ordering directly avoids breadth-over-depth scope creep: each phase's "done" bar includes its own correctness check (parity suite, import report, permission matrix, query-count budget) rather than deferring verification to an end-of-project testing phase.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 2 (Scoring Engine Port):** The de-duplication/curation step (identifying the authoritative version of each 3-4x-duplicated function) is bespoke to this specific 15,747-line file and has no external pattern to follow — needs careful manual analysis during planning.
- **Phase 4 (AI Layer):** LLM structured-output/grounding patterns are a fast-moving space; worth a fresh check on pydantic-ai's current API surface and provider support at build time.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Foundation):** Django/DRF CRUD, auth via simplejwt, and CSV-to-Postgres migration via `bulk_create(update_conflicts=True)` are all well-documented, HIGH-confidence, standard patterns.
- **Phase 3 (CRUD API Surface):** django-filter, DRF pagination, and N+1 prevention are mature, extensively documented DRF patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH (core Django/DRF/Postgres); MEDIUM (LLM libraries, pandas 3.0 compatibility) | Core versions verified via PyPI/official release notes; LLM interface space and pandas 3.0 impact on this specific script flagged for re-verification at build time |
| Features | MEDIUM-HIGH | Grounded primarily in the project's own PRD; competitor comparisons are WebSearch-derived and cross-referenced but not from official API access |
| Architecture | HIGH (layering/patterns and source-file facts, verified by direct inspection); MEDIUM (specific caching strategy is a judgment call, no load data yet) | The most load-bearing finding (no function scores a single player in isolation) was verified firsthand |
| Pitfalls | MEDIUM-HIGH | Grounded in this codebase's own CONCERNS.md/TESTING.md findings (direct evidence) plus well-established Django/pandas ecosystem practices |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Pandas 3.0 breaking-change specifics:** derived from search summaries, not the official whatsnew doc — re-verify before any future pandas 3.0 upgrade (not blocking for v1, since the recommendation is to pin `<3.0` anyway).
- **Celery/Redis version compatibility:** Celery 5.6.x's Redis-transport compatibility ceiling is WebSearch-derived — verify against the actual Celery changelog and target Redis version before deploying.
- **Scoring engine curation specifics:** which exact version of each duplicated function is authoritative needs direct code review during Phase 2 planning, cross-checked against `get_export_columns_for_position()`.
- **Transfer Probability score maturity:** likely the least mature/most modeled (vs. deterministic) score, involving sklearn training artifacts — budget extra validation time against known real transfers once ported.
- **Auth transition plan for existing Supabase users:** no decision yet exists for what happens to `pixel-perfect-clone-60729`'s existing Supabase-authenticated users — needs an explicit Key Decision recorded during roadmap/requirements work.

## Sources

### Primary (HIGH confidence)
- `.planning/PROJECT.md`, `GetScouted PRD.docx` — project scope and feature requirements
- `.planning/codebase/CONCERNS.md`, `TESTING.md`, `STACK.md`, `ARCHITECTURE.md`, `STRUCTURE.md` — direct codebase evidence
- Direct inspection of `pixel-perfect-clone-60729/docs/impact_model_v4.1.py` (15,747 lines)
- Django 5.2/6.0 release notes; PyPI JSON API (fetched 2026-07-20); psycopg3, Django async, and Django cache official docs
- Supabase JWT Signing Keys / JWKS docs

### Secondary (MEDIUM confidence)
- WebSearch: Django Ninja vs DRF; PydanticAI vs LiteLLM vs instructor; pandas 3.0 breaking changes summaries
- Wyscout API docs, TransferRoom API docs, TransferRoom xTV Q&A
- Django service-layer pattern articles and forum discussion
- Async worker / N+1 prevention articles
- NL-search-to-structured-query pattern sources (Typesense, Sease, Google Cloud)

### Tertiary (LOW confidence)
- Single-source cached-properties explainer, consistent with official docs but not independently verified

---
*Research completed: 2026-07-20*
*Ready for roadmap: yes*
