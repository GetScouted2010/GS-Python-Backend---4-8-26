# Phase 10: AI Grounded Report Generation - Research

**Researched:** 2026-07-25
**Domain:** LLM narrative generation with programmatic grounding validation (Django + Anthropic SDK)
**Confidence:** HIGH

## Summary

Phase 10 adds two new LLM-backed endpoints — a player scouting report and club insights — on top of infrastructure Phase 9 already proved out (provider-agnostic interface, factory dispatch, autouse test-safety net, `django-environ` config pattern) and Phase 6 already made fast (`get_summary()` sub-second on the own-club path). Nothing here requires new scoring logic, new Player/Club fields, or new infra (no cache, no persistence, no new Django app). It is entirely: (1) assemble a grounding dict from data that already exists, (2) call Anthropic for free-form prose with that dict in the prompt, (3) programmatically verify every number in the prose traces back to the dict, (4) return clean JSON or a clean error.

All 7 items flagged in CONTEXT.md were verified directly against the real code (not assumed): `Player.position/age/market_value/contract_expires/club` field types are confirmed; `get_summary()`'s exact signature/return shape (including every sub-dict's real keys) is documented below; Phase 9's `NLQueryParser`/`AnthropicNLQueryParser`/`get_nl_query_parser()` triad is read in full and is mirrorable almost verbatim; the Anthropic SDK (0.120.0, confirmed the current PyPI latest) supports plain non-tool-use `messages.create()` trivially, returning `TextBlock(type="text", text=...)` content blocks; `ClubDetailSerializer.get_transfer_aggregates`'s exact shape is captured; and — critically — the autouse Anthropic-blocking test fixture in `players/tests/conftest.py` is **directory-scoped and will NOT automatically cover `clubs/tests/`** if club-insights code+tests land there, which they should (see Architecture below). No existing money/percentage-formatting helper exists anywhere in the codebase (grep confirmed) — the grounding validator's numeric parser must be built from scratch.

**Primary recommendation:** Add a new `players/ai/report_generator.py` (+`anthropic_report_generator.py`, +`report_factory.py`, +`grounding.py`) mirroring Phase 9's file-per-concern split exactly. Player scouting-report orchestration lives in `players/services.py` + `players/views.py`. Club-insights orchestration (including the lightweight position-needs ORM aggregation) lives in NEW `clubs/services.py` + `clubs/views.py`, importing the shared `players.ai.*` factory/validator — mirroring the exact cross-app-import precedent `clubs/serializers.py` already set by importing `players.serializers.PlayerListSerializer`. Port a duplicate `_block_real_anthropic_calls` autouse fixture into `clubs/tests/conftest.py` (matching the project's own established "per-app duplication over cross-app import" convention, e.g. `ClubExportView`'s duplicated `Echo` class).

## User Constraints

### Locked Decisions

1. **Cross-phase Position Needs gap** — Phase 10 computes its own lightweight, internal-only position-needs aggregation (squad depth/position, avg age/position, contracts expiring within 12 months/position) directly from `Player.position/age/contract_expires/club` — NOT Phase 11's full canonical feature. No public endpoint, no strong/weak/at-risk labels.
2. **`ReportGenerator` interface mirroring Phase 9's `NLQueryParser`** — one abstract method, e.g. `generate(grounding: dict, report_type: str) -> GeneratedReport`, dispatched via `get_report_generator()` reading the same `LLM_PROVIDER` setting. Concrete Anthropic implementation uses its own configurable model, `ANTHROPIC_REPORT_MODEL` (stronger tier than Phase 9's cheap extraction model).
3. **Anthropic SDK plain text-generation** — report generation needs free-form narrative, not forced tool-use extraction; use a plain `client.messages.create()` call without `tool_choice`.
4. **Grounding validator** — extract numeric tokens from the LLM's narrative output and cross-check each against the grounding dict's numeric values (within reasonable formatting/rounding tolerance); reject/regenerate once if a number fails to trace back.
5. **Endpoint shape** — `POST /api/players/{id}/scouting-report/` (body `{"club_id": "..."}`) and `POST /api/clubs/{id}/insights/`. Both return structured JSON: narrative broken into named sections + the exact grounding dict used (transparency/traceability). Always regenerate, never cached/persisted.
6. **No narrative fallback on failure** — LLM call fails, or the post-generation grounding check fails twice → clean error response (e.g. 503), never a template-only or partially-fabricated report. Phase 9's 3-tier degradation pattern does NOT transfer here.
7. **Test-safety pattern** — must work within (and, if club-insights code lives in `clubs/`, extend) the existing autouse Anthropic-blocking pytest fixture.

### Claude's Discretion

- Exact prompt wording and section ordering within each report type.
- Exact numeric-tolerance rules for the grounding validator (e.g. rounding "€2.3M" from raw `2340000` should pass; a number with no match anywhere in grounding data should fail).
- Whether the validator retries generation once on failure or fails immediately — retry-once is the natural default; exact retry/backoff tuning is left open.
- Whether `RecentActivity` gets a new `activity_type` for report requests — not required by AI-03/AI-04's literal wording; may be added if low-cost, not a locked requirement.

### Deferred Ideas (OUT OF SCOPE)

