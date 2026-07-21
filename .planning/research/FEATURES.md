# Feature Research

**Domain:** Football scouting / recruitment intelligence backend (data platform + proprietary scoring + AI search & reporting)
**Researched:** 2026-07-20
**Confidence:** MEDIUM-HIGH (grounded in GetScouted PRD as primary source + verified against Wyscout/TransferRoom public API docs and established LLM structured-output/grounding patterns)

## Feature Landscape

### Table Stakes (Users Expect These)

These are what recruitment analysts, agents, and club decision-makers expect from *any* credible scouting data platform (Wyscout, InStat/Hudl, TransferRoom, Scout7, Transfermarkt-style tools). Missing these makes the backend feel like a toy rather than a professional tool.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Player CRUD + rich profile schema (bio, position, age, nationality, foot, height, contract expiry, market value) | Core unit of every scouting platform; every competitor (Wyscout, InStat, TransferRoom) exposes a player entity with this exact shape via API | LOW | Already partially defined in legacy Supabase schema + CSV dataset; straightforward Django model |
| Club CRUD + profile schema (league, country, manager, formation, squad size, playing style) | Clubs are the second core entity; needed for Club Intelligence page and as context for CS/TFM scoring | LOW | Playing style / tactical labels need a controlled vocabulary (high press, possession, direct, low block) |
| Position-aware performance stats (per-season, per-position metrics: goals, assists, tackles, interceptions, passing, duels, xG/xA) | Any recruitment analyst expects stats broken down by role, not one-size-fits-all — this is how Wyscout/InStat differentiate a striker's stats page from a CB's | MEDIUM | Requires a stats table keyed by (player, season, position) with position-conditional metric sets; already exists in CSV dataset per-position |
| Multi-season historical stats (season-by-season trend) | Scouts assess trajectory (improving/stable/declining), not a single snapshot — universal in Wyscout/InStat/TransferRoom | LOW-MEDIUM | Needs season as first-class dimension on stats records, not just "current" |
| Transfer history CRUD (fee, date, source/destination club, market value at time of transfer) | Needed for Financial Fit and Transfer Behaviour features; every recruitment platform tracks historical transfer fees as ground truth for valuation | LOW-MEDIUM | Data already exists in legacy CSVs; needs clean relational modeling (player, from_club, to_club, fee, date) |
| Filter & sort over player/club lists (position, age, market value, league, score thresholds) | Baseline expectation of any data table in this space — every platform supports faceted filtering | LOW | Standard DRF filtering/ordering backends (django-filter) |
| Role-based auth (scout, analyst, director, admin) | Recruitment tools are used by teams with different permission needs (who can approve a shortlist vs just browse) — matches PRD's explicit roles and reconciles the project's 3 conflicting legacy auth models | MEDIUM | One of the PROJECT.md's explicitly flagged risks; needs to be resolved once, cleanly, in Django |
| Watchlist (save/remove players) | Baseline "track this for later" feature present in every recruitment tool (TransferRoom shortlists, Wyscout tags) | LOW | Simple user↔player join table with CRUD endpoints |
| Shortlist / squad-plan persistence (named, shareable lists of ranked candidates) | Distinguishes a scouting *workflow* tool from a static database; PRD treats this as core (AI Shortlist page, Squad Planner) | MEDIUM | Needs ordering, club-context association, and score snapshotting (see Dependency notes) |
| Player/club comparison (side-by-side stats, scores, financials) | Universal recruitment analyst workflow — never make a decision on one player alone | LOW-MEDIUM | Backend just needs an endpoint returning N player payloads with aligned fields; comparison logic is a frontend concern but backend must support batch-by-id fetch |
| Export (CSV/PDF) of shortlists, club reports, club lists | Standard requirement — recruitment output is shared with directors/boards who don't log into the tool; every competitor platform supports export | MEDIUM | CSV is trivial; PDF generation (WeasyPrint/xhtml2pdf or similar) is a real backend service, budget time for it |
| Pagination, filtering, ordering conventions on all list endpoints | Baseline API hygiene expected by any frontend consuming a data-heavy backend; Wyscout/TransferRoom APIs are explicitly paginated, JSON, versioned | LOW | DRF pagination classes; consistent envelope across endpoints |
| Deterministic scoring engine exposed via API (Player Score/RMM, Compatibility Score, Financial Fit, Transfer Probability) | This *is* the product's credibility anchor per PROJECT.md ("the scores being right, not just the API being reachable") — every serious scouting platform (Wyscout Player Ratings, TransferRoom xTV, InStat Index) has a proprietary score as its centerpiece | HIGH | This is the ~15,700-line `impact_model_v4.1.py` port; correctness and score explainability (breakdown, not just a number) are non-negotiable per PRD 3.3/3.4/3.5 |
| Score breakdown / explainability (why this score, not just the number) | PRD explicitly requires "breakdown of why the player fits or does not fit" for CS, and "supporting metrics" for Player Score — recruitment analysts don't trust an opaque number | MEDIUM | Scoring engine must return component sub-scores, not just a final float; this is a data-modeling decision, not just a compute one |
| Recent activity / audit trail (recent searches, viewed players) | PRD explicit requirement (Dashboard 1.7); also standard in any professional tool for continuity across sessions | LOW-MEDIUM | Simple event-log table per user; needs write-path hooked into every "view" and "search" action |

