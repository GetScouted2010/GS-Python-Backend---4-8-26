"""Shared auth test fixtures for the accounts app and every downstream Phase 2/7/8
auth test that needs an authenticated client (UserFactory, authenticated_client(role)).
"""

import factory
import pytest
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    display_name = factory.Sequence(lambda n: f"Test User {n}")
    role = User.Role.SCOUT

    @factory.post_generation
    def password(obj, create, extracted, **kwargs):
        # So login tests can authenticate against a known password.
        obj.set_password(extracted or "testpass123")
        if create:
            obj.save()


@pytest.fixture
def user_factory():
    return UserFactory


@pytest.fixture
def authenticated_client():
    """Returns a callable `_make(role="scout", **kwargs)` -> (APIClient, user).

    Builds a real JWT (RefreshToken.for_user) and attaches it as a Bearer token,
    exercising the same JWTAuthentication path a real request would use.
    """

    def _make(role="scout", **kwargs):
        user = UserFactory(role=role, **kwargs)
        refresh = RefreshToken.for_user(user)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client, user

    return _make
