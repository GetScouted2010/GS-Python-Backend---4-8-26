from django.urls import path

from clubs.views import ClubDetailView, ClubExportView, ClubListView

urlpatterns = [
    path("", ClubListView.as_view(), name="club-list"),
    path("<uuid:pk>/export/", ClubExportView.as_view(), name="club-export"),
    path("<uuid:pk>/", ClubDetailView.as_view(), name="club-detail"),
]
