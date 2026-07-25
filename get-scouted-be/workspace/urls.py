from rest_framework.routers import DefaultRouter

from workspace.views import WatchlistViewSet

router = DefaultRouter()
router.register("watchlist", WatchlistViewSet, basename="watchlist")

urlpatterns = router.urls
