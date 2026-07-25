# Phase 8: User Workspace CRUD - Research

**Researched:** 2026-07-25
**Domain:** Django/DRF — user-owned CRUD resources, object-level permissions, synchronous CSV export
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

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


### Deferred Ideas (OUT OF SCOPE)

- Actually computing recalculated squad metrics (avg age, avg score, budget/wage impact) from `SquadPlan.proposed_changes` — that's Phase 11's job explicitly; this phase only stores the delta.
- Director/admin visibility into other users' workspaces — not asked for by any Phase 8 success criterion; would be a new capability if ever wanted, its own future decision.
- CSV export format alternatives (XLSX, PDF) — ROADMAP's CRUD-10 explicitly says CSV; the legacy script's `export_team_shortlist_xlsx` (found during Phase 3's characterization) is not being revived here.
- Retention/pruning policy for `RecentActivity` — left as Claude's Discretion for the planner, not a locked requirement.

</user_constraints>

## Summary

Phase 8 adds a single new Django app, `workspace/`, holding four models (`Watchlist`, `Shortlist`+`ShortlistEntry`, `SquadPlan`, `RecentActivity`) that are all owned by `accounts.User` and follow this project's already-established conventions almost mechanically: UUID PKs, `on_delete` choices matching the existing FK style, `models.UniqueConstraint`/`models.Index` in `Meta` (not the legacy `unique_together` tuple), DRF generic/viewset classes composed from selective mixins (the `AdminUserViewSet` precedent), explicit per-view `pagination_class` (no project-wide default), and zero new third-party dependencies — `django-filter`, DRF's own validators, and the stdlib `csv` module cover every requirement in CRUD-06 through CRUD-10.

The two things that need the most planning precision are (1) **object-level ownership must be paired with queryset scoping** — DRF's `has_object_permission` only fires on detail actions (retrieve/update/destroy), never on `list`/`create`, so every workspace `get_queryset()` MUST filter by `request.user` or the `IsOwner` permission alone will silently leak every user's data on list endpoints — and (2) **`ShortlistEntry` has no direct `user` FK** (ownership is via `shortlist.user`), so the new `IsOwner` permission needs a small polymorphic owner-resolution step beyond a literal copy of `IsSelfOrAdmin`. Both are documented below with concrete code.

**Primary recommendation:** One `workspace` app; `IsOwner` object-level permission (adapted from `IsSelfOrAdmin`, admin clause dropped, polymorphic owner lookup added) combined with mandatory `get_queryset()` scoping on every view; DRF `ModelViewSet`/mixin composition registered via `DefaultRouter` under `/api/workspace/`, mirroring `accounts/urls.py`; `RecentActivity` written by a direct, explicit ORM `.create()` call inserted into the existing `PlayerDetailView.get()` / `ClubDetailView.retrieve()` (override `retrieve()`, since `ClubDetailView` is a `RetrieveAPIView`, not a plain `APIView`); CSV export via Django's documented `StreamingHttpResponse` + `Echo` pseudo-buffer + `csv.writer` pattern, no new package.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CRUD-06 | User can save/remove players to/from a personal Watchlist | Per-`(user, player)` row model + `ListModelMixin`/`CreateModelMixin`/`DestroyModelMixin` viewset (mirrors `AdminUserViewSet`'s selective-mixin pattern) + `UniqueConstraint` + `HiddenField(default=CurrentUserDefault())` for auto per-user-uniqueness validation (DRF Validators docs, verified) |
| CRUD-07 | User can create, name, and manage Shortlists tied to a club context | `Shortlist` (full `ModelViewSet`) + `ShortlistEntry` (nested `@action` routes on `ShortlistViewSet`, no `drf-nested-routers` dependency — none is installed) |
| CRUD-08 | User can create and manage Squad Plans (formation, current squad, proposed changes) | `SquadPlan` model with `proposed_changes` `JSONField` + serializer-level structural validation; "current squad" computed live via `PlayerListSerializer(club.players.all())` (exact `ClubDetailSerializer.get_squad` pattern reused), not stored |
| CRUD-09 | User's Recent Activity (searches, viewed players) is recorded and retrievable | Explicit `.create()` write inserted into `PlayerDetailView.get()` and `ClubDetailView.retrieve()` (override needed — see Architecture Patterns); read-only `ListAPIView` scoped to `request.user`, ordered `-created_at` |
| CRUD-10 | User can export a Shortlist or Club report as CSV | Django's documented `StreamingHttpResponse` + `Echo` + `csv.writer` pattern (verified against current official docs); Shortlist export lives on `workspace` app (`IsOwner`-gated); Club report export lives on `clubs` app (`IsAuthenticated`-only — club data isn't user-owned) |
</phase_requirements>

## Verified Current Codebase State (confirmed by direct read, not assumed)