- Full canonical Position Needs analysis (strong/weak/at-risk classification, dedicated user-facing endpoint) — Phase 11's `PLAN-01`.
- Report caching/regeneration with data-version-aware invalidation — `REL-01`, v2, explicitly deferred.
- A new `RecentActivity` type for report requests — planner's discretion, not locked.
- Squad simulation consuming these reports — Phase 11's `PLAN-03`.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AI-03 | User can request an AI-generated scouting report for a player (strengths, weaknesses, tactical fit, financial fit, best use case), strictly grounded in already-computed scores/stats | `get_summary(player_id, club_id)`'s exact return shape documented below is the complete grounding source; endpoint/service placement in `players/views.py`+`players/services.py` mirrors `PlayerSearchView`'s existing AI-endpoint pattern |
| AI-04 | User can request AI-generated club insights (recruitment gaps, over-aged positions, financial constraints), grounded in Position Needs and Transfer Behaviour aggregates | New lightweight ORM position-needs aggregation (documented below) + `ClubDetailSerializer.get_transfer_aggregates`'s exact shape (documented below) together form the grounding source; new `clubs/services.py`+`clubs/views.py` mirrors `ClubExportView`'s existing pattern of reusing `ClubDetailSerializer`'s data |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `anthropic` | `0.120.0` (already pinned `>=0.120,<0.130` in `requirements/base.txt`, installed in `.venv`) | LLM narrative generation via `client.messages.create()` | Already the project's sole LLM SDK (Phase 9); no new dependency needed. Confirmed 0.120.0 is still the current latest release on PyPI as of this research date. |
| Django REST Framework `APIView` | (already installed) | New endpoints | Matches `PlayerSearchView`/`ClubExportView`'s existing `APIView` (not `generics.*`) pattern for non-CRUD, service-orchestrating endpoints |

No new packages need to be added to `requirements/base.txt` — everything required (regex numeric parsing, ORM aggregation, Anthropic calls) is either stdlib or already installed.

