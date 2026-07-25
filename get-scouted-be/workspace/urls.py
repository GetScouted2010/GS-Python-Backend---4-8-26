from django.urls import path
from rest_framework.routers import DefaultRouter

from workspace.views import (
    RecentActivityListView,
    ShortlistViewSet,
    SquadPlanViewSet,
    WatchlistViewSet,
)

router = DefaultRouter()
router.register("watchlist", WatchlistViewSet, basename="watchlist")
router.register("shortlists", ShortlistViewSet, basename="shortlist")
router.register("squad-plans", SquadPlanViewSet, basename="squad-plan")

urlpatterns = [
    path("activity/", RecentActivityListView.as_view(), name="recent-activity"),
] + router.urls
