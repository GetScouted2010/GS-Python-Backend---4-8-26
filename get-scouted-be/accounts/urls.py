from django.urls import path
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .views import (
    AdminUserViewSet,
    LoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    RegisterView,
)

# Stock SimpleJWT views -- annotated here (rather than in views.py, which we
# don't own their code in) purely for Swagger grouping/description; behavior
# is 100% SimpleJWT's own, untouched.
TokenRefreshView = extend_schema_view(
    post=extend_schema(
        tags=["auth"],
        summary="Refresh an access token",
        description=(
            "Exchanges a still-valid `refresh` token for a new `access` "
            "token (and, since `ROTATE_REFRESH_TOKENS=True`, a new "
            "`refresh` token too — the old refresh token is blacklisted "
            "and can't be reused). Call this when a request fails with a "
            "401 due to an expired access token, instead of logging in again."
        ),
    )
)(TokenRefreshView)

TokenBlacklistView = extend_schema_view(
    post=extend_schema(
        tags=["auth"],
        summary="Log out",
        description=(
            "Blacklists the given `refresh` token so it can no longer be "
            "used to obtain new access tokens. Does not invalidate any "
            "access token already issued — those simply expire naturally "
            "within 15 minutes. Send the `refresh` token in the body, not "
            "the access token."
        ),
    )
)(TokenBlacklistView)

router = DefaultRouter()
router.register("admin/users", AdminUserViewSet, basename="admin-users")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", TokenBlacklistView.as_view(), name="logout"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path(
        "password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path("me/", ProfileView.as_view(), name="profile"),
] + router.urls
