import pytest
from django.conf import settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
def test_login_flow(api_client, user_factory):
    user = user_factory(role="director", password="testpass123")

    response = api_client.post(
        "/api/auth/login/",
        {"email": user.email, "password": "testpass123"},
        format="json",
    )
    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data

    decoded = AccessToken(response.data["access"])
    assert decoded["role"] == "director"
    assert decoded["email"] == user.email


@pytest.mark.django_db
def test_login_wrong_password_generic_401(api_client, user_factory):
    user = user_factory(password="testpass123")

    response = api_client.post(
        "/api/auth/login/",
        {"email": user.email, "password": "wrong-password"},
        format="json",
    )
    assert response.status_code == 401
    wrong_password_detail = str(response.data["detail"])

    response2 = api_client.post(
        "/api/auth/login/",
        {"email": "no-such-user@example.com", "password": "whatever"},
        format="json",
    )
    assert response2.status_code == 401
    unknown_email_detail = str(response2.data["detail"])

    assert wrong_password_detail == unknown_email_detail


@pytest.mark.django_db
def test_refresh_rotation(api_client, user_factory):
    user = user_factory(password="testpass123")
    login_response = api_client.post(
        "/api/auth/login/",
        {"email": user.email, "password": "testpass123"},
        format="json",
    )
    old_refresh = login_response.data["refresh"]

    refresh_response = api_client.post(
        "/api/auth/token/refresh/", {"refresh": old_refresh}, format="json"
    )
    assert refresh_response.status_code == 200
    assert "access" in refresh_response.data
    assert "refresh" in refresh_response.data
    assert refresh_response.data["refresh"] != old_refresh

    reuse_response = api_client.post(
        "/api/auth/token/refresh/", {"refresh": old_refresh}, format="json"
    )
    assert reuse_response.status_code == 401


@pytest.mark.django_db
def test_logout_blacklist(api_client, user_factory):
    user = user_factory(password="testpass123")
    login_response = api_client.post(
        "/api/auth/login/",
        {"email": user.email, "password": "testpass123"},
        format="json",
    )
    refresh = login_response.data["refresh"]

    logout_response = api_client.post(
        "/api/auth/logout/", {"refresh": refresh}, format="json"
    )
    assert logout_response.status_code == 200

    refresh_after_logout = api_client.post(
        "/api/auth/token/refresh/", {"refresh": refresh}, format="json"
    )
    assert refresh_after_logout.status_code == 401


@pytest.mark.django_db
def test_single_auth_backend():
    assert settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] == [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ]
