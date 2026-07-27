import csv

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import generics, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from players.serializers import PlayerListSerializer
from workspace import services as workspace_services
from workspace.models import RecentActivity, Shortlist, ShortlistEntry, SquadPlan, Watchlist
from workspace.permissions import IsOwner
from workspace.serializers import (
    RecentActivitySerializer,
    ShortlistEntrySerializer,
    ShortlistSerializer,
    SquadPlanDetailSerializer,
    SquadPlanListSerializer,
    WatchlistSerializer,
)


class Echo:
    """Write-only buffer that returns the value instead of storing it
    (verbatim Django docs streaming-CSV pattern)."""

    def write(self, value):
        return value


PLAYER_EXPORT_COLUMNS = [
    "id", "player", "position", "main_position", "league", "club_name",
    "age", "market_value", "impact_score", "compatibility_score",
    "financial_fit_score", "transfer_probability_score",
]


@extend_schema_view(
    list=extend_schema(
        tags=["workspace"],
        summary="List my Watchlist",
        description="The caller's own Watchlist entries — a simple per-`(user, player)` bookmark, duplicate-safe. Always scoped to the authenticated user; there is no cross-user visibility.",
    ),
    create=extend_schema(
        tags=["workspace"],
        summary="Add a player to my Watchlist",
        description="Bookmarks a player for the calling user. Safe to call again for the same player — duplicates are not created.",
    ),
    destroy=extend_schema(
        tags=["workspace"],
        summary="Remove a player from my Watchlist",
        description="Removes one Watchlist entry. Only the owning user can delete their own entry — a 404 is returned for someone else's entry, not a 403 (existence isn't revealed).",
    ),
)
class WatchlistViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = WatchlistSerializer
    # Overriding permission_classes drops the global IsAuthenticated default,
    # so it must be listed explicitly alongside IsOwner (object-level only --
    # never runs for list/create) to deny anonymous requests with a clean 401
    # instead of crashing get_queryset() on AnonymousUser.
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        # CRITICAL (Pitfall 1): IsOwner.has_object_permission never runs
        # for list/create. Without this filter, list() leaks every user's rows.
        return Watchlist.objects.filter(user=self.request.user).order_by("-added_at")


@extend_schema_view(
    list=extend_schema(
        tags=["workspace"],
        summary="List my Shortlists",
        description="The caller's own Shortlists (club-scoped groupings of candidate players). Always scoped to the authenticated user.",
    ),
    create=extend_schema(
        tags=["workspace"],
        summary="Create a Shortlist",
        description="Creates a new, empty Shortlist owned by the calling user. Add players to it via **Add entry to Shortlist** below.",
    ),
    retrieve=extend_schema(tags=["workspace"], summary="Get a Shortlist", description="Fetch one of the caller's own Shortlists. A 404 (not 403) is returned for another user's Shortlist."),
    update=extend_schema(tags=["workspace"], summary="Replace a Shortlist", description="Full update of one of the caller's own Shortlists."),
    partial_update=extend_schema(tags=["workspace"], summary="Update a Shortlist", description="Partial update (e.g. rename) of one of the caller's own Shortlists."),
    destroy=extend_schema(tags=["workspace"], summary="Delete a Shortlist", description="Deletes a Shortlist and all its entries."),
)
class ShortlistViewSet(viewsets.ModelViewSet):
    serializer_class = ShortlistSerializer
    # Overriding permission_classes drops the global IsAuthenticated default,
    # so it must be listed explicitly alongside IsOwner (see WatchlistViewSet
    # comment above / 08-02 decision) to deny anonymous requests with a clean
    # 401 instead of crashing get_queryset() on AnonymousUser.
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Shortlist.objects.filter(user=self.request.user).order_by("-created_at")

    @extend_schema(
        tags=["workspace"],
        methods=["GET"],
        summary="List entries in a Shortlist",
        description="Every player currently on this Shortlist, most recently added first.",
        responses={200: ShortlistEntrySerializer(many=True)},
    )
    @extend_schema(
        tags=["workspace"],
        methods=["POST"],
        summary="Add entry to Shortlist",
        description="Adds a player (with an optional note) to this Shortlist.",
        request=ShortlistEntrySerializer,
        responses={201: ShortlistEntrySerializer},
    )
    @action(detail=True, methods=["get", "post"], url_path="entries")
    def entries(self, request, pk=None):
        shortlist = self.get_object()  # runs IsOwner via check_object_permissions
        if request.method == "POST":
            serializer = ShortlistEntrySerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(shortlist=shortlist)
            return Response(serializer.data, status=201)
        qs = shortlist.entries.all().order_by("-added_at")
        return Response(ShortlistEntrySerializer(qs, many=True).data)

    @extend_schema(
        tags=["workspace"],
        summary="Remove entry from Shortlist",
        description="Deletes one player entry from this Shortlist. The Shortlist itself is untouched.",
        request=None,
        responses={204: OpenApiResponse(description="Entry removed."), 404: OpenApiResponse(description="Unknown entry (or it belongs to a different Shortlist).")},
    )
    @action(detail=True, methods=["delete"], url_path=r"entries/(?P<entry_id>[^/.]+)")
    def delete_entry(self, request, pk=None, entry_id=None):
        shortlist = self.get_object()
        get_object_or_404(ShortlistEntry, pk=entry_id, shortlist=shortlist).delete()
        return Response(status=204)

    @extend_schema(
        tags=["workspace"],
        summary="Export a Shortlist as CSV",
        description="Streams this Shortlist's players (position, club, market value, all 4 scores) as a downloadable `text/csv` file — reuses the same player serializer shown elsewhere, so numbers never drift from the API.",
        request=None,
        responses={200: OpenApiResponse(description="text/csv file download.")},
    )
    @action(detail=True, methods=["get"], url_path="export")
    def export(self, request, pk=None):
        shortlist = self.get_object()  # IsOwner enforced via get_object()
        writer = csv.writer(Echo())

        def generate():
            yield writer.writerow(PLAYER_EXPORT_COLUMNS)
            for entry in shortlist.entries.select_related("player").all():
                data = PlayerListSerializer(entry.player).data
                yield writer.writerow([data.get(c) for c in PLAYER_EXPORT_COLUMNS])

        return StreamingHttpResponse(
            generate(),
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="shortlist-{shortlist.id}.csv"'
            },
        )


