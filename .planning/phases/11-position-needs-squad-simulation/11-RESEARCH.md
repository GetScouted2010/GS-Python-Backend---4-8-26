# Phase 11: Position Needs & Squad Simulation - Research

**Researched:** 2026-07-26
**Domain:** Django/DRF read-layer aggregation extension + in-memory (non-persisting) squad simulation on an existing DRF ModelViewSet
**Confidence:** HIGH

## Summary

Phase 11 is pure extension work on two already-built, already-tested surfaces: `clubs/services.py::position_needs_aggregate(club)` (Phase 10) and `workspace/views.py::SquadPlanViewSet` (Phase 8). Both target functions/classes were read in full. Nothing about this phase requires new infrastructure — no new app, no new model, no new migration. It requires: (1) a thin classification function layered on `position_needs_aggregate`'s existing dict output plus one new `APIView`/`generics.RetrieveAPIView`-style GET endpoint on `clubs`, wired with the exact same "specific routes before the `<uuid:pk>/` catch-all" ordering `clubs/urls.py` already uses for `export/` and `insights/`; and (2) one new `@action(detail=True, methods=["post"])` on `SquadPlanViewSet` that fetches referenced players in one `Player.objects.filter(id__in=...)` query, applies `add`/`remove`/`swap` to an in-memory list derived from `club.players.all()`, computes aggregate metrics using `impact_score` (never the club-context scores) and `market_value`, and returns a baseline/simulated/delta comparison — never writing to the database.

The one correction this research surfaces versus the CONTEXT.md's stated schema: `proposed_changes`' actual validated shape (from the real `validate_proposed_changes` in `workspace/serializers.py` and the real `test_create_squad_plan` test) uses `player_id` for the "add" entry's *added* player and the "remove"/"swap" entry's *outgoing* player — `incoming_player_id` is used ONLY on `swap` entries, not on `add`. This must be planned precisely (see Pitfall 1 below), or the simulate action will silently misinterpret `add` entries.

**Primary recommendation:** Add `classify_position_needs(club)` to `clubs/services.py` (wrapping `position_needs_aggregate`) + `PositionNeedsView` in `clubs/views.py`, routed at `clubs/urls.py` above the `<uuid:pk>/` catch-all. Add `simulate_squad_change(squad_plan, proposed_changes=None)` to a **new** `workspace/services.py` (the app currently has none — Phase 11 would be the one to create it, following the `clubs`/`players` per-app `services.py` convention already established) + a `simulate` `@action` on `SquadPlanViewSet`, reusing `IsOwner`/`get_object()` exactly like `ShortlistViewSet.export`.

## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Position Needs extends Phase 10's `position_needs_aggregate(club)`, not a rebuild.** Reuse the same bounded `.values("position").annotate(...)` ORM query as-is; add a classification layer (`strong`/`weak`/`at-risk`) and a new public, user-facing endpoint on top.

2. **Classification heuristic (exact thresholds, checked in this order):**
   - **weak** if `squad_depth < 2`
   - **at-risk** if `squad_depth >= 2` AND (`avg_age > 30` OR `contracts_expiring_within_12mo >= squad_depth / 2`)
   - **strong** otherwise
   A position gets exactly one label, checked weak → at-risk → strong.

3. **`POST /api/workspace/squad-plans/{id}/simulate/`** accepts an OPTIONAL `proposed_changes` override in the request body (same shape as the `SquadPlan.proposed_changes` field). If omitted, simulates the SquadPlan's own currently-stored `proposed_changes`. Computes metrics by applying changes to the live current squad **entirely in memory**; **never writes to the database**. "Committing" a simulated change means the user separately calls the existing `PATCH /api/workspace/squad-plans/{id}/` — no new commit endpoint.

4. **Metrics:** avg age (`Player.age`), avg score (`Player.impact_score` — club-independent, confirmed), budget impact (net `Player.market_value` delta of incoming vs outgoing players). Never use `compatibility_score`/`financial_fit_score`/`transfer_probability_score` for squad-average metrics — those are own-club-context fields and an incoming player from a different club would carry a meaningless number in this context.

### Claude's Discretion

- Exact response JSON shape for both new endpoints (field names, nesting).
- Whether the Position Needs endpoint also returns raw per-position numbers alongside the classification label — **recommended: yes**, matching this project's "never hide the numbers behind a label" pattern (Phase 10's grounding-echo design).
- Whether simulation validates that referenced `player_id`/`incoming_player_id` values actually exist before computing — **recommended: yes**, clean 400 on invalid ID, matching this project's "never fabricate, catch problems early" convention.
- Any additional squad-composition metrics beyond avg age/avg score/budget impact — not required by PLAN-03's literal wording, may be added if low-cost.

