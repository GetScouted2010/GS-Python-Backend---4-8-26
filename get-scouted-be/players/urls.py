from django.urls import path

from players.views import PlayerDetailView, PlayerListView, PlayerSearchView

urlpatterns = [
    path("", PlayerListView.as_view(), name="player-list"),
    path("search/", PlayerSearchView.as_view(), name="player-search"),
    path("<uuid:pk>/", PlayerDetailView.as_view(), name="player-detail"),
]
