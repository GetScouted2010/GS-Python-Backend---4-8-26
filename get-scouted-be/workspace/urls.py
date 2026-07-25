from rest_framework.routers import DefaultRouter

from workspace.views import ShortlistViewSet, SquadPlanViewSet, WatchlistViewSet

router = DefaultRouter()
router.register("watchlist", WatchlistViewSet, basename="watchlist")
router.register("shortlists", ShortlistViewSet, basename="shortlist")
router.register("squad-plans", SquadPlanViewSet, basename="squad-plan")

urlpatterns = router.urls