- **`accounts/permissions.py`** — `MinimumRole(role)` factory (`ROLE_RANK` dict, `has_permission` only) and `IsSelfOrAdmin` (`has_object_permission` only, `return obj == request.user or request.user.role == "admin"`). Exact current file reproduced below under Code Examples.
- **`players/views.py::PlayerDetailView`** — a plain `APIView` (not a generic view), `.get(self, request, pk)`. Fetches `player = get_object_or_404(Player, id=pk)`, then branches on `club_id` before returning `Response({**profile, "scores": scores})`. No `permission_classes` set (relies on global `IsAuthenticated`).
- **`clubs/views.py::ClubDetailView`** — `generics.RetrieveAPIView`, `queryset = Club.objects.all()`, `serializer_class = ClubDetailSerializer`, `lookup_field = "pk"`. No custom `get`/`retrieve` override exists yet — one must be added.
- **`clubs/serializers.py::ClubDetailSerializer`** — `get_transfer_aggregates` reads `Transfer.market_value_at_transfer` only, confirmed never `Transfer.fee`. `get_squad` returns `PlayerListSerializer(club.players.all(), many=True).data` (`related_name="players"`).
- **`players/serializers.py::PlayerListSerializer`** fields: `id, player, position, main_position, league, club, club_name, age, market_value, impact_score, compatibility_score, financial_fit_score, transfer_probability_score` — directly reusable verbatim for Squad Plan's current-squad view and Shortlist CSV columns, exactly as CONTEXT.md states.
- **`core/pagination.py`** — `StandardResultsPagination` (25/page, `page_size` param, max 100) and `IdsBypassPagination` (bypasses pagination when `?ids=` present). Deliberately **not** wired as `DEFAULT_PAGINATION_CLASS`; every list view opts in explicitly via `pagination_class = ...`.
- **`config/settings/base.py`** — `REST_FRAMEWORK` sets `DEFAULT_AUTHENTICATION_CLASSES=[JWTAuthentication]`, `DEFAULT_PERMISSION_CLASSES=[IsAuthenticated]`, `DEFAULT_FILTER_BACKENDS=[DjangoFilterBackend, OrderingFilter]`. No `DEFAULT_PAGINATION_CLASS` (deliberate, confirmed by inline comment referencing the real Phase 7 regression against `/api/auth/admin/users/`).
- **`config/urls.py`** — flat `path("api/<app>/", include("<app>.urls"))` list; `api/workspace/` needs to be appended here.
- **`accounts/urls.py`** — the router-composition precedent to copy: `router = DefaultRouter(); router.register("admin/users", AdminUserViewSet, basename="admin-users")`, then `urlpatterns = [...] + router.urls`.
- **`accounts/views.py::AdminUserViewSet`** — the strongest existing precedent for this phase's viewsets: selective mixins (`ListModelMixin, RetrieveModelMixin, UpdateModelMixin, GenericViewSet` — no create/destroy mixin), `get_permissions()` overridden per-action, and a custom `@action(detail=True, methods=["post"])` (`deactivate`) — the exact mechanism to use for Shortlist's nested `entries` route and both CSV `export` routes.
- **`Player`/`Club`/`PlayerRoleScore`/`PlayerClubCompatibility` models** — **`Meta.constraints = [models.UniqueConstraint(...)]`** and **`Meta.indexes = [models.Index(...)]`** are the established convention throughout this codebase. No model anywhere uses the legacy `unique_together = (...)` tuple, even though 08-CONTEXT.md's prose says "`unique_together = ("user", "player")`" for `Watchlist` — that phrasing describes the *constraint*, not literally the deprecated Django API. **Follow the codebase's actual convention (`UniqueConstraint`)**, not the literal string in CONTEXT.md; DRF's automatic per-serializer validator generation supports `UniqueConstraint` (added DRF 3.11+) exactly the same as the old tuple, so nothing is lost.
- **`django-filter` 26.1** is installed and registered (`INSTALLED_APPS = [..., "django_filters", ...]`), and `DjangoFilterBackend` is already a global default filter backend — so a view only needs a `filterset_class` if it actually wants filtering; declaring none is harmless (backend runs, does nothing).
- **No `drf-nested-routers` package is installed** (checked `requirements/base.txt` and `requirements/dev.txt` — only `Django`, `djangorestframework`, `psycopg`, `django-environ`, `pandas`, `djangorestframework-simplejwt`, `scikit-learn`, `joblib`, `django-filter`). Nested Shortlist→Entry routes must use plain DRF `@action` routes, not a new nested-router dependency.
- **No `StreamingHttpResponse` or CSV-response code exists anywhere in the codebase yet** (only CSV *importing*, via stdlib `csv`/`pandas`, in the Phase-1 management commands) — this is genuinely new ground for the project, verified against Django's own current docs below.
- **Django 5.2.16, DRF 3.15.2** confirmed installed in the project's `.venv` (not just the `>=` floor in `requirements/base.txt`).
- **Test conventions**: `players/tests/conftest.py`'s `real_data_available` fixture (skip-if-empty pattern for real-dataset-dependent tests) and `accounts/tests/conftest.py`'s `UserFactory` + `authenticated_client(role=...)` fixture (real JWT via `RefreshToken.for_user`, not `force_authenticate`, in most Phase 7/2 tests — though `players/tests/test_views.py` also shows a simpler `force_authenticate`-based `auth_client` fixture used alongside it). Workspace tests should import `UserFactory`/`authenticated_client` from `accounts/tests/conftest.py`'s pattern (pytest auto-discovers conftest fixtures only within an app's own test dir or descendants — per Phase 1's decision, a **new** `workspace/tests/conftest.py` with its own thin fixtures, or reuse via explicit import, will be needed; conftest fixtures are NOT automatically shared cross-app in this repo).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.2.16 (already installed) | ORM, `StreamingHttpResponse` | Already the project's framework; no new version needed |
| djangorestframework | 3.15.2 (already installed) | ViewSets, serializers, validators | Already the project's API framework |
| django-filter | 26.1 (already installed) | Optional list filtering | Already installed/registered; not required for this phase's minimal filtering needs (see Don't Hand-Roll / Open Questions) |