### Deferred Ideas (OUT OF SCOPE)

- AI-suggested replacement players ranked by RMM/CS/TFM fit — `PLAN-02`, Phase 12.
- Player → Club matching (ranked list of clubs that fit a player) — `PLAN-04`, Phase 12.
- A dedicated "commit simulation" endpoint distinct from Phase 8's existing SquadPlan PATCH — deliberately not built.
- Wage/salary as a distinct financial dimension from market value — not available in the migrated dataset.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PLAN-01 | User can view Position Needs analysis (strong/weak/at-risk) for a club's squad, based on depth, contract expiry, and age profile | `position_needs_aggregate(club)` (read in full below) already computes depth/avg_age/contract-expiry per position; this research specifies the exact classification function + endpoint + URL placement to expose it |
| PLAN-03 | User can simulate a squad change (add/remove/swap) and get recalculated aggregate squad metrics (avg age, avg score, budget/wage impact) without persisting until committed | `SquadPlan.proposed_changes`/`SquadPlanViewSet` (read in full below) already establish the schema and live-derivation pattern; this research specifies the exact `simulate` action, in-memory apply logic, `id__in` batch fetch, and null-safe metric computation |

## Architecture Patterns

### Pattern 1: Position Needs classification layered on the existing aggregation

**What:** `clubs/services.py::position_needs_aggregate(club)` (verified, current code below) returns:
```python
{
    "CB": {"squad_depth": 3, "avg_age": 26.7, "contracts_expiring_within_12mo": 1},
    "ST": {"squad_depth": 2, "avg_age": 25.0, "contracts_expiring_within_12mo": 1},
    ...
}
```
Full current source (`get-scouted-be/clubs/services.py`, lines 32–59):
```python
def position_needs_aggregate(club) -> dict:
    cutoff = date.today() + timedelta(days=365)
    rows = (
        club.players.exclude(position__isnull=True).values("position").annotate(
            squad_depth=Count("id"),
            avg_age=Avg("age"),
            expiring_within_12mo=Count(
                "id",
                filter=Q(contract_expires__lte=cutoff, contract_expires__isnull=False),
            ),
        ).order_by("position")
    )
    return {
        row["position"]: {
            "squad_depth": row["squad_depth"],
            "avg_age": round(row["avg_age"], 1) if row["avg_age"] is not None else None,
            "contracts_expiring_within_12mo": row["expiring_within_12mo"],
        }
        for row in rows
    }
```

