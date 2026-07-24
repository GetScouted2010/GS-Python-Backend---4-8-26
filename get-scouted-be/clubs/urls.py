from django.urls import path

from clubs.views import ClubDetailView, ClubListView

urlpatterns = [
    path("", ClubListView.as_view(), name="club-list"),
    path("<uuid:pk>/", ClubDetailView.as_view(), name="club-detail"),
]
