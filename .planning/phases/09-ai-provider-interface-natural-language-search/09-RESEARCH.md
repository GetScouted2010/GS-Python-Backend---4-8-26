# Phase 9: AI Provider Interface & Natural-Language Search - Research

**Researched:** 2026-07-25
**Domain:** LLM provider abstraction (Anthropic Messages API tool-use) + Django/DRF read-layer composition
**Confidence:** MEDIUM (HIGH on codebase facts/verified-in-repo items, MEDIUM on Anthropic SDK/model specifics because this is a fast-moving external API surface with no prior code in this repo to anchor against)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Concrete provider: Anthropic Claude (Messages API + tool-use), behind a swappable interface**
- The first concrete implementation calls Anthropic's Messages API using tool-use / a forced JSON schema to extract structured filters, via a small `NLQueryParser` abstract interface (one method: `parse(query: str) -> ParsedQuery`). A `get_nl_query_parser()` factory reads `LLM_PROVIDER` from settings/env (django-environ, matching `EMAIL_BACKEND`'s existing pattern) and returns the configured implementation. Swapping providers later means adding one new class + one env var change — zero changes to the search view/service that calls `get_nl_query_parser()`.
- Why: AI-05 requires provider-agnosticism, but a concrete phase still needs *a* real implementation to prove the interface actually works end-to-end. Anthropic's tool-use gives reliable structured/schema-constrained output. No LLM SDK exists yet anywhere in this codebase (verified via grep) — genuinely greenfield.

**Fixed field whitelist, including how "style" resolves**
- NL search targets **Players only**. The whitelist is exactly Phase 7's existing `PlayerFilter` query params: `position`, `league`, `age_min`/`age_max`, `market_value_min`/`market_value_max`, plus the 4 score thresholds. "Style" resolves through the player's **club's** playing-style fields (`club__control_possession`, `club__gegenpressing`, etc. — the same 8 fields `ClubFilter` already exposes), since `Player` itself has no style field. The LLM's job is to map free text onto this exact whitelist; it never invents new filter dimensions.
- Why: Reusing Phase 7's already-tested filter fields means the NL layer is a thin translation step, not a new source of correctness bugs.

**Endpoint shape: `POST /api/players/search/`, returns parsed filters + fallback flag + paginated results**
- New endpoint `POST /api/players/search/` (added to `players/urls.py`), body `{"query": "<free text>"}`. Response: `{"query": "...", "parsed_filters": {...}, "fallback_used": bool, "results": {<same paginated envelope as GET /api/players/, reusing PlayerListSerializer + IdsBypassPagination>}}`. POST because this triggers a non-idempotent, cost-bearing external LLM call — matching Shortlist's `export` `@action` precedent, not plain-GET semantics.
- Why: Exposing `parsed_filters` makes AI-02's "graceful degradation" verifiable/debuggable. Reusing `PlayerListSerializer`/pagination keeps result shape consistent.

**Fallback behavior (AI-02): partial-filter application, then keyword regex, then unfiltered — never an error**
- Three-tier degradation: (1) LLM returns full/partial structured filters, applied as-is, `fallback_used: false`. (2) LLM call itself fails (timeout, API error, malformed/empty response) → lightweight keyword/regex extractor (position synonyms, number+suffix parser for "under €5M", substring match against real league names) → `fallback_used: true`. (3) Keyword fallback extracts nothing usable → full unfiltered (still paginated) player list, `parsed_filters: {}`, `fallback_used: true`. Always HTTP 200, never 4xx/5xx or empty-crash.
- Why: ROADMAP's success criterion #2 is explicit: "never an error or empty crash."

**RecentActivity integration: NL search populates the `"searched"` event type Phase 8 built for it**
- Every call to `POST /api/players/search/` (success or fallback) writes a `RecentActivity` row with `activity_type="searched"`, `query_text=<raw query>`, `target_id=None`.
- Why: Phase 8 explicitly built `"searched"` as "structurally ready... Phase 9 is the only future producer of that event type."

