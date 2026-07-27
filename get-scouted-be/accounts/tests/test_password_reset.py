import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()


def _uid_and_token(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    return uid, token


@pytest.mark.django_db
def test_password_reset_request_existing_user_sends_email(api_client, user_factory):
    user = user_factory(password="oldpass123")
    mail.outbox = []

    response = api_client.post(
        "/api/v1/auth/password-reset/", {"email": user.email}, format="json"
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to


@pytest.mark.django_db
def test_password_reset_request_nonexistent_email_still_generic_200(api_client):
    mail.outbox = []

    response = api_client.post(
        "/api/v1/auth/password-reset/",
        {"email": "no-such-user@example.com"},
        format="json",
    )

    assert response.status_code == 200
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_password_reset_confirm_valid_token_changes_password(api_client, user_factory):
    user = user_factory(password="oldpass123")
    uid, token = _uid_and_token(user)

    response = api_client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "BrandNewPass9"},
        format="json",
    )

    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("oldpass123") is False
    assert user.check_password("BrandNewPass9") is True


@pytest.mark.django_db
def test_password_reset_confirm_invalid_token_rejected(api_client, user_factory):
    user = user_factory(password="oldpass123")
    uid, _ = _uid_and_token(user)

    response = api_client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": "tampered-token", "new_password": "BrandNewPass9"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["error"]["detail"] == "Invalid or expired reset link."
    user.refresh_from_db()
    assert user.check_password("oldpass123") is True


@pytest.mark.django_db
def test_password_reset_confirm_weak_password_rejected(api_client, user_factory):
    user = user_factory(password="oldpass123")
    uid, token = _uid_and_token(user)

    response = api_client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "123"},
        format="json",
    )

    assert response.status_code == 400
    user.refresh_from_db()
    assert user.check_password("oldpass123") is True


@pytest.mark.django_db
def test_password_reset_confirm_token_single_use(api_client, user_factory):
    user = user_factory(password="oldpass123")
    uid, token = _uid_and_token(user)

    first_response = api_client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "BrandNewPass9"},
        format="json",
    )
    assert first_response.status_code == 200

    second_response = api_client.post(
        "/api/v1/auth/password-reset/confirm/",
        {"uid": uid, "token": token, "new_password": "AnotherPass8"},
        format="json",
    )
    assert second_response.status_code == 400
