import pytest
from rest_framework.test import APIClient

from accounts.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
@pytest.mark.parametrize("role", ["scout", "analyst", "director"])
def test_register_allowed_role_creates_active_account(api_client, role):
    response = api_client.post(
        "/api/v1/auth/register/",
        {
            "email": f"{role}@example.com",
            "password": "S3cure-pass-word",
            "display_name": f"{role.title()} User",
            "role": role,
        },
        format="json",
    )
    assert response.status_code == 201
    user = User.objects.get(email=f"{role}@example.com")
    assert user.is_active is True
    assert user.role == role


@pytest.mark.django_db
def test_register_admin_role_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/register/",
        {
            "email": "wannabe-admin@example.com",
            "password": "S3cure-pass-word",
            "display_name": "Wannabe Admin",
            "role": "admin",
        },
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(email="wannabe-admin@example.com").exists()


@pytest.mark.django_db
def test_register_weak_password_rejected(api_client):
    response = api_client.post(
        "/api/v1/auth/register/",
        {
            "email": "weakpass@example.com",
            "password": "123",
            "display_name": "Weak Pass",
            "role": "scout",
        },
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(email="weakpass@example.com").exists()
