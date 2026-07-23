"""URL wiring for scoring/views.py's five endpoints (04-06-PLAN.md), included
into config/urls.py under `api/scoring/`.
"""

from django.urls import path

from .views import (
    CompatibilityView,
    FinancialFitView,
    PlayerImpactView,
    PlayerScoreSummaryView,
    TransferProbabilityView,
)

urlpatterns = [
    path("players/<uuid:player_id>/impact/", PlayerImpactView.as_view(), name="player-impact"),
    path(
        "players/<uuid:player_id>/clubs/<uuid:club_id>/compatibility/",
        CompatibilityView.as_view(),
        name="player-club-compatibility",
    ),
    path(
        "players/<uuid:player_id>/clubs/<uuid:club_id>/financial-fit/",
        FinancialFitView.as_view(),
        name="player-club-financial-fit",
    ),
    path(
        "players/<uuid:player_id>/clubs/<uuid:club_id>/transfer-probability/",
        TransferProbabilityView.as_view(),
        name="player-club-transfer-probability",
    ),
    path("players/<uuid:player_id>/summary/", PlayerScoreSummaryView.as_view(), name="player-score-summary"),
]