### Supporting
None — no new packages required. Confirmed by reading `requirements/base.txt` and `requirements/dev.txt`.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plain `@action` nested routes for `ShortlistEntry` | `drf-nested-routers` | Not installed; would be the first new dependency added purely for URL sugar — against this project's Phase 6 "don't add infra without a forcing reason" pattern that 08-CONTEXT.md explicitly cites for the CSV-export decision |
| `StreamingHttpResponse` + stdlib `csv` | `django-import-export`, `django-tablib`, `drf-renderer-csv` | 08-CONTEXT.md already locked stdlib `csv` + `StreamingHttpResponse`; a rendering library would be unnecessary weight for two bounded, simple export shapes |
| `models.UniqueConstraint` in `Meta.constraints` | legacy `unique_together = (...)` tuple | Codebase convention (`PlayerRoleScore`, `PlayerClubCompatibility`) uses `UniqueConstraint` exclusively; DRF's serializer auto-validator supports both equally |

**Installation:**
```bash
# No installation needed — everything required is already in requirements/base.txt
```

**Version verification:**
```
$ pip show djangorestframework  →  Version: 3.15.2
$ python -c "import django; print(django.VERSION)"  →  (5, 2, 16, 'final', 0)
```
Both confirmed live against the project's `.venv`, matching the `>=5.2,<5.3` / `>=3.15,<3.18` pins in `requirements/base.txt`. No staleness risk — these are the exact versions Phase 7 was built and tested against.

## Architecture Patterns

### Recommended Project Structure
```
get-scouted-be/
└── workspace/
    ├── __init__.py
    ├── apps.py
    ├── models.py           # Watchlist, Shortlist, ShortlistEntry, SquadPlan, RecentActivity
    ├── permissions.py       # IsOwner
    ├── serializers.py       # one serializer per model + a SquadPlanDetailSerializer variant
    ├── filters.py            # only if a real filtering need is found (see Open Questions) — likely skip
    ├── views.py              # WatchlistViewSet, ShortlistViewSet, SquadPlanViewSet, RecentActivityListView
    ├── urls.py                # DefaultRouter + explicit RecentActivity path, mirrors accounts/urls.py
    ├── migrations/
    │   └── 0001_initial.py
    └── tests/
        ├── __init__.py
        ├── conftest.py
        ├── test_watchlist.py
        ├── test_shortlists.py
        ├── test_squad_plans.py
        ├── test_recent_activity.py
        └── test_csv_export.py

# Modified, not new:
clubs/views.py     # add ClubReportExportView (or an action) for CRUD-10's club-report half
clubs/urls.py      # register the export route
clubs/views.py::ClubDetailView   # override retrieve() to log RecentActivity
players/views.py::PlayerDetailView   # add one explicit .create() call inside get()
config/settings/base.py  # add "workspace" to INSTALLED_APPS
config/urls.py            # add path("api/workspace/", include("workspace.urls"))
```

### Pattern 1: `IsOwner` — adapted from `IsSelfOrAdmin`, with polymorphic owner resolution

**What:** A single `BasePermission` subclass, same shape as `IsSelfOrAdmin` (one `has_object_permission` method, no admin override), but resolving "owner" differently depending on whether the object has a direct `user` FK (`Watchlist`, `Shortlist`, `SquadPlan`, `RecentActivity`) or only an indirect one via `shortlist.user` (`ShortlistEntry`).

**When to use:** Every workspace detail action (retrieve/update/destroy). **Not sufficient alone for list/create** — see Common Pitfalls.

**Example:**
```python
# workspace/permissions.py — adapted from accounts/permissions.py::IsSelfOrAdmin
# (verified current shape, read directly 2026-07-25):
#
#     class IsSelfOrAdmin(BasePermission):
#         def has_object_permission(self, request, view, obj):
#             return obj == request.user or request.user.role == "admin"
#
# IsOwner drops the admin-override clause per 08-CONTEXT.md, and adds
# polymorphic owner resolution since ShortlistEntry has no direct `user` FK.
from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object-level: a user may act only on their own workspace data.

    Most workspace models (Watchlist, Shortlist, SquadPlan, RecentActivity)
    have a direct `user` FK. ShortlistEntry does not (ownership flows through
    `shortlist.user`) -- resolved here rather than denormalizing a redundant
    `user` FK onto ShortlistEntry.
    """

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        if owner is None and hasattr(obj, "shortlist"):
            owner = obj.shortlist.user
        return owner == request.user
```

### Pattern 2: Mandatory `get_queryset()` scoping (has_object_permission is NOT enough)

**What:** `IsOwner.has_object_permission` only runs for actions DRF calls `check_object_permissions` on — `retrieve`, `update`, `partial_update`, `destroy`. It is **never called for `list` or `create`**. Every workspace `ViewSet`/`ListAPIView` MUST also override `get_queryset()` to filter by `self.request.user`, or `list` silently returns every user's rows.

