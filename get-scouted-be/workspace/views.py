import csv

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, mixins, viewsets
from rest_framework.decorators import action
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


class ShortlistViewSet(viewsets.ModelViewSet):
    serializer_class = ShortlistSerializer
    # Overriding permission_classes drops the global IsAuthenticated default,
    # so it must be listed explicitly alongside IsOwner (see WatchlistViewSet
    # comment above / 08-02 decision) to deny anonymous requests with a clean
    # 401 instead of crashing get_queryset() on AnonymousUser.
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Shortlist.objects.filter(user=self.request.user).order_by("-created_at")

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

    @action(detail=True, methods=["delete"], url_path=r"entries/(?P<entry_id>[^/.]+)")
    def delete_entry(self, request, pk=None, entry_id=None):
        shortlist = self.get_object()
        get_object_or_404(ShortlistEntry, pk=entry_id, shortlist=shortlist).delete()
        return Response(status=204)

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

    @action(detail=True, methods=["post"], url_path="simulate")
    def simulate(self, request, pk=None):
        squad_plan = self.get_object()  # IsOwner enforced via check_object_permissions
        override = request.data.get("proposed_changes")
        try:
            result = workspace_services.simulate_squad_change(
                squad_plan, proposed_changes=override
            )
        except workspace_services.InvalidPlayerReference as exc:
            return Response({"error": str(exc)}, status=400)
        return Response(result)


class RecentActivityListView(generics.ListAPIView):
    serializer_class = RecentActivitySerializer

    def get_queryset(self):
        return RecentActivity.objects.filter(user=self.request.user).order_by("-created_at")
