# Pitfalls Research

**Domain:** Porting an untested pandas scoring engine into a Django/DRF backend + migrating multi-source data (Mongo/CSV/Supabase) into Postgres + reconciling 3 legacy auth models
**Researched:** 2026-07-20
**Confidence:** MEDIUM-HIGH (grounded in this codebase's actual CONCERNS.md/TESTING.md findings + verified current Django/DRF/pandas ecosystem practices; some claims are well-established engineering wisdom rather than freshly-sourced facts)

## Critical Pitfalls

### Pitfall 1: Porting the pandas model by "reading and rewriting" instead of characterizing it first

**What goes wrong:**
The team reads `impact_model_v4.1.py` (15,747 lines), understands the intent, and rewrites it "cleanly" in Django/Python — restructuring functions, renaming variables, "fixing" what looks like dead code or odd defensive checks along the way. The port silently changes behavior wherever the port-author's mental model of "what this should do" differs from what the code actually does (which is common, because this code has never run against real production traffic and its defensive branches were written to survive *unknown* data problems the author never fully enumerated).

**Why it happens:**
There is no existing test suite, no known-good output to diff against, and no production track record to treat as ground truth. Under time pressure, engineers default to "understand and reimplement" rather than "capture behavior, then refactor" because reimplementation feels faster than building a characterization harness first.

**How to avoid:**
- Before writing a single line of Django scoring code, run `impact_model_v4.1.py` as-is (in a throwaway script/notebook, not Django) against a representative slice of the real dataset and **snapshot the output** (CSV/parquet of scores per player, including all intermediate component scores where `return_components=True` is available).
- Treat that snapshot as the oracle. The Django port's job is to reproduce it, not to reinterpret it.
- Port function-by-function, not model-by-model: port `_calc_cb_impact_raw`, snapshot-diff it against the Python original for a batch of CB rows, then move to the next function. Don't port all 15,700 lines and then test once at the end.
- Preserve the defensive/silent-default code paths exactly as written in phase 1, even when they look wrong — they encode undocumented knowledge about real data quality. Flag them for later cleanup, don't fix them mid-port.

**Warning signs:**
- No snapshot/reference output exists before porting begins.
- Pull requests for the port show renamed variables, restructured control flow, or "cleanup" diffs mixed in with logic changes — makes it impossible to tell what changed behavior.
- Scores for the same player differ between old script and new endpoint and nobody can explain why within an hour.

**Phase to address:**
Phase covering scoring engine port (before it's wired into any API endpoint). This must be the *first* thing done in that phase, not a follow-up task.

---

### Pitfall 2: No numerical parity test between the original pandas script and the Django port

**What goes wrong:**
The Django port "looks right" — scores are in the right range, ordering seems plausible — and ships without ever being diffed row-for-row against the pandas original. Small numeric drift (rounding, float64 vs Decimal, different `groupby`/aggregation order, NaN-handling differences) accumulates and produces subtly wrong rankings that are far more dangerous than an obvious crash, because they look correct to a reviewer but are wrong to a domain expert (a scout comparing two similar players).

**Why it happens:**
There is no CI, no existing test scaffolding, and a 4-day deadline pushes toward "ship if it doesn't error." Floating-point behavior differences are invisible unless explicitly compared — pandas `float64` arithmetic, Python's `round()`, and Postgres `numeric`/`double precision` do not all round the same way at the boundary (e.g., banker's rounding vs half-up), and per pandas' own documented behavior, aggregation/merge order can produce different float64 results even for mathematically identical operations.

**How to avoid:**
- Build a small parity test suite: run N representative players (cover every position group — GK, CB, FB, CMF, DMF, AMF, FWD — plus edge cases: missing minutes, missing market value, unknown league) through both the original script and the Django port, assert scores match within an explicit tolerance (e.g., `abs(diff) < 0.01`), not exact equality.
- Decide explicitly, once, how rounding is handled at each score's public boundary (e.g., "final RMM score rounds half-up to nearest integer at serialization time, all intermediate math stays float64") and document it — do not let each function invent its own rounding.
- Prefer computing internally in the same numeric type pandas used (float64) rather than converting to Postgres `Decimal`/`numeric` mid-calculation and back — type coercion mid-pipeline is a common silent-drift source.
- Re-run the parity suite any time a "silent default" branch (see Pitfall 1) is touched, since those are exactly where behavior is least specified.

**Warning signs:**
- Two players who were previously ranked A-then-B by the legacy/reference script flip order in the new API with no data change.
- Scores that are off by a small, inconsistent amount (not exactly 0, not wildly wrong) — the fingerprint of rounding/type drift rather than a logic bug.
- No test file exists that imports both the reference script's function and the Django equivalent for direct comparison.

**Phase to address:**
Same phase as the scoring engine port — parity testing is not a "nice to have" QA step afterward, it is the acceptance criterion for the port being "done."

---

### Pitfall 3: Running the full pandas scoring pipeline synchronously inside a DRF request/response cycle

**What goes wrong:**
A `GET /players/{id}/impact` or a search/list endpoint triggers on-the-fly pandas computation (loading a DataFrame, computing league/position averages, running the row-level scoring function) inside the Django request-response cycle. Under Django's default synchronous WSGI worker model, this blocks that worker for the full computation time; a handful of concurrent requests against a scoring-heavy endpoint can exhaust the worker pool and produce cascading 504 timeouts for unrelated, cheap endpoints served by the same process pool.

**Why it happens:**
It's the fastest thing to build under deadline pressure — call the scoring function directly from the view — and it "works" in local testing with one user and no concurrency. Django's synchronous default (WSGI, not ASGI) means a slow view genuinely blocks that worker; there is no free lunch from async unless the underlying work is offloaded.

**How to avoid:**
- Compute scores **at data-load/import time**, not at request time, for anything that doesn't depend on per-request filters (this is explicitly recommended in `CONCERNS.md`'s "Fix approach" for the performance section too). Store the computed score as a column/field on the Player model, recompute on a schedule or on data change, not per GET.
- Pre-compute and cache position-group/league-group averages (used as normalization baselines inside the model) rather than recomputing them per request — these are expensive aggregations that don't change per-request.
- For any score that must be computed live (e.g., a compatibility score against club-specific, user-supplied criteria), push it to a background task (Celery, Django-RQ, or even a simple thread pool with a task-status endpoint) rather than blocking the request thread, and cap/paginate how many players can be scored in one live request.
- If genuinely synchronous computation is unavoidable for a single-object endpoint, keep it scoped to one row's computation (not a full-dataset reload) and benchmark it under concurrent load before considering it "done."

