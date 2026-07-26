"""Tests for PLAN-03 squad simulation (11-02-PLAN.md).

Unit tests exercise workspace.services.simulate_squad_change directly;
integration tests exercise POST /api/workspace/squad-plans/{id}/simulate/
on SquadPlanViewSet.

Uses the `authenticated_client`, `club_factory`, and `player_factory`
fixtures (accounts/tests/conftest.py + workspace/tests/conftest.py),
mirroring workspace/tests/test_squad_plans.py's established style.
"""

from __future__ import annotations

import uuid

import pytest

from workspace import services as workspace_services
from workspace.models import SquadPlan

pytestmark = pytest.mark.django_db

SQUAD_PLANS_URL = "/api/workspace/squad-plans/"


# --- Unit tests: workspace.services.simulate_squad_change ---


def test_apply_add_remove_swap(authenticated_client, club_factory, player_factory):
    _client, user = authenticated_client()
    club = club_factory()
    squad_player_1 = player_factory(club=club, position="CB")
    squad_player_2 = player_factory(club=club, position="CM")
    squad_player_3 = player_factory(club=club, position="ST")
    added_player = player_factory(position="RW")
    swap_in_player = player_factory(position="LB")

    plan = SquadPlan.objects.create(user=user, club=club, name="Plan", proposed_changes=[])

    proposed_changes = [
        {"action": "add", "player_id": str(added_player.id)},
        {"action": "remove", "player_id": str(squad_player_1.id)},
        {
            "action": "swap",
            "player_id": str(squad_player_2.id),
            "incoming_player_id": str(swap_in_player.id),
        },
    ]

    result = workspace_services.simulate_squad_change(plan, proposed_changes=proposed_changes)

    simulated_ids = {row["id"] for row in result["simulated_squad"]}
    assert str(added_player.id) in simulated_ids
    assert str(squad_player_1.id) not in simulated_ids
    assert str(squad_player_2.id) not in simulated_ids
    assert str(swap_in_player.id) in simulated_ids
    assert str(squad_player_3.id) in simulated_ids

    assert result["baseline"]["squad_size"] == 3
    assert result["simulated"]["squad_size"] == 3  # -1 remove, -1+1 swap, +1 add
    assert result["delta"]["squad_size"] == 0


def test_null_values_excluded_not_zero_filled(authenticated_client, club_factory, player_factory):
    _client, user = authenticated_client()
    club = club_factory()
    player_factory(club=club, age=28, impact_score=50.0, market_value=1_000_000)
    player_factory(club=club, age=None, impact_score=None, market_value=None)

    plan = SquadPlan.objects.create(user=user, club=club, name="Plan", proposed_changes=[])

    result = workspace_services.simulate_squad_change(plan, proposed_changes=[])

    baseline = result["baseline"]
    assert baseline["avg_age"] == 28.0
    assert baseline["avg_score"] == 50.0
    assert baseline["total_market_value"] == 1_000_000
    assert baseline["missing_market_value_count"] == 1


def test_invalid_player_reference_raises(authenticated_client, club_factory, player_factory):
    _client, user = authenticated_client()
    club = club_factory()
    player_factory(club=club)
    plan = SquadPlan.objects.create(user=user, club=club, name="Plan", proposed_changes=[])

    bogus_id = str(uuid.uuid4())
    proposed_changes = [{"action": "add", "player_id": bogus_id}]

    with pytest.raises(workspace_services.InvalidPlayerReference):
        workspace_services.simulate_squad_change(plan, proposed_changes=proposed_changes)


def test_uses_stored_proposed_changes_when_no_override(authenticated_client, club_factory, player_factory):
    _client, user = authenticated_client()
    club = club_factory()
    player_factory(club=club)
    added_player = player_factory(position="RW")

    plan = SquadPlan.objects.create(
        user=user,
        club=club,
        name="Plan",
        proposed_changes=[{"action": "add", "player_id": str(added_player.id)}],
    )

    result = workspace_services.simulate_squad_change(plan, proposed_changes=None)

    simulated_ids = {row["id"] for row in result["simulated_squad"]}
    assert str(added_player.id) in simulated_ids
    assert result["simulated"]["squad_size"] == result["baseline"]["squad_size"] + 1


# --- Integration tests: POST /api/workspace/squad-plans/{id}/simulate/ ---


def test_simulate_response_shape(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player_factory(club=club)
    plan = SquadPlan.objects.create(user=user, club=club, name="Plan", proposed_changes=[])

    response = client.post(f"{SQUAD_PLANS_URL}{plan.id}/simulate/", {}, format="json")

    assert response.status_code == 200
    data = response.data
    assert set(["baseline", "simulated", "delta", "simulated_squad"]).issubset(data.keys())
    for key in ("avg_age", "avg_score", "total_market_value", "squad_size"):
        assert key in data["baseline"]
        assert key in data["simulated"]
    for key in ("avg_age", "avg_score", "budget_impact", "squad_size"):
        assert key in data["delta"]


def test_invalid_player_id_400(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player_factory(club=club)
    plan = SquadPlan.objects.create(user=user, club=club, name="Plan", proposed_changes=[])

    response = client.post(
        f"{SQUAD_PLANS_URL}{plan.id}/simulate/",
        {"proposed_changes": [{"action": "add", "player_id": str(uuid.uuid4())}]},
        format="json",
    )

    assert response.status_code == 400


def test_simulate_does_not_persist(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player_factory(club=club)
    added_player = player_factory(position="RW")
    stored_changes = []

    plan = SquadPlan.objects.create(
        user=user, club=club, name="Plan", proposed_changes=stored_changes
    )
    squad_count_before = club.players.count()

    override = [{"action": "add", "player_id": str(added_player.id)}]
    response = client.post(
        f"{SQUAD_PLANS_URL}{plan.id}/simulate/",
        {"proposed_changes": override},
        format="json",
    )

    assert response.status_code == 200
    refreshed = SquadPlan.objects.get(id=plan.id)
    assert refreshed.proposed_changes == stored_changes
    assert club.players.count() == squad_count_before


def test_simulate_uses_override_when_provided(authenticated_client, club_factory, player_factory):
    client, user = authenticated_client()
    club = club_factory()
    player_factory(club=club)
    added_player = player_factory(position="RW")

    plan = SquadPlan.objects.create(user=user, club=club, name="Plan", proposed_changes=[])
    baseline_squad_size = club.players.count()

    override = [{"action": "add", "player_id": str(added_player.id)}]
    response = client.post(
        f"{SQUAD_PLANS_URL}{plan.id}/simulate/",
        {"proposed_changes": override},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["simulated"]["squad_size"] == baseline_squad_size + 1


def test_simulate_ownership_denied(authenticated_client, club_factory):
    _client_a, user_a = authenticated_client()
    client_b, _user_b = authenticated_client()
    club = club_factory()

    plan_a = SquadPlan.objects.create(user=user_a, club=club, name="A's plan", proposed_changes=[])

    response = client_b.post(f"{SQUAD_PLANS_URL}{plan_a.id}/simulate/", {}, format="json")

    assert response.status_code == 404
