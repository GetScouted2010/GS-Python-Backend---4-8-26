"""Thin DRF APIViews exposing the four score services + the combined
summary as five authenticated endpoints under /api/v1/scoring/ (04-06-PLAN.md).

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
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from players.models import Player
from scoring.services import compatibility, financial_fit, rmm, summary, transfer_probability

_CLUB_DEPENDENT_NOTE = (
    "Club-dependent — the same player scores differently against different "
    "clubs, since this factors in the buying club's style/squad/spending "
    "profile, not just the player in isolation."
)


class PlayerImpactView(APIView):
    """GET /api/v1/scoring/players/<uuid:player_id>/impact/ -- RMM (SCORE-01)."""

    @extend_schema(
        tags=["scoring"],
        summary="Get a player's RMM (Impact) score",
        description=(
            "Real Match Metric — a player's overall impact score, computed "
            "from their real performance stats via a position-specific "
            "calculator. **Club-independent**: unlike the other three "
            "scores below, RMM doesn't change based on which club you "
            "compare against — a player's own ability doesn't depend on "
            "who's asking. Returns the score plus its full component "
            "breakdown, never just a bare number. Read from a denormalized "
            "field (O(1)), not recomputed live."
        ),
        responses={200: OpenApiResponse(description="RMM score + component breakdown."), 404: OpenApiResponse(description="Unknown player.")},
    )
    def get(self, request, player_id):
        get_object_or_404(Player, id=player_id)
        return Response(rmm.get_rmm(player_id))


class CompatibilityView(APIView):
    """GET /api/v1/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/compatibility/ -- SCORE-02."""

    @extend_schema(
        tags=["scoring"],
        summary="Get a player's Compatibility Score (CS) against a club",
        description=(
            "How well a player's playing style/role fits a specific club's "
            "tactical profile. " + _CLUB_DEPENDENT_NOTE + " Fast (O(1)) "
            "when `club_id` is the player's own current club (memoized); "
            "an arbitrary other club still computes live but stays "
            "sub-second on this dataset. Returns the score plus its "
            "component breakdown."
        ),
        responses={200: OpenApiResponse(description="Compatibility score + component breakdown."), 404: OpenApiResponse(description="Unknown player or club.")},
    )
    def get(self, request, player_id, club_id):
        return Response(compatibility.get_compatibility(player_id, club_id))


class FinancialFitView(APIView):
    """GET /api/v1/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/financial-fit/ -- SCORE-03."""

    @extend_schema(
        tags=["scoring"],
        summary="Get a player's Financial Fit (TFM) against a club",
        description=(
            "A trained ML model's predicted transfer fee and a "
            "bargain/overpriced/fair verdict for this player, priced "
            "specifically against the given club's spending profile. "
            + _CLUB_DEPENDENT_NOTE + " Changing `club_id` genuinely changes "
            "the predicted fee — it isn't just a label on an unchanged "
            "number. Returns `predicted_fee`, `value_verdict`, and the "
            "underlying feature breakdown."
        ),
        responses={200: OpenApiResponse(description="Predicted fee, value verdict, feature breakdown."), 404: OpenApiResponse(description="Unknown player or club.")},
    )
    def get(self, request, player_id, club_id):
        return Response(financial_fit.get_financial_fit(player_id, club_id))


class TransferProbabilityView(APIView):
    """GET /api/v1/scoring/players/<uuid:player_id>/clubs/<uuid:club_id>/transfer-probability/ -- SCORE-04."""

    @extend_schema(
        tags=["scoring"],
        summary="Get a player's Transfer Probability against a club",
        description=(
            "A single deterministic (non-ML) blended score estimating how "
            "likely this transfer is to happen, combining Compatibility, "
            "performance, Financial Fit, and contract situation into one "
            "number via a fixed formula — no black-box weighting. "
            + _CLUB_DEPENDENT_NOTE + " This is also the primary ranking key "
            "used by the bidirectional matching endpoints "
            "(`clubs/{id}/replacements/`, `players/{id}/club-matches/`)."
        ),
        responses={200: OpenApiResponse(description="Transfer probability + component breakdown."), 404: OpenApiResponse(description="Unknown player or club.")},
    )
    def get(self, request, player_id, club_id):
        return Response(transfer_probability.get_transfer_probability(player_id, club_id))


class PlayerScoreSummaryView(APIView):
    """GET /api/v1/scoring/players/<uuid:player_id>/summary/?club_id=<uuid> -- SCORE-05.

    club_id is a QUERY param here, not a path segment (the combined Player
    Profile view needs a single-player URL with the club chosen separately).
    """

    @extend_schema(
        tags=["scoring"],
        summary="Get all four scores for a player + club in one call",
        description=(
            "Convenience endpoint combining RMM, Compatibility, Financial "
            "Fit, and Transfer Probability into a single response — saves "
            "4 separate round trips when you need the full picture (e.g. "
            "for a player profile screen). `club_id` is a **query** "
            "parameter here rather than part of the path, since the same "
            "single-player URL needs to work with a club chosen "
            "separately by the caller. Each of the 4 scores in the "
            "response still carries its own breakdown, same as calling "
            "the individual endpoints."
        ),
        parameters=[
            OpenApiParameter(
                "club_id", type=str, location=OpenApiParameter.QUERY, required=True,
                description="UUID of the club to score against. Required — a 400 is returned if omitted.",
            ),
        ],
        responses={
            200: OpenApiResponse(description="All 4 scores, each with its own breakdown."),
            400: OpenApiResponse(description="club_id query parameter is required."),
            404: OpenApiResponse(description="Unknown player or club."),
        },
    )
    def get(self, request, player_id):
        club_id = request.query_params.get("club_id")
        if not club_id:
            return Response({"detail": "club_id query parameter is required"}, status=400)
        return Response(summary.get_summary(player_id, club_id))
