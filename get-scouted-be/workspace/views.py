from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from workspace.models import Shortlist, ShortlistEntry, Watchlist
from workspace.permissions import IsOwner
from workspace.serializers import ShortlistEntrySerializer, ShortlistSerializer, WatchlistSerializer


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
