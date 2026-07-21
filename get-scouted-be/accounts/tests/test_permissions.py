"""AUTH-02: role-based permission enforcement tests.

Covers accounts/permissions.py (MinimumRole/IsSelfOrAdmin), the self-service
profile endpoint (/api/auth/me/), and the admin user-management endpoint
(/api/auth/admin/users/).
"""

import pytest
from rest_framework.test import APIClient

from accounts.models import User
from accounts.permissions import MinimumRole

pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Task 1: /api/auth/me/ — self-service profile
# ---------------------------------------------------------------------------


def test_write_requires_auth():
    """Unauthenticated PATCH /me/ -> 401 (deny-by-default via global IsAuthenticated)."""
    client = APIClient()
    response = client.patch("/api/auth/me/", {"display_name": "Nope"}, format="json")
    assert response.status_code == 401

    response = client.get("/api/auth/me/")
    assert response.status_code == 401


def test_profile_self_edit(authenticated_client):
    """A scout can view and edit their own display_name."""
    client, user = authenticated_client(role="scout")

    response = client.get("/api/auth/me/")
    assert response.status_code == 200
    assert response.data["email"] == user.email
    assert response.data["role"] == "scout"

    response = client.patch("/api/auth/me/", {"display_name": "New Name"}, format="json")
    assert response.status_code == 200
    assert response.data["display_name"] == "New Name"
    user.refresh_from_db()
    assert user.display_name == "New Name"


def test_profile_role_read_only(authenticated_client):
    """A scout PATCHing role=admin on their own profile leaves role unchanged."""
    client, user = authenticated_client(role="scout")

    response = client.patch("/api/auth/me/", {"role": "admin"}, format="json")
    assert response.status_code == 200
    assert response.data["role"] == "scout"
    user.refresh_from_db()
    assert user.role == "scout"


def test_role_change_takes_effect_immediately(authenticated_client):
    """A director's role dropped to scout mid-session is denied director-gated
    access on the very next request, with no re-login (DB-fresh role read).

    Exercises a real endpoint (Task 2's /api/auth/admin/users/); also directly
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
    response = client.get("/api/auth/admin/users/")
    assert response.status_code == 403


class _FakeRequest:
    """Minimal stand-in exposing .user for has_permission() unit assertions."""

    def __init__(self, user):
        self.user = user
