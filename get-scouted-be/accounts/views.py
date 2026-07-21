from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
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


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer
    permission_classes = [AllowAny]


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

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

    def post(self, request):
        uidb64 = request.data.get("uid")
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({"detail": "Invalid reset link."}, status=status.HTTP_400_BAD_REQUEST)

        if not default_token_generator.check_token(user, token):
            return Response(
                {"detail": "Invalid or expired reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_password(new_password, user=user)
        except ValidationError as e:
            return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save(update_fields=["password"])
        return Response({"detail": "Password has been reset."})


class ProfileView(generics.RetrieveUpdateAPIView):
    """Self-service profile at /api/auth/me/ -- always targets the calling
    user (no pk in the URL); role is read-only via ProfileSerializer so a
    user can never self-escalate their own role.
    """

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]  # explicit; matches the global default

    def get_object(self):
        return self.request.user


class AdminUserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Org-wide user management at /api/auth/admin/users/.

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

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active"])
        return Response(self.get_serializer(user).data)