**Example:**
```python
# workspace/views.py
from rest_framework import mixins, viewsets

from workspace.models import Watchlist
from workspace.permissions import IsOwner
from workspace.serializers import WatchlistSerializer


class WatchlistViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """/api/workspace/watchlist/ -- CRUD-06. No update mixin: a watchlist
    row is add/remove only, mirroring AdminUserViewSet's selective-mixin
    composition (no create/destroy mixins there; the inverse selection here).
    """

    serializer_class = WatchlistSerializer
    permission_classes = [IsOwner]

    def get_queryset(self):
        # CRITICAL: IsOwner.has_object_permission never runs for list/create.
        # Without this filter, list() would return every user's watchlist.
        return Watchlist.objects.filter(user=self.request.user).order_by("-added_at")
```

### Pattern 3: Per-user uniqueness via `HiddenField(default=CurrentUserDefault())`

**What:** DRF's documented mechanism (Validators docs, verified live 2026-07-25) for enforcing a uniqueness constraint that includes the *current authenticated user* without requiring the client to submit `user` in the request body — the field is hidden from serializer input but still participates in the auto-generated `UniqueTogetherValidator`/`UniqueConstraint` validator DRF's `ModelSerializer` builds from `Meta.constraints`.

**Example:**
```python
# workspace/serializers.py
from rest_framework import serializers

from workspace.models import Watchlist


class WatchlistSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Watchlist
        fields = ["id", "user", "player", "added_at"]
        read_only_fields = ["id", "added_at"]
        # UniqueConstraint(fields=["user", "player"], ...) on Watchlist.Meta
        # is auto-detected by ModelSerializer -- a duplicate add returns a
        # normal 400 {"non_field_errors": [...]} instead of an unhandled
        # IntegrityError/500.
```

### Pattern 4: List vs Detail serializer split for `SquadPlan` (mirrors `PlayerListSerializer`/`PlayerDetailSerializer`)

**What:** `SquadPlan.list` should stay light (no live squad computation per row); only `SquadPlan.retrieve` needs the derived "current squad." This directly mirrors the codebase's existing `PlayerListSerializer`/`PlayerDetailSerializer` and `ClubListSerializer`/`ClubDetailSerializer` split.

**Example:**
```python
# workspace/serializers.py
from rest_framework import serializers

from players.serializers import PlayerListSerializer
from workspace.models import SquadPlan


class SquadPlanListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SquadPlan
        fields = ["id", "club", "name", "formation", "created_at", "updated_at"]


class SquadPlanDetailSerializer(serializers.ModelSerializer):
    current_squad = serializers.SerializerMethodField()

    class Meta:
        model = SquadPlan
        fields = [
            "id", "club", "name", "formation", "proposed_changes",
            "created_at", "updated_at", "current_squad",
        ]

    def get_current_squad(self, obj):
        # Live, never frozen -- exact ClubDetailSerializer.get_squad pattern.
        return PlayerListSerializer(obj.club.players.all(), many=True).data

    def validate_proposed_changes(self, value):
        allowed_actions = {"add", "remove", "swap"}
        if not isinstance(value, list):
            raise serializers.ValidationError("proposed_changes must be a list.")
        for entry in value:
            if not isinstance(entry, dict) or entry.get("action") not in allowed_actions:
                raise serializers.ValidationError(
                    f"each entry needs action in {allowed_actions}."
                )
            if entry["action"] == "swap" and not entry.get("incoming_player_id"):
                raise serializers.ValidationError(
                    "swap entries require incoming_player_id."
                )
        return value


class SquadPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwner]

    def get_queryset(self):
        return SquadPlan.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        return SquadPlanListSerializer if self.action == "list" else SquadPlanDetailSerializer
```

### Pattern 5: Nested `ShortlistEntry` routes without a new dependency

**What:** `@action(detail=True, ...)` on `ShortlistViewSet` for list/create of entries; a second `@action` with a regex `url_path` for delete-by-entry-id — the exact mechanism `AdminUserViewSet.deactivate` already uses for a single sub-route, extended to a parametrized one.

