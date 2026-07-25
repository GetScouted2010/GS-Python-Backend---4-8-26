"""DRF APIClient integration tests for workspace/views.py::SquadPlanViewSet
(08-04-PLAN.md) -- covers CRUD-08 create, live current_squad derivation on
detail, the lightweight list serializer, proposed_changes write-time
validation, list-scoping to the calling user, and cross-user ownership
denial.

Uses the `authenticated_client`, `club_factory`, and `player_factory`
fixtures (accounts/tests/conftest.py + workspace/tests/conftest.py).
"""

from __future__ import annotations

import pytest

from workspace.models import SquadPlan

pytestmark = pytest.mark.django_db

SQUAD_PLANS_URL = "/api/workspace/squad-plans/"


def test_create_squad_plan(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player = player_factory()

    response = client.post(
        SQUAD_PLANS_URL,
        {
            "name": "New formation idea",
            "club": str(club.id),
            "formation": "4-3-3",
            "proposed_changes": [{"action": "add", "player_id": str(player.id)}],
        },
        format="json",
    )

    assert response.status_code == 201
    row = SquadPlan.objects.get(id=response.data["id"])
    assert row.user == user
    assert row.club == club
    assert row.formation == "4-3-3"
    assert row.proposed_changes == [{"action": "add", "player_id": str(player.id)}]


def test_detail_returns_live_current_squad(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player_a = player_factory(club=club)
    player_b = player_factory(club=club)
    plan = SquadPlan.objects.create(user=user, club=club, name="Plan A", formation="4-4-2")

    response = client.get(f"{SQUAD_PLANS_URL}{plan.id}/")

    assert response.status_code == 200
    assert "current_squad" in response.data
    current_squad_ids = {row["id"] for row in response.data["current_squad"]}
    assert current_squad_ids == {str(player_a.id), str(player_b.id)}


def test_list_is_lightweight_no_current_squad(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()
    SquadPlan.objects.create(user=user, club=club, name="Plan A", formation="4-4-2")

    response = client.get(SQUAD_PLANS_URL)

    assert response.status_code == 200
    for row in response.data:
        assert "current_squad" not in row


def test_proposed_changes_must_be_list(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()

    response = client.post(
        SQUAD_PLANS_URL,
        {"name": "Plan", "club": str(club.id), "proposed_changes": {"x": 1}},
        format="json",
    )

    assert response.status_code == 400


def test_proposed_changes_bad_action_rejected(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()

    response = client.post(
        SQUAD_PLANS_URL,
        {"name": "Plan", "club": str(club.id), "proposed_changes": [{"action": "jump"}]},
        format="json",
    )

    assert response.status_code == 400


def test_swap_requires_incoming_player_id(authenticated_client, club_factory):
    client, user = authenticated_client()
    club = club_factory()

    response = client.post(
        SQUAD_PLANS_URL,
        {
            "name": "Plan",
            "club": str(club.id),
            "proposed_changes": [{"action": "swap", "player_id": "x"}],
        },
        format="json",
    )

    assert response.status_code == 400


def test_scoping_list_excludes_other_users(authenticated_client, club_factory):
    client_a, user_a = authenticated_client()
    _client_b, user_b = authenticated_client()
    club = club_factory()

    plan_a = SquadPlan.objects.create(user=user_a, club=club, name="A's plan")
    plan_b = SquadPlan.objects.create(user=user_b, club=club, name="B's plan")

    response = client_a.get(SQUAD_PLANS_URL)

    assert response.status_code == 200
    result_ids = {row["id"] for row in response.data}
    assert result_ids == {str(plan_a.id)}
    assert str(plan_b.id) not in result_ids


def test_ownership_cannot_get_other_users_plan(authenticated_client, club_factory):
    _client_a, user_a = authenticated_client()
    client_b, user_b = authenticated_client()
    club = club_factory()

    plan_a = SquadPlan.objects.create(user=user_a, club=club, name="A's plan")

    response = client_b.get(f"{SQUAD_PLANS_URL}{plan_a.id}/")

    assert response.status_code == 404
