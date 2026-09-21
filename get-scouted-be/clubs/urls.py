from django.urls import path

from clubs.views import (
    ClubDetailView, ClubExportView, ClubInsightsView, ClubListView, LeagueListView,
    PositionNeedsView, ReplacementsView,
)

urlpatterns = [
    path("", ClubListView.as_view(), name="club-list"),
    path("leagues/", LeagueListView.as_view(), name="club-league-list"),
    path("<uuid:pk>/export/", ClubExportView.as_view(), name="club-export"),
    path("<uuid:pk>/insights/", ClubInsightsView.as_view(), name="club-insights"),
    path("<uuid:pk>/position-needs/", PositionNeedsView.as_view(), name="club-position-needs"),
    path("<uuid:pk>/replacements/", ReplacementsView.as_view(), name="club-replacements"),
    path("<uuid:pk>/", ClubDetailView.as_view(), name="club-detail"),
]