**Warning signs:**
- Any DRF view function directly instantiates or reloads a full players DataFrame inside `get()`/`list()`.
- Response times balloon linearly with the number of players being scored in a single request.
- Load testing with >5 concurrent requests to a scoring endpoint causes unrelated endpoints (e.g., login) to slow down or time out.

**Phase to address:**
Architecture/API design phase (decide compute-on-write vs compute-on-read before building endpoints) and the scoring integration phase specifically.

---

### Pitfall 4: N+1 query patterns from per-row score access in serializers

**What goes wrong:**
A `PlayerSerializer` exposes `impact_score`, `compatibility_score`, or related club/transfer data as `SerializerMethodField`s or via related-object traversal (`player.club.name`, `player.transfers.all()`). For a list endpoint returning 20-50 players, each of these per-row lookups fires a separate DB query if the queryset wasn't eager-loaded — turning one logical "list players" request into hundreds of queries, which is invisible at 5 test records and catastrophic at the real 41,700-player scale.

**Why it happens:**
DRF's `SerializerMethodField` and related-field access are lazy by default and don't automatically batch; this only shows up once you serialize a realistic result set, which under a 4-day deadline usually isn't tested until very late (or in production).

**How to avoid:**
- Any FK/OneToOne relation surfaced in a list serializer must be pulled in via `select_related()` on the view's `get_queryset()`.
- Any reverse-FK/M2M (e.g., transfer history, playstyles) must use `prefetch_related()`, ideally with `Prefetch()` objects that pre-filter/pre-order to avoid pulling unnecessary rows.
- Precomputed scores (see Pitfall 3) should be plain model fields, not `SerializerMethodField`s that trigger computation — this collapses an entire class of N+1 risk since a stored field comes back with `select_related`/the base query for free.
- Add `django-silk` or simply log query counts (`django.db.connection.queries` in tests, or `assertNumQueries` in DRF test cases) for every list endpoint before considering it done — set an explicit query-count budget (e.g., "player list endpoint must issue ≤5 queries regardless of page size") and enforce it in tests.

