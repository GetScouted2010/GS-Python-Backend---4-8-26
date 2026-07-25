from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from workspace.models import Watchlist
from workspace.permissions import IsOwner
from workspace.serializers import WatchlistSerializer


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
