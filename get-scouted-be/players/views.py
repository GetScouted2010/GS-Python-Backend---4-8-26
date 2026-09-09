"""Player read-layer views (07-02-PLAN.md): CRUD-01 (list, filter/sort/
paginate), CRUD-03 (detail, full profile + score breakdowns), CRUD-05
(?ids= multi-fetch, player half).

No explicit permission_classes are set on either view -- the project's
global DEFAULT_PERMISSION_CLASSES (IsAuthenticated) + DEFAULT_AUTHENTICATION
_CLASSES (JWTAuthentication) already deny-by-default (config/settings/base.py).
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import generics, serializers
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from core.exceptions import ServiceUnavailableError
from core.pagination import IdsBypassPagination
from players import services
from players.ai import fallback
from players.ai.base import NLQueryParserError
from players.ai.factory import get_nl_query_parser
from players.ai.report_generator import ReportGeneratorError
from players.filters import PlayerFilter
from players.models import Player
from players.serializers import PlayerDetailSerializer, PlayerListSerializer
from scoring.exceptions import null_with_reason
from scoring.services import rmm, summary
from scoring.services.matching import rank_clubs_for_player
from workspace.models import RecentActivity


@extend_schema_view(
    get=extend_schema(
        tags=["players"],
        summary="List / filter / search players",
        description=(
            "Browse the full player dataset with filtering, sorting, and "
            "pagination — position, age, market value, league, score "
            "thresholds, and playing style (resolved through the player's "
            "current club). Player rows are player-SEASON records: results "
            "are always scoped to ONE season, defaulting to the latest "
            "(`Last Calendar Year`) when `?season=` is omitted — pass "
            "`?season=2023-2024` etc. to view a different one. Pass "
            "`?ids=<uuid>,<uuid>,...` instead of the normal filters to "
            "fetch a specific set of players by id in one call (used for "
            "side-by-side comparison) — this bypasses pagination AND the "
            "season default entirely (an explicit id already pins one exact "
            "season-row) and returns a plain list. For plain-English "
            "queries instead of structured filters, use **Search players** "
            "below."
        ),
        parameters=[
            OpenApiParameter("ids", type=str, location=OpenApiParameter.QUERY, required=False, description="Comma-separated player UUIDs — bypasses filtering/pagination/season-default, returns exactly these players."),
            OpenApiParameter("season", type=str, location=OpenApiParameter.QUERY, required=False, description="One of `Last Calendar Year`, `2024-2025`, `2023-2024`, `2022-2023`. Defaults to `Last Calendar Year` (the latest) when omitted."),
            OpenApiParameter("ordering", type=str, location=OpenApiParameter.QUERY, required=False, description="Sort field, e.g. `-impact_score` (default) or `age`."),
            OpenApiParameter("page_size", type=int, location=OpenApiParameter.QUERY, required=False, description="Results per page (only applies when not using ?ids=)."),
        ],
    )
)
class PlayerListView(generics.ListAPIView):
    """GET /api/v1/players/ -- CRUD-01 (filter/sort/paginate) + CRUD-05 (?ids=)."""

    queryset = Player.objects.all()
    serializer_class = PlayerListSerializer
    filterset_class = PlayerFilter
    pagination_class = IdsBypassPagination
    ordering_fields = [
        "age", "market_value",
        "impact_score", "compatibility_score",
        "financial_fit_score", "transfer_probability_score",
    ]
    ordering = ["-impact_score"]  # deterministic default, not Postgres insertion order


class PlayerDetailView(APIView):
    """GET /api/v1/players/{id}/?club_id=<uuid> -- CRUD-03.

    Full profile + single labeled season + all four score breakdowns.
    club_id defaults to the player's own current club (the Phase-6 fast
    own-club path). If the player has NO club, get_summary() would raise a
    misleading Http404 (resolve_club_name(None) -> get_object_or_404) -- so
    branch explicitly: RMM is context-free and still computed, the 3
    club-dependent scores return the shared null+reason envelope.
    """

    @extend_schema(
        tags=["players"],
        summary="Get a player's full profile + scores",
        description=(
            "Full player profile (identity, position, contract, latest "
            "season stats) plus all four computed scores (RMM, "
            "Compatibility, Financial Fit, Transfer Probability). "
            "`club_id` defaults to the player's own current club if "
            "omitted. If the player has no club at all, RMM is still "
            "computed (it's club-independent) but the three club-dependent "
            "scores come back as `null` with an explicit `reason` — never "
            "silently zeroed or omitted. Also logs a `viewed_player` "
            "entry to the caller's Recent Activity."
        ),
        parameters=[
            OpenApiParameter("club_id", type=str, location=OpenApiParameter.QUERY, required=False, description="UUID of the club to score against. Defaults to the player's own current club."),
        ],
        responses={200: OpenApiResponse(description="Player profile + scores object."), 404: OpenApiResponse(description="Unknown player.")},
    )
    def get(self, request, pk):
        player = get_object_or_404(Player, id=pk)
        RecentActivity.objects.create(
            user=request.user, activity_type="viewed_player", target_id=player.id
        )
        profile = PlayerDetailSerializer(player).data

        club_id = request.query_params.get("club_id") or player.club_id
        if club_id is None:
            scores = {
                "rmm": rmm.get_rmm(pk),
                "compatibility": null_with_reason("compatibility_score", "player_has_no_club"),
                "financial_fit": null_with_reason("financial_fit", "player_has_no_club"),
                "transfer_probability": null_with_reason("transfer_probability", "player_has_no_club"),
            }
        else:
            scores = summary.get_summary(pk, club_id)

        return Response({**profile, "scores": scores})


class PlayerScoutingReportView(APIView):
    """POST /api/v1/players/{id}/scouting-report/ -- AI-03.

    Thin orchestration: all grounding/retry/validation logic lives inside
    the Wave-2 generator (players.ai.report_generator /
    players.ai.report_factory); this view only resolves club context,
    calls the service, and maps ReportGeneratorError to a clean 503 --
    NEVER a fabricated/template report.

    No explicit permission_classes -- the global IsAuthenticated default
    already denies anonymous, matching every other players view.
    """

    @extend_schema(
        tags=["players"],
        summary="Generate an AI scouting report for a player",
        description=(
            "Generates narrative scouting text (strengths, weaknesses, fit "
            "assessment) grounded in this player's real computed scores "
            "against the given club. **Every number that appears in the "
            "narrative is validated against the real pre-computed scores "
            "before the response is returned** — if the LLM's output "
            "doesn't check out, generation is retried once with corrective "
            "feedback, then fails clean rather than ever return a "
            "fabricated report. `club_id` defaults to the player's own "
            "current club; if the player has no club at all, `club_id` "
            "must be supplied explicitly (400 otherwise). Slower than the "
            "deterministic endpoints — this is a real LLM call, not a "
            "cached lookup."
        ),
        request=inline_serializer(
            "ScoutingReportRequest",
            fields={"club_id": serializers.UUIDField(required=False)},
        ),
        responses={
            200: OpenApiResponse(description="Generated report + the grounding scores it's based on."),
            400: OpenApiResponse(description="club_id required (player has no current club)."),
            404: OpenApiResponse(description="Unknown player."),
            503: OpenApiResponse(description="Report generation failed (LLM error or failed grounding validation twice) — never a fabricated report."),
        },
        examples=[OpenApiExample("Request body", value={"club_id": "b3f1e2a0-....."}, request_only=True)],
    )
    def post(self, request, pk):
        player = get_object_or_404(Player, id=pk)

        club_id = request.data.get("club_id") or player.club_id
        if club_id is None:
            raise ValidationError({"club_id": "Required for a club-relative scouting report."})

        try:
            report = services.generate_scouting_report(pk, club_id)
        except ReportGeneratorError:
            raise ServiceUnavailableError("Report generation failed.") from None

        return Response(report)


class ClubMatchesView(APIView):
    """GET /api/v1/players/{id}/club-matches/ -- PLAN-04.

    Deterministic ranked list of clubs that fit this player (Player -> Club
    matching), scored by CS + real TFM, sorted by transfer_probability, own
    current club excluded, bounded to top-N. GET, no LLM/503 path. No
    explicit permission_classes -- global IsAuthenticated default (matching
    PositionNeedsView; this data is not user-owned).

    Runs the Pattern 2 per-club loop live (see 12-03-SUMMARY.md /
    12-04-SUMMARY.md for measured latency: ~78.3-78.7s cold against the real
    41,708-player/1,060-club dev DB -- no caching added per 12-CONTEXT.md's
    explicit deferred-caching decision for this phase). Unknown player ->
    404 (Http404 raised inside rank_clubs_for_player).
    """

    @extend_schema(
        tags=["players"],
        summary="Rank clubs that fit this player (Player -> Club matching)",
        description=(
            "The mirror image of **Rank replacement players** on the "
            "clubs side: given a player, ranks real candidate clubs by how "
            "well they fit — Compatibility Score + real Financial Fit, "
            "sorted by Transfer Probability. The player's own current club "
            "is excluded (matching a player to their existing club isn't a "
            "transfer suggestion). Bounded to a top-N list, not a full "
            "browse. Fully deterministic — no LLM, no 503 path. "
            "**Slow by design**: computes live against every real club "
            "(~1,060), typically 40s-2min on the full dataset — this is a "
            "\"suggestions\" surface, not a hot path, and isn't cached "
            "on purpose."
        ),
        responses={200: OpenApiResponse(description="Top-N ranked club list with CS/TFM breakdown per entry."), 404: OpenApiResponse(description="Unknown player.")},
    )
    def get(self, request, pk):
        get_object_or_404(Player, id=pk)  # fast 404 on unknown player
        return Response(rank_clubs_for_player(pk))


class PlayerSearchView(APIView):
    """POST /api/v1/players/search/ -- AI-01/AI-02 natural-language search.

    3-tier degradation, always HTTP 200:
      tier 1: the provider-agnostic LLM parser (players.ai.factory).
      tier 2: NLQueryParserError -> the deterministic keyword extractor.
      tier 3: keyword extractor also yields nothing -> unfiltered list.
    Exactly one RecentActivity(activity_type="searched") row is logged per
    call regardless of which tier actually served the request (completes
    the "searched" producer contract Phase 8 reserved for this endpoint).

    No explicit permission_classes -- the global IsAuthenticated default
    already denies anonymous, matching every other players view.
    """

    @extend_schema(
        tags=["players"],
        summary="Search players with a plain-English query",
        description=(
            "Turns a natural-language description into structured player "
            "filters and returns matching results — the alternative to "
            "manually building query params on **List / filter players**. "
            "**Always returns 200**, degrading gracefully through 3 tiers: "
            "(1) an LLM parses the query into structured filters, "
            "(2) if the LLM call fails, a deterministic keyword/regex "
            "extractor takes over, (3) if that also finds nothing usable, "
            "an unfiltered list is returned rather than an error. The "
            "response's `fallback_used` field tells you whether tier 1 "
            "(LLM) or tier 2 (keyword fallback) actually served the "
            "request — a successful-but-empty LLM parse still counts as "
            "tier 1. Logs a `searched` entry to the caller's Recent Activity."
        ),
        request=inline_serializer("PlayerSearchRequest", fields={"query": serializers.CharField()}),
        examples=[OpenApiExample("Request body", value={"query": "young left-backs under €5M at possession-based clubs"}, request_only=True)],
        responses={200: OpenApiResponse(description="query, parsed_filters, fallback_used, and results.")},
    )
    def post(self, request):
        query = request.data.get("query", "")

        fallback_used = False
        try:
            parsed = get_nl_query_parser().parse(query)  # tier 1
            filters = parsed.filters
        except NLQueryParserError:
            filters = fallback.keyword_extract(query)  # tier 2 (deterministic)
            fallback_used = True
        # tier 3: keyword extractor produced nothing usable -> unfiltered list
        if not filters and fallback_used:
            filters = {}  # already empty; explicit for clarity
        # Note: a SUCCESSFUL-but-partial/empty tier-1 parse stays
        # fallback_used=False (it is still "the LLM's real answer").
        # fallback_used only flips true when the LLM CALL failed and tier 2
        # took over.

        results = services.search_players(filters, request)

        RecentActivity.objects.create(
            user=request.user, activity_type="searched", query_text=query, target_id=None
        )

        return Response(
            {
                "query": query,
                "parsed_filters": filters,
                "fallback_used": fallback_used,
                "results": results,
            }
        )
