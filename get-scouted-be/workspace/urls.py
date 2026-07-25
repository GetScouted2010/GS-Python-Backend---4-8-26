from rest_framework.routers import DefaultRouter

from workspace.views import ShortlistViewSet, WatchlistViewSet

router = DefaultRouter()
router.register("watchlist", WatchlistViewSet, basename="watchlist")
router.register("shortlists", ShortlistViewSet, basename="shortlist")

urlpatterns = router.urls
