"""AUTH-02: role-based permission enforcement tests.

Covers accounts/permissions.py (MinimumRole/IsSelfOrAdmin), the self-service
profile endpoint (/api/v1/auth/me/), and the admin user-management endpoint
(/api/v1/auth/admin/users/).
"""

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from accounts.permissions import MinimumRole

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Task 1: /api/v1/auth/me/ — self-service profile
# ---------------------------------------------------------------------------


def test_write_requires_auth():
    """Unauthenticated PATCH /me/ -> 401 (deny-by-default via global IsAuthenticated)."""
    client = APIClient()
    response = client.patch("/api/v1/auth/me/", {"display_name": "Nope"}, format="json")
    assert response.status_code == 401

    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 401


def test_profile_self_edit(authenticated_client):
    """A scout can view and edit their own display_name."""
    client, user = authenticated_client(role="scout")

    response = client.get("/api/v1/auth/me/")
    assert response.status_code == 200
    assert response.data["email"] == user.email
    assert response.data["role"] == "scout"

    response = client.patch("/api/v1/auth/me/", {"display_name": "New Name"}, format="json")
    assert response.status_code == 200
    assert response.data["display_name"] == "New Name"
    user.refresh_from_db()
    assert user.display_name == "New Name"


def test_profile_role_read_only(authenticated_client):
    """A scout PATCHing role=admin on their own profile leaves role unchanged."""
    client, user = authenticated_client(role="scout")

    response = client.patch("/api/v1/auth/me/", {"role": "admin"}, format="json")
    assert response.status_code == 200
    assert response.data["role"] == "scout"
    user.refresh_from_db()
    assert user.role == "scout"


def test_role_change_takes_effect_immediately(authenticated_client):
    """A director's role dropped to scout mid-session is denied director-gated
    access on the very next request, with no re-login (DB-fresh role read).

    Exercises a real endpoint (Task 2's /api/v1/auth/admin/users/); also directly
    asserts the permission class flips for immediacy in case Task 2 isn't
    wired up yet when this test file is first created.
    """
    client, user = authenticated_client(role="director")

    # Sanity: director rank currently passes the MinimumRole("director") check
    # directly against a freshly-fetched user instance.
    assert MinimumRole("director")().has_permission(
        _FakeRequest(user), None
    )

    # Admin (via ORM, not the API) demotes this user.
    user.role = User.Role.SCOUT
    user.save(update_fields=["role"])

    refreshed_user = User.objects.get(pk=user.pk)
    assert not MinimumRole("director")().has_permission(
        _FakeRequest(refreshed_user), None
    )

    # Real endpoint: same original access token, no re-login.
    response = client.get("/api/v1/auth/admin/users/")
    assert response.status_code == 403


class _FakeRequest:
    """Minimal stand-in exposing .user for has_permission() unit assertions."""

    def __init__(self, user):
        self.user = user


# ---------------------------------------------------------------------------
# Task 2: /api/v1/auth/admin/users/ — director read-only, admin read/write
# ---------------------------------------------------------------------------


def test_role_gated_403(authenticated_client):
    """A scout/analyst (below director rank) is denied list access."""
    client, _ = authenticated_client(role="scout")
    response = client.get("/api/v1/auth/admin/users/")
    assert response.status_code == 403

    client, _ = authenticated_client(role="analyst")
    response = client.get("/api/v1/auth/admin/users/")
    assert response.status_code == 403


def test_director_read_only_visibility(authenticated_client, user_factory):
    """Director sees the full org-wide user list/detail but cannot write."""
    client, _ = authenticated_client(role="director")
    other = user_factory(role="scout")

    response = client.get("/api/v1/auth/admin/users/")
    assert response.status_code == 200
    emails = [row["email"] for row in response.data]
    assert other.email in emails

    response = client.get(f"/api/v1/auth/admin/users/{other.pk}/")
    assert response.status_code == 200
    assert response.data["email"] == other.email

    response = client.patch(
        f"/api/v1/auth/admin/users/{other.pk}/", {"role": "director"}, format="json"
    )
    assert response.status_code == 403

    response = client.post(f"/api/v1/auth/admin/users/{other.pk}/deactivate/")
    assert response.status_code == 403


def test_admin_can_change_role(authenticated_client, user_factory):
    """Admin PATCHing another user's role -> 200; role persisted."""
    client, _ = authenticated_client(role="admin")
    target = user_factory(role="scout")

    response = client.patch(
        f"/api/v1/auth/admin/users/{target.pk}/", {"role": "director"}, format="json"
    )
    assert response.status_code == 200
    assert response.data["role"] == "director"
    target.refresh_from_db()
    assert target.role == "director"


def test_admin_can_deactivate_soft(authenticated_client, user_factory):
    """Admin POST deactivate/ -> 200, is_active False, row still exists (soft only)."""
    client, _ = authenticated_client(role="admin")
    target = user_factory(role="scout")

    response = client.post(f"/api/v1/auth/admin/users/{target.pk}/deactivate/")
    assert response.status_code == 200
    target.refresh_from_db()
    assert target.is_active is False
    assert User.objects.filter(pk=target.pk).exists()


def test_no_hard_delete_route(authenticated_client, user_factory):
    """No destroy action is registered on the viewset at all -- DELETE -> 405."""
    client, _ = authenticated_client(role="admin")
    target = user_factory(role="scout")

    response = client.delete(f"/api/v1/auth/admin/users/{target.pk}/")
    assert response.status_code == 405
    assert User.objects.filter(pk=target.pk).exists()
