from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from accounts.serializers import RegisterSerializer, RoleTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(TokenObtainPairView):
    serializer_class = RoleTokenObtainPairSerializer
    permission_classes = [AllowAny]


class PasswordResetRequestView(APIView):
    """Placeholder wired for url routing; full logic lands in Task 2."""

    permission_classes = [AllowAny]

    def post(self, request):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)


class PasswordResetConfirmView(APIView):
    """Placeholder wired for url routing; full logic lands in Task 2."""

    permission_classes = [AllowAny]

    def post(self, request):
        return Response(status=status.HTTP_501_NOT_IMPLEMENTED)
