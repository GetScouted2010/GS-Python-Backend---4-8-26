"""Club read-layer views (07-03-PLAN.md): CRUD-02 (list, filter/paginate),
CRUD-04 (detail, full profile + squad + transfer aggregates), CRUD-05
(?ids= multi-fetch, club half).

No explicit permission_classes are set on either view -- the project's
global DEFAULT_PERMISSION_CLASSES (IsAuthenticated) + DEFAULT_AUTHENTICATION
_CLASSES (JWTAuthentication) already deny-by-default (config/settings/base.py).
"""

import csv

from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from clubs import services
from clubs.filters import ClubFilter
from clubs.models import Club
from clubs.serializers import ClubDetailSerializer, ClubListSerializer
from core.pagination import IdsBypassPagination
from players.ai.report_generator import ReportGeneratorError
from scoring.services.matching import rank_replacement_players
from workspace.models import RecentActivity


class Echo:
    """Write-only buffer that returns the value instead of storing it
    (verbatim Django docs streaming-CSV pattern). Duplicated from
    workspace/views.py rather than cross-app imported, keeping club-data
    concerns inside the clubs app."""

    def write(self, value):
        return value


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

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        RecentActivity.objects.create(
            user=request.user, activity_type="viewed_club", target_id=kwargs["pk"]
        )
        return response


class ClubExportView(APIView):
    """GET /api/clubs/{id}/export/ -- CRUD-10: streams a text/csv of the club
    profile + transfer aggregates, reusing ClubDetailSerializer so the
    exported numbers never diverge from the API. IsAuthenticated only (the
    project global default) -- club data is not user-owned, so no IsOwner."""

    def get(self, request, pk):
        club = get_object_or_404(Club, pk=pk)
        detail = ClubDetailSerializer(club).data
        aggregates = detail["transfer_aggregates"]
        profile_fields = [
            "id", "name", "league", "country", "manager", "formation",
        ]
        agg_fields = [
            "total_transfers", "arrivals", "departures",
            "avg_market_value_at_transfer", "total_market_value_at_transfer",
        ]
        header = profile_fields + agg_fields
        row = [detail.get(f) for f in profile_fields] + [aggregates.get(f) for f in agg_fields]
        writer = csv.writer(Echo())

        def generate():
            yield writer.writerow(header)
            yield writer.writerow(row)

        return StreamingHttpResponse(
            generate(),
            content_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="club-{club.id}.csv"'},
        )


class ClubInsightsView(APIView):
    """POST /api/clubs/{id}/insights/ -- AI-04: AI-generated club insights
    (recruitment gaps, over-aged positions, financial constraints), grounded
    in position-needs + transfer-behaviour aggregates. No explicit
    permission_classes -- global IsAuthenticated default (matching
    ClubExportView; club data is not user-owned, so no IsOwner).

    A generation failure (ReportGeneratorError) returns a clean 503 --
    NEVER a fabricated report (locked decision #6). A nonexistent club's
    Http404 (from generate_club_insights' get_object_or_404) is left to
    surface naturally, not caught."""

    def post(self, request, pk):
        try:
            insights = services.generate_club_insights(pk)
        except ReportGeneratorError:
            return Response(
                {"error": "insights generation failed"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response(insights)


class PositionNeedsView(APIView):
    """GET /api/clubs/{id}/position-needs/ -- PLAN-01 (11-01-PLAN.md):
    per-position strong/weak/at-risk classification, extending Phase 10's
    position_needs_aggregate. Deterministic read (GET, not POST) -- no
    LLM call, no 503 path. No explicit permission_classes -- global
    IsAuthenticated default (matching ClubExportView/ClubInsightsView;
    club data is not user-owned). Nonexistent club -> natural Http404."""

    def get(self, request, pk):
        club = get_object_or_404(Club, pk=pk)
        return Response(services.classify_position_needs(club))


class ReplacementsView(APIView):
    """GET /api/clubs/{id}/replacements/?position=<POS> -- PLAN-02.

    Deterministic ranked replacement suggestions for a club's (already-known-weak)
    position. GET, no LLM/503 path. No explicit permission_classes -- global
    IsAuthenticated default (matching PositionNeedsView; club data is not user-owned).
    NOTE: this endpoint runs the arbitrary-other-club live scoring pass
    (score_population) and takes ~40-50s on the full real dataset by design
    (Phase 6 deferred this path here, uncached -- see 12-CONTEXT.md). Unknown club -> 404.
    A missing/invalid `position` query param -> 400.
    """

    def get(self, request, pk):
        get_object_or_404(Club, pk=pk)  # 404 fast on unknown club before the ~44s pass
        position = request.query_params.get("position")
        if not position:
            return Response(
                {"error": "position query parameter is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(rank_replacement_players(pk, position))
