import pytest

from accounts.models import User


@pytest.mark.django_db
def test_create_user_defaults_to_scout():
    user = User.objects.create_user(
        email="a@b.com", password="testpass123", display_name="A"
    )
    assert user.role == User.Role.SCOUT
    assert user.is_active is True
    assert user.check_password("testpass123")
    assert user.id is not None


@pytest.mark.django_db
def test_create_superuser_is_admin():
    user = User.objects.create_superuser(
        email="admin@b.com", password="testpass123", display_name="Admin"
    )
    assert user.role == User.Role.ADMIN
    assert user.is_staff is True
    assert user.is_superuser is True


@pytest.mark.django_db
def test_email_is_username_field():
    assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_authenticated_client_fixture(authenticated_client):
    client, user = authenticated_client(role="director")
    assert user.role == "director"
