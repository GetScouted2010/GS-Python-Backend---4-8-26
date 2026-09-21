"""Club read-layer views (07-03-PLAN.md): CRUD-02 (list, filter/paginate),
CRUD-04 (detail, full profile + squad + transfer aggregates), CRUD-05
(?ids= multi-fetch, club half).

No explicit permission_classes are set on either view -- the project's
global DEFAULT_PERMISSION_CLASSES (IsAuthenticated) + DEFAULT_AUTHENTICATION
_CLASSES (JWTAuthentication) already deny-by-default (config/settings/base.py).
"""

import csv

from django.db.models import Count
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from clubs import services
from clubs.filters import ClubFilter
from clubs.leagues import league_country
from clubs.models import Club
from clubs.serializers import ClubDetailSerializer, ClubListSerializer
from core.exceptions import ServiceUnavailableError
from core.pagination import IdsBypassPagination
from players.ai.report_generator import ReportGeneratorError
from players.season import request_season
from scoring.services.matching import rank_replacement_players
from workspace.models import RecentActivity


class Echo:
    """Write-only buffer that returns the value instead of storing it
    (verbatim Django docs streaming-CSV pattern). Duplicated from
    workspace/views.py rather than cross-app imported, keeping club-data
    concerns inside the clubs app."""

    def write(self, value):
        return value


@extend_schema_view(
    get=extend_schema(
        tags=["clubs"],
        summary="List / filter clubs",
        description=(
            "Browse the full club dataset with filtering, sorting, and "
            "pagination — league, country, squad profile fields. Pass "
            "`?ids=<uuid>,<uuid>,...` instead of the normal filters to "
            "fetch a specific set of clubs by id in one call (side-by-side "
            "comparison) — bypasses pagination, returns a plain list."
        ),
        parameters=[
            OpenApiParameter("ids", type=str, location=OpenApiParameter.QUERY, required=False, description="Comma-separated club UUIDs — bypasses filtering/pagination, returns exactly these clubs."),
        ],
    )
)
class ClubListView(generics.ListAPIView):
    """GET /api/v1/clubs/ -- CRUD-02 (filter/paginate) + CRUD-05 (?ids=)."""

    queryset = Club.objects.all()
    serializer_class = ClubListSerializer
    filterset_class = ClubFilter
    pagination_class = IdsBypassPagination
    ordering_fields = ["name", "league", "country"]
    ordering = ["name"]


