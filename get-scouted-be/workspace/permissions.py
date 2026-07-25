from rest_framework.permissions import BasePermission


class IsOwner(BasePermission):
    """Object-level: a user may act only on their own workspace data.

    Watchlist/Shortlist/SquadPlan/RecentActivity have a direct `user` FK.
    ShortlistEntry does not — ownership flows through `shortlist.user`.
    """

    def has_object_permission(self, request, view, obj):
        owner = getattr(obj, "user", None)
        if owner is None and hasattr(obj, "shortlist"):
            owner = obj.shortlist.user
        return owner == request.user