### Claude's Discretion
- Exact Anthropic model choice for the parsing call (a small/fast model is sufficient for structured extraction against a fixed whitelist — this isn't open-ended generation).
- Exact prompt/tool-schema wording sent to the LLM.
- Whether parsed-but-unmappable terms are surfaced back to the caller as an `unparsed_terms` list (nice-to-have transparency, not required by AI-01/AI-02's literal wording) — planner may include if low-cost.
- Retry/timeout tuning for the Anthropic API call before falling back to tier 2.
- Exact regex/synonym dictionary shape for the keyword-fallback tier.

### Deferred Ideas (OUT OF SCOPE)
- Combined Player+Club dual-entity NL search (e.g. "find clubs that need a striker").
- AI-generated scouting reports / club insights consuming this phase's parser — that's Phase 10 explicitly, a generation task not an extraction task.
- Caching/memoizing repeated identical NL queries to reduce LLM cost.
- Multi-turn conversational refinement of a search ("no, cheaper than that").
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| AI-01 | User can submit a natural-language query parsed into structured filters (position, age, value, league, style) against a fixed whitelist of real fields | `NLQueryParser`/`AnthropicNLQueryParser` tool-use pattern (below) maps free text to the exact verified `PlayerFilter`/`ClubFilter` field whitelist; `POST /api/players/search/` endpoint composition pattern |
| AI-02 | NL query parsing gracefully falls back (partial parse / keyword fallback) when input is ambiguous or unparseable | 3-tier fallback architecture; verified Anthropic SDK exception hierarchy for tier1→tier2 trigger; verified real league/position values for the tier-2 keyword extractor |
| AI-05 | The LLM integration is built behind a provider-agnostic interface so the concrete provider can be swapped without touching calling code | `NLQueryParser` ABC + `get_nl_query_parser()` factory pattern reading `LLM_PROVIDER`, mirroring `EMAIL_BACKEND`'s exact django-environ pattern in `config/settings/base.py` |
</phase_requirements>

## Summary

This phase is genuinely greenfield inside the repo (verified via `grep -rniE "anthropic|openai|llm|nlquery"` across `get-scouted-be`: zero hits) but architecturally low-risk: every reusable piece it needs (`PlayerFilter`, `ClubFilter`'s 8 style fields, `PlayerListSerializer`, `IdsBypassPagination`, `RecentActivity`, django-environ's `env()` pattern) already exists, is already tested, and was directly read/verified during this research pass. The only genuinely new engineering is (1) a small `NLQueryParser` ABC + factory + one Anthropic implementation, (2) a `POST /api/players/search/` view that composes the existing filter/pagination/serializer primitives against an LLM-produced (or fallback-produced) filter dict instead of `request.query_params`, and (3) a 3-tier degradation path with real exception handling.

The external-facing risk is the Anthropic Python SDK itself: it is a fast-moving, frequently-released package (0.2.x → 0.120.x history), and this research's model-name findings (e.g. "Claude Sonnet 5", "Haiku 4.5") come from web search results that mix official docs with SEO content of uncertain reliability — model identifiers should be treated as MEDIUM/LOW confidence and re-verified at build time, not hardcoded from this document. The classic tool-use pattern (`tools=[...]`, `tool_choice={"type":"tool","name":...}`, reading `block.input` off a `tool_use` content block) is HIGH confidence — it has been Anthropic's stable function-calling/structured-extraction pattern for a long time and is independent of exact model name. A newer GA "structured outputs" mode (`client.messages.parse()` + Pydantic `output_format`, or `strict: true` tool params) exists per current docs but is restricted to "Claude 4.5 and later" models — safer to note as an optional enhancement than to build the phase around it.

**Primary recommendation:** Build `NLQueryParser` (ABC, one method `parse(query: str) -> ParsedQuery`) + `AnthropicNLQueryParser` using the classic forced tool-use pattern (`tool_choice` naming one tool whose `input_schema` is exactly the whitelist), catch `anthropic.APIError` (parent of both `APIStatusError` and `APIConnectionError`/`APITimeoutError`) around the SDK call for tier1→tier2 fallback, and compose the search endpoint directly out of `PlayerFilter(data=filters_dict, queryset=...).qs` + a manual `club__<style>__gte` filter step + `IdsBypassPagination` + `PlayerListSerializer` rather than trying to reuse `PlayerListView`'s bound-to-`request.query_params` machinery.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `anthropic` | 0.120.0 (verified via `pip index versions anthropic`, 2026-07-25) | Official Anthropic Python SDK — Messages API client, tool-use, typed exceptions | Official first-party SDK; only credible choice for "Anthropic Claude" per the locked decision |
| `django-environ` | already installed (`>=0.11`, `requirements/base.txt`) | `LLM_PROVIDER`/`ANTHROPIC_API_KEY`/`ANTHROPIC_MODEL` env config | Already the project's exclusive config pattern (`EMAIL_BACKEND`, `DATABASE_URL`, `DATASET_DIR`) |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|--------------|
| stdlib `re` | n/a | Tier-2 keyword/regex fallback extractor (position synonyms, "under €5M" number+suffix, league substring match) | Always for tier 2 — no new dependency needed, matches the project's "stdlib first" pattern already seen in Phase 8's CSV export (`csv`+`StreamingHttpResponse`, no new dependency) |
| stdlib `abc` (`ABC`, `abstractmethod`) | n/a | `NLQueryParser` interface | No ABC/interface pattern exists yet anywhere in this codebase (verified via grep) — this is the first one; stdlib `abc` is the correct, dependency-free choice for a one-method interface |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Classic forced tool-use (`tool_choice`) | `client.messages.parse()` + Pydantic `output_format` (Anthropic's newer "structured outputs" GA feature) | Newer feature restricted to "Claude 4.5 and later" models per current docs (as of this research); classic tool-use works across the whole current model lineup and has a longer track record. Recommend classic tool-use as the safe default; `strict: true` / `.parse()` is a viable low-risk upgrade to note as Claude's Discretion, verified at build time. |
| `anthropic` official SDK | Raw `httpx`/`requests` against the REST API | No — official SDK gives typed exceptions (critical for tier1→tier2 fallback dispatch) and message/tool-schema validation for free; hand-rolling HTTP is exactly the kind of thing `## Don't Hand-Roll` below warns against. |

**Installation:**
```bash
pip install anthropic
```
Add to `get-scouted-be/requirements/base.txt` following this project's existing pin convention. Given `anthropic` is still a pre-1.0 package (0.120.x) where minor versions can carry breaking changes (unlike e.g. Django's stable 5.2.x), a narrower cap than the project's `scikit-learn>=1.5,<2.0`-style "next major" convention is prudent:
```
anthropic>=0.120,<0.130
```
This is a discretionary choice (the project's literal convention is "cap at next major"; a 0.x package's "next major" is `<1.0`, which is too wide to be a meaningful guardrail) — flag for planner/implementer sign-off.

**Version verification:** Verified 2026-07-25 via `pip index versions anthropic` → latest `0.120.0`. Re-verify at implementation time; this SDK ships frequently.

## Architecture Patterns

### Recommended Project Structure
```
get-scouted-be/
├── players/
│   ├── ai/                        # new — mirrors scoring/services/ as an established sub-package convention
│   │   ├── __init__.py
│   │   ├── base.py                 # NLQueryParser ABC + ParsedQuery dataclass
│   │   ├── anthropic_parser.py     # AnthropicNLQueryParser(NLQueryParser)
│   │   ├── factory.py              # get_nl_query_parser() reading settings.LLM_PROVIDER
│   │   └── fallback.py             # tier-2 keyword/regex extractor (no LLM dependency)
│   ├── services.py                 # new — search_players(filters: dict) -> queryset composition, shared by the search view (and reusable later)
│   ├── views.py                    # + PlayerSearchView (POST)
│   ├── urls.py                     # + path("search/", PlayerSearchView.as_view())
│   └── filters.py                  # UNCHANGED — PlayerFilter reused as-is, not modified
```
The `players/ai/` sub-package mirrors the codebase's one existing precedent for grouping non-CRUD domain logic into its own sub-package: `scoring/services/` (population.py, rmm.py, compatibility.py, financial_fit.py, transfer_probability.py, summary.py — each a thin service module the views call into). No prior `ABC`/interface pattern exists in this repo, so `NLQueryParser` is a new pattern, not a reused one — verified via `grep -rn "abstractmethod\|ABC\b"` returning zero hits outside `.venv`.

### Pattern 1: Provider-agnostic factory (mirrors `EMAIL_BACKEND`)
**What:** `LLM_PROVIDER` env var (django-environ) selects the concrete `NLQueryParser` implementation at import/call time; calling code only ever imports `get_nl_query_parser()`, never a concrete class.
**When to use:** Every call site that needs NL parsing (currently only `players/services.py`'s search flow; Phase 10 will likely add its own factory for a *different* interface — report/insight generation is not the same interface shape as `parse(query) -> ParsedQuery`, per CONTEXT.md's own note that Phase 10 "reuse[s] this phase's provider-agnostic interface *pattern*," not the same class).
**Example (verified pattern, not verified against this exact repo since it's new code):**
```python
# config/settings/base.py — new lines, following EMAIL_BACKEND's exact shape (verified in repo, line 170-172)
LLM_PROVIDER = env("LLM_PROVIDER", default="anthropic")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
ANTHROPIC_MODEL = env("ANTHROPIC_MODEL", default="claude-haiku-4-5")  # verify exact current model id at build time -- see Open Questions

# players/ai/factory.py
from django.conf import settings
from players.ai.base import NLQueryParser

def get_nl_query_parser() -> NLQueryParser:
    if settings.LLM_PROVIDER == "anthropic":
        from players.ai.anthropic_parser import AnthropicNLQueryParser
        return AnthropicNLQueryParser()
    raise ValueError(f"Unknown LLM_PROVIDER: {settings.LLM_PROVIDER!r}")
```

### Pattern 2: Forced tool-use for schema-constrained extraction
**What:** Define one tool whose `input_schema` is exactly the whitelisted filter fields (JSON Schema, enum-constrained where possible — e.g. `position` as an `enum` of the 10 real values, `league` as an `enum` of the 25 real values), then force the model to call it via `tool_choice`.
**When to use:** The single Anthropic parsing call in `AnthropicNLQueryParser.parse()`.
**Example:**
```python
# Source: Anthropic docs (platform.claude.com/docs/en/build-with-claude/structured-outputs)
# + anthropic-cookbook tool_use/extracting_structured_json.ipynb pattern (stable, long-standing)
import anthropic

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

FILTER_TOOL = {
    "name": "extract_player_filters",
    "description": "Extract structured player-search filters from a free-text query. Only use fields you are confident about; omit fields the query doesn't address.",
    "input_schema": {
        "type": "object",
        "properties": {
            "position": {"type": "string", "enum": ["AM", "CB", "CM", "DM", "FWD", "GK", "LB", "LW", "RB", "RW"]},
            "league": {"type": "string", "enum": [/* the 25 real league strings, see Code Examples */]},
            "age_min": {"type": "integer"},
            "age_max": {"type": "integer"},
            "market_value_min": {"type": "integer"},
            "market_value_max": {"type": "integer"},
            "impact_score_min": {"type": "number"},
            "compatibility_score_min": {"type": "number"},
            "financial_fit_score_min": {"type": "number"},
            "transfer_probability_score_min": {"type": "number"},
            "club__control_possession_min": {"type": "number"},
            "club__gegenpressing_min": {"type": "number"},
            "club__direct_play_min": {"type": "number"},
            "club__tiki_taka_min": {"type": "number"},
            "club__counter_attack_min": {"type": "number"},
            "club__wing_play_min": {"type": "number"},
            "club__low_block_min": {"type": "number"},
            "club__defensive_counter_attack_min": {"type": "number"},
        },
        "additionalProperties": False,
    },
}

response = client.messages.create(
    model=settings.ANTHROPIC_MODEL,
    max_tokens=512,
    tools=[FILTER_TOOL],
    tool_choice={"type": "tool", "name": "extract_player_filters"},
    messages=[{"role": "user", "content": query}],
)

tool_block = next(b for b in response.content if b.type == "tool_use")
parsed_filters = tool_block.input  # dict, already JSON-schema-shaped
```
**Note on `strict: true`:** Current Anthropic docs (fetched 2026-07-25) show a newer `"strict": True` flag on the tool definition that guarantees schema-perfect `input` (part of a GA "structured outputs" feature restricted to "Claude 4.5 and later" models). Recommend planner add `"strict": True` to `FILTER_TOOL` if the configured model supports it, with a defensive `try/except (KeyError, TypeError)` around reading `tool_block.input` regardless — do not assume strict mode eliminates the need for defensive parsing, since `LLM_PROVIDER` could point at a differently-behaved future implementation.

### Pattern 3: Compose search results directly from Phase 7's primitives (don't call into `PlayerListView`)
**What:** `PlayerListView` is a `generics.ListAPIView` whose filtering/pagination is driven by `request.query_params` via `DjangoFilterBackend`. The new POST search view needs to filter by an LLM-produced dict, not `request.GET`. **Do not** try to invoke `PlayerListView`'s bound methods (`filter_queryset`, `get_queryset`) — they're wired to DRF's request-object assumptions. Instead, directly reuse the three underlying reusable components, which is what `DjangoFilterBackend` itself does internally (`FilterSetClass(request.GET, queryset=queryset, request=request)` — `django_filters.FilterSet` accepts any `Mapping`/`QueryDict`-like object for `data`, not only `request.GET`, so a plain `dict` works identically).
**When to use:** `players/services.py::search_players(filters: dict, request) -> dict` (paginated envelope), called by both the new `PlayerSearchView` and, if ever wanted later, other callers.
**Example (verified: `PlayerFilter`/`IdsBypassPagination`/`PlayerListSerializer` signatures read directly from `players/filters.py`, `core/pagination.py`, `players/serializers.py`):**
```python
# players/services.py — new
from clubs.filters import ClubFilter  # for the 8 real style-field names, not reimplemented
from core.pagination import IdsBypassPagination
from players.filters import PlayerFilter
from players.models import Player
from players.serializers import PlayerListSerializer

STYLE_FIELDS = [
    "control_possession", "gegenpressing", "direct_play", "tiki_taka",
    "counter_attack", "wing_play", "low_block", "defensive_counter_attack",
]

def search_players(filters: dict, request):
    style_filters = {
        k: v for k, v in filters.items()
        if k.startswith("club__") and k[len("club__"):].removesuffix("_min") in STYLE_FIELDS
    }
    player_filter_data = {k: v for k, v in filters.items() if k not in style_filters}

    qs = PlayerFilter(data=player_filter_data, queryset=Player.objects.all()).qs
    for key, value in style_filters.items():
        field = key.removesuffix("_min")  # e.g. "club__control_possession"
        qs = qs.filter(**{f"{field}__gte": value})
    qs = qs.order_by("-impact_score")  # same deterministic default as PlayerListView

    paginator = IdsBypassPagination()
    page = paginator.paginate_queryset(qs, request, view=None)
    serialized = PlayerListSerializer(page, many=True).data
    return paginator.get_paginated_response(serialized).data
```
**Verified constraint:** `PlayerFilter.Meta.fields` does NOT include any `club__` lookups (confirmed by reading `players/filters.py` in full — its declared filters are `ids, position, league, age_min, age_max, market_value_min, market_value_max`, plus the 4 score-threshold mins). Passing an undeclared key like `club__control_possession_min` inside `data=` to `PlayerFilter` is silently ignored by django-filter (a `FilterSet` only processes keys matching its own declared/`Meta.fields` filters) — it will **not** raise, and it will **not** filter. This confirms the CONTEXT.md's flagged risk: style filters MUST be applied as a separate manual `.filter(club__<field>__gte=...)` step, not smuggled through `PlayerFilter`'s `data` dict. Recommend leaving `PlayerFilter` itself unmodified (Phase 7's tested class, "reuse not reinvent" per CONTEXT.md) rather than adding `club__` fields to it — this keeps the style-filter composition local to the search feature.

### Anti-Patterns to Avoid
- **Modifying `PlayerFilter`/`ClubFilter` to add search-specific fields:** Phase 7's filter classes are already tested and used by the plain GET list endpoints; adding `club__*` fields to `PlayerFilter` would silently change `GET /api/players/`'s public filter surface too. Keep style-filter composition inside the search service function instead.
- **Catching only `anthropic.APITimeoutError`:** Too narrow — `RateLimitError`, `InternalServerError`, `APIConnectionError`, and any 4xx/5xx `APIStatusError` should all trigger tier1→tier2 fallback, not just timeouts. Catch the common parent `anthropic.APIError` (see Common Pitfalls).
- **Hardcoding the Anthropic model name without an env override:** given this research's own uncertainty about exact current model IDs (see Open Questions), hardcoding risks the endpoint silently 404/400-ing against a deprecated model string with no easy fix path. Always route through `settings.ANTHROPIC_MODEL` (env-overridable).
- **Trusting `tool_block.input` values as final filter values without a defensive re-check against the whitelist:** even with `tool_choice` forcing, treat the LLM's output as untrusted input — explicitly validate `position`/`league` values are in the real enum sets before passing them to `PlayerFilter`, rather than passing arbitrary LLM-invented strings straight into a Django ORM filter (low risk of injection given django-filter/ORM parameterization, but a fabricated `position` value would silently return zero results instead of gracefully degrading).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Talking to the Anthropic API | Raw `httpx` calls against `https://api.anthropic.com/v1/messages` | Official `anthropic` SDK | Typed exception hierarchy (critical for tier1→tier2 dispatch), request/response validation, retry policy already built in |
| JSON-Schema-shaped LLM output | Free-text prompt + manual regex/JSON parsing of the model's text response | `tools` + `tool_choice` forced tool-use | This is exactly the problem tool-use exists to solve — free-text parsing of LLM prose is unreliable and was already rejected implicitly by the locked decision to use tool-use |
| Filtering Players by their club's style fields | A parallel/duplicate style-filter implementation inside the search view | Reuse `ClubFilter`'s 8 verified field names (just applied via `club__<field>__gte` on the Player queryset, not through `ClubFilter` itself, which filters `Club` not `Player`) | Field names/semantics already correct and tested in `clubs/filters.py` |
| Paginated player list response shape | A third bespoke pagination/serialization scheme for search results | `IdsBypassPagination` + `PlayerListSerializer` (same as `GET /api/players/`) | CONTEXT.md's explicit locked decision — consistent result shape across every player-listing surface |

**Key insight:** Nearly everything this phase needs already exists in the codebase in tested form; the actual net-new surface area is small (one ABC, one factory, one Anthropic implementation, one regex fallback module, one view, one service function).

## Common Pitfalls

### Pitfall 1: Catching too narrow an exception set around the Anthropic call
**What goes wrong:** Code catches only `anthropic.APITimeoutError` (or nothing), and a rate-limit (429) or a 5xx from Anthropic propagates as an unhandled exception, producing a 500 response — directly violating AI-02's "never an error" requirement.
**Why it happens:** It's easy to think "timeout" is the only failure mode worth handling for an external API call; in practice rate limits, auth errors (misconfigured `ANTHROPIC_API_KEY`), and transient 5xx/529 overloaded errors are all real, encountered-in-production failure modes.
**How to avoid:** Catch `anthropic.APIError` (verified base class — via GitHub source, `APIError` is the common ancestor of both `APIStatusError` [400/401/403/404/409/413/422/429/503/529/504/5xx] and `APIConnectionError`→`APITimeoutError`) around the single `client.messages.create()` call, and treat any exception there (plus a defensive `except (KeyError, StopIteration, TypeError)` around extracting `tool_block.input`, for a genuinely malformed/empty response that didn't raise at the HTTP layer) as "go to tier 2."
**Warning signs:** A test that mocks `anthropic.RateLimitError` or a malformed tool response and asserts the endpoint still returns 200 with `fallback_used: true` — if this test doesn't exist, the narrow-catch pitfall is likely present.

### Pitfall 2: Testing accidentally calls the real Anthropic API
**What goes wrong:** Since this project's pytest config (`pyproject.toml`: `DJANGO_SETTINGS_MODULE = "config.settings.local"`) has **no dedicated test settings module** — verified: `local.py` just re-imports `base.py` and sets `DEBUG=True`/`ALLOWED_HOSTS` — there is no environment-based safety net preventing a real `ANTHROPIC_API_KEY` (if present in a developer's local `.env`) from being used during `pytest` runs. A test that doesn't explicitly mock the parser could make a real, billed API call.
**Why it happens:** Every other phase's tests either use real DB data (verified skip-if-empty pattern) or mock pure-Python/sklearn functions — this is the first external network call in the codebase, so there's no existing "test settings safety net" convention to fall back on.
**How to avoid:** Every test touching `PlayerSearchView`/`AnthropicNLQueryParser` MUST patch the parser (or the `anthropic.Anthropic` client construction) — never rely on `ANTHROPIC_API_KEY` being unset as the only guard. Follow this codebase's established mocking convention (verified via grep across `players/tests`, `scoring/tests`, `workspace/tests`): **patch the caller's own import binding**, not the definition module — e.g. `monkeypatch.setattr("players.views.get_nl_query_parser", lambda: fake_parser)` or `patch("players.ai.factory.get_nl_query_parser")`, mirroring the exact pattern `players/tests/test_views.py::test_detail_club_none_returns_null_with_reason` uses for `players.views.summary.get_summary`/`players.views.rmm.get_rmm`, and the corrected-target lesson explicitly recorded in `STATE.md`'s Phase 6-07 entry ("patch targets from the definition modules... are silent no-ops... the caller's own import bindings" actually intercept the call).
**Warning signs:** `.env.example`'s `ANTHROPIC_API_KEY=` left blank is necessary but not sufficient — CI or a developer with a real key set locally would still leak real calls without explicit test-level mocking.

### Pitfall 3: `IdsBypassPagination`/`PlayerFilter` expect a DRF `request` object, not a bare query dict, in places
**What goes wrong:** `IdsBypassPagination.paginate_queryset(queryset, request, view=None)` reads `request.query_params.get("ids")` — for a `POST /api/players/search/` request this is fine (POST requests still have `query_params` from the URL, which will simply be empty for this endpoint), but a naive implementation might try to pass the parsed-filters dict as if it were the DRF `request`, which would crash.
**Why it happens:** Conflating "the filters dict I built from the LLM" with "the DRF request object the pagination class expects."
**How to avoid:** Pass the real `request` object (untouched) to `paginate_queryset`; pass only the `filters` dict to `PlayerFilter(data=filters_dict, ...)`. These are two separate parameters in the recommended `search_players(filters, request)` service signature above.
**Warning signs:** An `AttributeError` on `.query_params` during a search endpoint test.

### Pitfall 4: Style-field filter naming mismatch (`club__<field>_min` vs `club__<field>__min` vs bare field name)
**What goes wrong:** The verified real `ClubFilter` field names are e.g. `control_possession_min` (a *filter name*, django-filter convention), which maps to the underlying model field `control_possession` with `lookup_expr="gte"`. If the LLM's tool-schema key is designed as `club__control_possession_min` (matching CONTEXT.md's own suggested shape) but the code that turns it into an ORM lookup forgets to strip the `_min` suffix and add `__gte`, the resulting queryset filter (`club__control_possession_min__gte=X`) will raise `FieldError: Cannot resolve keyword 'control_possession_min' into field` at request time — the club model has no field literally named `control_possession_min`.
**Why it happens:** The whitelist mixes two different naming conventions (django-filter's `_min` suffix convention vs. the ORM's `__gte` lookup convention) and it's easy to conflate them when composing the `club__` traversal.
**How to avoid:** Explicitly test the string transform `"club__control_possession_min"` → `filter(club__control_possession__gte=value)` (strip `_min`, append `__gte`) with a unit test, as shown in Pattern 3's code example.
**Warning signs:** A 500 error (unhandled `FieldError`) on any search query that includes a style term — this would be a stark contradiction of AI-02's "never an error or empty crash," so it should be caught by a Wave-0-level test before it's shippable.

## Code Examples

### Real values to hardcode into the tool schema `enum`s and the tier-2 fallback dictionary (verified live against the real dev DB, 2026-07-25)

**`Player.position` — 10 real distinct values** (verified via `Player.objects.values_list("position", flat=True).distinct()`; matches Phase 7's already-documented finding that `position`, not `main_position`, is the correct 10-value clean group):
```
AM, CB, CM, DM, FWD, GK, LB, LW, RB, RW
```

**`Player.league` — 25 real distinct values** (verified via `Player.objects.values_list("league", flat=True).distinct()`):
```
Allsvenskan (Sweden), Bundesliga (Austria), Bundesliga (Germany), Bundesliga 2,
Challenger Pro League, EFL Championship, EFL League One, Eerste Divisie,
Eliteserien, Eredivisie (Netherlands), La Liga (Spain), La Liga 2,
Liga Portugal 2, Ligue 1 (France), Ligue 2 (France), MLS (USA),
Premier League (England), Primeira Liga (Portugal), Pro League (Belgium), SPL,
Serie A (Brazil), Serie A (Italy), Serie B, Super Lig (Turkey), Superliga (Denmark)
```
Note for tier-2 substring fallback: several names share a base term across country variants (`Bundesliga (Austria)` vs `Bundesliga (Germany)` vs `Bundesliga 2`; `Serie A (Brazil)` vs `Serie A (Italy)` vs `Serie B`) — a naive `"bundesliga" in league.lower()` substring match is ambiguous across 3 leagues. Recommend the tier-2 fallback either (a) requires the country qualifier too when present in the query, or (b) returns the full multi-match set rather than guessing one, consistent with the "never fabricate, degrade gracefully" principle already established for scores in this project.

**`Player.market_value`** — plain `BigIntegerField`, not currency-scaled (verified: max real value `180000000` = €180,000,000). A "under €5M" tier-2 regex should parse to `market_value_max = 5_000_000` (not `5`).

**`Club` style fields** — all `FloatField(null=True, blank=True)`, verified real sample row: `control_possession=16.0, gegenpressing=15.09, direct_play=13.1, tiki_taka=17.74, counter_attack=11.47, wing_play=10.5, low_block=11.69, defensive_counter_attack=4.42`. Values are NOT obviously a 0-100 percentage scale (all real sample values are well under 20) — recommend the planner spot-check the actual min/max distribution across all clubs before choosing a "possession-based" threshold default in any prompt example, rather than assuming a 0-100 scale.

### Anthropic error handling for tier1→tier2 dispatch
```python
# Source: verified via github.com/anthropics/anthropic-sdk-python exception hierarchy
# (AnthropicError -> APIError -> {APIStatusError -> [BadRequestError, AuthenticationError,
#  PermissionDeniedError, NotFoundError, ConflictError, RequestTooLargeError,
#  UnprocessableEntityError, RateLimitError, ServiceUnavailableError, OverloadedError,
#  DeadlineExceededError, InternalServerError], APIConnectionError -> APITimeoutError})
import anthropic

def parse(self, query: str) -> ParsedQuery:
    try:
        response = self._client.messages.create(...)
        tool_block = next(b for b in response.content if b.type == "tool_use")
        filters = dict(tool_block.input)
    except anthropic.APIError:
        raise NLQueryParserError("LLM call failed")  # caller (search service) catches this, goes to tier 2
    except (StopIteration, KeyError, TypeError, AttributeError):
        raise NLQueryParserError("LLM returned an unusable/malformed response")
    return ParsedQuery(filters=filters, raw_query=query)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| Free-text prompting + manual JSON parsing of the model's prose reply | Forced tool-use (`tool_choice` naming a specific tool) for guaranteed-shape extraction | Long-standing (multiple years) Anthropic pattern, not new | This phase's locked decision already picked the current-best approach |
| Tool-use with best-effort schema adherence | `strict: true` tool params / `client.messages.parse()` + Pydantic `output_format` for guaranteed schema-valid output | GA per Anthropic docs fetched 2026-07-25, restricted to "Claude 4.5 and later" models, requires SDK ≥0.74.1 (this project would install 0.120.x, well above that floor) | Optional reliability upgrade; not required to satisfy AI-01/AI-02 since classic tool-use is already reliable enough combined with this phase's own defensive validation + fallback tiers |

**Deprecated/outdated:** None identified specific to this phase's scope — the tool-use pattern this phase is built on has been stable, not something recently replaced.

## Open Questions

1. **Exact current Anthropic model identifier string to hardcode as `ANTHROPIC_MODEL`'s default**
   - What we know: Anthropic's current (2026) lineup includes a fast/cheap tier suitable for structured extraction (web search results reference "Haiku 4.5" and similar naming), and a mid tier ("Sonnet 5" — notably, this matches this research agent's own reported model identity, which is at least one point of corroboration). `STATE.md`'s own Blockers/Concerns section already flagged this exact risk: "AI layer (Phases 9-10) LLM library/API surface should get a fresh check at build time given how fast that space moves."
   - What's unclear: The precise API model ID string (e.g. whether it's `claude-haiku-4-5-<date>` or a different format) — web search results for this are a mix of official docs and SEO-style aggregator content, not verified against Anthropic's own model-list API.
   - Recommendation: Make `ANTHROPIC_MODEL` env-configurable with no baked-in assumption the planner treats as certain; the implementer should call `GET /v1/models` (via `client.models.list()`) or check `https://platform.claude.com/docs/en/about-claude/models` at build time to pick the current fast/cheap model ID, then set it as the `.env.example` default. Do not let this research document's model-name mentions be copied verbatim into code without that verification step.

2. **Whether `strict: true` tool params are worth adopting in v1 of this phase**
   - What we know: `strict: true` guarantees schema-valid tool `input`, removing one class of "malformed response" the tier1→tier2 fallback needs to defend against.
   - What's unclear: Whether the model selected (per Open Question 1) supports it, and whether the marginal reliability gain is worth the added version/model coupling for a phase whose fallback tiers already defend against malformed output regardless.
   - Recommendation: Classic tool-use (no `strict`) + defensive parsing is sufficient to satisfy AI-01/AI-02; treat `strict: true` as a Claude's-Discretion enhancement, not a requirement.

3. **Whether the LLM should also be prompted with the real league-name list / position list inline (few-shot / enum-in-prompt) vs. relying solely on the JSON-Schema `enum` constraint**
   - What we know: JSON-Schema `enum` in `input_schema` constrains the *tool call's argument values* but doesn't guarantee the model correctly maps "the Prem" → `"Premier League (England)"` without some hint of the real string.
   - What's unclear: Whether enum-only is sufficient in practice, or whether the system prompt should also list the real values as a lookup aid.
   - Recommendation: Include the real value lists (Code Examples section, verified above) directly in the tool schema's `enum` AND in a short system-prompt reference table — both are cheap (small string lists) and reduce mismapping risk; this is Claude's Discretion on exact prompt wording per CONTEXT.md.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-django ≥4.9 (verified: `requirements/dev.txt`) |
| Config file | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`) — `DJANGO_SETTINGS_MODULE = "config.settings.local"`, `testpaths` currently lists `clubs, players, transfers, core, accounts, scoring, workspace` (no new app needed if this phase's code lives inside `players/`) |
| Quick run command | `pytest players/tests/ -x` |
| Full suite command | `pytest` (from `get-scouted-be/`, using the project `.venv`) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| AI-05 | `get_nl_query_parser()` returns the Anthropic implementation when `LLM_PROVIDER=anthropic`; swapping the setting requires no view/service code change | unit | `pytest players/tests/test_ai_factory.py -x` | ❌ Wave 0 |
| AI-01 | `AnthropicNLQueryParser.parse()` maps a mocked tool-use response into a `ParsedQuery` restricted to the real whitelist | unit (mocked `anthropic.Anthropic` client — never a real call) | `pytest players/tests/test_ai_anthropic_parser.py -x` | ❌ Wave 0 |
| AI-01 | `POST /api/players/search/` with a mocked successful parse returns `fallback_used: false` + correctly filtered/paginated real players | integration (DRF `APIClient`, real dev-DB-dependent via the established `real_data_available` skip-fixture) | `pytest players/tests/test_search_view.py -x` | ❌ Wave 0 |
| AI-01 | Style-term query (`club__<field>_min`) round-trips to a correct `club__<field>__gte` ORM filter, not a `FieldError` | unit | `pytest players/tests/test_services_search.py::test_style_filter_field_name_transform -x` | ❌ Wave 0 |
| AI-02 | Mocked `anthropic.RateLimitError`/`anthropic.APITimeoutError`/`anthropic.APIConnectionError` on the parse call → tier-2 keyword fallback engages, `fallback_used: true`, HTTP 200 | unit + integration | `pytest players/tests/test_search_view.py -k fallback -x` | ❌ Wave 0 |
| AI-02 | Tier-2 keyword extractor produces zero usable filters → tier-3 unfiltered paginated list, `parsed_filters: {}`, HTTP 200 | unit | `pytest players/tests/test_ai_fallback.py -x` | ❌ Wave 0 |
| AI-02 | Tier-2 regex correctly parses "under €5M" → `market_value_max=5000000`, real position synonyms (e.g. "centre back"/"CB"), and league substring matches against the real 25-value list (including the ambiguous "Bundesliga"/"Serie" cases from Code Examples) | unit | `pytest players/tests/test_ai_fallback.py -k keyword -x` | ❌ Wave 0 |
| CRUD-09 (integration point) | Every `POST /api/players/search/` call (success or fallback) writes exactly one `RecentActivity(activity_type="searched", query_text=<raw>, target_id=None)` row | integration | `pytest players/tests/test_search_view.py -k recent_activity -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest players/tests/ -x`
- **Per wave merge:** `pytest` (full suite, from `get-scouted-be/`)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `players/tests/test_ai_factory.py` — covers AI-05
- [ ] `players/tests/test_ai_anthropic_parser.py` — covers AI-01 (mocked Anthropic client, following the "patch caller's own import binding" convention — patch `players.ai.anthropic_parser.anthropic.Anthropic` or construct the parser with an injected fake client, never allow a real `client.messages.create()` call to fire during pytest)
- [ ] `players/tests/test_ai_fallback.py` — covers AI-02's tier-2/tier-3 keyword fallback, no LLM/network involved at all (pure regex unit tests)
- [ ] `players/tests/test_services_search.py` — covers the `search_players()` service function's filter/style-field composition, including the Pitfall 4 field-name-transform regression test
- [ ] `players/tests/test_search_view.py` — DRF `APIClient` integration tests for `POST /api/players/search/`, covering success, all 3 fallback tiers, `RecentActivity` logging, and the authentication gate (mirroring `players/tests/test_views.py`'s existing `auth_client` fixture and `real_data_available` skip pattern)
- [ ] No new test-framework/config install needed — pytest/pytest-django/factory_boy already present (`requirements/dev.txt`)
- [ ] **Explicit safety net recommended (not a pre-existing gap, but a new-risk mitigation):** since no test-settings module isolates `ANTHROPIC_API_KEY` (Pitfall 2), Wave 0 should also add a `conftest.py`-level `autouse` fixture in `players/tests/` (or a session-scoped guard) that fails loudly if any test attempts a real `anthropic.Anthropic().messages.create()` call without mocking — e.g. via `pytest-socket` (new dev dependency, not currently installed) or a simpler `monkeypatch`-based blanket stub of `anthropic.Anthropic` at the top of the AI-specific test modules. Recommend the lighter-weight option (module-level fixture, no new dependency) given this project's consistent "stdlib/existing-deps-first" pattern.

## Sources

### Primary (HIGH confidence)
- Direct repo reads (2026-07-25): `players/filters.py`, `clubs/filters.py`, `players/views.py`, `players/urls.py`, `players/serializers.py`, `core/pagination.py`, `workspace/models.py`, `workspace/views.py`, `config/settings/base.py`, `config/settings/local.py`, `config/settings/production.py`, `players/tests/test_views.py`, `players/tests/conftest.py`, `requirements/base.txt`, `requirements/dev.txt`, `pyproject.toml`, `.env.example`
- Live `manage.py shell` queries against the real 41,708-player / 1,060-club dev DB (2026-07-25): real `Player.position` (10 values), real `Player.league` (25 values), real `Player.market_value` range, real `Club` style-field sample row
- `pip index versions anthropic` (2026-07-25): confirms latest `anthropic==0.120.0`
- `grep -rniE "anthropic|openai|llm|nlquery"` and `grep -rn "abstractmethod|ABC\b"` across `get-scouted-be` (excluding `.venv`): confirms zero existing LLM SDK usage and zero existing ABC/interface pattern
- `github.com/anthropics/anthropic-sdk-python` `_exceptions.py` (fetched 2026-07-25 via WebFetch): verified exception class hierarchy

### Secondary (MEDIUM confidence)
- `platform.claude.com/docs/en/build-with-claude/structured-outputs` (fetched 2026-07-25 via WebFetch): tool-use/structured-output code patterns, `strict: true`, `client.messages.parse()`, model-family restriction note
- WebSearch: Anthropic SDK exception class summary (cross-checked against the GitHub source fetch above — consistent)

### Tertiary (LOW confidence)
- WebSearch: current (2026) Claude model lineup/naming ("Sonnet 5", "Haiku 4.5", "Opus 4.8", "Fable 5") — sourced from a mix of official-adjacent and SEO/aggregator content, not cross-verified against Anthropic's own model-list API; flagged explicitly in Open Questions as needing build-time re-verification, not to be hardcoded from this document

## Metadata

**Confidence breakdown:**
- Standard stack (anthropic SDK choice/version): HIGH — verified via `pip index versions`, official SDK is the only sane choice for "Anthropic" per locked decision
- Architecture (search endpoint composition, `NLQueryParser` interface shape): HIGH — every reused piece verified by direct repo read; the composition pattern itself is new code but follows verified, existing primitives' actual signatures
- Anthropic model-name/exact-tier specifics: LOW — flagged as Open Question, must be re-verified at build time
- Pitfalls (exception handling, test-mocking safety, field-name transform, test-settings gap): HIGH — all derived from direct repo verification (exception hierarchy from SDK source, mocking convention from existing test files, `pyproject.toml`'s actual settings module)

**Research date:** 2026-07-25
**Valid until:** ~7 days for anything Anthropic-SDK/model-specific (fast-moving external API surface, per `STATE.md`'s own flagged concern); ~30 days for the codebase-internal architecture findings (stable until Phase 9/10 code lands)