**Version verification:**
```bash
$ pip index versions anthropic
anthropic (0.120.0)   # latest — matches installed .venv version and requirements pin
```

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| stdlib `re` | n/a | Grounding validator's numeric-token extraction from prose | No existing money/percentage formatter exists anywhere in the codebase (verified via grep across `scoring/`, `players/`, `clubs/`) — build the parser directly with `re`, matching Phase 9's `fallback.py` precedent of hand-rolled `re`-based extraction for exactly this kind of "parse loosely-structured text against a known vocabulary" problem |
| stdlib `math`/`decimal` | n/a | Tolerance comparison (relative % difference) between a parsed narrative number and a grounding-dict value | Simple relative-tolerance check, same spirit as `_parity_helpers.py`'s Phase 5 tolerance comparator (`abs 0.01`/`rel 0.1%`) — reuse that precedent's *shape*, not its code (different domain: scores vs. free-text money/percent tokens) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled regex numeric extraction | A general "extract numbers from text" NLP library (e.g. `word2number`, `text2num`) | Unnecessary dependency for a bounded problem (numbers already appear as digits in the LLM's own JSON-adjacent prose, not spelled out as English words); adds supply-chain surface for zero real benefit — the project's own `fallback.py` precedent already proves regex is sufficient for this class of problem |
| Post-hoc validator regenerating on failure | Forcing the LLM to cite grounding-dict keys inline (e.g. `[[rmm]]` placeholders the server then substitutes) | More "guaranteed correct" in theory, but a bigger prompt-engineering lift and a UX/prose-quality regression (stilted, template-like text) — the CONTEXT.md locked decision already explicitly chose free-form + post-validation over this |
| Plain `messages.create()` for narrative | Forced tool-use with a schema that has one `narrative_sections` string field per section | Tool-use forces valid JSON section boundaries "for free," but narrative prose is exactly the case Anthropic's own docs describe forced tool-use as unsuited for (it constrains content structure, not prose quality) — CONTEXT.md's own locked decision (#3) already resolved this in favor of plain text generation. Consider structuring the *sections* via a lightweight sentinel/heading convention in the prompt instead (e.g. `## Strengths` headers) parsed server-side with simple string splitting — cheaper than a second tool-use round-trip. |

**Installation:** None required — `anthropic` is already installed and pinned.

## Architecture Patterns

### Recommended Project Structure

```
get-scouted-be/
├── players/
│   ├── ai/
│   │   ├── base.py                    # existing — NLQueryParser (untouched)
│   │   ├── anthropic_parser.py        # existing — AnthropicNLQueryParser (untouched)
│   │   ├── factory.py                 # existing — get_nl_query_parser() (untouched)
│   │   ├── fallback.py                # existing — keyword_extract() (untouched)
│   │   ├── report_generator.py        # NEW — ReportGenerator ABC, GeneratedReport dataclass, ReportGeneratorError
│   │   ├── anthropic_report_generator.py  # NEW — AnthropicReportGenerator (plain messages.create())
│   │   ├── report_factory.py          # NEW — get_report_generator(), dispatches on settings.LLM_PROVIDER
│   │   └── grounding.py               # NEW — shared numeric-extraction + validation (used by BOTH player + club reports)
│   ├── services.py                    # add generate_scouting_report(player_id, club_id)
│   ├── views.py                       # add PlayerScoutingReportView (POST)
│   ├── urls.py                        # add scouting-report/ route
│   └── tests/
│       ├── conftest.py                # existing autouse Anthropic guard — covers these new tests, no change needed
│       ├── test_ai_report_generator.py    # NEW
│       ├── test_ai_anthropic_report_generator.py  # NEW
│       ├── test_ai_report_factory.py      # NEW
│       ├── test_ai_grounding.py           # NEW
│       └── test_scouting_report_view.py   # NEW
├── clubs/
│   ├── services.py                    # NEW — position_needs_aggregate(club), generate_club_insights(club_id)
│   ├── views.py                       # add ClubInsightsView (POST)
│   ├── urls.py                        # add insights/ route
│   └── tests/
│       ├── conftest.py                # EXTEND — port a duplicate _block_real_anthropic_calls autouse fixture here
│       └── test_ai_club_insights.py   # NEW
└── config/settings/base.py            # add ANTHROPIC_REPORT_MODEL alongside the existing 3 LLM settings
```

**Why club insights lives in `clubs/`, not `players/ai/`:** club insights are club-scoped data (position-needs aggregation reads `club.players.all()`, transfer aggregates read `Transfer.objects.filter(club=club)`) — keeping the orchestration in `clubs/services.py` matches the existing app-boundary convention (`players/services.py` owns player-scoped orchestration, e.g. `search_players`; `clubs/` has no `services.py` yet, but `ClubDetailView`/`ClubExportView` already do inline club-scoped aggregation work directly in `clubs/views.py` — a new `clubs/services.py` is the natural next step, not a deviation). The *shared* LLM plumbing (`ReportGenerator` interface, Anthropic implementation, factory, grounding validator) stays in `players/ai/` since that's where Phase 9 already established the project's one-and-only LLM integration layer — `clubs/services.py` imports from it, exactly mirroring the precedent already set by `clubs/serializers.py` importing `players.serializers.PlayerListSerializer`.

### Pattern 1: `ReportGenerator` interface (mirrors `NLQueryParser` exactly)

**What:** One-method ABC + a result dataclass + a dedicated exception class, following Phase 9's `players/ai/base.py` shape verbatim.
**When to use:** Any new LLM "task" this project adds (Phase 10's second one, after Phase 9's extraction task).
**Example (new `players/ai/report_generator.py`):**
```python
# Source: mirrors get-scouted-be/players/ai/base.py (NLQueryParser/ParsedQuery/NLQueryParserError)
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class GeneratedReport:
    """narrative: dict[str, str] keyed by section name (e.g. "strengths",
    "weaknesses", "tactical_fit", "financial_fit", "best_use_case" for a
    player report; "recruitment_gaps", "over_aged_positions",
    "financial_constraints" for a club-insights report). grounding echoes
    back the exact dict used to build the prompt, per the locked endpoint
    contract (transparency/traceability)."""

    narrative: dict = field(default_factory=dict)
    grounding: dict = field(default_factory=dict)


class ReportGeneratorError(Exception):
    """Raised by a concrete generator when the provider call fails, returns
    unusable output, or the grounding validator rejects the result twice.
    The calling view catches this to return the locked-decision clean error
    response (no fallback narrative, ever)."""


class ReportGenerator(ABC):
    """Provider-agnostic narrative-generation interface (AI-03/AI-04),
    parallel in shape to NLQueryParser. Concrete implementations selected by
    players.ai.report_factory.get_report_generator() reading
    settings.LLM_PROVIDER -- calling code never imports a concrete class."""

    @abstractmethod
    def generate(self, grounding: dict, report_type: str) -> GeneratedReport:
        """Write narrative prose strictly grounded in `grounding`'s numbers.
        Raise ReportGeneratorError on provider failure / malformed output."""
```

### Pattern 2: Plain (non-tool-use) Anthropic call for free-form narrative

**What:** `client.messages.create()` with no `tools`/`tool_choice` — the response's `content` list contains `TextBlock(type="text", text=...)` objects instead of `tool_use` blocks.
**When to use:** Whenever the desired output is prose, not schema-constrained structured data (Phase 9 used forced tool-use because it needed the opposite).
**Example:**
```python
# Source: verified directly against the installed anthropic==0.120.0 SDK
# (anthropic.types.TextBlock; response.content is List[TextBlock] when no
# tools/tool_choice are passed)
response = client.messages.create(
    model=settings.ANTHROPIC_REPORT_MODEL,
    max_tokens=1500,
    messages=[{"role": "user", "content": prompt}],
)
text = "".join(block.text for block in response.content if block.type == "text")
```
Constructor/DI seam should mirror `AnthropicNLQueryParser` exactly: `__init__(self, client=None)`, real client constructed lazily inside `generate()`, never in `__init__` — this is what lets tests inject a fake client without tripping the autouse guard.

### Pattern 3: Section-delimited prompting for structured narrative output

**What:** Instruct the LLM to emit clearly-delimited section headers (e.g. `## Strengths`) in its plain-text response; parse server-side via simple string splitting on the known header set, rather than a second tool-use round trip.
**When to use:** Any time free-form prose needs to map onto the locked endpoint contract's named sections (strengths/weaknesses/tactical_fit/financial_fit/best_use_case for players; recruitment_gaps/over_aged_positions/financial_constraints for clubs).
**Example:**
```python
SECTION_HEADERS = ["Strengths", "Weaknesses", "Tactical Fit", "Financial Fit", "Best Use Case"]
# Prompt instructs: "Structure your response with exactly these ## headers, in this order: ..."
# Parse: split text on r"^##\s+(Strengths|Weaknesses|...)\s*$" with re.MULTILINE
```
Treat parse failure (missing/misnamed headers) as a `ReportGeneratorError` — same "never fabricate, fail clean" posture as the grounding check.

### Pattern 4: Lightweight club-scoped position-needs ORM aggregation

**What:** A plain Django ORM `.values().annotate()` grouped query over `club.players.all()`, computed fresh per request — no caching, no denormalized fields, no pandas.
**When to use:** Building the internal-only position-needs grounding data for club insights (locked decision #1).
**Why plain ORM, not pandas, and confirmed against real scale:** Phase 6's SCORE-07 precedent (`06-scoring-performance-caching-layer` STATE.md entries) established "no full-dataset pandas operations inside a request cycle" specifically because the *scoring* population is 41,708 players wide. This aggregation is different in kind — it is scoped to exactly one club's current squad via the confirmed `related_name="players"` FK (`Player.club` → `SET_NULL`, `related_name="players"`, verified in `players/models.py`). The real population is 41,708 players across 1,060 clubs (≈39 players/club on average, per-club squads bounded well under a few hundred rows even in worst case) — a single grouped ORM query over a few dozen rows is sub-millisecond, no different in cost profile from `ClubDetailSerializer.get_transfer_aggregates`'s existing per-club `Avg`/`Sum`/`Count` aggregates, which already ship in production with no caching layer. Plain ORM aggregation is confirmed correct and fast; no pandas, no new caching infra needed.
**Example:**
```python
# Source: pattern mirrors clubs/serializers.py::ClubDetailSerializer.get_transfer_aggregates
# (Avg/Count over a club-scoped queryset), applied to Player instead of Transfer.
from datetime import date, timedelta
from django.db.models import Avg, Count, Q

def position_needs_aggregate(club) -> dict:
    cutoff = date.today() + timedelta(days=365)
    rows = (
        club.players
        .exclude(position__isnull=True)
        .values("position")
        .annotate(
            squad_depth=Count("id"),
            avg_age=Avg("age"),
            expiring_within_12mo=Count("id", filter=Q(contract_expires__lte=cutoff, contract_expires__isnull=False)),
        )
        .order_by("position")
    )
    return {row["position"]: {
        "squad_depth": row["squad_depth"],
        "avg_age": round(row["avg_age"], 1) if row["avg_age"] is not None else None,
        "contracts_expiring_within_12mo": row["expiring_within_12mo"],
    } for row in rows}
```
Note: `contract_expires` is a `DateField(null=True, blank=True)` (confirmed) — the `contract_expires__isnull=False` guard in the `Count(..., filter=Q(...))` is required so NULL contract dates aren't miscounted as "expiring."

### Pattern 5: Grounding validator (numeric extraction + tolerance match)

**What:** Extract every numeric token from the LLM's narrative text, normalize each to a raw scale-agnostic float, and confirm at least one value in the flattened grounding dict matches within tolerance.
**When to use:** After every `generate()` call, before returning a report to the client.
**Concrete regex/parsing strategy (no existing formatter to reuse — grep-confirmed none exists in `scoring/`, `players/`, or `clubs/`):**
```python
# Source: new code — no existing money/percentage formatting helper found
# anywhere in the codebase (grep: def format_ / money / humanize -> zero hits
# outside unrelated matches in tfm_model.py's characterization module).
import re

# Matches: "€2.3M", "$5,000,000", "23", "7.4/10", "15%", "2.34 million", "23yo"
NUMERIC_TOKEN_RE = re.compile(
    r"""
    [€$]?\s*
    (?P<num>\d[\d,]*(?:\.\d+)?)
    \s*
    (?P<suffix>million|mil|m\b|thousand|k\b|%|percent)?
    """,
    re.IGNORECASE | re.VERBOSE,
)

def _normalize(num_str: str, suffix: str | None) -> float:
    value = float(num_str.replace(",", ""))
    suffix = (suffix or "").lower()
    if suffix in ("million", "mil", "m"):
        return value * 1_000_000
    if suffix in ("thousand", "k"):
        return value * 1_000
    return value  # percentages/plain numbers/ratios pass through as-is

def extract_numeric_tokens(text: str) -> list[float]:
    return [_normalize(m.group("num"), m.group("suffix")) for m in NUMERIC_TOKEN_RE.finditer(text)]

def flatten_grounding_values(grounding: dict) -> list[float]:
    """Recursively walk the grounding dict, collecting every int/float leaf
    (skip strings/None/bools) -- get_summary()'s and the club-insights
    dict's nested breakdown/component structures require recursion, not a
    flat .values() call."""
    values = []
    def _walk(node):
        if isinstance(node, dict):
            for v in node.values():
                _walk(v)
        elif isinstance(node, (list, tuple)):
            for v in node:
                _walk(v)
        elif isinstance(node, (int, float)) and not isinstance(node, bool):
            values.append(float(node))
    _walk(grounding)
    return values

def is_grounded(value: float, grounding_values: list[float], rel_tol: float = 0.05, abs_tol: float = 0.5) -> bool:
    """Tolerant match: handles LLM rounding ("€2.3M" from raw 2,340,000;
    "7.4/10" from raw 7.42; "15%" from a raw 0.1523 fraction OR a raw 15.23
    already-percent value -- check both scales). rel_tol=5% covers realistic
    prose rounding; abs_tol handles near-zero values where relative tolerance
    is meaningless."""
    candidates = {value, value / 100, value * 100}  # handle fraction<->percent scale mismatches
    for gv in grounding_values:
        for cand in candidates:
            if abs(cand - gv) <= max(abs_tol, rel_tol * max(abs(gv), 1)):
                return True
    return False

def validate_grounding(narrative_text: str, grounding: dict) -> list[float]:
    """Returns the list of ungrounded numbers found (empty list = fully
    grounded). Small, deliberately excludable numbers (years like "2026",
    single-digit list markers) are a known tolerance gap -- see Open
    Questions."""
    grounding_values = flatten_grounding_values(grounding)
    tokens = extract_numeric_tokens(narrative_text)
    return [t for t in tokens if not is_grounded(t, grounding_values)]
```

### Anti-Patterns to Avoid

- **Trusting prompt instructions alone for grounding:** CONTEXT.md already locked this — "only use these numbers" in the prompt is well-known to not fully prevent hallucination. The programmatic post-generation check is mandatory, not optional polish.
- **Reconstructing the scoring population inside the report-generation path:** `get_summary()` already does the RMM-first reconstruction exactly once and returns everything needed — do not call individual `rmm.get_rmm()`/`compatibility.get_compatibility()`/etc. separately, which would multiply reconstruction cost (the exact anti-pattern `get_summary()`'s own docstring warns against).
- **Constructing `anthropic.Anthropic()` in `__init__`:** breaks the DI/test-safety seam every existing AI class in this codebase uses. Always construct lazily inside the method that needs it, accepting an injected `client` first.
- **Assuming `players/tests/conftest.py`'s autouse fixture protects new test files anywhere in the repo:** it does not — pytest autouse fixtures only apply to the conftest's own directory and descendants. `clubs/tests/` is a sibling, not a descendant, of `players/tests/`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Grounding data assembly for player reports | A new player-summary query | `scoring.services.summary.get_summary(player_id, club_id)` | Already returns everything a scouting report needs (RMM/CS/TFM/TP + breakdowns) in one sub-second call; re-deriving any of it risks silently drifting from the already-verified (Phase 5 parity-tested) scoring logic |
| Transfer-behaviour grounding data for club insights | A new transfer aggregation query | `ClubDetailSerializer.get_transfer_aggregates` (or its exact same query logic, reused) | Already correctly sourced from `Transfer.market_value_at_transfer` (never the free-text `Transfer.fee`) — re-deriving risks reintroducing the exact bug class Phase 7 explicitly avoided |
| LLM provider swapping | A second bespoke Anthropic call site with its own settings/error handling | The `ReportGenerator`/`get_report_generator()` pair, mirroring `NLQueryParser`/`get_nl_query_parser()` | AI-05 already established this is the project's one LLM-integration pattern; a second, differently-shaped LLM integration would fragment the codebase's one proven pattern for no benefit |
| Numeric prose parsing | A generic NLP number-extraction library | Hand-rolled `re`, per Pattern 5 above | The problem is bounded (digits + a small fixed suffix vocabulary: M/K/%/million/thousand) — matches the exact scope and precedent of `players/ai/fallback.py`'s existing hand-rolled money-parsing regex (`_MONEY_RE`) |

**Key insight:** Every "don't hand-roll" item above already has a working, tested equivalent somewhere in this codebase from a prior phase — Phase 10's job is composition (call these things, wrap them in an LLM prompt, validate the output), not new computation.

## Common Pitfalls

### Pitfall 1: Trusting `get_summary()`'s Http404 semantics for a missing club

**What goes wrong:** `get_summary(player_id, club_id)` raises `Http404` if `club_id` is unresolvable (via `resolve_club_name`) — but the ROADMAP endpoint contract requires `club_id` in the request body. If `club_id` is omitted or a player has no club, calling `get_summary` directly (rather than branching first, as `PlayerDetailView.get()` already does) will raise a misleading 404 instead of a clean, honest response.
**Why it happens:** `resolve_club_name(None)` internally does a `get_object_or_404` lookup.
**How to avoid:** Mirror `PlayerDetailView.get()`'s existing branch: if `club_id` is missing, either default to the player's own current club (`player.club_id`) — consistent with `PlayerDetailView`'s existing default — or return a clean 400 ("club_id required for a club-relative scouting report") per the endpoint's documented body contract. Do not let `get_summary`'s `Http404` be the only signal.
**Warning signs:** A scouting-report test for "player has no club" returns 404 instead of a clear validation error or a partial (RMM-only) report.

### Pitfall 2: Autouse test-safety fixture silently NOT applying to new test files

**What goes wrong:** A `clubs/tests/test_ai_club_insights.py` test accidentally constructs a real `anthropic.Anthropic()` client (e.g. forgetting the `client=` DI seam) and the autouse guard in `players/tests/conftest.py` does not intercept it, because pytest conftest fixture scoping is directory-tree-based and `clubs/tests/` is a sibling directory.
**Why it happens:** Directory-scoped conftest fixture discovery is a pytest structural fact, not a bug — but it is easy to assume a repo-wide safety net exists when it does not (confirmed: `clubs/tests/conftest.py` currently has no such fixture).
**How to avoid:** Explicitly port a duplicate `_block_real_anthropic_calls` autouse fixture into `clubs/tests/conftest.py` if any club-insights code/tests land in `clubs/` — this exact "duplicate per-app rather than cross-app import" tradeoff is already the established convention in this codebase (`ClubExportView`'s duplicated `Echo` streaming-buffer class, explicitly noted as "per-app duplication over cross-app import, per plan" in `clubs/views.py`).
**Warning signs:** A club-insights test passes locally with `ANTHROPIC_API_KEY` unset (silently succeeds because the key is empty, not because a guard blocked it) but would fail loudly (or worse, fire a real billed call) once a real key is configured in CI/prod-adjacent environments.

### Pitfall 3: Grounding validator false-negatives on innocuous numbers

**What goes wrong:** The narrative naturally contains numbers that are NOT scores/stats but also aren't hallucinations — e.g. "5 strengths", "a top-3 fit", a year like "2026" (contract expiry year mentioned in prose), or numbered list markers ("1.", "2."). A naive validator flags these as ungrounded and triggers an unnecessary regeneration/failure.
**Why it happens:** The validator can't distinguish "a number referring to real data" from "a number that's just part of English prose" purely from regex.
**How to avoid:** This is a genuine open design tradeoff (see Open Questions) — mitigate by (a) prompting the LLM to avoid incidental numbers in list/ranking language where possible, (b) whitelisting a small set of structurally-safe patterns (bare list-item markers like `^\d+\.\s`, calendar years matching `\b(19|20)\d{2}\b` when they plausibly correspond to a `contract_expires` year already in the grounding dict) before flagging, and (c) treating occasional false-positive retries as an acceptable cost for a low-volume, on-demand endpoint (matches CONTEXT.md's own stated cost/quality tradeoff for this phase).
**Warning signs:** High regeneration/failure rate on manual testing despite narratives that are clearly well-grounded to a human reader.

### Pitfall 4: Financial Fit's `predicted_fee` scale confusion leaking into the validator

**What goes wrong:** `financial_fit_from_population`'s `predicted_fee` is already unwrapped to money-scale (`np.expm1(...)` applied) before it reaches `get_summary()`'s output — but if any new code path accidentally re-reads the raw TFM pipeline output for a report, the validator would need to match a wildly different (log-scale, ~13-17) number against a money-scale grounding dict and fail confusingly.
**Why it happens:** This exact log-scale bug class was flagged and fixed in Phase 3/4 (`financial_fit.py`'s own docstring calls it out as "the confirmed log-scale bug").
**How to avoid:** Only ever source financial grounding data through `get_summary()`'s `financial_fit` key (already money-scale, confirmed) — never call `get_tfm_pipeline().predict()` directly for report generation.
**Warning signs:** A financial-fit narrative number in the €10-20 range instead of realistic transfer-fee magnitudes.

## Code Examples

Verified patterns from official sources / direct code inspection:

### `get_summary()`'s exact return shape (the player-report grounding source)

```python
# Source: get-scouted-be/scoring/services/summary.py + rmm.py/compatibility.py/
# transfer_probability.py/financial_fit.py (read in full, 2026-07-25)
{
    "rmm": {
        "rmm": float,                          # or null_with_reason envelope: {"rmm": None, "reason": "insufficient_player_data"}
        "positive": float | None,
        "negative": float | None,
        "components": {"<component name>": float, ...},  # from "Impact Comp - <name>" columns
        "reliability": str | None,             # categorical "Very Low"/"Low"/"Medium"/"High" -- NEVER numeric
    },
    "compatibility": {
        "compatibility_score": float,          # or null_with_reason envelope: {"compatibility_score": None, "reason": "club_style_data_unavailable"}
        "components": {
            "role_fit_score": float | None,
            "similarity_pct": None,            # ALWAYS None -- Phase 3 scope gap, no comparison pool
            "bonus": 100.0 | 70.0,
        },
    },
    "financial_fit": {
        "predicted_fee": float,                # money-scale (np.expm1 already applied)
        "market_value": float | None,
        "value_comparison": {"fee_diff": float | None, "ratio_market_to_predicted": float | None},
        "value_verdict": str | None,           # e.g. "Bargain"/"Fair Value"/"Overpay"
        "buying_club": str,
    },  # or null_with_reason envelope: {"predicted_fee": None, "reason": "no_transfer_features"|"no_club_context"}
    "transfer_probability": {
        "transfer_probability": float,         # rounded to 1 decimal, or null_with_reason envelope
        "components": {
            "<term>": {"raw": float | None, "weight": float, "contribution": float | None}
            for term in ("compatibility", "performance", "financial", "contract_fit")
        },
    },
}
```

### `ClubDetailSerializer.get_transfer_aggregates`'s exact return shape (club-insights grounding source, transfer half)

```python
# Source: get-scouted-be/clubs/serializers.py, read in full 2026-07-25
{
    "total_transfers": int,
    "arrivals": int,
    "departures": int,
    "avg_market_value_at_transfer": float | None,   # None on an empty queryset -- real null, not 0
    "total_market_value_at_transfer": int | None,
    "by_window": [{"window": str, "count": int}, ...],
}
```

### Anthropic plain-text generation call + text extraction

```python
# Source: verified directly against installed anthropic==0.120.0
# (anthropic.types.TextBlock: {citations, text: str, type: Literal["text"]})
response = client.messages.create(
    model=settings.ANTHROPIC_REPORT_MODEL,
    max_tokens=1500,
    messages=[{"role": "user", "content": prompt}],
)
narrative_text = "".join(
    block.text for block in response.content if getattr(block, "type", None) == "text"
)
```

### Config addition (mirrors the existing `ANTHROPIC_MODEL` pattern exactly)

```python
# Source: get-scouted-be/config/settings/base.py lines 174-185 (existing 3 settings, read in full)
# Add immediately after ANTHROPIC_MODEL:
ANTHROPIC_REPORT_MODEL = env("ANTHROPIC_REPORT_MODEL", default="claude-sonnet-5")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Anthropic `claude-haiku-4-5` (Phase 9's extraction model) | For Phase 10's report generation: a stronger-tier model, confirmed available in the installed 0.120.0 SDK's `ModelParam` Literal type as of this research date: `claude-sonnet-5`, `claude-opus-5`, `claude-sonnet-4-5`, `claude-opus-4-5`, among others | N/A — this is a model *choice* research finding, not a deprecation | `ANTHROPIC_REPORT_MODEL` should default to a general-purpose flagship-tier model (`claude-sonnet-5` is the reasonable default: stronger than `haiku-4-5` for narrative quality, cheaper than `opus-5` for an on-demand, not-per-search-volume endpoint) — **verify this string is still valid at actual build/execution time** the same way Phase 9's research flagged for `ANTHROPIC_MODEL`; the SDK's own `anthropic.types.model_param.ModelParam` Literal type is the cheapest live-verification method (no API key/network call needed) |

**Deprecated/outdated:** Nothing in this phase's domain is deprecated — this is new capability on stable, already-integrated infrastructure.

## Open Questions

1. **Exact numeric-tolerance rule for the grounding validator (explicitly Claude's Discretion per CONTEXT.md)**
   - What we know: rounding formats like "€2.3M" from a raw `2340000` must pass; a genuinely invented number must fail. A relative tolerance (~5%) plus a small absolute floor (for near-zero values) is a reasonable default, sketched in Pattern 5 above.
   - What's unclear: the exact tolerance percentage that best balances false-positive regenerations against real hallucination catches — this can only really be tuned empirically once real LLM output is observed during implementation/testing, not derivable from research alone.
   - Recommendation: implement with the sketched `rel_tol=0.05`/`abs_tol=0.5` defaults, make both easily adjustable constants, and have the phase's own test suite (with a mocked/injected fake client producing deliberately-hallucinated numbers) validate the rejection path works — tune the exact thresholds during implementation against real generated text, not before.

2. **Whether incidental non-data numbers (years, list markers, ordinals) need a validator whitelist**
   - What we know: a naive "every digit sequence must match a grounding value" check will false-positive on things like "2026" (if it happens to appear in prose for a reason unrelated to grounding) or "top 3".
   - What's unclear: how much this matters in practice depends on actual prompt design (a well-designed prompt largely avoids incidental numbers) — not knowable without a real generation sample.
   - Recommendation: start with the strict validator (Pattern 5), and prompt-engineer to minimize incidental numbers first (cheapest fix); add a narrow allowlist (calendar years, ordinal list markers) only if real testing during implementation shows it's actually needed. Document this as a known limitation either way.

3. **Retry-once semantics: same prompt or a corrective follow-up prompt?**
   - What we know: CONTEXT.md leaves "retry once" as the natural default but leaves exact tuning open.
   - What's unclear: whether a bare retry (identical prompt, hoping for a better sample) or a corrective retry (telling the LLM which specific number(s) failed validation and asking it to revise) yields materially better second-attempt success rates.
   - Recommendation: implement the corrective variant if it's not meaningfully more complex (pass the failed narrative + the specific ungrounded numbers back in a follow-up message) — it's a small addition to the same `generate()` call and is likely to have a materially higher success rate than a blind retry, but either is consistent with the locked decision; the planner can choose based on implementation-time complexity tradeoff.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (`pytest-django`), version already pinned project-wide |
| Config file | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`, `testpaths = ["clubs", "players", "transfers", "core", "accounts", "scoring", "workspace"]` — both `players` and `clubs` already included, no testpaths change needed) |
| Quick run command | `cd get-scouted-be && .venv/bin/pytest players/tests/test_ai_report_generator.py clubs/tests/test_ai_club_insights.py -x` |
| Full suite command | `cd get-scouted-be && .venv/bin/pytest` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AI-03 | `ReportGenerator` ABC contract (mirrors `test_ai_base.py`) | unit | `pytest players/tests/test_ai_report_generator.py -x` | ❌ Wave 0 |
| AI-03 | `AnthropicReportGenerator` happy path + error handling (mirrors `test_ai_anthropic_parser.py`, injected fake client) | unit | `pytest players/tests/test_ai_anthropic_report_generator.py -x` | ❌ Wave 0 |
| AI-03 | `get_report_generator()` factory dispatch (mirrors `test_ai_factory.py`) | unit | `pytest players/tests/test_ai_report_factory.py -x` | ❌ Wave 0 |
| AI-03 / AI-04 | Grounding validator: correctly matches tolerant numbers, correctly rejects hallucinated ones | unit | `pytest players/tests/test_ai_grounding.py -x` | ❌ Wave 0 |
| AI-03 | `POST /api/players/{id}/scouting-report/` end-to-end (mocked client, real `get_summary` grounding, real DB) | integration | `pytest players/tests/test_scouting_report_view.py -x` | ❌ Wave 0 |
| AI-04 | Position-needs ORM aggregation correctness against real club squad shape | unit | `pytest clubs/tests/test_services_club_insights.py -x` | ❌ Wave 0 |
| AI-04 | `POST /api/clubs/{id}/insights/` end-to-end (mocked client, real aggregation + `transfer_aggregates`) | integration | `pytest clubs/tests/test_ai_club_insights.py -x` | ❌ Wave 0 |
| AI-03 / AI-04 | Autouse Anthropic-block guard covers `clubs/tests/` too | unit | `pytest clubs/tests/test_ai_safety_net.py -x` | ❌ Wave 0 |
| AI-03 / AI-04 | No-fallback-on-failure: LLM error / double grounding-failure → clean error response, never a fabricated report | integration | `pytest players/tests/test_scouting_report_view.py -k failure -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** the specific new/modified test file(s) for that task
- **Per wave merge:** `cd get-scouted-be && .venv/bin/pytest players clubs` (both apps, since this phase spans two)
- **Phase gate:** Full suite green (`.venv/bin/pytest`) before `/gsd:verify-work`, plus a live `manage.py shell` check against the real dev DB for at least one real player+club and one real club-only insights call (matching every prior phase's "live-verified against the real 41,708-player dev DB" convention) — a mocked-client test suite alone cannot prove the prompt actually produces well-grounded narrative from a real LLM call, only that the plumbing/validator logic is correct.

### Wave 0 Gaps

- [ ] `players/tests/test_ai_report_generator.py` — covers `ReportGenerator`/`GeneratedReport`/`ReportGeneratorError` contract
- [ ] `players/tests/test_ai_anthropic_report_generator.py` — covers `AnthropicReportGenerator` (injected-client pattern, mirrors `test_ai_anthropic_parser.py`)
- [ ] `players/tests/test_ai_report_factory.py` — covers `get_report_generator()` dispatch (mirrors `test_ai_factory.py`)
- [ ] `players/tests/test_ai_grounding.py` — covers the numeric-extraction/tolerance-match validator, both accept and reject paths
- [ ] `players/tests/test_scouting_report_view.py` — covers the `POST /api/players/{id}/scouting-report/` endpoint end-to-end (mocked client) including the club_id-missing/no-club branch (Pitfall 1) and the clean-error-on-failure path (locked decision #6)
- [ ] `clubs/services.py` — does not exist yet; new module needed before its tests can run
- [ ] `clubs/tests/test_services_club_insights.py` — covers `position_needs_aggregate()` against a real/factory-built club squad
- [ ] `clubs/tests/test_ai_club_insights.py` — covers the `POST /api/clubs/{id}/insights/` endpoint end-to-end (mocked client)
- [ ] `clubs/tests/conftest.py` — needs the autouse `_block_real_anthropic_calls` fixture ported in (currently absent — verified by direct read); without this, any club-insights test that forgets the `client=` DI seam could attempt a real network call
- [ ] Framework install: none — pytest/pytest-django already fully configured project-wide, no new install needed

## Sources

### Primary (HIGH confidence — direct code inspection, 2026-07-25)
- `get-scouted-be/players/ai/base.py`, `anthropic_parser.py`, `factory.py`, `fallback.py` — full read, the interface/pattern this phase mirrors
- `get-scouted-be/players/tests/conftest.py`, `test_ai_factory.py`, `test_ai_anthropic_parser.py`, `test_ai_safety_net.py` — full read, the test-pattern this phase mirrors
- `get-scouted-be/scoring/services/summary.py`, `rmm.py`, `compatibility.py`, `transfer_probability.py`, `financial_fit.py` — full read, exact grounding-data shape
- `get-scouted-be/clubs/serializers.py`, `views.py`, `models.py` — full read, transfer-aggregates shape + `related_name="players"` confirmation + cross-app import precedent
- `get-scouted-be/players/models.py` — full read, `position`/`age`/`market_value`/`contract_expires`/`club` field types confirmed
- `get-scouted-be/players/views.py`, `players/urls.py`, `clubs/urls.py` — full read, existing endpoint/routing conventions
- `get-scouted-be/config/settings/base.py` (lines 165-186) — full read, exact current `LLM_PROVIDER`/`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` state
- `get-scouted-be/workspace/models.py` — `RecentActivity.ActivityType` choices confirmed (currently `viewed_player`/`viewed_club`/`searched` only)
- `get-scouted-be/scoring/exceptions.py` — `null_with_reason` envelope shape confirmed
- Installed `anthropic==0.120.0` package (`.venv/lib/python3.12/site-packages/anthropic-0.120.0.dist-info`) + `anthropic.types.model_param.ModelParam` Literal type — direct SDK inspection for text-block response shape and current model lineup
- `pip index versions anthropic` — confirms 0.120.0 is the current PyPI latest, matching the existing `>=0.120,<0.130` pin
- `get-scouted-be/pyproject.toml` — `testpaths` confirmed to already include both `clubs` and `players`
- `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/phases/10-ai-grounded-report-generation/10-CONTEXT.md` — full read

### Secondary (MEDIUM confidence)
- None — all findings in this phase were verifiable directly against the real, already-existing codebase; no external/web sources were needed since this phase is almost entirely a composition of already-built, already-verified project internals.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; exact installed/pinned `anthropic` version directly verified
- Architecture: HIGH — every file/pattern to mirror was read in full, not inferred from memory
- Pitfalls: HIGH — all 4 pitfalls are grounded in directly-observed code facts (conftest directory-scoping, `Http404` semantics, log-scale TFM history, no existing numeric formatter)
- Grounding validator design: MEDIUM — the mechanism (regex extraction + tolerance match) is sound and precedented by the project's own `fallback.py` style, but exact tolerance constants are Claude's Discretion and can only be tuned against real LLM output during implementation, not fully resolved by research alone

**Research date:** 2026-07-25
**Valid until:** ~30 days for the architecture/pattern findings (stable, based on existing code); the `ANTHROPIC_REPORT_MODEL` default should be re-verified at actual build/execution time regardless of elapsed time, per the same caveat Phase 9's own research and STATE.md blockers note flagged for `ANTHROPIC_MODEL` (Anthropic SDK model lineups can drift within weeks)

---
*Phase: 10-ai-grounded-report-generation*
*Research completed: 2026-07-25*