**Example:**
```python
# workspace/views.py
from rest_framework.decorators import action
from rest_framework.response import Response

from workspace.models import Shortlist, ShortlistEntry
from workspace.serializers import ShortlistEntrySerializer


class ShortlistViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwner]

    def get_queryset(self):
        return Shortlist.objects.filter(user=self.request.user)

    @action(detail=True, methods=["get", "post"], url_path="entries")
    def entries(self, request, pk=None):
        shortlist = self.get_object()  # IsOwner already checked via get_object()
        if request.method == "POST":
            serializer = ShortlistEntrySerializer(
                data=request.data, context={"shortlist": shortlist}
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(shortlist=shortlist)
            return Response(serializer.data, status=201)
        qs = shortlist.entries.all()  # related_name="entries" on ShortlistEntry.shortlist
        return Response(ShortlistEntrySerializer(qs, many=True).data)

    @action(detail=True, methods=["delete"], url_path=r"entries/(?P<entry_id>[^/.]+)")
    def delete_entry(self, request, pk=None, entry_id=None):
        shortlist = self.get_object()
        get_object_or_404(ShortlistEntry, pk=entry_id, shortlist=shortlist).delete()
        return Response(status=204)
```
`self.get_object()` already runs `check_object_permissions` (i.e. `IsOwner`) against the parent `Shortlist`, so entry sub-routes inherit ownership enforcement for free — no separate `IsOwner` check needed on `ShortlistEntry` itself for these two actions. (`IsOwner`'s `ShortlistEntry`-specific branch, Pattern 1, is only needed if a standalone `ShortlistEntry` detail route is ever added later.)

### Pattern 6: `RecentActivity` logging — insertion points, verified against current view code

**What:** A direct, explicit `.create()` call, no signals (matches the "no Django signals anywhere in this codebase" convention, confirmed again this phase).

**`PlayerDetailView` (a plain `APIView`) — insert directly in `.get()`:**
```python
# players/views.py — modify PlayerDetailView.get(), insertion point right after
# the object is confirmed to exist (never logs a view of a nonexistent player):
def get(self, request, pk):
    player = get_object_or_404(Player, id=pk)
    RecentActivity.objects.create(
        user=request.user, activity_type="viewed_player", target_id=player.id
    )
    profile = PlayerDetailSerializer(player).data
    # ... unchanged from here — response contract (profile + scores) untouched
```

**`ClubDetailView` (a `generics.RetrieveAPIView`) — no existing `get`/`retrieve` override exists; one must be added:**
```python
# clubs/views.py — modify ClubDetailView, override retrieve() (RetrieveModelMixin's
# default retrieve() has no hook point otherwise):
class ClubDetailView(generics.RetrieveAPIView):
    queryset = Club.objects.all()
    serializer_class = ClubDetailSerializer
    lookup_field = "pk"

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        RecentActivity.objects.create(
            user=request.user, activity_type="viewed_club", target_id=kwargs["pk"]
        )
        return response
```
Both insertions are additive — they do not touch `PlayerDetailSerializer`/`ClubDetailSerializer` output, so Phase 7's existing response-shape tests (`test_detail_returns_profile_and_score_breakdowns`, etc.) keep passing unmodified. `request.user` is guaranteed authenticated at this point (global `IsAuthenticated` already gated the request), so no extra `is_authenticated` guard is needed.

### Pattern 7: CSV export — verified current Django docs pattern

**What:** Django's own documented `Echo` pseudo-buffer + `csv.writer` + `StreamingHttpResponse`, fetched live from `docs.djangoproject.com/en/5.2/howto/outputting-csv/` on 2026-07-25.

**Example (Shortlist export — `IsOwner`-gated, in `workspace/views.py`):**
```python
import csv

from django.http import StreamingHttpResponse
from rest_framework.decorators import action


class Echo:
    """Implements only .write(), returning the value instead of buffering it
    (verbatim Django docs pattern)."""
    def write(self, value):
        return value


PLAYER_EXPORT_COLUMNS = [
    "id", "player", "position", "main_position", "league", "club_name",
    "age", "market_value", "impact_score", "compatibility_score",
    "financial_fit_score", "transfer_probability_score",
]


class ShortlistViewSet(viewsets.ModelViewSet):
    ...

    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        shortlist = self.get_object()  # IsOwner enforced via get_object()
        players = (e.player for e in shortlist.entries.select_related("player").all())
        rows = (
            [getattr(PlayerListSerializer(p).data.get(c), "__str__", lambda: "")() or PlayerListSerializer(p).data.get(c)
             for c in PLAYER_EXPORT_COLUMNS]
            for p in players
        )
        writer = csv.writer(Echo())
        header_and_rows = ([PLAYER_EXPORT_COLUMNS] + [] )  # header written first row
        def generate():
            yield writer.writerow(PLAYER_EXPORT_COLUMNS)
            for p in players:
                data = PlayerListSerializer(p).data
                yield writer.writerow([data.get(c) for c in PLAYER_EXPORT_COLUMNS])
        return StreamingHttpResponse(
            generate(),
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="shortlist-{shortlist.id}.csv"'},
        )
```
(The commented-out `rows`/`header_and_rows` lines above are planning scratch, not meant to ship — the `generate()` generator is the actual pattern; simplify at plan-writing time. Core point: reuse `PlayerListSerializer(...).data` per row rather than hand-picking model attributes, so the export columns never drift from the list/detail API shape.)

**Club report export** (in `clubs/views.py`, **not** `workspace/` — club data isn't user-owned, so `IsOwner` doesn't apply; global `IsAuthenticated` is sufficient):
```python
# clubs/views.py
class ClubExportView(APIView):
    def get(self, request, pk):
        club = get_object_or_404(Club, pk=pk)
        detail = ClubDetailSerializer(club).data  # reuses the exact aggregate computation
        ...  # flatten detail["transfer_aggregates"] + profile fields into one CSV row,
             # StreamingHttpResponse + Echo + csv.writer as above
```

### Anti-Patterns to Avoid
- **Relying on `IsOwner` alone to scope `list`:** DRF never calls `has_object_permission` for `list`/`create` — always pair with `get_queryset()` filtering (Pattern 2). This is the single highest-risk mistake for this phase.
- **Denormalizing a redundant `user` FK onto `ShortlistEntry`:** adds a sync-drift risk for no benefit; resolve ownership via `shortlist.user` in `IsOwner` instead (Pattern 1), and via `get_object()` on the parent `Shortlist` for nested entry actions (Pattern 5).
- **Freezing "current squad" into `SquadPlan` at creation time:** explicitly rejected by 08-CONTEXT.md; always derive live via `club.players.all()` (Pattern 4).
- **Buffering the whole CSV in memory** (`HttpResponse` + a fully-built string) instead of `StreamingHttpResponse` + generator: works fine at this dataset's per-shortlist/per-club scale today, but the official pattern costs nothing extra to use correctly from the start.
- **Adding `drf-nested-routers` for URL sugar:** not installed, not needed — `@action` with a regex `url_path` covers the one nested-detail-under-detail case this phase has (Pattern 5).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-user duplicate-add prevention (Watchlist) | Manual `if Watchlist.objects.filter(user=..., player=...).exists(): raise ...` in the view | `UniqueConstraint` + `HiddenField(default=CurrentUserDefault())` (Pattern 3) | DRF auto-generates the validator; returns a clean 400 instead of an unhandled `IntegrityError`/500 |
| CSV generation/streaming | Manual string-concatenation + `HttpResponse` | `csv.writer` + `Echo` + `StreamingHttpResponse` (Pattern 7, verified against current Django docs) | Handles quoting/escaping correctly (commas/quotes in player names, club names) for free; streaming avoids buffering |
| Nested resource URL structure | `drf-nested-routers` | Plain `@action` with `detail=True` + regex `url_path` (Pattern 5) | No new dependency for a single nesting level this project doesn't already have elsewhere |
| Ownership check on every action | Custom `if obj.user != request.user: raise PermissionDenied` scattered per view | `IsOwner` as `permission_classes` (Pattern 1) + `get_queryset()` scoping (Pattern 2) | Centralizes the rule in one class, matches `IsSelfOrAdmin`/`MinimumRole`'s existing centralization pattern |

**Key insight:** Every "don't hand-roll" item above already has a DRF-native or Django-native mechanism this project already uses elsewhere (the `MinimumRole`/`IsSelfOrAdmin` centralization pattern, the Phase-1 stdlib-`csv` precedent) — Phase 8 is assembling already-proven primitives, not introducing new ones.

## Common Pitfalls

### Pitfall 1: `has_object_permission` doesn't scope `list`/`create`
**What goes wrong:** A user calls `GET /api/workspace/watchlist/` and sees every user's watchlist rows, despite `IsOwner` being set as `permission_classes`.
**Why it happens:** DRF's `GenericAPIView.check_object_permissions()` is only invoked by `get_object()` (used by retrieve/update/destroy) — `ListModelMixin.list()` never calls it.
**How to avoid:** Every workspace view/viewset overrides `get_queryset()` to filter by `self.request.user` (or `shortlist__user=self.request.user` for `ShortlistEntry`), unconditionally, even though `IsOwner` is also set. Pattern 2 above.
**Warning signs:** A test authenticated as user A that creates data as user B (or a fixture) and asserts A's list response does NOT contain B's rows — if this test is missing, the pitfall is likely present and undetected.

### Pitfall 2: `RecentActivity` write breaking an otherwise-successful read
**What goes wrong:** If the `RecentActivity.objects.create(...)` call raises (e.g. a future migration adds a NOT NULL constraint or FK that isn't satisfied), the entire player/club detail response fails with a 500, even though the actual read succeeded.
**Why it happens:** The write is inserted directly and unconditionally into the read view.
**How to avoid:** Keep `RecentActivity`'s fields maximally permissive (`target_id` nullable, no FK constraint to `Player`/`Club` — store as a bare `UUIDField`, not a `ForeignKey`, so a future player/club deletion can never cascade-break activity logging, and so the write can never fail on a FK integrity check). This also matches "never fabricate, null means null" from 08-CONTEXT.md's own Code Context notes. If stricter guarantees are wanted later, wrap in `try/except Exception: logger.warning(...)` — not needed for v1 given the plain-`UUIDField` design avoids the failure mode entirely.
**Warning signs:** A previously-passing Phase 7 detail-view test starts failing only after Phase 8 lands, with no change to the test itself.

### Pitfall 3: `ShortlistEntry` ownership is indirect
**What goes wrong:** A literal copy-paste of `IsSelfOrAdmin`'s `obj == request.user` check on `ShortlistEntry` always returns `False` (a `ShortlistEntry` is never equal to a `User`), so every entry-level detail action gets a false 403.
**Why it happens:** `IsSelfOrAdmin`'s shape assumes `obj` IS a `User`; `ShortlistEntry` isn't and doesn't have a direct `user` FK either.
**How to avoid:** `IsOwner`'s polymorphic owner-resolution (Pattern 1), or — as designed in Pattern 5 — route entry actions through the parent `Shortlist`'s `get_object()` so `IsOwner` only ever needs to check `Shortlist`/`Watchlist`/`SquadPlan`/`RecentActivity` (all of which do have a direct `user` FK) and the `ShortlistEntry` branch becomes a defensive fallback rather than the primary path.
**Warning signs:** 403s on entry endpoints for a legitimately-owning user.

### Pitfall 4: `Meta.unique_together` vs `Meta.constraints` inconsistency
**What goes wrong:** Following 08-CONTEXT.md's literal `unique_together = (...)` phrasing produces a model that works but is inconsistent with every other model in the codebase (`PlayerRoleScore`, `PlayerClubCompatibility` both use `models.UniqueConstraint` in `Meta.constraints`), creating a stylistic drift a future reviewer/phase would need to reconcile.
**Why it happens:** CONTEXT.md's decision prose used the constraint's common name, not necessarily the literal Django API name.
**How to avoid:** Use `models.UniqueConstraint(fields=["user", "player"], name="uniq_user_player_watchlist")` — functionally identical, DRF-validator-compatible, and matches the codebase's actual convention (verified by reading `players/models.py` directly).
**Warning signs:** None functional — purely a consistency/maintainability concern flagged for the planner's awareness.

## Code Examples

### `accounts/permissions.py` — verbatim current file (the adaptation source)
```python
# Source: get-scouted-be/accounts/permissions.py, read directly 2026-07-25
from rest_framework.permissions import BasePermission

ROLE_RANK = {"scout": 1, "analyst": 1, "director": 2, "admin": 3}


def MinimumRole(role: str):
    required_rank = ROLE_RANK[role]

    class _MinimumRole(BasePermission):
        message = "You do not have the required role for this action."

        def has_permission(self, request, view):
            user = request.user
            if not user or not user.is_authenticated:
                return False
            return ROLE_RANK.get(user.role, 0) >= required_rank

    return _MinimumRole


class IsSelfOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.role == "admin"
```

### `workspace/urls.py` — mirrors `accounts/urls.py`'s router-composition pattern
```python
# Source pattern: get-scouted-be/accounts/urls.py, read directly 2026-07-25
from django.urls import path
from rest_framework.routers import DefaultRouter

from workspace.views import RecentActivityListView, ShortlistViewSet, SquadPlanViewSet, WatchlistViewSet

router = DefaultRouter()
router.register("watchlist", WatchlistViewSet, basename="watchlist")
router.register("shortlists", ShortlistViewSet, basename="shortlist")
router.register("squad-plans", SquadPlanViewSet, basename="squad-plan")

urlpatterns = [
    path("activity/", RecentActivityListView.as_view(), name="recent-activity"),
] + router.urls
```

## State of the Art

No "old vs current approach" drift applies here — Django 5.2 / DRF 3.15's CSV-streaming and validator patterns are the same stable, long-standing APIs (`StreamingHttpResponse` has existed since Django 1.5; `UniqueTogetherValidator`/`CurrentUserDefault` since DRF 3.0/3.1). Nothing in this phase's domain has meaningfully changed in the last 12-18 months.

**Deprecated/outdated:**
- `unique_together` (Meta option, not the validator) — still functional in Django 5.2, but the codebase's own convention has already moved to `UniqueConstraint`; new phase code should match that, not the older API.

## Open Questions

1. **Is `django-filter` warranted for any workspace list endpoint (e.g. filtering Watchlist by position)?**
   - What we know: CRUD-06 through CRUD-10's wording is "save/remove," "create/name/manage," "record/retrieve," "export" — none mention filtering. `django-filter` is already installed and its backend already runs globally as a no-op when no `filterset_class` is set.
   - What's unclear: Whether a real UX need (e.g. filtering a large watchlist by position/club) will surface during planning despite not being in the literal requirement text.
   - Recommendation: Skip `FilterSet` classes for v1 of this phase — rely on `ordering_fields`/`ordering` (already the CRUD-01/02 pattern) for Watchlist/Shortlist/SquadPlan/RecentActivity lists. Nothing here blocks adding a `FilterSet` later without a breaking change (it's purely additive to a `ListAPIView`/`ListModelMixin`).

2. **Where exactly does the Club report export endpoint live — `clubs/urls.py` or `workspace/urls.py`?**
   - What we know: 08-CONTEXT.md explicitly leaves this ambiguous ("`GET /api/clubs/{id}/export/` (or equivalent)"), and flags exact URL structure as Claude's Discretion.
   - What's unclear: Whether keeping club-data concerns entirely inside the `clubs` app (this research's recommendation) vs. centralizing all workspace-adjacent exports under `/api/workspace/` is preferred stylistically.
   - Recommendation: `clubs/views.py` + `clubs/urls.py` (`GET /api/clubs/{id}/export/`) — club report data is global club data, not user-owned, so it doesn't need `IsOwner` and doesn't conceptually belong under a personal-workspace URL prefix. This also keeps `ClubDetailSerializer`'s aggregate-computation reuse a same-app import rather than a cross-app one.

3. **Should `RecentActivity` writes be wrapped in `transaction.atomic()`/best-effort try-except so a logging failure can never break the underlying read?**
   - What we know: 08-CONTEXT.md doesn't specify; the plain-`UUIDField`-not-`ForeignKey` design (Pitfall 2) already removes the most likely failure mode (cascade/FK integrity).
   - What's unclear: Whether any other realistic failure mode exists (e.g. a DB connection blip) worth defending against explicitly.
   - Recommendation: No wrapping needed for v1 — matches this project's "explicit over implicit, no swallowed exceptions" convention (e.g. `players/views.py`'s docstring: "service calls never wrapped in try/except so ... both propagate naturally"). If it becomes a real operational concern, that's a v2 hardening decision, not a v1 blocker.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-django 4.9 (confirmed via `requirements/dev.txt`) |
| Config file | `get-scouted-be/pyproject.toml` (pytest-django settings) + repo-root `conftest.py` (`fixture_dir` fixture, shared across all app test dirs per Phase 1's decision) |
| Quick run command | `cd get-scouted-be && pytest workspace/tests/ -x` |
| Full suite command | `cd get-scouted-be && pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CRUD-06 | Save/remove player to/from Watchlist; duplicate add rejected; list scoped to own user | integration (APIClient) | `pytest workspace/tests/test_watchlist.py -x` | ❌ Wave 0 |
| CRUD-07 | Create/name Shortlist tied to a club; add/remove entries; list scoped to own user | integration (APIClient) | `pytest workspace/tests/test_shortlists.py -x` | ❌ Wave 0 |
| CRUD-08 | Create/manage SquadPlan; `current_squad` derived live; `proposed_changes` validated | integration (APIClient) | `pytest workspace/tests/test_squad_plans.py -x` | ❌ Wave 0 |
| CRUD-09 | `RecentActivity` auto-logged on player/club detail view; retrievable, scoped to own user | integration (APIClient, real Player/Club fixture rows) | `pytest workspace/tests/test_recent_activity.py -x` | ❌ Wave 0 |
| CRUD-10 | Shortlist export returns valid CSV with expected columns; Club export returns valid CSV | integration (APIClient, parse `response.content` via stdlib `csv.reader`) | `pytest workspace/tests/test_csv_export.py -x` | ❌ Wave 0 |
| (cross-cutting) | `IsOwner` blocks cross-user access on every detail/update/destroy action | integration | `pytest workspace/tests/ -k ownership -x` | ❌ Wave 0 |
| (cross-cutting) | `list` endpoints never leak other users' rows (Pitfall 1) | integration | `pytest workspace/tests/ -k scoping -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest workspace/tests/ -x`
- **Per wave merge:** `pytest` (full suite — protects Phase 7's `players`/`clubs` detail-view tests against the `RecentActivity`-logging insertion, per Pitfall 2)
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `workspace/tests/conftest.py` — shared fixtures (likely re-export `UserFactory`/`authenticated_client` from `accounts/tests/conftest.py`'s pattern, since conftest fixtures aren't auto-shared cross-app in this repo per Phase 1's established structure; a minimal local `player_factory`/`club_factory`-style fixture for creating a Player/Club without depending on real CSV-imported data, mirroring `players/tests/test_views.py::test_detail_club_none_returns_null_with_reason`'s inline `Player.objects.create(...)` pattern)
- [ ] `workspace/tests/test_watchlist.py`, `test_shortlists.py`, `test_squad_plans.py`, `test_recent_activity.py`, `test_csv_export.py` — all new
- [ ] `workspace/__init__.py`, `apps.py`, `migrations/0001_initial.py` — new app scaffold (`python manage.py startapp workspace` + `makemigrations`)
- [ ] Framework install: none — pytest/pytest-django/factory_boy already in `requirements/dev.txt`

## Sources

### Primary (HIGH confidence)
- Direct file reads (2026-07-25) of: `accounts/permissions.py`, `accounts/views.py`, `accounts/urls.py`, `accounts/models.py`, `accounts/tests/conftest.py`, `accounts/tests/test_permissions.py`, `players/views.py`, `players/serializers.py`, `players/urls.py`, `players/filters.py`, `players/models.py`, `players/tests/conftest.py`, `players/tests/test_views.py`, `clubs/views.py`, `clubs/serializers.py`, `clubs/urls.py`, `clubs/models.py`, `core/pagination.py`, `config/settings/base.py`, `config/urls.py`, `requirements/base.txt`, `requirements/dev.txt`, `scoring/exceptions.py`
- [Django 5.2 official docs — Outputting CSV with Django](https://docs.djangoproject.com/en/5.2/howto/outputting-csv/) — fetched live 2026-07-25, `StreamingHttpResponse` + `Echo` + `csv.writer` pattern verified exact
- Live `pip show djangorestframework` / `python -c "import django; print(django.VERSION)"` against the project's own `.venv` — Django 5.2.16, DRF 3.15.2 confirmed

### Secondary (MEDIUM confidence)
- [DRF Validators docs](https://www.django-rest-framework.org/api-guide/validators/) — confirms `HiddenField(default=CurrentUserDefault())` + `UniqueTogetherValidator`/auto-generated-from-`Meta` pattern exists and is the documented mechanism for per-current-user uniqueness, though the docs page itself doesn't show the combined worked example verbatim (constructed here from the documented individual pieces, consistent with widely-corroborated community usage per WebSearch cross-check)

### Tertiary (LOW confidence)
None used as load-bearing — all findings above are either direct codebase reads or verified against current official docs.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies; all versions confirmed live against the project's own `.venv`
- Architecture: HIGH — every pattern is either a direct extension of an already-existing, already-tested pattern in this exact codebase (`AdminUserViewSet`, `PlayerListSerializer`/`PlayerDetailSerializer` split, `IsSelfOrAdmin`) or verified against current official Django/DRF docs
- Pitfalls: HIGH — Pitfall 1 (list/create not covered by `has_object_permission`) and Pitfall 3 (indirect `ShortlistEntry` ownership) are well-established DRF behavior, not speculative; Pitfall 4 is a direct grep-verified codebase-consistency observation

**Research date:** 2026-07-25
**Valid until:** 2026-08-24 (30 days — stable Django/DRF APIs, no fast-moving dependency in this phase's scope)
