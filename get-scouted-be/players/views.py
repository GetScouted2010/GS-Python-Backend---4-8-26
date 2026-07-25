"""Player read-layer views (07-02-PLAN.md): CRUD-01 (list, filter/sort/
paginate), CRUD-03 (detail, full profile + score breakdowns), CRUD-05
(?ids= multi-fetch, player half).

No explicit permission_classes are set on either view -- the project's
global DEFAULT_PERMISSION_CLASSES (IsAuthenticated) + DEFAULT_AUTHENTICATION
_CLASSES (JWTAuthentication) already deny-by-default (config/settings/base.py).
"""

from django.shortcuts import get_object_or_404
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import IdsBypassPagination
from players import services
from players.ai import fallback
from players.ai.base import NLQueryParserError
from players.ai.factory import get_nl_query_parser
from players.filters import PlayerFilter
from players.models import Player
from players.serializers import PlayerDetailSerializer, PlayerListSerializer
from scoring.exceptions import null_with_reason
from scoring.services import rmm, summary
from workspace.models import RecentActivity


class PlayerListView(generics.ListAPIView):
    """GET /api/players/ -- CRUD-01 (filter/sort/paginate) + CRUD-05 (?ids=)."""

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
    """GET /api/players/{id}/?club_id=<uuid> -- CRUD-03.

    Full profile + single labeled season + all four score breakdowns.
    club_id defaults to the player's own current club (the Phase-6 fast
    own-club path). If the player has NO club, get_summary() would raise a
    misleading Http404 (resolve_club_name(None) -> get_object_or_404) -- so
    branch explicitly: RMM is context-free and still computed, the 3
    club-dependent scores return the shared null+reason envelope.
    """

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


class PlayerSearchView(APIView):
    """POST /api/players/search/ -- AI-01/AI-02 natural-language search.

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
