from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import generics, mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.models import User
from accounts.permissions import MinimumRole
from accounts.serializers import (
    AdminUserSerializer,
    ProfileSerializer,
    RegisterSerializer,
    RoleTokenObtainPairSerializer,
)


@extend_schema_view(
    post=extend_schema(
        tags=["auth"],
        summary="Register a new user",
        description=(
            "**Step 1 of the auth flow.** Creates a user with role "
            "`scout`, `analyst`, or `director` — `admin` is deliberately "
            "excluded from self-service (granted only via "
            "`manage.py createsuperuser` or an existing admin through "
            "`PATCH /auth/admin/users/{id}/`). Password is validated with "
            "Django's standard rules (min length, not too common, not "
            "entirely numeric). Returns the created profile, **not** "
            "tokens — call **Log in** next to obtain an access/refresh pair."
        ),
    )
)
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


@extend_schema_view(
    post=extend_schema(
        tags=["auth"],
        summary="Log in and obtain a JWT token pair",
        description=(
            "**Step 2 of the auth flow.** Exchanges `email` + `password` "
            "for an `access` token (15 min lifetime) and a `refresh` token "
            "(7 days, rotated and blacklisted on every use). Send the "
            "access token as `Authorization: Bearer <token>` on every "
            "other request in this API. The token payload also carries "
            "the user's `role` and `email`, so a client doesn't need a "
            "separate call just to know who's logged in. When the access "
            "token expires, use **Refresh token** instead of logging in "
            "again."
        ),
    )
)
class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer
    permission_classes = [AllowAny]


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Request a password-reset email",
        description=(
            "Sends a reset link (uid + token) to the given email if an "
            "active account exists for it. Always returns `200` with the "
            "same generic message regardless of whether the email matched "
            "— this deliberately prevents an attacker from using this "
            "endpoint to discover which emails are registered. Note: this "
            "environment's default email backend just logs to stdout "
            "instead of sending a real email, unless `EMAIL_BACKEND` is "
            "configured for a real provider (see `.env.example`). Follow "
            "up with **Confirm password reset** using the uid/token from "
            "the email."
        ),
        request=inline_serializer(
            "PasswordResetRequest", fields={"email": serializers.EmailField()}
        ),
        responses={200: OpenApiResponse(description="Always 200 — no user enumeration.")},
    )
    def post(self, request):
        email = request.data.get("email")
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user is not None:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            # Console backend for now — logs to stdout instead of sending real email.
            send_mail(
                subject="Password reset",
                message=f"Reset link: /reset-password/confirm/{uid}/{token}/",
                from_email=None,
                recipient_list=[user.email],
            )
        # Always 200 regardless of whether the email matched — no user enumeration.
        return Response({"detail": "If that email exists, a reset link has been sent."})


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["auth"],
        summary="Confirm a password reset",
        description=(
            "Second half of the reset flow: takes the `uid` + `token` from "
            "the reset email (see **Request password reset**) plus a "
            "`new_password`, and sets it if the token is valid and unexpired. "
            "`new_password` still goes through Django's standard password "
            "validators. Returns `400` for an invalid/expired link or a "
            "password that fails validation."
        ),
        request=inline_serializer(
            "PasswordResetConfirm",
            fields={
                "uid": serializers.CharField(),
                "token": serializers.CharField(),
                "new_password": serializers.CharField(),
            },
        ),
        responses={
            200: OpenApiResponse(description="Password has been reset."),
            400: OpenApiResponse(description="Invalid/expired link, or password failed validation."),
        },
    )
    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            raise DRFValidationError("Invalid reset link.") from None

        if not default_token_generator.check_token(user, token):
            raise DRFValidationError("Invalid or expired reset link.")

        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            raise DRFValidationError(e.messages) from None

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password has been reset."})


@extend_schema_view(
    get=extend_schema(
        tags=["auth"],
        summary="Get my profile",
        description="Returns the currently authenticated user's own profile — no `id` in the URL, it always targets the caller.",
    ),
    put=extend_schema(
        tags=["auth"],
        summary="Replace my profile",
        description="Full update of the caller's own profile. `role` is read-only here — a user can never self-escalate their own role; only an admin can change it via `PATCH /auth/admin/users/{id}/`.",
    ),
    patch=extend_schema(
        tags=["auth"],
        summary="Update my profile",
        description="Partial update of the caller's own profile (e.g. just `display_name`). `role` is read-only here for the same reason as PUT.",
    ),
)
class ProfileView(generics.RetrieveUpdateAPIView):
    """Self-service profile at /api/v1/auth/me/ -- always targets the calling
    user (no pk in the URL); role is read-only via ProfileSerializer so a
    user can never self-escalate their own role.
    """

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]  # explicit; matches the global default

    def get_object(self):
        return self.request.user


@extend_schema_view(
    list=extend_schema(
        tags=["auth"],
        summary="List all users (director+)",
        description="Org-wide user list. Requires `director` role or above. Directors get read-only access here — only an `admin` can update or deactivate a user.",
    ),
    retrieve=extend_schema(
        tags=["auth"],
        summary="Get a user (director+)",
        description="Fetch one user's admin-facing profile. Requires `director` role or above.",
    ),
    update=extend_schema(
        tags=["auth"],
        summary="Replace a user (admin only)",
        description="Full update of another user's record — including `role` and `is_active`. Requires `admin` role. There is no destroy/delete route: accounts are never hard-deleted, only soft-deactivated via **Deactivate user**.",
    ),
    partial_update=extend_schema(
        tags=["auth"],
        summary="Update a user (admin only)",
        description="Partial update of another user's record (e.g. change just their `role`). Requires `admin` role.",
    ),
)
class AdminUserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Org-wide user management at /api/v1/auth/admin/users/.

    Director+ gets read-only visibility (list/retrieve); admin-only for
    writes (update/partial_update/deactivate). Deliberately excludes the
    create mixin (registration is the only creation path) and the hard-delete
    mixin (accounts are never hard-deleted, only soft-deactivated) -- no
    destroy route is ever registered on this viewset.
    """

    queryset = User.objects.all().order_by("email")
    serializer_class = AdminUserSerializer
    permission_classes = [MinimumRole("director")]

    def get_permissions(self):
        if self.action in ("update", "partial_update", "deactivate"):
            return [MinimumRole("admin")()]
        return [MinimumRole("director")()]

    @extend_schema(
        tags=["auth"],
        summary="Deactivate a user (admin only)",
        description="Soft-deactivates a user (`is_active=False`) — the only way to remove access to an account. Requires `admin` role. A deactivated user's existing tokens still validate structurally but should be rejected by downstream checks tied to `is_active`.",
        request=None,
        responses={200: AdminUserSerializer},
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(self.get_serializer(user).data)
