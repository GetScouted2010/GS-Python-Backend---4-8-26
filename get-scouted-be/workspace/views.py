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
    serializer_class = WatchlistSerializer
    permission_classes = [IsOwner]

    def get_queryset(self):
        # CRITICAL (Pitfall 1): IsOwner.has_object_permission never runs
        # for list/create. Without this filter, list() leaks every user's rows.
        return Watchlist.objects.filter(user=self.request.user).order_by("-added_at")