@extend_schema_view(
    get=extend_schema(
        tags=["clubs"],
        summary="Get a club's full profile",
        description=(
            "Full club profile — identity, playing style, current squad, "
            "and transfer-history aggregates (arrivals/departures, avg "
            "market value at transfer). Pure ORM aggregation, no live "
            "scoring pass, so this is always fast. Also logs a "
            "`viewed_club` entry to the caller's Recent Activity."
        ),
        responses={200: OpenApiResponse(description="Club profile + squad + transfer aggregates."), 404: OpenApiResponse(description="Unknown club.")},
    )
)
class ClubDetailView(generics.RetrieveAPIView):
    """GET /api/v1/clubs/{id}/ -- CRUD-04 (profile + squad + transfer aggregates).

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
    """GET /api/v1/clubs/{id}/export/ -- CRUD-10: streams a text/csv of the club
    profile + transfer aggregates, reusing ClubDetailSerializer so the
    exported numbers never diverge from the API. IsAuthenticated only (the
    project global default) -- club data is not user-owned, so no IsOwner."""

    @extend_schema(
        tags=["clubs"],
        summary="Export a club report as CSV",
        description=(
            "Streams the same profile + transfer-aggregate data as "
            "**Get a club's full profile**, as a downloadable "
            "`text/csv` file instead of JSON — reuses the same "
            "serializer under the hood so the exported numbers can never "
            "drift from what the API shows."
        ),
        responses={200: OpenApiResponse(description="text/csv file download.")},
    )
    def get(self, request, pk):
        club = get_object_or_404(Club, pk=pk)
        detail = ClubDetailSerializer(club, context={"request": request}).data
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
    """POST /api/v1/clubs/{id}/insights/ -- AI-04: AI-generated club insights
    (recruitment gaps, over-aged positions, financial constraints), grounded
    in position-needs + transfer-behaviour aggregates. No explicit
    permission_classes -- global IsAuthenticated default (matching
    ClubExportView; club data is not user-owned, so no IsOwner).

    A generation failure (ReportGeneratorError) returns a clean 503 --
    NEVER a fabricated report (locked decision #6). A nonexistent club's
    Http404 (from generate_club_insights' get_object_or_404) is left to
    surface naturally, not caught."""

    @extend_schema(
        tags=["clubs"],
        summary="Generate AI insights for a club",
        description=(
            "Generates narrative insights about a club — recruitment "
            "gaps, over-aged positions, financial constraints — grounded "
            "in the same position-needs classification and transfer-"
            "behaviour aggregates available elsewhere in the API, not "
            "invented by the LLM. Numbers in the narrative are validated "
            "against those real aggregates before the response is "
            "returned. A generation failure returns a clean 503 rather "
            "than a fabricated report — never trust an insights response "
            "you didn't get a 200 for."
        ),
        request=None,
        responses={
            200: OpenApiResponse(description="Generated insights + the grounding aggregates they're based on."),
            404: OpenApiResponse(description="Unknown club."),
            503: OpenApiResponse(description="Insights generation failed — never a fabricated report."),
        },
    )
    def post(self, request, pk):
        try:
            insights = services.generate_club_insights(pk)
        except ReportGeneratorError:
            raise ServiceUnavailableError("Insights generation failed.") from None
        return Response(insights)


class PositionNeedsView(APIView):
    """GET /api/v1/clubs/{id}/position-needs/ -- PLAN-01 (11-01-PLAN.md):
    per-position strong/weak/at-risk classification, extending Phase 10's
    position_needs_aggregate. Deterministic read (GET, not POST) -- no
    LLM call, no 503 path. No explicit permission_classes -- global
    IsAuthenticated default (matching ClubExportView/ClubInsightsView;
    club data is not user-owned). Nonexistent club -> natural Http404."""

    @extend_schema(
        tags=["clubs"],
        summary="Get a club's position-needs breakdown",
        description=(
            "Classifies every position on the club's squad as `strong`, "
            "`weak` (depth below 2), or `at-risk` (adequate depth but "
            "average age over 30, or half or more of the squad's "
            "contracts expiring within 12 months). **Call this first** to "
            "find out which position is weak, then pass that position to "
            "**Rank replacement players** below. Deterministic — no LLM, "
            "always fast. Computed over one season's squad "
            "(`season`, default the latest)."
        ),
        parameters=[
            OpenApiParameter("season", type=str, location=OpenApiParameter.QUERY, required=False, description="Season whose squad to classify (e.g. 2025-2026). Defaults to the latest season."),
        ],
        responses={200: OpenApiResponse(description="Per-position classification + depth/age/contract detail."), 404: OpenApiResponse(description="Unknown club.")},
    )
    def get(self, request, pk):
        club = get_object_or_404(Club, pk=pk)
        return Response(services.classify_position_needs(club, request_season(request)))


class ReplacementsView(APIView):
    """GET /api/v1/clubs/{id}/replacements/?position=<POS> -- PLAN-02.

    Deterministic ranked replacement suggestions for a club's (already-known-weak)
    position. GET, no LLM/503 path. No explicit permission_classes -- global
    IsAuthenticated default (matching PositionNeedsView; club data is not user-owned).
    NOTE: this endpoint runs the arbitrary-other-club live scoring pass
    (score_population) and takes ~40-50s on the full real dataset by design
    (Phase 6 deferred this path here, uncached -- see 12-CONTEXT.md). Unknown club -> 404.
    A missing/invalid `position` query param -> 400.
    """

    @extend_schema(
        tags=["clubs"],
        summary="Rank replacement players for a weak position",
        description=(
            "Given a position you already know is weak (see **Get a "
            "club's position-needs breakdown** above), returns a ranked "
            "list of real candidate players for that position across the "
            "whole dataset — ordered by RMM/Compatibility/real Financial "
            "Fit, sorted by Transfer Probability. Players already on this "
            "club's squad are excluded (a \"replacement\" is by definition "
            "someone not already there). Bounded to a top-N list, not a "
            "full browse. Fully deterministic — no LLM, no 503 path. "
            "**Slow by design**: scores the entire ~41,708-player "
            "population against this one club in a single live pass, "
            "typically 40-50s — this is a \"suggestions\" surface, not a "
            "hot path, and isn't cached on purpose."
        ),
        parameters=[
            OpenApiParameter("position", type=str, location=OpenApiParameter.QUERY, required=True, description="Position code to search for replacements in (e.g. CB, LB, ST). Required — 400 if omitted."),
        ],
        responses={
            200: OpenApiResponse(description="Top-N ranked replacement list with RMM/CS/TFM breakdown per entry."),
            400: OpenApiResponse(description="position query parameter is required."),
            404: OpenApiResponse(description="Unknown club."),
        },
    )
    def get(self, request, pk):
        get_object_or_404(Club, pk=pk)  # 404 fast on unknown club before the ~44s pass
        position = request.query_params.get("position")
        if not position:
            raise ValidationError({"position": "This query parameter is required."})
        return Response(rank_replacement_players(pk, position))


class LeagueListView(APIView):
    """GET /api/v1/clubs/leagues/ -- the leagues a league -> club dropdown
    can offer, each with how many clubs it holds. Feeds
    `GET /api/v1/clubs/?league=<league>` (the second step of the cascade)."""

    @extend_schema(
        tags=["clubs"],
        summary="List available leagues",
        description=(
            "Every league that has at least one club, with a club count and "
            "the league's country. Use the `league` value verbatim as the "
            "`league` filter on `GET /clubs/` (to list that league's clubs) "
            "or on `GET /players/`. Sorted by league name."
        ),
        responses={200: OpenApiResponse(description="List of {league, country, club_count}.")},
    )
    def get(self, request):
        rows = (
            Club.objects.exclude(league__isnull=True)
            .exclude(league="")
            .values("league")
            .annotate(club_count=Count("id"))
            .order_by("league")
        )
        return Response(
            [
                {
                    "league": row["league"],
                    "country": league_country(row["league"]),
                    "club_count": row["club_count"],
                }
                for row in rows
            ]
        )