**Warning signs:**
- Query count in Django Debug Toolbar / `assertNumQueries` scales with the number of rows returned rather than staying constant.
- List endpoints feel fast with 10 seeded rows and slow with the full imported dataset.
- Serializers reference `.club.name`, `.transfers.all()`, or similar dotted/related lookups without a corresponding `select_related`/`prefetch_related` in the view.

**Phase to address:**
API/endpoint-building phase, enforced via test assertions from the first list endpoint built (establishes the pattern before it's copy-pasted across all 6 PRD pages' endpoints).

---

### Pitfall 5: Treating CSV/Mongo import as "just load it in" without a validation and reconciliation layer

**What goes wrong:**
The 41,709-row `Players.csv` (and transfer history CSV) get imported directly into the new Postgres schema with a straightforward pandas `read_csv()` → Django ORM `bulk_create()`/`update_or_create()` script. Rows with missing fields, type mismatches (numeric column read as string due to a stray "N/A"), or duplicate/near-duplicate player identities either raise unhandled exceptions mid-import (partial, silently incomplete data in Postgres) or get coerced/dropped without anyone noticing — e.g., pandas silently upcasting an int column with nulls to float64 (turning IDs or shirt numbers into `85.0` instead of `85`), or `errors='coerce'` turning malformed numeric strings into `NaN` that then null out a field the scoring model requires.

**Why it happens:**
CSV import feels like a solved, boring problem, so it gets the least design attention despite being the highest silent-failure-risk step in the whole pipeline. `CONCERNS.md` already flags this: the Mongo schema had 100+ fields marked `required: true` with no visible pre-import validation, and this codebase's CSVs are known to have field-naming inconsistencies against the scoring model's expected columns (`Team_within_selected_timeframe` vs `Team`, `Market_value` vs `Market Value`, position field variants).

**How to avoid:**
- Write an explicit `FIELD_MAPPING` (CSV column → canonical Django field name → expected dtype) before import code is written — this exists as a documentation gap already flagged in `CONCERNS.md`; closing it is a prerequisite, not a nice-to-have.
- Specify dtypes explicitly on `read_csv()` (`dtype=` / `converters=`) rather than letting pandas infer them — inference is exactly what silently turns IDs into floats or drops leading zeros.
- Run and log a pre-import data quality pass: null counts per column, out-of-range values (age > 50, negative market value), and non-parseable numeric strings — before touching the database, not discovered after.
- Make the import idempotent and resumable (`update_or_create` keyed on a stable natural key, or an explicit staging table) so a partial failure can be diagnosed and re-run rather than leaving Postgres in an unknown partial state.
- Import in a transaction (or batched transactions with checkpointing) so a mid-import failure doesn't leave half the dataset committed silently.
- Produce and keep an import report (rows attempted, rows succeeded, rows skipped + reason) as a build artifact — this is the fastest way to catch "41,709 in CSV, 38,200 in Postgres" silently.

