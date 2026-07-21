from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from accounts.models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])
    role = serializers.ChoiceField(
        choices=[
            (User.Role.SCOUT, User.Role.SCOUT.label),
            (User.Role.ANALYST, User.Role.ANALYST.label),
            (User.Role.DIRECTOR, User.Role.DIRECTOR.label),
        ]  # admin deliberately excluded from self-service
    )

    class Meta:
        model = User
        fields = ["email", "password", "display_name", "role"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token


class ProfileSerializer(serializers.ModelSerializer):
    """Self-service profile view/edit. role is read-only here to block
    self-escalation -- role changes are admin-only (see AdminUserSerializer).
    """

    class Meta:
        model = User
        fields = ["id", "email", "display_name", "role"]
        read_only_fields = ["id", "email", "role"]
