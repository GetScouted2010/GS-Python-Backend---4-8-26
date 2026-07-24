from django.urls import path

from players.views import PlayerDetailView, PlayerListView

urlpatterns = [
    path("", PlayerListView.as_view(), name="player-list"),
    path("<uuid:pk>/", PlayerDetailView.as_view(), name="player-detail"),
]
