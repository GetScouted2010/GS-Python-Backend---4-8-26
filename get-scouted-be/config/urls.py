from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/scoring/", include("scoring.urls")),
    path("api/players/", include("players.urls")),
]