@extend_schema_view(
    list=extend_schema(
        tags=["workspace"],
        summary="List my Squad Plans",
        description="The caller's own Squad Plans (formation + a proposed add/remove/swap delta against a club's real current squad).",
    ),
    create=extend_schema(tags=["workspace"], summary="Create a Squad Plan", description="Creates a new Squad Plan owned by the calling user, for a chosen club and formation."),
    retrieve=extend_schema(
        tags=["workspace"],
        summary="Get a Squad Plan",
        description="Fetch one of the caller's own Squad Plans. `current_squad` is always derived live from the real club roster — never a stale snapshot — so it reflects any roster changes since the plan was created.",
    ),
    update=extend_schema(tags=["workspace"], summary="Replace a Squad Plan", description="Full update, including committing edited `proposed_changes` — this is the permanent save step, distinct from the non-persisting **Simulate a squad change** below."),
    partial_update=extend_schema(tags=["workspace"], summary="Update a Squad Plan", description="Partial update of one of the caller's own Squad Plans."),
    destroy=extend_schema(tags=["workspace"], summary="Delete a Squad Plan", description="Deletes a Squad Plan."),
)
class SquadPlanViewSet(viewsets.ModelViewSet):
    # Overriding permission_classes drops the global IsAuthenticated default,
    # so it must be listed explicitly alongside IsOwner (see WatchlistViewSet
    # comment above / 08-02 decision) to deny anonymous requests with a clean
    # 401 instead of crashing get_queryset() on AnonymousUser.
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return SquadPlan.objects.filter(user=self.request.user).order_by("-updated_at")

    def get_serializer_class(self):
        if self.action == "list":
            return SquadPlanListSerializer
        return SquadPlanDetailSerializer

    @extend_schema(
        tags=["workspace"],
        summary="Simulate a squad change",
        description=(
            "Previews the effect of an add/remove/swap change on this "
            "Squad Plan's aggregate metrics (avg age, avg score, budget/"
            "wage impact) **entirely in memory — nothing is saved.** Pass "
            "`proposed_changes` in the body to try a change without "
            "committing it first; omit it to simulate the plan's already-"
            "saved changes. Returns `baseline` (current squad metrics), "
            "`simulated` (after the change), and `delta` between them. "
            "Null `market_value`/`age`/`impact_score` values are excluded "
            "from averages, never treated as 0. To make a change "
            "permanent, save it via **Replace a Squad Plan** instead."
        ),
        request=inline_serializer(
            "SimulateSquadChangeRequest",
            fields={"proposed_changes": serializers.JSONField(required=False)},
        ),
        responses={
            200: OpenApiResponse(description="baseline, simulated, and delta squad metrics."),
            400: OpenApiResponse(description="proposed_changes references a player id that doesn't exist."),
        },
    )
    @action(detail=True, methods=["post"], url_path="simulate")
    def simulate(self, request, pk=None):
        squad_plan = self.get_object()  # IsOwner enforced via check_object_permissions
        override = request.data.get("proposed_changes")
        try:
            result = workspace_services.simulate_squad_change(
                squad_plan, proposed_changes=override
            )
        except workspace_services.InvalidPlayerReference as exc:
            raise ValidationError(str(exc)) from None
        return Response(result)


@extend_schema_view(
    get=extend_schema(
        tags=["workspace"],
        summary="List my Recent Activity",
        description=(
            "An auto-logged feed of the calling user's own actions — "
            "player/club views and searches — most recent first. Rows are "
            "written automatically by the endpoints themselves (e.g. "
            "viewing a player detail, running a search); there is no "
            "manual log-entry endpoint."
        ),
    )
)
class RecentActivityListView(generics.ListAPIView):
    serializer_class = RecentActivitySerializer

    def get_queryset(self):
        return RecentActivity.objects.filter(user=self.request.user).order_by("-created_at")
