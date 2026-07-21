"""Role-based permission primitives for the additive role hierarchy.

ROLE_RANK is the single source of truth for the hierarchy (scout == analyst <
director < admin). MinimumRole(role) is the one reusable factory Phase 7/8
import instead of hand-rolling per-app permission classes.
"""

from rest_framework.permissions import BasePermission

ROLE_RANK = {
    "scout": 1,
    "analyst": 1,  # scout/analyst share rank — locked decision, no distinct permission
    "director": 2,
    "admin": 3,
}


def MinimumRole(role: str):
    """Factory returning a BasePermission class requiring at least `role`'s rank.

    Usage: permission_classes = [MinimumRole("director")]

    Always reads request.user.role fresh from the DB-fetched request.user
    (JWTAuthentication re-fetches the user row per request) -- never the JWT
    claim, so role changes/deactivation take effect on the very next request.
    """
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
    """Object-level: a user may act on their own account; admin may act on any."""

    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.role == "admin"