**Recommended new function** (append to `clubs/services.py`, right after `position_needs_aggregate`):
```python
def classify_position_needs(club) -> dict:
    """PLAN-01: layers strong/weak/at-risk classification onto
    position_needs_aggregate's existing numbers. Never recomputes the
    underlying aggregation -- reuses it as-is (see module docstring)."""
    needs = position_needs_aggregate(club)
    result = {}
    for position, stats in needs.items():
        depth = stats["squad_depth"]
        avg_age = stats["avg_age"]
        expiring = stats["contracts_expiring_within_12mo"]
        if depth < 2:
            label = "weak"
        elif (avg_age is not None and avg_age > 30) or expiring >= depth / 2:
            label = "at-risk"
        else:
            label = "strong"
        result[position] = {**stats, "classification": label}
    return result
```
Note: `avg_age is not None and avg_age > 30` guards the case where `position_needs_aggregate` could theoretically return `avg_age: None` (it can't in practice since `squad_depth >= 1` implies at least one Player row exists in the group-by, and `Age` being null for all players in that position group is the only way `avg_age` comes back `None` — a real, if rare, possibility given `Player.age` is nullable). Do not skip this guard.

**When to use:** Directly inside the new `PositionNeedsView`.

### Pattern 2: New Club endpoint — exact route-ordering requirement (verified against real `clubs/urls.py`)

Current file (`get-scouted-be/clubs/urls.py`), read in full:
```python
from django.urls import path

from clubs.views import ClubDetailView, ClubExportView, ClubInsightsView, ClubListView

urlpatterns = [
    path("", ClubListView.as_view(), name="club-list"),
    path("<uuid:pk>/export/", ClubExportView.as_view(), name="club-export"),
    path("<uuid:pk>/insights/", ClubInsightsView.as_view(), name="club-insights"),
    path("<uuid:pk>/", ClubDetailView.as_view(), name="club-detail"),
]
```
Django's `urlpatterns` are matched top-to-bottom, first match wins. `<uuid:pk>/` is a catch-all for anything shaped like `{uuid}/` — it MUST stay last, or `/api/clubs/{id}/position-needs/` would instead match `<uuid:pk>/` with `pk` failing UUID-cast (404) or (if pattern were looser) silently routing to the wrong view. This project has already gotten this right twice (`export/`, `insights/`) and both times placed the new specific route directly above the existing specific routes, below `ClubListView`, above `ClubDetailView`. Follow the identical placement:
```python
from clubs.views import (
    ClubDetailView, ClubExportView, ClubInsightsView, ClubListView, PositionNeedsView,
)

urlpatterns = [
    path("", ClubListView.as_view(), name="club-list"),
    path("<uuid:pk>/export/", ClubExportView.as_view(), name="club-export"),
    path("<uuid:pk>/insights/", ClubInsightsView.as_view(), name="club-insights"),
    path("<uuid:pk>/position-needs/", PositionNeedsView.as_view(), name="club-position-needs"),
    path("<uuid:pk>/", ClubDetailView.as_view(), name="club-detail"),
]
```
Order among the three specific-suffix routes (`export/`, `insights/`, `position-needs/`) doesn't matter relative to each other — only that ALL of them precede the bare `<uuid:pk>/`.

**Recommended view** (`clubs/views.py`, follows `ClubInsightsView`'s exact style — plain `APIView`, no explicit `permission_classes` since club data isn't user-owned, matching `ClubExportView`/`ClubInsightsView`):
```python
class PositionNeedsView(APIView):
    """GET /api/clubs/{id}/position-needs/ -- PLAN-01: per-position
    strong/weak/at-risk classification, extending Phase 10's
    position_needs_aggregate. No explicit permission_classes -- global
    IsAuthenticated default (matching ClubExportView/ClubInsightsView)."""

    def get(self, request, pk):
        club = get_object_or_404(Club, pk=pk)
        return Response(services.classify_position_needs(club))
```
This is a GET (not POST like `ClubInsightsView`) since it's a deterministic read, not an LLM generation call — no `ReportGeneratorError` handling needed, no 503 path. A nonexistent club's `Http404` surfaces naturally (matching `ClubDetailView`/`ClubExportView`/`ClubInsightsView` convention).

### Pattern 3: Squad simulation as a `SquadPlanViewSet` `@action` (verified against real `workspace/views.py`)

`ShortlistViewSet` already establishes the exact pattern this phase should mirror for `SquadPlanViewSet`:
```python
@action(detail=True, methods=["get"], url_path="export")
def export(self, request, pk=None):
    shortlist = self.get_object()  # IsOwner enforced via get_object()
    ...
    return StreamingHttpResponse(...)
```
`self.get_object()` runs `check_object_permissions` (i.e. `IsOwner`) automatically — this is the exact mechanism to reuse for `simulate`, giving 404 (not raw 403) on a non-owned SquadPlan, consistent with `test_ownership_cannot_get_other_users_plan`'s existing assertion pattern (`assert response.status_code == 404`).

DRF's `DefaultRouter` (used in `workspace/urls.py`) automatically prioritizes registered `@action`s over the default detail route — unlike `clubs/urls.py`'s manual `path()` list, **no manual URL-ordering care is needed** for `router.register(...)`-based apps. This is a real, verified distinction between the two apps' routing mechanisms (`clubs` uses `path()`, `workspace` uses `DefaultRouter`), worth stating explicitly in the plan so the executor doesn't over-apply the Phase 9/10 route-ordering lesson where it doesn't structurally apply.

**Recommended action** (`workspace/views.py`, added to `SquadPlanViewSet`):
```python
from workspace import services as workspace_services

...

    @action(detail=True, methods=["post"], url_path="simulate")
    def simulate(self, request, pk=None):
        squad_plan = self.get_object()  # IsOwner enforced via get_object()
        override = request.data.get("proposed_changes")
        try:
            result = workspace_services.simulate_squad_change(squad_plan, proposed_changes=override)
        except workspace_services.InvalidPlayerReference as exc:
            return Response({"error": str(exc)}, status=400)
        return Response(result)
```

### Pattern 4: New `workspace/services.py` (does not exist yet — this phase creates it)

Verified: `workspace/` currently has no `services.py` (only `models.py`, `views.py`, `serializers.py`, `permissions.py`, `urls.py`). `clubs/services.py` and `players/services.py` both already establish the per-app `services.py` business-logic convention this project uses consistently (module docstring citing the originating plan, service functions the view calls thinly). Phase 11 should create `workspace/services.py` following that exact convention rather than putting simulation logic inline in `views.py`.

**Applying `proposed_changes` — exact schema correction (verified against real code, not just CONTEXT.md's description):**

`workspace/serializers.py::SquadPlanDetailSerializer.validate_proposed_changes` (current, full):
```python
def validate_proposed_changes(self, value):
    allowed = {"add", "remove", "swap"}
    if not isinstance(value, list):
        raise serializers.ValidationError("proposed_changes must be a list.")
    for entry in value:
        if not isinstance(entry, dict) or entry.get("action") not in allowed:
            raise serializers.ValidationError(f"each entry needs action in {allowed}.")
        if entry["action"] == "swap" and not entry.get("incoming_player_id"):
            raise serializers.ValidationError("swap entries require incoming_player_id.")
    return value
```
And the real, passing test `test_create_squad_plan` (`workspace/tests/test_squad_plans.py`) posts:
```python
"proposed_changes": [{"action": "add", "player_id": str(player.id)}]
```
**This means the actual, validated field semantics are:**
| action | `player_id` means | `incoming_player_id` means |
|--------|-------------------|------------------------------|
| `add` | the player being added to the squad | not used |
| `remove` | the player being removed from the squad | not used |
| `swap` | the outgoing player (removed) | **required** — the incoming player (added) |

CONTEXT.md's canonical_refs description ("`{action, player_id, incoming_player_id}`" applied generically to all three actions) is imprecise on this point — plan the simulate logic against the verified validator/test behavior above, not the CONTEXT.md prose.

**Recommended `simulate_squad_change` implementation:**
```python
"""Squad simulation service (11-PLAN.md, PLAN-03).

simulate_squad_change applies a SquadPlan's proposed_changes (or an ad-hoc
override) to the club's live current squad ENTIRELY IN MEMORY -- never
writes to the DB. Metrics use Player.impact_score (club-independent) for
avg score and Player.market_value for budget impact, matching this
project's own-club-context-score trap documented in players/models.py.
"""
from __future__ import annotations

from players.models import Player
from players.serializers import PlayerListSerializer


class InvalidPlayerReference(Exception):
    pass


def _referenced_ids(proposed_changes):
    ids = set()
    for entry in proposed_changes:
        if entry.get("player_id"):
            ids.add(str(entry["player_id"]))
        if entry.get("incoming_player_id"):
            ids.add(str(entry["incoming_player_id"]))
    return ids


def _squad_metrics(players):
    ages = [p.age for p in players if p.age is not None]
    scores = [p.impact_score for p in players if p.impact_score is not None]
    values = [p.market_value for p in players if p.market_value is not None]
    return {
        "squad_size": len(players),
        "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
        "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
        "total_market_value": sum(values) if values else None,
        "missing_market_value_count": len(players) - len(values),
    }


def simulate_squad_change(squad_plan, proposed_changes=None) -> dict:
    changes = proposed_changes if proposed_changes is not None else squad_plan.proposed_changes

    ref_ids = _referenced_ids(changes)
    players_by_id = {
        str(p.id): p for p in Player.objects.filter(id__in=ref_ids)
    } if ref_ids else {}
    missing = ref_ids - players_by_id.keys()
    if missing:
        raise InvalidPlayerReference(f"unknown player id(s): {sorted(missing)}")

    current_squad = list(squad_plan.club.players.all())
    simulated_squad = list(current_squad)  # shallow copy, in-memory only

    for entry in changes:
        action = entry["action"]
        if action == "add":
            simulated_squad.append(players_by_id[str(entry["player_id"])])
        elif action == "remove":
            target_id = str(entry["player_id"])
            simulated_squad = [p for p in simulated_squad if str(p.id) != target_id]
        elif action == "swap":
            out_id = str(entry["player_id"])
            simulated_squad = [p for p in simulated_squad if str(p.id) != out_id]
            simulated_squad.append(players_by_id[str(entry["incoming_player_id"])])

    baseline = _squad_metrics(current_squad)
    simulated = _squad_metrics(simulated_squad)
    delta = {
        "avg_age": (
            round(simulated["avg_age"] - baseline["avg_age"], 1)
            if simulated["avg_age"] is not None and baseline["avg_age"] is not None
            else None
        ),
        "avg_score": (
            round(simulated["avg_score"] - baseline["avg_score"], 2)
            if simulated["avg_score"] is not None and baseline["avg_score"] is not None
            else None
        ),
        "budget_impact": (
            simulated["total_market_value"] - baseline["total_market_value"]
            if simulated["total_market_value"] is not None and baseline["total_market_value"] is not None
            else None
        ),
        "squad_size": simulated["squad_size"] - baseline["squad_size"],
    }

    return {
        "baseline": baseline,
        "simulated": simulated,
        "delta": delta,
        "proposed_changes": changes,
        "simulated_squad": PlayerListSerializer(simulated_squad, many=True).data,
    }
```

**Why `Player.objects.filter(id__in=ref_ids)` in one query:** verified no existing `id__in=` precedent elsewhere in the codebase (grepped clean), but this is standard, idiomatic Django ORM — a single `SELECT ... WHERE id IN (...)` avoids N+1 per-reference `get_object_or_404` calls when a `proposed_changes` list could reference several distinct players. Given the real dataset is 41,708 players, `id` is the UUID primary key (always indexed), so this is an efficient indexed lookup regardless of list size.

### Pattern 5: Null-handling for metrics (this project's "never fabricate, null means null" convention)

Per CONTEXT.md's discretion note, referencing Phase 8's `RecentActivity` "never fabricate" convention and the `players/models.py` comment style (`impact_score`/`compatibility_score` etc. kept `null=True` deliberately rather than zero-filled): the recommended `_squad_metrics` above:
- Excludes `None`-valued players entirely from averages (never coerces `None` to `0` in a sum/average, which would silently and wrongly pull the average down).
- Returns `None` (not `0`) for `avg_age`/`avg_score`/`total_market_value` if the whole list has no non-null values (empty squad or all-null field) — never a fabricated `0`.
- Surfaces `missing_market_value_count` explicitly in each block, so the API consumer can see how many players were excluded from the money sum rather than the gap being silently hidden — matches Phase 10's "never hide the numbers behind a label" pattern the CONTEXT.md itself points to.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Fetching several specific players by UUID | N individual `get_object_or_404(Player, pk=...)` calls in a loop | `Player.objects.filter(id__in=ref_ids)` — one query | N+1 query risk against a 41,708-row table; single indexed `IN` query is both simpler and faster |
| Ownership check on the `simulate` action | A hand-rolled `if squad_plan.user != request.user: return 403` | `self.get_object()` (already runs `IsOwner.has_object_permission` via `check_object_permissions`) | Matches `ShortlistViewSet.export`'s exact established pattern; keeps the 404-not-403 behavior other tests already assert |
| A second, parallel position-needs aggregation query | A fresh `.values("position").annotate(...)` written directly in the new view/service | `position_needs_aggregate(club)` (Phase 10, reused as-is) | Phase 10's own docstring explicitly anticipates this reuse; a second aggregation risks silently disagreeing with the first — this project has hit and fixed that exact bug class before (Phase 4 TFM log-scale bug, Phase 6 compatibility-score merge collision) |
| A "commit simulation" endpoint | A new `POST .../commit/` action that writes `proposed_changes` to the DB | The existing `PATCH /api/workspace/squad-plans/{id}/` | CONTEXT.md explicitly locks this — Phase 8's PATCH already does exactly this write, fully tested; a second write path would duplicate it |

**Key insight:** every piece of this phase's plumbing (ownership, routing precedence, serializer reuse, own-club-vs-arbitrary-club score correctness) already has a directly analogous, already-tested precedent somewhere in Phases 7–10. There is no genuinely new architectural risk here — the risk is entirely in getting the details (exact `proposed_changes` field semantics, exact URL ordering, exact null-handling) right by reading the real code rather than assuming.

## Common Pitfalls

### Pitfall 1: Misreading `proposed_changes`' field semantics for `add`
**What goes wrong:** Treating `incoming_player_id` as the field carrying the added player for `add` actions (per CONTEXT.md's generic prose description), when the real, tested schema uses `player_id` for `add`'s added player.
**Why it happens:** CONTEXT.md's canonical_refs describes the shape generically (`{action, player_id, incoming_player_id}`) without breaking out per-action field semantics; the real distinguishing detail only lives in `validate_proposed_changes`'s validation logic (which only requires `incoming_player_id` for `swap`) and in the real `test_create_squad_plan` test payload.
**How to avoid:** Implement exactly per Pattern 4's table above: `add`/`remove` use `player_id` only; `swap` uses `player_id` (outgoing) + `incoming_player_id` (incoming).
**Warning signs:** A test posting `{"action": "add", "incoming_player_id": ...}` (no `player_id`) would currently fail `validate_proposed_changes`'s own action-based requirement inconsistently if the simulate logic expects `incoming_player_id` for adds — a structural mismatch between the PATCH-time validator and the simulate-time interpreter.

### Pitfall 2: Route ordering on `clubs/urls.py` (manual `path()` list)
**What goes wrong:** Adding `path("<uuid:pk>/position-needs/", ...)` AFTER `path("<uuid:pk>/", ClubDetailView.as_view())` — Django matches top-to-bottom, so the catch-all would swallow the new route first, causing `pk` to be parsed as `"position-needs"`-adjacent garbage or (worse, if it did somehow UUID-parse) silently hitting the wrong view.
**Why it happens:** Easy to append new routes at the end of a list without checking existing ordering, especially since `<uuid:pk>/` visually "looks like" it belongs last stylistically even when it isn't in match-order.
**How to avoid:** Insert the new specific-suffix route directly alongside `export/`/`insights/`, above `<uuid:pk>/` — exactly Pattern 2 above. This exact class of bug is explicitly flagged as having bitten Phase 9 and Phase 10 already.
**Warning signs:** `GET /api/clubs/{id}/position-needs/` returns 404 with a UUID-cast error instead of the expected classification payload.

### Pitfall 3: Using own-club-context score fields for a simulated squad that includes players from other clubs
**What goes wrong:** Using `PlayerListSerializer`'s included `compatibility_score`/`financial_fit_score`/`transfer_probability_score` fields (or worse, computing an "avg compatibility" metric) for an incoming player who currently plays for a DIFFERENT club — those fields are denormalized relative to that player's OWN current club, not the club being simulated into.
**Why it happens:** `PlayerListSerializer` includes all 4 denormalized score fields by default (it's the general-purpose player list shape), so it's easy to reach for "just average whatever score field is already on the object" without checking which club-context it was computed against.
**How to avoid:** Only `impact_score` (RMM) is used for the simulation's "avg score" metric — it is confirmed club-independent (model comment: plainly `"RMM (Player Impact)"`, unlike the other three fields' explicit `"vs own club"` comments). `PlayerListSerializer`'s other score fields may still be included in the response for display/transparency (they're real, just not usable in the aggregate math), but never summed/averaged.
**Warning signs:** A simulated squad's "avg compatibility" (if ever added) silently mixes each player's own-different-club compatibility numbers into one meaningless average — this is exactly why CONTEXT.md's Decision #4 restricts "avg score" to `impact_score` only.

### Pitfall 4: Treating `None` `market_value`/`age`/`impact_score` as `0` in aggregate sums
**What goes wrong:** `sum(p.market_value for p in squad)` where some `market_value` is `None` raises a `TypeError` (can't add `None` to `int`) if not filtered first, OR (if naively coerced with `or 0`) silently understates budget impact as if a player transferred for free.
**Why it happens:** `Player.market_value`/`Player.age`/`Player.impact_score` are all `null=True` fields — real, not-uncommon nulls exist in the migrated 41,708-player dataset (e.g. Phase 6 confirmed `impact_score` non-null for 41,707/41,708; `compatibility_score`/`transfer_probability_score` null for GK/LB/RB by design).
**How to avoid:** Filter to non-null values before summing/averaging (Pattern 5 above); surface a `missing_*_count` in the response rather than silently zero-filling.
**Warning signs:** A budget-impact number that looks suspiciously round or small when a squad contains a player known to have no `market_value` on file.

### Pitfall 5: Assuming `workspace/services.py` already exists
**What goes wrong:** Planning a task that says "add `simulate_squad_change` to `workspace/services.py`" as if editing an existing file, when the file does not yet exist (verified: `workspace/` currently has no `services.py`).
**How to avoid:** Plan this as a NEW file creation, following the `clubs/services.py`/`players/services.py` per-app convention (module docstring citing the phase/plan, thin view calling into it).

## Code Examples

### Existing `SquadPlanViewSet` (verified current, full source)
```python
# Source: get-scouted-be/workspace/views.py, lines 105-118
class SquadPlanViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return SquadPlan.objects.filter(user=self.request.user).order_by("-updated_at")

    def get_serializer_class(self):
        if self.action == "list":
            return SquadPlanListSerializer
        return SquadPlanDetailSerializer
```

### Existing `current_squad` live-derivation (verified, the baseline pattern simulation must match)
```python
# Source: get-scouted-be/workspace/serializers.py, lines 55-57
def get_current_squad(self, obj):
    # Live, never frozen -- exact ClubDetailSerializer.get_squad pattern.
    return PlayerListSerializer(obj.club.players.all(), many=True).data
```
`simulate_squad_change`'s `current_squad = list(squad_plan.club.players.all())` baseline mirrors this exactly (`squad_plan.club` is the same FK `obj.club` refers to).

## State of the Art

No externally-facing technology choices in this phase — everything is internal Django/DRF ORM/service-layer work on an already-fixed stack (Django 4.2.13, DRF 3.15.2, both already pinned and in use project-wide; verified via `pip show`/`django.get_version()`). No new package installation required.

## Open Questions

None blocking. Two minor judgment calls left fully to the planner/executor per CONTEXT.md's own "Claude's Discretion" list:
1. Exact response field naming beyond `{baseline, simulated, delta}` (e.g. whether to also echo `current_squad`/`simulated_squad` as full `PlayerListSerializer` payloads, or just IDs) — this research recommends including `simulated_squad` (full serialized) for transparency, omitting `current_squad` in the simulate response since it's already available via the existing detail endpoint's `current_squad` field, avoiding redundant payload size.
2. Whether "at-risk" `avg_age > 30` should apply `None`-guarding when `avg_age` is `None` (research recommends: treat as not-triggering the at-risk-by-age branch, falls through to depth/contract-expiry check only — see Pattern 1's explicit guard).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 7.x + pytest-django (existing project-wide setup) |
| Config file | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`) — `testpaths = ["clubs", "players", "transfers", "core", "accounts", "scoring", "workspace"]` already includes both apps this phase touches |
| Quick run command | `cd get-scouted-be && pytest clubs/tests/test_position_needs.py workspace/tests/test_squad_simulation.py -x` |
| Full suite command | `cd get-scouted-be && pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAN-01 | `classify_position_needs` labels weak when `squad_depth < 2` | unit | `pytest clubs/tests/test_position_needs.py::test_classify_weak_when_depth_below_2 -x` | ❌ Wave 0 |
| PLAN-01 | labels at-risk when depth adequate but `avg_age > 30` | unit | `pytest clubs/tests/test_position_needs.py::test_classify_at_risk_by_age -x` | ❌ Wave 0 |
| PLAN-01 | labels at-risk when `contracts_expiring_within_12mo >= squad_depth / 2` | unit | `pytest clubs/tests/test_position_needs.py::test_classify_at_risk_by_contract_expiry -x` | ❌ Wave 0 |
| PLAN-01 | labels strong when depth adequate, not aging, no mass expiry | unit | `pytest clubs/tests/test_position_needs.py::test_classify_strong -x` | ❌ Wave 0 |
| PLAN-01 | `GET /api/clubs/{id}/position-needs/` returns per-position classified payload; nonexistent club 404 | integration | `pytest clubs/tests/test_views_position_needs.py -x` | ❌ Wave 0 |
| PLAN-01 | route ordering: `position-needs/` resolves correctly (not swallowed by `<uuid:pk>/`) | integration (implicit in above) | same as above | ❌ Wave 0 |
| PLAN-03 | `simulate` applies add/remove/swap correctly to an in-memory copy | unit | `pytest workspace/tests/test_squad_simulation.py::test_apply_add_remove_swap -x` | ❌ Wave 0 |
| PLAN-03 | invalid `player_id`/`incoming_player_id` -> clean 400 | unit + integration | `pytest workspace/tests/test_squad_simulation.py::test_invalid_player_id_400 -x` | ❌ Wave 0 |
| PLAN-03 | response contains baseline/simulated/delta for avg age, avg score, budget impact | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_response_shape -x` | ❌ Wave 0 |
| PLAN-03 | simulate NEVER persists — DB `proposed_changes`/squad unchanged after call | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_does_not_persist -x` | ❌ Wave 0 |
| PLAN-03 | optional override `proposed_changes` used instead of stored value when provided | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_uses_override_when_provided -x` | ❌ Wave 0 |
| PLAN-03 | ownership: another user's SquadPlan -> 404 on `/simulate/` (matches existing `IsOwner` convention) | integration | `pytest workspace/tests/test_squad_simulation.py::test_simulate_ownership_denied -x` | ❌ Wave 0 |
| PLAN-03 | null-safe metrics: player with `market_value=None`/`age=None`/`impact_score=None` excluded from averages, not coerced to 0 | unit | `pytest workspace/tests/test_squad_simulation.py::test_null_values_excluded_not_zero_filled -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** quick run command above
- **Per wave merge:** `cd get-scouted-be && pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `clubs/tests/test_position_needs.py` — unit tests for `classify_position_needs` (mirror `clubs/tests/test_services_club_insights.py`'s factory-based, non-real-data-dependent style — no `real_data_available` fixture needed, synthetic `Club.objects.create`/`Player.objects.create` suffice, same as `test_services_club_insights.py` already does)
- [ ] `clubs/tests/test_views_position_needs.py` — integration tests for the new endpoint (mirror `clubs/tests/test_ai_club_insights.py`'s `auth_client` fixture pattern, though no Anthropic mocking needed here since this is a deterministic, non-AI endpoint)
- [ ] `workspace/tests/test_squad_simulation.py` — unit + integration tests for `simulate_squad_change` and the `simulate` action (reuse `workspace/tests/conftest.py`'s existing `player_factory`/`club_factory` and `accounts/tests/conftest.py`'s `authenticated_client` directly — both confirmed sufficient without modification; mirror `workspace/tests/test_squad_plans.py`'s existing `SquadPlanViewSet` test style, e.g. `client.post(f"{SQUAD_PLANS_URL}{plan.id}/simulate/", ...)`)
- [ ] `workspace/services.py` — does not exist yet; must be created (framework file, not a test gap, but a structural prerequisite the plan must call out explicitly per Pitfall 5)

No new test framework/fixture installation needed — `pytest-django`, `factory_boy` (via `factory.django.DjangoModelFactory`), and `rest_framework.test.APIClient` are all already wired project-wide.

## Sources

### Primary (HIGH confidence — direct file reads of this repository's real, current code)
- `get-scouted-be/clubs/services.py` — full read, `position_needs_aggregate`/`generate_club_insights`
- `get-scouted-be/clubs/urls.py` — full read, current route ordering
- `get-scouted-be/clubs/views.py` — full read, `ClubListView`/`ClubDetailView`/`ClubExportView`/`ClubInsightsView`
- `get-scouted-be/workspace/models.py` — full read, `SquadPlan` model
- `get-scouted-be/workspace/views.py` — full read, `SquadPlanViewSet`/`ShortlistViewSet`/`WatchlistViewSet`
- `get-scouted-be/workspace/urls.py` — full read, `DefaultRouter` registration
- `get-scouted-be/workspace/serializers.py` — full read, `SquadPlanDetailSerializer.validate_proposed_changes` (the actual field-semantics source of truth)
- `get-scouted-be/workspace/permissions.py` — full read, `IsOwner`
- `get-scouted-be/players/models.py` — grep + targeted read, `impact_score`/`compatibility_score`/`financial_fit_score`/`transfer_probability_score`/`age`/`market_value`/`contract_expires`/`club` field definitions and comments
- `get-scouted-be/players/serializers.py` — read, `PlayerListSerializer`
- `get-scouted-be/workspace/tests/conftest.py`, `get-scouted-be/accounts/tests/conftest.py` — full read, existing fixtures confirmed reusable as-is
- `get-scouted-be/workspace/tests/test_squad_plans.py` — full read, confirms real `proposed_changes` field semantics via `test_create_squad_plan`
- `get-scouted-be/clubs/tests/test_services_club_insights.py`, `get-scouted-be/clubs/tests/test_ai_club_insights.py`, `get-scouted-be/clubs/tests/conftest.py` — full/partial read, existing test-style precedent
- `get-scouted-be/pyproject.toml` — `[tool.pytest.ini_options]`, confirms `clubs`/`workspace` already in `testpaths`
- Shell verification: `django.get_version()` → 4.2.13; `pip show djangorestframework` → 3.15.2; grep confirms no pre-existing `id__in=` pattern and no pre-existing `workspace/services.py`

### Secondary / Tertiary
None used — this phase required no external library research; all findings are grounded in direct reads of this repository's own code, which is the authoritative source per CONTEXT.md's explicit instruction to "verify all of the above directly by reading the actual files."

## Metadata

**Confidence breakdown:**
- Standard stack: N/A — no new libraries needed, pure extension of existing Django/DRF code (HIGH — verified via direct reads + shell version checks)
- Architecture: HIGH — every pattern is a direct extension of an already-built, already-tested precedent in this exact repository
- Pitfalls: HIGH — all 5 pitfalls are grounded in a specific, verified discrepancy or convention found in the real code (not speculative)

**Research date:** 2026-07-26
**Valid until:** Stable — no external dependency drift risk; valid until the underlying `clubs`/`workspace` app code changes (effectively indefinite for this internal-only research)
