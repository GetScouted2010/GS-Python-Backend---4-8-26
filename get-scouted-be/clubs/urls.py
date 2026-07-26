from django.urls import path

from clubs.views import ClubDetailView, ClubExportView, ClubInsightsView, ClubListView

urlpatterns = [
    path("", ClubListView.as_view(), name="club-list"),
    path("<uuid:pk>/export/", ClubExportView.as_view(), name="club-export"),
    path("<uuid:pk>/insights/", ClubInsightsView.as_view(), name="club-insights"),
    path("<uuid:pk>/", ClubDetailView.as_view(), name="club-detail"),
]
