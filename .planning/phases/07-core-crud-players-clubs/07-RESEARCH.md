# Phase 7: Core CRUD - Players & Clubs - Research

**Researched:** 2026-07-24
**Domain:** DRF read-only list/filter/sort/paginate + detail APIs over an existing Postgres-backed Django project
**Confidence:** HIGH (verified directly against live code, live dev DB, and current PyPI/DRF docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Filtering, sorting, and pagination stack**
- Adopt `django-filter` for `FilterSet`-based query-param filtering (exact match on position/league/country/playing-style; range filters via `gte`/`lte` on age/market_value/the 4 score fields), DRF's built-in `OrderingFilter` for `?ordering=-impact_score`-style sorting, and DRF's `PageNumberPagination` (default page size 25, client-adjustable via `page_size` up to a capped max of 100) for pagination.
- Why a new dependency here, unlike Phase 6's Redis-avoidance: `django-filter` is the de facto standard DRF companion for exactly this shape of problem — low-risk, single-purpose, doesn't commit the project to an infrastructure decision. Not currently installed; this phase adds it.
- Why range filters, not just exact match: CRUD-01 explicitly requires filtering by age, market value, and score *thresholds* — inherently range queries.

**List vs. detail response depth**
- Two-tier serializers per entity.
  - **List** (`GET /api/players/`, `GET /api/clubs/`): lightweight — identity fields, position/league/club, market value, and the 4 denormalized own-club scores already built in Phase 6. No stat breakdown, no full 99-column stat block.
  - **Detail** (`GET /api/players/{id}/`, `GET /api/clubs/{id}/`): full profile — every stat field, plus score **breakdowns**, not just the 4 scalar values.
- Detail calls the existing scoring service (`scoring.services.summary.get_summary(player_id, club_id)`) instead of re-deriving breakdowns — it's already fast (~0.2s, verified against real data) specifically so call sites like this could use it inline.

**"Season-by-season stats" — scoped to match the real data model**
- Player detail exposes the single season snapshot that actually exists for that player (labeled with the real `season` field value: `"2024-2025"`, `"2023-2024"`, `"2022-2023"`, or `"Last Calendar Year"`), not a fabricated multi-season history.
- Verified directly against the live dev DB: every one of the 41,708 players has exactly **one** row. The migrated dataset never contained true per-player multi-season history. Do not fabricate a fake history array.

**Club detail: squad overview & transfer behaviour aggregates**
- Both computed live via Django ORM aggregation at request time, not precomputed/cached — bounded to one club's data, not a whole-population scan.
  - **Squad overview:** `Player.objects.filter(club=club)`, using the existing lightweight list serializer.
  - **Transfer behaviour aggregates:** computed from `Transfer.market_value_at_transfer` (a clean `BigIntegerField`) and count/movement/window breakdowns — **not** from `Transfer.fee` (free-text, not safely aggregatable). `fee` stays available as a raw display field on individual transfer records only.

**Multi-fetch comparison endpoint (CRUD-05)**
- Reuse the same list endpoints with an `ids` filter rather than building bespoke comparison endpoints — e.g. `GET /api/players/?ids=<uuid1>,<uuid2>,<uuid3>` returns those specific players through the existing list serializer (unpaginated when `ids` is present). Same pattern for `/api/clubs/?ids=...`.

**Auth (carried forward, not re-decided)**
- All Phase 7 endpoints require authentication only (global `IsAuthenticated` + JWT). No role restriction beyond "logged in" — `MinimumRole` gating is reserved for Phase 8's write endpoints.

### Claude's Discretion
- Exact `FilterSet` field names and filter-class choices (e.g. `NumberFilter` vs `RangeFilter` for age/market_value/scores).
- Exact URL structure under `/api/players/` and `/api/clubs/` (e.g. whether `/api/players/{id}/transfers/` is a separate nested route or embedded in detail).
- Whether `ids` multi-fetch has a sane upper bound (e.g. reject more than ~100 ids) to prevent an accidentally enormous unpaginated response.
- Exact set of orderable/filterable fields beyond the ones ROADMAP explicitly names — reasonable additions (e.g. ordering by `market_value`) are fine; wholesale new filter dimensions are not.

### Deferred Ideas (OUT OF SCOPE)
- Parsing/normalizing `Transfer.fee`'s free-text values into a clean numeric field — deferred; `market_value_at_transfer` already covers the aggregate use case.
- True multi-season player history (schema/migration change) — deferred, out of scope for a read-layer phase.
- CSV export (CRUD-10) — Phase 8's requirement, not this phase's.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| CRUD-01 | List/filter/sort/paginate Players by position, age, market value, league, score thresholds | `django-filter` FilterSet + `Player.position` (verified correct field, not `main_position`) + `OrderingFilter` + `PageNumberPagination` — see Standard Stack, Architecture Patterns, and "Which position field" pitfall below |
| CRUD-02 | List/filter Clubs by league, country, playing style | Same FilterSet pattern applied to `Club`; playing-style fields are nullable floats (~22.6% coverage) — filter as `isnull`/range, never assume non-null |
| CRUD-03 | Retrieve single Player's full profile, season-by-season stats, score breakdowns | Detail serializer (all ~99 stat fields + profile) + `scoring.services.summary.get_summary(player_id, club_id)` inline; `season` field exposed as single labeled snapshot; club=None edge case documented below |
| CRUD-04 | Retrieve single Club's full profile, squad overview, transfer behaviour aggregates | `club.players.all()` (verified `related_name="players"`) for squad; `Transfer.objects.filter(club=club).aggregate(...)` on `market_value_at_transfer`, grouped by `movement`/`window`, for aggregates |
| CRUD-05 | Fetch multiple players/clubs by ID in one request | `ids` query param via `django_filters.BaseInFilter` + `UUIDFilter`, pagination bypassed when present (`paginate_queryset` override), upper bound recommended |
</phase_requirements>

## Summary

The `players` and `clubs` Django apps currently have models only — no `views.py`/`serializers.py`/`urls.py` exist for either, confirming CONTEXT.md's "greenfield" framing. `django-filter` is genuinely absent from the venv and needs to be added at the current stable version (26.1, which requires Django ≥5.2 — the project runs Django 5.2.16, so this is a clean fit). The project's `REST_FRAMEWORK` setting in `config/settings/base.py` currently has no `DEFAULT_FILTER_BACKENDS` or `DEFAULT_PAGINATION_CLASS` key set, so this phase adds both cleanly without overwriting or duplicating anything.

The single most important correction this research surfaces: **CONTEXT.md/ROADMAP's assumption about which "position" field to filter on needs verification against the real data, and the real data contradicts the doc-comment in `docs/FIELD_MAPPING.md`.** `Player.main_position` is NOT the clean 10-value position group — it holds 22 fine-grained values (`AMF`, `LCB`, `RWB`, `RDMF`, plus one literal `'0'` placeholder row). It is `Player.position` that holds the clean 10-value group (`AM`, `CB`, `CM`, `DM`, `FWD`, `GK`, `LB`, `LW`, `RB`, `RW`) — and this is confirmed as the intended filter dimension by two independent facts: (1) `PlayerRoleScore.position_group`'s 9 real distinct values (`AM, CB, CM, DM, FWD, LB, LW, RB, RW`) match `position`, not `main_position`; and (2) `Player.Meta.indexes` already includes `models.Index(fields=["position"])` — the codebase's own indexing choice anticipated this. CRUD-01's "filter by position" should filter on `Player.position`, not `Player.main_position`.

The `club`-is-`None` edge case flagged in the task brief is real as a structural possibility (`Player.club` is `on_delete=SET_NULL, null=True`) but does **not** currently occur in the live dev DB — all 41,708 players have a non-null club today. The plan should still handle it defensively (never assume `player.club_id` is truthy) because `scoring.services.summary.get_summary(player_id, club_id)` raises `Http404` if `club_id` is `None` or unresolvable (via `resolve_club_name`), so Player detail cannot blindly pass `player.club_id` through — it must branch and fall back to a null-with-reason envelope (mirroring the shared `null_with_reason` shape already used everywhere else in `scoring/`) for players with no club, while still surfacing RMM via `scoring.services.rmm.get_rmm(player_id)` (which needs no club at all).

**Primary recommendation:** Build `players/views.py` and `clubs/views.py` as thin DRF `generics.ListAPIView`/`RetrieveAPIView` subclasses (matching `scoring/views.py`'s existing thin-view convention — no viewsets/routers, explicit `path()` lists in `urls.py` matching `scoring/urls.py`'s style), backed by `django-filter` `FilterSet`s + DRF `OrderingFilter` + a shared capped `PageNumberPagination` subclass, with `ids`-based unpaginated multi-fetch reusing the list endpoints.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|---------------|
| `django-filter` | 26.1 (verified current on PyPI 2026-07-24; requires `Django>=5.2`, no DRF version pin) | `FilterSet`-based query-param filtering | De facto standard DRF companion library for exactly this problem shape; already the plan CONTEXT.md locked in |
| `djangorestframework` | 3.17.1 (already installed, unpinned upper bound `<3.18` in `requirements/base.txt`) | `generics.ListAPIView`/`RetrieveAPIView`, `filters.OrderingFilter`, `pagination.PageNumberPagination` | Already the project's API framework; no new dependency needed for ordering/pagination, only for `django-filter` |
| `Django` | 5.2.16 (already installed) | ORM aggregation (`Count`/`Sum`/`Avg` for Club transfer/squad aggregates) | Already the project's framework |

### Supporting
None beyond the above — no serializer library, no schema-generation library needed for this phase (project has no OpenAPI/drf-spectacular wiring yet; out of scope here).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `django-filter` `FilterSet` | Hand-rolled `queryset.filter(**request.query_params)` in the view | Rejected: no type coercion, no `gte`/`lte` range support out of the box, reinvents a solved problem — exactly the "Don't Hand-Roll" case CONTEXT.md already ruled on |
| `generics.ListAPIView`/`RetrieveAPIView` | `viewsets.ReadOnlyModelViewSet` + `DefaultRouter` | Rejected to match the existing `scoring/` app's explicit-`path()`-list convention (no router anywhere else in the project); viewsets would introduce a second URL-wiring style with no corresponding benefit for a 2-entity read-only surface |
| `ids` filter via `django_filters.BaseInFilter` | Bespoke `?ids=` parsing inside the view | `BaseInFilter` is the documented django-filter idiom for CSV-style "IN" filters and integrates with `FilterSet.Meta`/`OrderingFilter` cleanly rather than a special-cased view branch |

**Installation:**
```bash
pip install "django-filter>=26.1,<27.0"
```
Add to `requirements/base.txt` following the project's existing pinning convention (`>=X,<X+1` ranges, e.g. `Django>=5.2,<5.3`):
```
django-filter>=26.1,<27.0
```

**Version verification:** Confirmed via `pip index versions django-filter` against the live PyPI index on 2026-07-24 — 26.1 is the newest release (ahead of 25.2, 25.1, 24.3...). Confirmed via `https://pypi.org/pypi/django-filter/26.1/json` that its only hard requirement is `Django>=5.2` (the `djangorestframework` dependency is an optional `extra`, not a version-pinned requirement) — no conflict with the project's `djangorestframework>=3.15,<3.18` pin.

## Architecture Patterns

### Recommended Project Structure
```
players/
├── models.py            # existing — no changes needed
├── serializers.py        # NEW — PlayerListSerializer, PlayerDetailSerializer
├── filters.py             # NEW — PlayerFilter(django_filters.FilterSet)
├── views.py               # NEW — PlayerListView, PlayerDetailView
├── urls.py                # NEW — path("", ...), path("<uuid:pk>/", ...)
├── pagination.py          # NEW (or shared in core/) — StandardResultsPagination
└── tests/
    ├── conftest.py         # NEW — real_data_available fixture (mirror scoring/tests/conftest.py)
    ├── test_filters.py
    └── test_views.py

clubs/
├── models.py
├── serializers.py        # NEW — ClubListSerializer, ClubDetailSerializer (embeds squad + transfer aggregates)
├── filters.py
├── views.py
├── urls.py
└── tests/
    ├── conftest.py
    └── test_views.py
```
Consider putting the shared `StandardResultsPagination` class in `core/pagination.py` (the `core` app already exists as the shared-utility app per `INSTALLED_APPS`) rather than duplicating it in both `players/` and `clubs/` — both apps' list views need the identical 25/100 page-size config.

### Pattern 1: Settings wiring (additive, not replacing anything)
**What:** Add `django_filters` to `INSTALLED_APPS`, and add `DEFAULT_FILTER_BACKENDS`/`DEFAULT_PAGINATION_CLASS`/`PAGE_SIZE` to the existing `REST_FRAMEWORK` dict in `config/settings/base.py`.
**When to use:** Once, in this phase's settings task.
**Verified current state (config/settings/base.py, read 2026-07-24):**
```python
# CURRENT — no filter backend, no pagination class set:
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}
```
**Recommended addition (do not remove the existing two keys):**
```python
INSTALLED_APPS = [
    ...
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",   # NEW
    "clubs",
    "players",
    ...
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}
```
Note: `django_filters` does NOT strictly need to be in `INSTALLED_APPS` for the DRF integration to work (only its template-rendering/admin-integration features need it registered), but adding it is the documented convention and avoids surprises if the crispy-forms-style browsable-API filter form is ever used. Cheap to add, no downside.

### Pattern 2: FilterSet with range filters (Source: django-filter 26.1 docs, https://django-filter.readthedocs.io/en/latest/guide/rest_framework.html)
```python
# players/filters.py
import django_filters as filters

from players.models import Player


class IdsInFilter(filters.BaseInFilter, filters.UUIDFilter):
    """?ids=<uuid1>,<uuid2>,... -- CRUD-05 multi-fetch."""


class PlayerFilter(filters.FilterSet):
    ids = IdsInFilter(field_name="id")
    position = filters.CharFilter(field_name="position")  # the 10-value clean group -- see pitfall below
    league = filters.CharFilter(field_name="league")
    age_min = filters.NumberFilter(field_name="age", lookup_expr="gte")
    age_max = filters.NumberFilter(field_name="age", lookup_expr="lte")
    market_value_min = filters.NumberFilter(field_name="market_value", lookup_expr="gte")
    market_value_max = filters.NumberFilter(field_name="market_value", lookup_expr="lte")
    impact_score_min = filters.NumberFilter(field_name="impact_score", lookup_expr="gte")
    compatibility_score_min = filters.NumberFilter(field_name="compatibility_score", lookup_expr="gte")
    financial_fit_score_min = filters.NumberFilter(field_name="financial_fit_score", lookup_expr="gte")
    transfer_probability_score_min = filters.NumberFilter(field_name="transfer_probability_score", lookup_expr="gte")

    class Meta:
        model = Player
        fields = ["ids", "position", "league", "age_min", "age_max", "market_value_min", "market_value_max"]
```
`django_filters.rest_framework.DjangoFilterBackend` (the DRF-specific import path) and the bare `django_filters` (`import django_filters as filters`) top-level import both work for `FilterSet`/filter-class definitions — only the *backend* class needs the `.rest_framework` submodule path. Both forms appear in the official docs; either is fine, but views must import the backend from `django_filters.rest_framework`.

### Pattern 3: OrderingFilter (Source: DRF official docs, https://www.django-rest-framework.org/api-guide/filtering/#orderingfilter)
```python
class PlayerListView(generics.ListAPIView):
    queryset = Player.objects.all()
    serializer_class = PlayerListSerializer
    filterset_class = PlayerFilter
    ordering_fields = [
        "age", "market_value",
        "impact_score", "compatibility_score", "financial_fit_score", "transfer_probability_score",
    ]
    ordering = ["-impact_score"]  # sane default so an unordered page isn't Postgres's arbitrary insertion order
```

### Pattern 4: Capped client-adjustable pagination, bypassed for `ids` multi-fetch (Source: DRF official docs, https://www.django-rest-framework.org/api-guide/pagination/#pagenumberpagination)
```python
# core/pagination.py
from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class IdsBypassPagination(StandardResultsPagination):
    """CRUD-05: when ?ids=... is present, the caller named an exact, bounded
    set -- return it unpaginated rather than forcing a second page-2 request
    for a 3-5 item comparison."""

    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get("ids"):
            return None  # DRF's generics.ListAPIView.list() returns Response(serializer.data) directly when this is None
        return super().paginate_queryset(queryset, request, view)
```
This is the standard, documented way to conditionally skip pagination in DRF — `paginate_queryset` returning `None` is explicitly the "don't paginate this response" signal `GenericAPIView.list()`/`ListModelMixin.list()` checks for; no need to hand-roll a custom `list()` override.

**Discretionary recommendation:** cap `ids` at 100 (matching `max_page_size`) via `PlayerFilter.clean()` or a view-level check that returns `400` if more than 100 ids are supplied — prevents an accidentally enormous unpaginated response (CONTEXT.md flags this as open discretion).

### Pattern 5: Club detail embedding squad + transfer aggregates (live ORM aggregation, not cached)
```python
# clubs/serializers.py
from django.db.models import Avg, Count, Sum

from players.serializers import PlayerListSerializer
from transfers.models import Transfer


class ClubDetailSerializer(serializers.ModelSerializer):
    squad = serializers.SerializerMethodField()
    transfer_aggregates = serializers.SerializerMethodField()

    def get_squad(self, club):
        return PlayerListSerializer(club.players.all(), many=True).data  # related_name="players", verified

    def get_transfer_aggregates(self, club):
        qs = Transfer.objects.filter(club=club)
        return {
            "total_transfers": qs.count(),
            "arrivals": qs.filter(movement="arrival").count(),
            "departures": qs.filter(movement="departure").count(),
            "avg_market_value_at_transfer": qs.aggregate(v=Avg("market_value_at_transfer"))["v"],
            "total_market_value_at_transfer": qs.aggregate(v=Sum("market_value_at_transfer"))["v"],
            "by_window": list(qs.values("window").annotate(count=Count("id"))),
        }
```
`movement` has exactly 2 real values (`"arrival"`, `"departure"`) and `window` has exactly 2 (`"Summer"`, `"Winter"`) — verified against the live dev DB (47,201 real Transfer rows, 0 with `club=null`, 0 with `market_value_at_transfer=null`), so these aggregates need no null-handling beyond Django's own `Avg`/`Sum` returning `None` on an empty queryset (a club with zero transfers) — which is correct "null means null" behavior, not a bug to work around.

### Pattern 6: Player detail's club=None edge case (structurally possible, not currently present)
```python
# players/views.py (sketch)
def get(self, request, pk):
    player = get_object_or_404(Player, id=pk)
    club_id = request.query_params.get("club_id") or player.club_id
    if club_id is None:
        # No club to evaluate CS/TFM/TP against -- get_summary() would 404 on
        # a None club_id via resolve_club_name(). Never fabricate a fake club
        # context; return the RMM-only breakdown (context-free, see rmm.py)
        # plus explicit null+reason for the 3 club-dependent scores.
        breakdown = {
            "rmm": rmm.get_rmm(pk),
            "compatibility": null_with_reason("compatibility_score", "player_has_no_club"),
            "financial_fit": null_with_reason("financial_fit", "player_has_no_club"),
            "transfer_probability": null_with_reason("transfer_probability", "player_has_no_club"),
        }
    else:
        breakdown = summary.get_summary(pk, club_id)
    ...
```
Verified this is the correct behavior, not a hypothetical: `scoring.services.summary.get_summary(player_id, club_id)` calls `resolve_club_name(club_id)` as its first line, which does `get_object_or_404(Club, id=club_id)` — passing `club_id=None` raises `Http404` (a `Club` `UUIDField` lookup against `None` never matches), which would incorrectly turn "player has no club" into a fake "player/club not found" 404 on the whole detail endpoint. `scoring.services.rmm.get_rmm(player_id)` is documented as "the only Phase 4 score needing no club context" and works unconditionally. `scoring.exceptions.null_with_reason(field, code)` is the exact shared envelope shape (`{"<field>": None, "reason": "<code>"}`) already used by every other score service — reuse it verbatim rather than inventing a new null shape for this one call site.

**Currently a non-issue in practice:** live dev DB query confirms `Player.objects.filter(club__isnull=True).count() == 0` — all 41,708 players have a club today. Still worth the defensive branch since `Player.club` is `on_delete=models.SET_NULL, null=True` (a future club deletion, or a future data refresh, could produce one), and CONTEXT.md's "never fabricate — null means null" invariant applies here exactly as it did to Phase 3-6's score computations.

### Anti-Patterns to Avoid
- **Filtering position on `main_position`:** `main_position` holds 22 fine-grained values (`AMF`, `LCB`, `RWB`, `RDMF`, ...) plus a literal `"0"` placeholder for 1 known-bad row — not the clean 10-value group ROADMAP's "filter by position" implies. Use `Player.position` instead (verified: matches `PlayerRoleScore.position_group`'s 9 real values, and is the field the model's own `Meta.indexes` already indexes).
- **Re-deriving score breakdowns instead of calling `get_summary`:** would duplicate ~100 lines of merge/slice logic Plan 4-6 already built and tested for parity; also loses the Phase 6 own-club fast path.
- **Passing `player.club_id` straight into `get_summary` without a None-guard:** produces a misleading `404 Not Found` for a legitimately-club-less player instead of a correct `200` with null-with-reason scores.
- **Aggregating `Transfer.fee`:** it's a free-text `CharField` (`"Free"`, `"loan"`, currency strings) — `Sum`/`Avg` on it will raise a database error or silently coerce garbage. Use `market_value_at_transfer` only (locked decision, also independently verified: 0 nulls across all 47,201 real rows, safe to aggregate directly).
- **Confusing `PlayerClubCompatibility` (Phase 1's raw CSV-imported legacy compatibility table, 8.1M rows, `players/models.py`) with Phase 6's live `Player.compatibility_score` field:** they are different tables/fields with similar names. Phase 7's list/detail serializers should read the denormalized `Player.compatibility_score` field and `scoring.services.summary`, never `PlayerClubCompatibility` directly — that table is Phase 1 migration provenance data, not part of this phase's read surface.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Range/threshold filtering (age, market_value, 4 scores) | Manual `if request.query_params.get(...)` chains building `.filter()` kwargs | `django_filters.FilterSet` with `NumberFilter(lookup_expr="gte"/"lte")` | Type coercion, validation errors as proper 400s, composability with `OrderingFilter`, already the locked stack choice |
| `?ids=uuid1,uuid2,...` CSV-to-list parsing | Bespoke `request.query_params.get("ids").split(",")` + manual UUID validation in the view | `django_filters.BaseInFilter` + `UUIDFilter` composed together | Documented django-filter idiom, integrates into the same `FilterSet`/`Meta` machinery, gets consistent 400s on malformed UUIDs for free |
| Score breakdown assembly for Player detail | Re-slicing `pop.players_df`/`cs_tp`/`scored` frames directly in `players/views.py` | `scoring.services.summary.get_summary(player_id, club_id)` | Already built, already fast (~0.2s post-Phase-6), already parity-tested in Phase 5 — re-deriving here duplicates tested logic and risks silently drifting from it |
| Skipping pagination conditionally | Custom `list()` override that branches on query params | `paginate_queryset()` returning `None` | The documented DRF mechanism `ListModelMixin.list()` already checks for |

**Key insight:** Every "don't hand-roll" item here has an existing, already-verified building block in this codebase or in `django-filter`/DRF itself — this phase is assembly, not invention, matching CONTEXT.md's explicit framing of Phase 7 as "the read/browse layer on top of everything built so far."

## Common Pitfalls

### Pitfall 1: Filtering/ordering by the wrong "position" field
**What goes wrong:** A plan that filters `Player.main_position` for CRUD-01's "filter by position" returns confusing fine-grained results (`RCB` vs `LCB` as separate values) and misses the intended coarse-group semantics ROADMAP describes.
**Why it happens:** `docs/FIELD_MAPPING.md`'s section 1a docstring for `Main_Position` says it's "the single position group... AM, CB, CM, DM, FWD, LB, LW, RB, RW, GK" — this description was written before/without verifying the actual imported values, and is backwards from what the real CSV/DB contains.
**How to avoid:** Use `Player.position` (verified 10 real distinct values matching `PlayerRoleScore.position_group`, and already indexed) as the primary `position` filter. Optionally expose `main_position` as a secondary, more granular filter dimension if the plan wants it (Claude's Discretion territory), but never as the sole/primary one.
**Warning signs:** A test asserting `?position=CB` returns Center Backs but silently missing `LCB`/`RCB`-tagged rows (because it filtered `main_position` instead) would be the symptom.

### Pitfall 2: Passing `club_id=None` through to `get_summary()`
**What goes wrong:** `Http404` raised for a legitimate player (misleading — looks like "player not found" when it's really "no club to evaluate against").
**Why it happens:** `resolve_club_name(None)` does `get_object_or_404(Club, id=None)`, which never matches any row.
**How to avoid:** Branch explicitly before calling `get_summary`; use `rmm.get_rmm()` + `null_with_reason()` for the club-less case (see Pattern 6 above).
**Warning signs:** A previously-working detail endpoint suddenly 404ing after a data refresh that nulls out some `club` FKs (e.g. a club gets deleted) would be the symptom in production.

### Pitfall 3: Aggregating `Transfer.fee` instead of `market_value_at_transfer`
**What goes wrong:** `Sum`/`Avg` on a `CharField` containing `"Free"`/`"loan"`/currency-formatted strings either raises a Postgres type error or (if Django coerces first) produces nonsense.
**Why it happens:** `fee` is the more "obviously named" field for "how much did this transfer cost" — easy to reach for by instinct.
**How to avoid:** Aggregate `market_value_at_transfer` only (a clean `BigIntegerField`, verified 0 nulls across all 47,201 real rows); keep `fee` as a raw per-record display string.
**Warning signs:** A `django.db.utils.DataError` or `ProgrammingError` on the Club detail endpoint the first time it's hit against real data.

### Pitfall 4: Overwriting the existing `REST_FRAMEWORK` settings dict
**What goes wrong:** A naive settings edit that replaces the whole `REST_FRAMEWORK = {...}` block (rather than adding keys to it) silently drops `DEFAULT_AUTHENTICATION_CLASSES`/`DEFAULT_PERMISSION_CLASSES`, breaking the project's deny-by-default posture (AUTH-02/AUTH-03) for every existing endpoint, not just this phase's new ones.
**Why it happens:** Copy-pasting a django-filter tutorial's `REST_FRAMEWORK = {...}` snippet verbatim over the existing one.
**How to avoid:** Add `DEFAULT_FILTER_BACKENDS`/`DEFAULT_PAGINATION_CLASS`/`PAGE_SIZE` as new keys inside the existing dict (see Pattern 1) — verified current state has neither key set, so this is purely additive, zero risk of collision.
**Warning signs:** `scoring/tests/test_views.py::test_endpoints_require_authentication` (or any Phase 2/4 auth test) starting to fail after this phase's settings changes.

### Pitfall 5: Assuming Club playing-style fields are always present
**What goes wrong:** A CRUD-02 "filter by playing style" implementation that does e.g. `?tiki_taka__gte=0.5` silently excludes ~77.4% of clubs (the ones with no Playstyles.csv coverage) without the caller realizing that's a data-coverage artifact, not "no clubs play tiki-taka."
**Why it happens:** The 8 playing-style `FloatField`s are `null=True` by design (verified in `clubs/models.py`'s own docstring: "Only ~22.6% of clubs have coverage here — nulls are expected, not a data quality failure").
**How to avoid:** Document this in the endpoint's behavior (filtering on a playing-style field inherently excludes null-coverage clubs — that's correct, not a bug) rather than trying to zero-fill or otherwise paper over the null rate.
**Warning signs:** A test asserting Club list returns "most" clubs when filtered by a playing-style threshold and getting suspiciously few.

## Code Examples

### Verified: `related_name` for Player→Club and Transfer→Club reverse queries
```python
# players/models.py — Player.club FK:
club = models.ForeignKey("clubs.Club", on_delete=models.SET_NULL, null=True, blank=True, related_name="players")

# transfers/models.py — Transfer.club FK:
club = models.ForeignKey("clubs.Club", on_delete=models.SET_NULL, null=True, blank=True, related_name="transfers")
```
Live-verified via `manage.py shell` against the real dev DB: `club.players.count()` and `club.transfers.count()` both work as expected (no `club.player_set`/`club.transfer_set` fallback needed — CONTEXT.md's task brief flagged this as an open question; it is resolved: named `related_name`s exist on both FKs).

### Verified real-data facts used above (manage.py shell, live dev DB, 2026-07-24)
```
players 41708 | clubs 1060 | transfers 47201
distinct Player.position: ['AM','CB','CM','DM','FWD','GK','LB','LW','RB','RW']  (+ 1 null row)
distinct Player.main_position: 22 values incl. 'AMF','LCB','RWB','RDMF', + 1 literal '0' row
distinct PlayerRoleScore.position_group: ['AM','CB','CM','DM','FWD','LB','LW','RB','RW']  (matches .position, not .main_position)
players with club__isnull=True: 0  (all 41,708 have a club today; FK is still nullable)
distinct Player.season: ['2024-2025','2023-2024','2022-2023','Last Calendar Year']
Transfer.movement distinct: ['arrival','departure']
Transfer.window distinct: ['Winter','Summer']
Transfer.market_value_at_transfer nulls: 0 / 47201
Transfer.club__isnull: 0 / 47201
```

### Existing thin-view convention to match (Source: scoring/views.py, verified current file)
```python
class PlayerImpactView(APIView):
    def get(self, request, player_id):
        get_object_or_404(Player, id=player_id)
        return Response(rmm.get_rmm(player_id))
```
No `try/except` wrapping service calls — `Http404` and any reconstruction `ValueError` are left to propagate (404/500), matching this phase's views too.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| django-filter's built-in DRF `AutoSchema`/coreapi schema generation | Removed in django-filter 26.x; use `drf-spectacular` if OpenAPI schema generation is ever needed | django-filter 23.2 deprecated it, removed by 26.x | Not relevant to this phase (project has no schema generation wired), but worth knowing if a later phase adds `drf-spectacular` |

**Deprecated/outdated:** None else relevant — `django-filter`, DRF `generics`, `PageNumberPagination`, and `OrderingFilter` are all current, actively maintained, non-deprecated APIs as of this research date.

## Open Questions

1. **Should `main_position` also be exposed as a filter, alongside the primary `position` filter?**
   - What we know: `position` is the correct primary "position group" filter (verified above); `main_position` is a real, populated field with finer granularity that some users might want.
   - What's unclear: Whether product value justifies exposing both dimensions in v1, or whether it adds confusing surface area.
   - Recommendation: Ship `position` as the only position filter for CRUD-01 (matches ROADMAP's literal wording and the role-score taxonomy); leave `main_position`/`positions` (multi-value list) as Claude's Discretion additions if the planner judges them low-risk/high-value — they are NOT required by CRUD-01.

2. **Should new DB indexes be added for `Player.league`, `Club.league`, `Club.country`?**
   - What we know: None of these three fields are currently indexed (verified against `Player.Meta.indexes` and the absence of any `Meta` class on `Club`). At current scale (41,708 players / 1,060 clubs), a sequential scan filter on any of these is sub-10ms in Postgres — not a performance problem today.
   - What's unclear: Whether the phase should proactively add indexes as good practice for a "core CRUD" phase, vs. leaving it as a future optimization once real usage patterns are known.
   - Recommendation: Not required to satisfy CRUD-01/02 at this data scale; treat as a nice-to-have, low-priority addition the planner can include opportunistically (cheap migration) but should not block the phase on.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-django 4.12.0 |
| Config file | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`) — `DJANGO_SETTINGS_MODULE = "config.settings.local"`, `testpaths = ["clubs", "players", "transfers", "core", "accounts", "scoring"]` |
| Quick run command | `cd get-scouted-be && source .venv/bin/activate && pytest players/tests/ clubs/tests/ -x` |
| Full suite command | `cd get-scouted-be && source .venv/bin/activate && pytest` |

Critical environment fact: pytest-django's own test database (`test_getscouted`) is created empty each session — Phase 1's migrated real data (41,708 players etc.) lives only in the dev DB (`getscouted`), never copied into the test DB. Real-data assertions MUST use the `django_db_blocker.unblock()` module-scope-fixture pattern (see below), not the plain `db`/`django_db` fixtures, which only see the empty test DB.

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| CRUD-01 | Player list filters/sorts/paginates by position/age/market_value/league/score thresholds | integration (real data) | `pytest players/tests/test_views.py -k list -x` | ❌ Wave 0 |
| CRUD-02 | Club list filters by league/country/playing style | integration (real data) | `pytest clubs/tests/test_views.py -k list -x` | ❌ Wave 0 |
| CRUD-03 | Player detail returns full profile + season + score breakdowns (incl. club=None edge case) | integration (real data) | `pytest players/tests/test_views.py -k detail -x` | ❌ Wave 0 |
| CRUD-04 | Club detail returns full profile + squad + transfer aggregates | integration (real data) | `pytest clubs/tests/test_views.py -k detail -x` | ❌ Wave 0 |
| CRUD-05 | Multi-fetch via `?ids=` returns unpaginated exact set, for both players and clubs | integration (real data) | `pytest players/tests/test_views.py clubs/tests/test_views.py -k ids -x` | ❌ Wave 0 |
| (cross-cutting) | Unauthenticated request denied on every new endpoint | unit | `pytest players/tests/test_views.py clubs/tests/test_views.py -k authentication -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest players/tests/ clubs/tests/ -x` (fast subset)
- **Per wave merge:** `pytest` (full suite — pytest-django tears down/rebuilds `test_getscouted`, so this stays fast; only the manually-triggered real-data module-scope fixtures pay the real-DB cost, and only when the dev DB has data)
- **Phase gate:** Full suite green before `/gsd:verify-work`, plus at least one `manage.py shell`-driven live check against the real dev DB per success criterion (matching every prior phase's own verification pattern in STATE.md)

### Wave 0 Gaps
- [ ] `players/tests/conftest.py` — needs its own `real_data_available` fixture (mirror `scoring/tests/conftest.py`'s implementation verbatim; it is NOT automatically visible to `players/tests/` since pytest only auto-discovers a `conftest.py`'s fixtures within the same directory or a descendant — `scoring/tests/` is a sibling, not an ancestor, of `players/tests/`)
- [ ] `clubs/tests/conftest.py` — same real_data_available fixture, club-scoped
- [ ] `players/tests/test_views.py`, `clubs/tests/test_views.py` — new files, follow `scoring/tests/test_views.py`'s `auth_client` fixture pattern (force-authenticate a real `accounts.User`) verbatim
- [ ] For any test needing the expensive real-population reconstruction (none of CRUD-01/02/04/05 do — they're plain ORM queries; only CRUD-03's `get_summary` call does), reuse the `django_db_blocker.unblock()` module-scope pattern from `scoring/tests/test_parity_bulk.py`'s `bulk_scored` fixture
- [ ] No new test framework/dependency install needed — pytest/pytest-django are already fully configured project-wide

## Sources

### Primary (HIGH confidence)
- Live codebase read 2026-07-24: `players/models.py`, `clubs/models.py`, `transfers/models.py`, `config/settings/base.py`, `scoring/views.py`, `scoring/urls.py`, `scoring/services/summary.py`, `scoring/services/population.py`, `scoring/services/rmm.py`, `scoring/services/financial_fit.py`, `scoring/exceptions.py`, `scoring/tests/test_views.py`, `scoring/tests/conftest.py`, `scoring/tests/test_parity_bulk.py`, `players/management/commands/import_players.py`, `docs/FIELD_MAPPING.md`, `pyproject.toml`, `requirements/base.txt`
- Live dev DB query (`manage.py shell`, real migrated data, 2026-07-24) — all facts under "Verified real-data facts" above
- `pip index versions django-filter` + `https://pypi.org/pypi/django-filter/26.1/json` (live PyPI queries, 2026-07-24) — version + dependency constraints
- `pip show djangorestframework django-environ djangorestframework_simplejwt psycopg pytest-django` inside the project's `.venv` (2026-07-24) — installed version confirmation
- [DRF Pagination official docs](https://www.django-rest-framework.org/api-guide/pagination/) — `PageNumberPagination` config keys
- [django-filter 26.1 DRF integration guide](https://django-filter.readthedocs.io/en/latest/guide/rest_framework.html) — `DEFAULT_FILTER_BACKENDS`, `FilterSet`/`NumberFilter` patterns

### Secondary (MEDIUM confidence)
- [django-filter Migration Guide](https://django-filter.readthedocs.io/en/latest/guide/migration.html) — schema-generation removal note (WebSearch summary, not independently re-verified against the full changelog text, but consistent with the PyPI release cadence observed)

### Tertiary (LOW confidence)
None — every claim in this document was either read directly from the live codebase/dev DB or verified against current official docs/PyPI metadata.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versions/compatibility verified live against PyPI and the project's own `.venv`, not training-data assumptions
- Architecture: HIGH — every pattern either matches an existing verified project convention (`scoring/views.py`'s thin-view style) or is a documented django-filter/DRF idiom fetched from current official docs
- Pitfalls: HIGH — the position-field pitfall and the club=None edge case were both independently confirmed against live dev-DB query results, not assumptions carried over from CONTEXT.md's framing

**Research date:** 2026-07-24
**Valid until:** 30 days (stable Django/DRF/django-filter stack; re-check django-filter's latest version if planning is delayed past ~2026-08-24)
