"""Thin DRF APIViews exposing the four score services + the combined
summary as five authenticated endpoints under /api/scoring/ (04-06-PLAN.md).

Completes SCORE-01..05's "exposed via API" clause. Views do exactly three
things: validate the Player exists (get_object_or_404), delegate to the
scoring.services.* layer, and wrap the result in a Response -- zero scoring
math lives here (ARCHITECTURE Pattern 1 / Anti-Pattern 1). No explicit
permission_classes are set -- the project's global DEFAULT_PERMISSION_CLASSES
(IsAuthenticated) + DEFAULT_AUTHENTICATION_CLASSES (JWTAuthentication)
already deny-by-default (config/settings/base.py).

Service calls are NOT wrapped in a broad try/except: each service already
returns the shared null+reason envelope for genuine missing-data cases, and
already raises Http404 for an unknown player/club (DRF's exception handler
turns that into a 404 response automatically) -- swallowing a reconstruction
ValueError into a fabricated null response here would hide a real bug
(Pitfall 5), so it is left to surface as a 500 instead.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from players.models import Player
from scoring.services import compatibility, financial_fit, rmm, summary, transfer_probability


class PlayerImpactView(APIView):
    """GET /api/scoring/players/<uuid:player_id>/impact/ -- RMM (SCORE-01)."""

    def get(self, request, player_id):
        get_object_or_404(Player, id=player_id)
        return Response(rmm.get_rmm(player_id))


class CompatibilityView(APIView):
    """GET /api/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/compatibility/ -- SCORE-02."""

    def get(self, request, player_id, club_id):
        return Response(compatibility.get_compatibility(player_id, club_id))


class FinancialFitView(APIView):
    """GET /api/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/financial-fit/ -- SCORE-03."""

    def get(self, request, player_id, club_id):
        return Response(financial_fit.get_financial_fit(player_id, club_id))


class TransferProbabilityView(APIView):
    """GET /api/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/transfer-probability/ -- SCORE-04."""

    def get(self, request, player_id, club_id):
        return Response(transfer_probability.get_transfer_probability(player_id, club_id))


class PlayerScoreSummaryView(APIView):
    """GET /api/scoring/players/<uuid:player_id>/summary/?club_id=<uuid> -- SCORE-05.

    club_id is a QUERY param here, not a path segment (the combined Player
    Profile view needs a single-player URL with the club chosen separately).
    """

    def get(self, request, player_id):
        club_id = request.query_params.get("club_id")
        if not club_id:
            return Response({"detail": "club_id query parameter is required"}, status=400)
        return Response(summary.get_summary(player_id, club_id))