### Differentiators (Competitive Advantage)

Features that set GetScouted apart from a plain scouting database. These map directly to the PRD's stated core value ("AI-powered") and to what legacy competitors (Wyscout, InStat, Scout7) generally do *not* do natively — they're primarily data providers, not decision/recommendation engines.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Natural-language search → structured filter parsing (AI Dashboard search bar, AI Shortlist refinement loop) | Lets a non-technical scout type "young left-back under 25, high press fit, under €5m" instead of building filters manually — this is the product's entry-point differentiator (PRD 1.0, 1.1, 2.9) | MEDIUM-HIGH | Standard, verified pattern: LLM call with a **strict JSON-schema/function-calling contract** that maps free text → a validated filter object (position, age range, value range, league, style tags, budget) against a fixed whitelist of real DB fields. This is NOT vector/semantic search over player docs — the data is structured/tabular, so the LLM's only job is *query translation*, and the actual retrieval is a deterministic Django ORM query against the parsed filters. Must handle: ambiguous/unparseable input (fallback to keyword search or clarification), partial parses (some filters extracted, rest ignored gracefully), and query refinement (2.9 "AI Loop") by re-parsing edited text with prior filter state as context. |
| AI-generated scouting reports (strengths/weaknesses/tactical fit/financial fit/best use case) | Turns raw stats into a readable narrative a director can act on without reading tables — this is what separates a "database" from an "intelligence platform" (PRD 3.6) | MEDIUM-HIGH | Standard grounding pattern to avoid hallucination: **never let the LLM invent numbers.** Compute all scores/stats deterministically first (RMM, CS, TFM, per-position stats), then pass those *real, already-computed values* into the prompt as structured context, and constrain output to a **fixed JSON schema** (strengths[], weaknesses[], tactical_fit, financial_fit, best_use_case) that references only the supplied facts. This is prompt-level grounding/RAG-lite (retrieval = your own DB, not a vector store) rather than open-ended generation. |
| AI club insights (recruitment gaps, over-aged position areas, financial constraints) | Same grounding pattern applied at the club level — flips player-centric intelligence into club-centric intelligence (PRD 4.8) | MEDIUM-HIGH | Depends on Position Needs + Transfer Behaviour aggregation already being computed server-side; the LLM narrates pre-computed structured facts, doesn't derive them itself |
| Report caching + regeneration | Report generation is expensive (LLM latency/cost) and largely stable data (stats change weekly, not per-request) — caching + explicit regenerate avoids cost blowup and gives users control | MEDIUM | Standard pattern: cache key = `(entity_id, club_context_id, model/prompt_version, underlying_data_version_or_hash)`. Serve cached report until underlying data changes or user explicitly hits "regenerate." PRD 3.6 explicitly calls out "refresh/regenerate behaviour" as a requirement — this needs to be a first-class backend decision, not an afterthought. |
| AI-suggested squad replacements (position-need-driven player recommendations) | Goes beyond scoring a given player — proactively recommends *which* players solve a *specific* squad gap, ranked by fit (PRD 5.5) | MEDIUM-HIGH | Depends on: Position Needs analysis (squad depth/contract/age) + full scoring engine (RMM/CS/TFM) run across the whole player pool filtered by position — essentially the same "match players to context" primitive reused across Dashboard, Squad Planner, and Club Intelligence |
| Bidirectional matching: Player→Club (not just Club→Player) | Most scouting tools are club-perspective-first (find players for my club); flipping to "find clubs for this player" is comparatively rare and is explicitly the PRD's differentiator page (Player → Club Matching) | MEDIUM-HIGH | Backend-wise this reuses the same CS/TFM computation but iterates over clubs instead of players for a fixed player — same scoring primitives, different iteration axis; worth designing the scoring service to be axis-agnostic (player↔club, not player-only) from the start |
| Transfer Probability modeling | Goes beyond static valuation (like Transfermarkt) into predictive likelihood — closer to what only well-funded platforms (TransferRoom xTV-adjacent signals) attempt | HIGH | This is a modeled/derived score (not raw data), likely the least mature part of the ported `impact_model_v4.1.py`; flag for extra validation against real outcomes since it's the hardest score to trust |
| Squad simulation (before/after comparison, budget impact of hypothetical swaps) | Turns squad planning from a spreadsheet exercise into an interactive "what-if" tool — differentiator vs static database platforms | MEDIUM | Backend needs a stateless "simulate" endpoint: given a squad + a proposed change (add/remove/swap), recompute aggregate squad metrics (avg age, avg score, budget/wage impact) without persisting until the user commits — avoid conflating "planning drafts" with committed squad state |
| Financial Fit classification tied to club spending profile (not just player market value in isolation) | Contextualizes valuation against a *specific* club's real spending history rather than a generic market-value number — more actionable than Transfermarkt-style flat valuations | MEDIUM | Depends on Club Transfer Behaviour aggregation (avg fee, avg MV, historical spend) being computed from the transfer-history dataset first |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|------------------|-------------|
| Free-form conversational chat/agent interface (multi-turn LLM "assistant" with tool-calling loops) for search | Feels more "AI-native," matches ChatGPT-style UX expectations | Massively increases scope, latency, and failure surface for v1; unpredictable tool-call chains are hard to test/ground, and the PRD only asks for single-shot query→filter parsing plus a "refine" loop, not an open agent | Build NL search as a bounded, single-call "text → structured filter JSON" function with a strict schema; treat "refinement" as re-parsing edited text with prior filters as context, not a stateful agent loop |
| Real-time match/event data ingestion (live tracking, in-match event streams à la Opta/StatsBomb) | Looks impressive, matches what top-tier platforms (Wyscout, InStat) eventually offer | Building or licensing live tracking data is an entirely different (and expensive) data-engineering problem, unrelated to the PRD's actual scope (season-level aggregated stats, not live match events); would blow the timeline for zero PRD-required value | Consume/import pre-aggregated season/per-position stats (already the CSV dataset approach) and leave live tracking as a future third-party integration, not a build target |
| LLM directly computing scores (asking the model to "rate this player out of 100") | Seems like a shortcut to "AI-powered scoring" | Non-deterministic, unauditable, and directly undermines the PROJECT.md core value statement that scores must be "real (not approximated)" — an LLM-guessed score is the exact crude heuristic this project exists to replace | Keep all four scores (RMM, CS, TFM, Transfer Probability) as deterministic, versioned outputs of the ported Python model; LLM only narrates/explains already-computed scores, never invents them |
| Building a transfer marketplace / negotiation / messaging layer (agent-to-club deal-making, offers, contracts) | TransferRoom's actual product includes a real marketplace; tempting to think "why not add deal-making" | Completely different product surface (workflow/negotiation state machine, legal/compliance concerns, multi-party messaging) — not in the PRD's 6 pages at all, and explicitly a distraction from "backend serves scouting intelligence" | Keep the product scoped to discovery/evaluation/planning; if deal execution is ever wanted, it's a separate, later-scoped product, not a feature bolt-on |
| Full multi-tenant white-labeling / per-club data isolation infrastructure | Sounds like sensible enterprise-readiness | Adds significant auth/data-partitioning complexity with zero PRD requirement right now (PRD roles are scout/analyst/director/admin within one org, not cross-tenant isolation) | Build role-based access within a single-tenant model now; revisit multi-tenancy if/when GetScouted actually sells to multiple competing clubs who must not see each other's shortlists |
| Real-time collaborative editing (multiple users live-editing the same squad plan simultaneously, like Figma) | Squad Planner's drag-and-drop pitch view *feels* like it wants live collaboration | Requires websockets/CRDT-style infrastructure disproportionate to the PRD, which describes single-user planning workflows with save/compare, not concurrent multi-user editing | Standard REST CRUD with optimistic locking/last-write-wins on squad plans; add real-time collab only if explicitly requested later |
| Training/fine-tuning a custom ML model for scoring (vs. porting the existing deterministic model) | "AI-powered platform" branding might suggest an ML pipeline | The scoring methodology already exists as a working, if untested, deterministic pandas model (`impact_model_v4.1.py`) — replacing it with an ML model trained from scratch discards known-good business logic, introduces training-data/labeling problems, and isn't what the PRD asks for | Port the existing deterministic model faithfully first; treat "train a predictive model" as a distinct, much later research question if ever pursued |
| Video/footage storage and clip-tagging (à la Wyscout/InStat's core video product) | Wyscout/InStat's actual competitive moat is synchronized video+event data, so it "feels" like table stakes for the category | Explicitly out of scope — nothing in the PRD's 6 pages references video; this is a separate, very large product category (media storage, sync tagging) that InStat/Wyscout spent years building | Treat GetScouted as data-and-scores intelligence layer, not a video platform; if video is ever wanted, it's licensed/integrated (e.g., linking out to Wyscout), not built |

## Feature Dependencies

```
Player CRUD + Position-aware stats + Season history
    └──requires──> Real dataset migration (CSV → Postgres)

Scoring Engine (RMM, CS, TFM, Transfer Probability)
    └──requires──> Player CRUD + Club CRUD + Transfer history CRUD
                       └──requires──> Real dataset migration

AI Scouting Report (player-level)
    └──requires──> Scoring Engine (RMM, CS, TFM) — reports narrate real computed scores, never invent them
    └──requires──> Position-aware stats (feeds "strengths/weaknesses")

AI Club Insights
    └──requires──> Position Needs analysis (squad depth/contract/age aggregation)
    └──requires──> Transfer Behaviour aggregation (from Transfer history CRUD)

Natural-language Search (query → filters)
    └──requires──> Filter & Sort system (the whitelist of real, queryable fields the LLM is allowed to target)

AI Suggested Replacements (Squad Planner)
    └──requires──> Position Needs analysis
    └──requires──> Scoring Engine (ranks candidates by RMM/CS/TFM)

Player → Club Matching (bidirectional)
    └──requires──> Scoring Engine (CS/TFM computed per club, not just per player)
    └──requires──> Club Transfer Behaviour + Financial Fit classification

Squad Budget Tracker / Simulation
    └──requires──> Financial Fit classification
    └──requires──> Squad Plan persistence (shortlist/watchlist pattern)

Export (PDF/CSV)
    └──requires──> All underlying entities + scores already computed (export is a rendering layer, not a data source)

Report Caching/Regeneration ──enhances──> AI Scouting Report, AI Club Insights
    (avoids recomputation cost; must invalidate when underlying scores/data change)

Role-based Auth ──gates──> all write endpoints (watchlist, shortlist, squad plan mutation)
```

### Dependency Notes

- **Scoring Engine requires real dataset migration:** The ported `impact_model_v4.1.py` cannot be meaningfully validated against fake/seed data — it must run against the migrated real CSVs (players, playstyles, per-position stats, compatibility scores, transfer history) to be trustworthy. This makes dataset migration a hard blocker for any phase that touches scoring.
- **AI features require the scoring engine to exist first, not the other way around:** Both NL search (needs real filterable fields) and AI reports (needs real scores to narrate) are consumers of the CRUD + scoring layers. Sequencing AI work before the scoring engine is stable risks either fabricated/hallucinated content or reports that need rewriting once real scores land.
- **AI Suggested Replacements and Player↔Club Matching share one underlying primitive:** "given a fixed side (player or club), rank the other side by CS/TFM/RMM fit." Building this as one axis-agnostic scoring/ranking service (rather than two separate implementations) avoids duplicated logic across Squad Planner, Club Intelligence, and the Matching page.
- **Report caching enhances but does not gate AI reports:** Reports can ship without caching (regenerate every time) for a first pass, but cost/latency will make this unsustainable quickly — caching should be treated as near-term, not deferred indefinitely, especially given LLM calls are the most expensive/slowest part of every request path.
- **Role-based auth gates all mutation endpoints:** Watchlist, shortlist, and squad-plan writes should not ship before the auth model is settled, since retrofitting permission checks onto existing endpoints is more error-prone than building them in from the start.

## MVP Definition

Per PROJECT.md, this project's scope is already fixed by the PRD and explicitly *not* being cut to fit the 4-day soft deadline — so "MVP" here means "what must exist for the backend to be a credible v1," not a reduced scope.

### Launch With (v1)

- [ ] Full CRUD for Players, Clubs, Transfers, Watchlist, Shortlists, Squad Plans, Recent Activity, Profiles — the foundational data layer every other feature depends on
- [ ] Real dataset migration (CSV → Postgres) — without real data, scores and AI outputs are demoing against nothing credible
- [ ] Full scoring engine port (RMM, CS, TFM, Transfer Probability) with score breakdowns/explainability — the product's stated core value; nothing else matters if scores aren't real
- [ ] Role-based auth (scout/analyst/director/admin) — gates every write path; reconciles the 3 conflicting legacy auth models
- [ ] Filter/sort/pagination on all list endpoints — baseline API hygiene every consuming page depends on
- [ ] Natural-language search → structured filter parsing (LLM-provider-agnostic) — PRD's stated entry point (AI Dashboard) and explicitly in v1 scope per PROJECT.md
- [ ] AI-generated scouting reports (player) and club insights, grounded in real computed scores, structured JSON output — explicitly in v1 scope per PROJECT.md, core to "AI-powered" positioning
- [ ] Export endpoints (CSV minimum; PDF if time allows) — standard professional-tool expectation, low-risk to build once data model is stable

### Add After Validation (v1.x)

- [ ] Report caching/regeneration with data-version-aware invalidation — ship "always regenerate" first if LLM cost/latency isn't yet a proven problem, then add caching once real usage patterns are observed
- [ ] AI Suggested Replacements / squad simulation "what-if" engine — depends on Position Needs analysis being solid first; can follow once core scoring is proven correct
- [ ] Refinement/trust tuning of Transfer Probability (the least mature score) — once initial version ships, validate against known real transfers and iterate
- [ ] Query clarification UX for ambiguous NL search input (vs. simple graceful fallback to keyword search in v1)

### Future Consideration (v2+)

- [ ] Multi-tenant data isolation — only if GetScouted sells to multiple competing clubs
- [ ] Video/footage integration (linking to or licensing Wyscout/InStat-style media) — separate large product surface, not requested in PRD
- [ ] Marketplace/negotiation/messaging layer — different product entirely, would need its own PRD
- [ ] Real-time collaborative squad planning — only if usage shows single-user planning is insufficient
- [ ] Conversational multi-turn AI agent (beyond bounded query-parse + report-generation) — only if bounded NL search proves insufficient for real usage

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Scoring engine port (RMM/CS/TFM/Transfer Probability) | HIGH | HIGH | P1 |
| Real dataset migration | HIGH | MEDIUM | P1 |
| Core entity CRUD (Player/Club/Transfer/Watchlist/Shortlist/Squad Plan) | HIGH | MEDIUM | P1 |
| Role-based auth | HIGH | MEDIUM | P1 |
| Natural-language search → filters | HIGH | MEDIUM-HIGH | P1 |
| AI scouting reports / club insights | HIGH | MEDIUM-HIGH | P1 |
| Filter/sort/pagination | MEDIUM | LOW | P1 |
| Export (CSV/PDF) | MEDIUM | MEDIUM | P2 |
| Report caching/regeneration | MEDIUM | MEDIUM | P2 |
| AI Suggested Replacements / squad simulation | MEDIUM-HIGH | MEDIUM-HIGH | P2 |
| Bidirectional Player↔Club matching service | MEDIUM-HIGH | MEDIUM | P2 (shares primitives with P1 scoring) |
| NL search clarification/disambiguation UX | LOW-MEDIUM | MEDIUM | P3 |
| Video/marketplace/multi-tenant/real-time collab (anti-features) | LOW (for this product) | HIGH | Not planned |

**Priority key:**
- P1: Must have for launch (backend-only v1 per PROJECT.md)
- P2: Should have, add when possible within v1 or immediately after
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Wyscout (Hudl) | TransferRoom | GetScouted's Approach |
|---------|--------------------|--------------|------------------------|
| Player/team/competition data API | Full REST API (OpenAPI 3.0), 600+ leagues, per-competition/team/player/match endpoints, versioned (v4) | JSON REST API, 130,000+ players, structured datasets for in-house integration | Same shape (DRF REST, paginated, filterable) but scoped to the PRD's real dataset rather than live third-party league coverage |
| Proprietary score/valuation | Player ratings/index (per-match, position-weighted) | Expected Transfer Value (xTV) — real-time, similarity-score-weighted valuation | Four distinct scores (RMM, CS, TFM, Transfer Probability) covering performance, tactical fit, financial fit, and likelihood — broader than either single-score competitor |
| Video/event data | Core product strength (synced video + event tagging) | Not a focus | Explicitly out of scope (anti-feature) — GetScouted is a scores/intelligence layer, not a video platform |
| AI-generated narrative reports | Not a standard API feature; largely raw data + ratings | Not a standard feature; focus is valuation/marketplace | Differentiator — structured, grounded AI reports narrating already-computed scores (PRD 3.6, 4.8) |
| Natural-language search | Not a standard API feature (structured query params only) | Not a standard API feature | Differentiator — LLM-parsed text → structured filters (PRD 1.0, 2.9) |
| Marketplace/deal-making | Not core (data/video platform) | Core product (real-time transfer marketplace, 7,000+ coaches) | Explicit anti-feature for GetScouted — stays in discovery/evaluation/planning scope |
| Squad planning / simulation | Not a core feature | Not a core feature | Differentiator — pitch-view squad planning with AI-suggested replacements and budget simulation (PRD Squad Planner page) |

## Sources

- `/Users/MAC/Desktop/getScouted/GetScouted PRD.docx` (Jan 2026, World In Motion Ltd) — primary source for all page-level feature requirements (highest confidence; product-specific, not general ecosystem inference)
- `/Users/MAC/Desktop/getScouted/.planning/PROJECT.md` — scope, constraints, and explicit v1 inclusion of AI features
- [Wyscout API](https://apidocs.wyscout.com/) — API v4, OpenAPI 3.0, 600+ leagues, player/team/competition/match endpoints (MEDIUM confidence, WebSearch-derived, cross-referenced across multiple results)
- [Wyscout — SoccerEDU platform overview](https://www.socceredu.com/en-US/blog/wyscout)
- [TransferRoom API Documentation](https://www.transferroom.com/api-docs) — JSON REST API, structured datasets (MEDIUM confidence, WebSearch-derived)
- [TransferRoom xTV Q&A](https://blog.transferroom.com/expected-transfer-value-xtv-qa) — expected transfer value / similarity-score valuation model (MEDIUM confidence)
- [TransferRoom API blog post](https://blog.transferroom.com/transferroom-api-smarter-team-building-powered-by-data)
- [Typesense: Natural Language Search](https://typesense.org/docs/guide/natural-language-search.html) — standard text-to-filter pattern (MEDIUM confidence)
- [Sease: From Natural Language to Structured Solr Queries using LLMs](https://sease.io/2024/08/from-natural-language-to-structured-solr-queries-using-llms.html) — LLM query-parsing pattern (MEDIUM confidence)
- [Atlassian: Structured Queries — Enhancing Search with Natural Language and Filters](https://www.atlassian.com/blog/company-news/enhancing-search-with-natural-language-and-filters) — deterministic filter extraction from NL query pattern (MEDIUM confidence)
- [Google Cloud: Filter with natural-language understanding (Agent Search)](https://cloud.google.com/generative-ai-app-builder/docs/natural-language-queries) — official doc on NL-to-filter parsing (MEDIUM-HIGH confidence, official vendor docs)
- Hallucination mitigation / structured-output grounding patterns — multiple 2025 sources agree on: structured JSON schema output contracts, RAG/grounding via supplying real computed data as context, and forbidding ungrounded claims (MEDIUM confidence, WebSearch-derived, consistent across sources but no single authoritative spec since this is an evolving best-practice area, not a standard)

---
*Feature research for: AI-powered football scouting/recruitment platform backend (GetScouted)*
*Researched: 2026-07-20*
