from django.urls import path

from players.views import (
    ClubMatchesView,
    PlayerDetailView,
    PlayerListView,
    PlayerScoutingReportView,
    PlayerSearchView,
)

urlpatterns = [
    path("", PlayerListView.as_view(), name="player-list"),
    path("search/", PlayerSearchView.as_view(), name="player-search"),
    path("<uuid:pk>/scouting-report/", PlayerScoutingReportView.as_view(), name="player-scouting-report"),
    path("<uuid:pk>/club-matches/", ClubMatchesView.as_view(), name="player-club-matches"),
    path("<uuid:pk>/", PlayerDetailView.as_view(), name="player-detail"),
]