**Warning signs:**
- Import script has no logging of skip/failure counts — it either "works" or throws once.
- Row counts in Postgres don't match CSV row counts and nobody checked.
- A numeric field imported as a Django `IntegerField` came from a pandas column that pandas itself reported as `float64` or `object` dtype.
- Field names in the Django model were chosen by "closest guess" from the CSV header without cross-checking against what `impact_model_v4.1.py` actually expects.

**Phase to address:**
Data migration phase — must precede or run in lockstep with the scoring engine port phase, since the scoring engine's expected column names are the actual spec for what the import needs to produce.

---

### Pitfall 6: Field-naming/schema mismatch surfacing only inside the scoring engine at runtime

**What goes wrong:**
Because `impact_model_v4.1.py` has defensive column-existence checks (`if "Minutes" not in club_df.columns: ... else: club_df["Minutes"] = 0`), a field-mapping mistake in the Django/Postgres import doesn't crash — it silently falls through to a default value (often `0`), which then propagates into a plausible-looking but wrong score. This is worse than a crash because it's undetectable without deliberately checking for it.

**Why it happens:**
The original script was written to be resilient against missing/misnamed columns in ad hoc analysis contexts (Jupyter, one-off exports) — a reasonable design there, but a liability once it's silently absorbing real schema drift from a fresh Django/Postgres migration where every column name is a new decision point.

