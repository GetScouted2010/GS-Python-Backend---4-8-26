"""Club read-layer views (07-03-PLAN.md): CRUD-02 (list, filter/paginate),
CRUD-04 (detail, full profile + squad + transfer aggregates), CRUD-05
(?ids= multi-fetch, club half).

No explicit permission_classes are set on either view -- the project's
global DEFAULT_PERMISSION_CLASSES (IsAuthenticated) + DEFAULT_AUTHENTICATION
_CLASSES (JWTAuthentication) already deny-by-default (config/settings/base.py).
"""

from rest_framework import generics

from clubs.filters import ClubFilter
from clubs.models import Club
from clubs.serializers import ClubDetailSerializer, ClubListSerializer
from core.pagination import IdsBypassPagination


class ClubListView(generics.ListAPIView):
    """GET /api/clubs/ -- CRUD-02 (filter/paginate) + CRUD-05 (?ids=)."""

    queryset = Club.objects.all()
    serializer_class = ClubListSerializer
    filterset_class = ClubFilter
    pagination_class = IdsBypassPagination
    ordering_fields = ["name", "league", "country"]
    ordering = ["name"]


class ClubDetailView(generics.RetrieveAPIView):
    """GET /api/clubs/{id}/ -- CRUD-04 (profile + squad + transfer aggregates).

    Pure ORM aggregation (bounded to one club) -- no scoring service call,
    so a plain RetrieveAPIView + ClubDetailSerializer is sufficient.
    """

    queryset = Club.objects.all()
    serializer_class = ClubDetailSerializer
    lookup_field = "pk"
