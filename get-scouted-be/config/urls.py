from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

# v1 is the only version today; every app's URLs live under this one literal
# prefix (see REST_FRAMEWORK's DEFAULT_VERSIONING_CLASS/DEFAULT_VERSION for how
# `request.version` gets populated from it without a per-pattern <version> group).
v1_urlpatterns = [
    path("auth/", include("accounts.urls")),
    path("scoring/", include("scoring.urls")),
    path("players/", include("players.urls")),
    path("clubs/", include("clubs.urls")),
    path("workspace/", include("workspace.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(v1_urlpatterns)),
    # OpenAPI schema + docs UIs -- unversioned surface describing the v1 API.
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