**How to avoid:**
- Before scoring, run the imported DataFrame through an explicit schema-conformance check that fails loudly (raises, doesn't default) if any column the model requires is missing or empty for a nontrivial fraction of rows — invert the model's own permissiveness for the migration/import boundary specifically.
- Use the existing "known mismatches" list from `.planning/codebase/CONCERNS.md` (Team vs Team_within_selected_timeframe, Market_value vs "Market Value", Minutes variants, Position variants, attributes as separate fields vs jsonb) as the starting checklist to explicitly resolve, not as background risk to hope doesn't bite.
- Add a smoke test: import a small known dataset, run it through scoring, and assert that specific fields used defensive defaults are *not* triggered (e.g., assert `Minutes` was populated from source, not fallen back to 0) for a sample of real rows.

**Warning signs:**
- A meaningful fraction of players show identical or suspiciously-round component scores (fingerprint of shared default values across many rows).
- No log/metric exists for how often each defensive fallback branch in the ported model fires.

**Phase to address:**
Scoring engine integration phase, immediately after data migration — this is the join point between Pitfall 5 (import) and Pitfall 1/2 (port correctness), and needs an explicit verification step, not an assumption that "if import succeeded, mapping was correct."

---

### Pitfall 7: Auth reconciliation treated as "pick one and migrate later" without a transition plan

**What goes wrong:**
Under time pressure, the team picks one auth model (commonly: just build fresh Django auth, ignore the legacy JWT/Supabase users) without a considered plan for existing Supabase-authenticated users in `pixel-perfect-clone-60729`, and without deciding what happens to the currently-disabled API-key middleware. This either (a) silently breaks existing sessions/users when the frontend eventually points at the new backend, or (b) reintroduces the exact "everything gets through" security hole currently present in the legacy Node API (`middleware/apikey.js` has `next()` unconditionally, per `CONCERNS.md`) by copy-pasting a similar disabled-check pattern into Django under deadline pressure "to get it working" and forgetting to re-enable it.

**Why it happens:**
Three genuinely different trust models exist (stateless JWT from a Node API, a disabled shared-secret API key, and Supabase's own hosted auth/session/RLS model), and reconciling them properly (token verification, claim mapping, role mapping) is real design work that's easy to defer when the immediate goal is "make one endpoint work for the demo."

**How to avoid:**
- Make an explicit decision, in Key Decisions, about the single source of truth for identity going forward (this project's constraints already state Django/DRF replaces Supabase — confirm this means Django becomes the *auth* system of record too, not just the data API, since ambiguity here is exactly what caused the original three-way split).
- If Supabase-issued JWTs must be accepted (e.g., because `pixel-perfect-clone-60729` already has real Supabase users), verify them properly against Supabase's JWKS/signing key rather than trusting an unverified token — treat this as equivalent-risk to rolling your own auth if done wrong.
- Do not carry forward the API-key middleware pattern at all unless it's actually re-enabled and enforced; a disabled security check should never be ported, even structurally, into new code — the "commented-out check that defaults to allow" pattern is exactly what caused the original vulnerability and is easy to reintroduce by habit.
- Define role mapping (scout, analyst, director, admin) once, centrally, and test that every protected endpoint actually enforces it — `CONCERNS.md` already found inconsistent per-route auth enforcement in the legacy Node API; don't repeat that pattern of "most routes protected, a few silently aren't."
- Write a permission test matrix (role × endpoint × expected allow/deny) early, even a small one — this catches "forgot to protect this endpoint" before it ships, cheaper than any other prevention here.

**Warning signs:**
- Some DRF views have explicit `permission_classes`, others rely on defaults or none at all, with no single settings-level default (`DEFAULT_PERMISSION_CLASSES`) requiring authentication.
- No decision is recorded for what happens to Supabase-authenticated users of the existing frontend prototype once the backend swap happens.
- Any code path that checks a credential and falls through to "allow" when the check is skipped/misconfigured, rather than "deny by default."

**Phase to address:**
Auth phase — should be one of the earliest phases (most other endpoints depend on `permission_classes`/role checks being stable), and should explicitly include a permission-matrix test, not just "login works."

---

### Pitfall 8: Full-scope-under-deadline pressure causes scope creep into the port instead of scope discipline

**What goes wrong:**
Given the explicit project decision to keep full scope on a 4-day soft deadline, the highest-risk failure mode isn't "too little gets built" but "the scoring port, migration, and auth work all get partially done in parallel with too little verification on each, so by day 4 everything looks superficially complete (endpoints return 200s) but nothing has been checked for correctness" — i.e., a demo that works for the happy path shown but is silently wrong or insecure underneath, which is worse for a product whose "core value is that scores are right" than an honest partial build.

**Why it happens:**
Deadline pressure combined with "keep full scope" creates strong incentive to prioritize breadth (does every endpoint exist) over depth (is every endpoint correct), especially since correctness here is invisible without deliberate testing (see Pitfalls 1, 2, 5).

**How to avoid:**
- Sequence phases so scoring-parity verification and import validation are *inside* the definition of done for their respective phases, not deferred to a "testing phase" at the end that will get cut first under time pressure.
- Protect a fixed, non-negotiable time budget for the parity test suite (Pitfall 2) and the auth permission matrix (Pitfall 7) specifically — these are the two checks most likely to be silently skipped when time runs short, and both guard the two things the project explicitly says matter most (score correctness, and not shipping an unauthenticated API again).
- Report progress against the deadline in terms of "phases with verified correctness" rather than "endpoints that exist," consistent with the project's own stated intent to report realistically rather than force-fit scope.

**Warning signs:**
- Roadmap phases define "done" as "endpoint returns data" without a parity/correctness check attached.
- Testing/verification work is scheduled as a distinct later phase rather than embedded in each phase that produces risk (scoring, import, auth).

**Phase to address:**
Roadmap structuring itself — this is a meta-pitfall the phase sequencing must account for, not a single implementation phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|--------------------|-----------------|------------------|
| Skip the pandas-vs-Django parity test suite, ship on "looks right" | Saves 0.5-1 day | Wrong scores erode the platform's core credibility claim; bugs surface as scout-facing ranking errors, hardest failure mode to debug retroactively | Never for the core scoring endpoints; may be acceptable temporarily for a clearly-labeled "experimental" secondary score not on the critical PRD path |
| Compute scores on-the-fly per request instead of precomputing at import time | Simpler initial implementation, no cache-invalidation logic needed | Breaks under any real concurrency; becomes a rewrite once more than a couple of scouts use it simultaneously | Only acceptable for genuinely dynamic, user-parameterized scores (e.g., live compatibility against custom club criteria) that can't be precomputed, and only if pushed to a background task |
| Import CSVs with pandas' inferred dtypes, no explicit schema | Faster to write the first import script | Silent ID/precision corruption, NaN propagation into scoring defaults (Pitfall 6) | Only for a disposable local dev seed, never for the dataset that demo/production will run against |
| Support only one legacy auth model and silently drop the others | Fastest path to a working demo login | Breaks any existing Supabase-authenticated frontend users; may resurrect an unauthenticated-by-default pattern if the decision isn't explicit | Acceptable only if explicitly decided and documented as "Supabase users will be asked to re-register," not as an accidental side effect |
| Leave the ported scoring code's defensive `if column not in df.columns` fallbacks unaudited | Faster port, fewer decisions | Import/mapping bugs become invisible instead of loud (Pitfall 6) | Acceptable to leave the code structurally as-is; not acceptable to skip the audit of which branches are firing |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|------------------|--------------------|
| MongoDB → Postgres (via CSV or direct dump) | Assuming MongoDB's schema-less/optional fields map 1:1 to Postgres NOT NULL columns; assuming "required: true" in Mongoose meant the data was actually always present | Audit real field-presence rates in the actual data before defining Postgres NOT NULL/required constraints; make fields nullable with sensible defaults unless presence is empirically verified |
| CSV import → Django ORM | Using naive `for row in reader: Model.objects.create(...)` for 41K+ rows — extremely slow, and each row failure aborts without a report | Use `bulk_create`/`bulk_update` in batches with `ignore_conflicts`/explicit error collection, and produce a per-batch success/failure report |
| Supabase Auth → Django | Trusting a Supabase-issued JWT without verifying its signature against Supabase's actual signing key/JWKS | Verify signature and claims properly (issuer, audience, expiry) server-side; don't just decode-and-trust |
| pandas scoring engine → Django ORM | Passing Django QuerySets directly into pandas operations expecting a certain column dtype/shape (e.g., via `django-pandas`'s `read_frame`) without confirming the resulting DataFrame's dtypes match what the scoring functions expect | Explicitly cast/validate DataFrame dtypes immediately after `read_frame()`/query conversion, before calling into ported scoring functions |
| pixel-perfect-clone-60729 frontend ↔ new Django API (future, out of scope here but shapes contracts now) | Designing Django API responses solely against Supabase's existing shape without checking what `impact_model_v4.1.py`'s scoring output actually looks like structurally (component breakdowns, not just a single number) | Design the score endpoint response shape around what the ported model can actually produce (including component breakdowns already supported via `return_components=True`), not just the old Supabase `attributes jsonb` shape |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Recomputing per-request pandas DataFrames from the full player table on every scoring call | Endpoint latency scales with total dataset size, not requested page size | Precompute scores at import/update time; cache position/league baseline aggregates | Noticeable already at dozens of concurrent requests against 41K rows; severe past a few hundred |
| Unbounded/unpaginated list endpoints (already flagged in `CONCERNS.md` for the legacy Node API) | Large JSON payloads, slow serialization, memory spikes | Enforce pagination (limit/offset or cursor) on every list endpoint from the start | Breaks as soon as a client requests the full player list without filters, e.g., first frontend integration test |
| N+1 queries from serializer-level related lookups (Pitfall 4) | Query count scales linearly with row count | `select_related`/`prefetch_related` + `assertNumQueries` tests | Already problematic at realistic page sizes (20-50 rows with several relations each) |
| Loading entire CSVs into memory at once during import | Memory spikes during import (25MB Players.csv is survivable, but combined with transfer CSV and any joins done in-process it adds up) | Chunked `read_csv(chunksize=...)` or streaming import, or a one-time script that's acceptable to be memory-heavy if run outside the request cycle | Only becomes urgent if the import needs to run repeatedly/on a constrained host; for a one-time migration script on a dev machine it's a lower priority than the other traps here |
| Group-by/aggregate operations for position/league baselines recomputed inline inside per-row scoring loops | Scoring a full player list becomes O(n × groups) instead of O(n) | Compute baseline aggregates once per scoring run (already how the original pandas script is structured — preserve that, don't accidentally move it inside a per-row loop during the port) | Becomes visible once scoring more than a handful of players at once |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Porting the "disabled but present" API-key middleware pattern into Django, intending to re-enable "later" | Repeats the exact current vulnerability (`CONCERNS.md`: "Everything gets through") — an unauthenticated production API | Don't scaffold disabled security checks at all; if a check isn't ready, don't write the code path that defaults to allow |
| Inconsistent `permission_classes`/auth enforcement across endpoints (some protected, some not) | Data leakage on unprotected endpoints, inconsistent with the rest of the API's security posture | Set a global `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` in DRF settings and require explicit opt-out (e.g., `AllowAny`) per view, so the default is secure, not the exception |
| Trusting client-supplied role/user-type fields (e.g., a JWT claim or request body field claiming "admin") without server-side verification against the canonical role store | Privilege escalation | Always resolve role from the verified, server-side user record, never from a client-controlled claim without cross-checking |
| No input validation on search/filter query parameters (already flagged generically in `CONCERNS.md` for the legacy Node API) feeding into pandas filtering or raw SQL-adjacent ORM `.extra()`/raw queries | Injection risk, unexpected DataFrame filter behavior on malformed input | Use DRF serializers/validators for all query params; never build raw SQL or `eval`-style pandas query strings from unsanitized user input |

## "Looks Done But Isn't" Checklist

- [ ] **Scoring engine port:** Endpoint returns a plausible-looking number — verify it was diffed against the original pandas script's output for a representative sample across all position groups, not just spot-checked once.
- [ ] **Data migration:** Postgres row counts match source row counts, and a documented, reviewed field-mapping exists — verify by comparing `SELECT COUNT(*)` against source CSV/Mongo row counts and checking the import report for skip/failure counts, not just "the script ran without crashing."
- [ ] **Auth:** Login works for a demo user — verify a role/permission matrix test exists covering every protected endpoint × every role, and that no endpoint silently allows unauthenticated access.
- [ ] **List/search endpoints:** Returns correct data for a small test set — verify query count stays constant (not linear) as result-set size grows, and that pagination is enforced.
- [ ] **CSV import:** Import script completes — verify explicit dtype handling was used (not pandas type inference) for identifier and monetary fields, and that a data-quality/null report was generated and reviewed, not just eyeballed.
- [ ] **Field mapping:** Column names "match" — verify against the specific known mismatches list (Team/Team_within_selected_timeframe, Market_value/"Market Value", Minutes variants, Position variants, attributes-as-fields-vs-jsonb) one by one, not assumed resolved because import didn't error.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|-----------------|------------------|
| Scoring port shipped without parity testing, drift discovered later | MEDIUM | Freeze the current port, generate the reference snapshot from the original script retroactively, diff function-by-function, patch drift, re-run parity suite before re-shipping |
| Silent CSV import data loss discovered post-migration | MEDIUM-HIGH | Re-run import from source CSVs with explicit dtypes and validation into a staging schema, diff staging vs live Postgres, reconcile/backfill affected rows; do not patch live data ad hoc without a diff first |
| Auth reconciliation gaps (unprotected endpoint) found in review/audit | LOW-MEDIUM | Set global `DEFAULT_PERMISSION_CLASSES` immediately as a stop-gap, then build the permission matrix test to find and fix remaining gaps systematically |
| N+1 query patterns found under load | LOW | Add `select_related`/`prefetch_related` to the offending `get_queryset()`, add regression test with `assertNumQueries`, no data changes needed — cheapest recovery on this list |
| Synchronous heavy pandas computation causing timeouts under concurrent demo load | MEDIUM | Move computation to precompute-at-import or background task without changing the scoring logic itself (isolate the fix to the request/response boundary, not the model) |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|--------------------|----------------|
| Port-by-rewrite drift (P1) | Scoring engine port phase | Snapshot of original script's output exists and is checked into the repo/artifacts before port code is written |
| No numerical parity testing (P2) | Scoring engine port phase | Parity test suite exists, covers all position groups + edge cases, run in CI or at minimum before merge |
| Synchronous heavy compute in request cycle (P3) | Architecture/API design phase + scoring integration phase | Load test against realistic concurrency shows constant, not linear, response time for score endpoints |
| N+1 queries from per-row serializers (P4) | API/endpoint-building phase | `assertNumQueries` tests exist for every list endpoint with an explicit query budget |
| Silent CSV/Mongo import data loss (P5) | Data migration phase | Import report (attempted/succeeded/skipped+reason) generated and reviewed; Postgres row counts reconciled against source |
| Field-naming mismatch surfacing only at scoring runtime (P6) | Data migration phase → scoring integration phase (joint) | Explicit FIELD_MAPPING doc resolved against known mismatches list; smoke test confirms defensive fallback branches aren't silently firing on real data |
| Auth reconciliation without a transition plan (P7) | Auth phase (early) | Permission matrix test (role × endpoint) passes; no endpoint relies on default-allow; decision recorded for legacy Supabase/JWT user handling |
| Breadth-over-depth scope creep under deadline (P8) | Roadmap structuring (all phases) | Each phase's "done" definition includes its correctness/verification step, not just "endpoint exists" |

## Sources

- `.planning/codebase/CONCERNS.md` — project-specific findings: disabled API-key middleware, inconsistent auth enforcement, field-naming mismatches (Team/Team_within_selected_timeframe, Market_value, Minutes, Position, attributes-as-fields-vs-jsonb), unvalidated CSV import, monolithic files, no pagination, no input validation (HIGH confidence — direct codebase evidence)
- `.planning/codebase/TESTING.md` — confirms zero test coverage across all sub-projects, including the 15,700-line scoring engine, and enumerates the specific functions most in need of characterization tests (HIGH confidence — direct codebase evidence)
- [Async Workers in Django: How to Avoid 504 Timeouts with Celery & Redis (Medium, 2026)](https://medium.com/@ahmetdeger/async-workers-in-django-how-to-avoid-504-timeouts-with-celery-redis-cae55548805d) — MEDIUM confidence, corroborates well-known Django sync-worker-blocking behavior
- [Django asynchronous support — official docs](https://docs.djangoproject.com/en/5.2/topics/async/) — HIGH confidence, official source on sync/async boundaries
- [Optimizing Django REST Framework — fix the N+1 problem](https://ahmadsalah.hashnode.dev/optimizing-django-rest-framework-fix-the-n1-problem) and [DRF serializer relations docs](https://www.django-rest-framework.org/api-guide/relations/) — MEDIUM/HIGH confidence, standard DRF N+1 guidance
- [10 Pandas Casting Rules That Avoid Silent Precision Loss (Medium)](https://medium.com/@sparknp1/10-pandas-casting-rules-that-avoid-silent-precision-loss-7ba7917c8f8f) and [pandas GitHub issue on read_csv data loss](https://github.com/pandas-dev/pandas/issues/5697) — MEDIUM confidence, corroborates well-documented pandas dtype-inference/coercion pitfalls
- [Supabase JWT Signing Keys / JWKS migration docs](https://supabase.com/docs/guides/auth/signing-keys) — HIGH confidence, official Supabase source on JWT verification requirements
- General pandas float64/IEEE-754 rounding behavior — well-established, widely-documented numerical computing fact (HIGH confidence, standard knowledge, not dependent on a single source)

---
*Pitfalls research for: Django backend porting an untested pandas scoring engine + multi-source data migration + auth reconciliation*
*Researched: 2026-07-20*
