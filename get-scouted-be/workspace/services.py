"""Squad simulation service (11-02-PLAN.md, PLAN-03).

simulate_squad_change applies a SquadPlan's proposed_changes (or an ad-hoc
override) to the club's live current squad ENTIRELY IN MEMORY -- it never
writes to the DB. Metrics use Player.impact_score (club-independent RMM)
for avg score and Player.market_value for budget impact; the other three
denormalized score fields are own-club-context and would be meaningless for
an incoming player from a different club (players/models.py trap).
Follows the clubs/services.py / players/services.py per-app convention.
"""
from __future__ import annotations

from players.models import Player
from players.serializers import PlayerListSerializer


class InvalidPlayerReference(Exception):
    pass


def _referenced_ids(proposed_changes):
    ids = set()
    for entry in proposed_changes:
        if entry.get("player_id"):
            ids.add(str(entry["player_id"]))
        if entry.get("incoming_player_id"):
            ids.add(str(entry["incoming_player_id"]))
    return ids


def _squad_metrics(players):
    ages = [p.age for p in players if p.age is not None]
    scores = [p.impact_score for p in players if p.impact_score is not None]
    values = [p.market_value for p in players if p.market_value is not None]
    return {
        "squad_size": len(players),
        "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
        "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
        "total_market_value": sum(values) if values else None,
        "missing_market_value_count": len(players) - len(values),
    }


def simulate_squad_change(squad_plan, proposed_changes=None) -> dict:
    changes = proposed_changes if proposed_changes is not None else squad_plan.proposed_changes

    ref_ids = _referenced_ids(changes)
    players_by_id = (
        {str(p.id): p for p in Player.objects.filter(id__in=ref_ids)} if ref_ids else {}
    )
    missing = ref_ids - players_by_id.keys()
    if missing:
        raise InvalidPlayerReference(f"unknown player id(s): {sorted(missing)}")

    current_squad = list(squad_plan.club.players.all())
    simulated_squad = list(current_squad)  # shallow copy, in-memory only

    for entry in changes:
        action = entry["action"]
        if action == "add":
            simulated_squad.append(players_by_id[str(entry["player_id"])])
        elif action == "remove":
            target_id = str(entry["player_id"])
            simulated_squad = [p for p in simulated_squad if str(p.id) != target_id]
        elif action == "swap":
            out_id = str(entry["player_id"])
            simulated_squad = [p for p in simulated_squad if str(p.id) != out_id]
            simulated_squad.append(players_by_id[str(entry["incoming_player_id"])])

    baseline = _squad_metrics(current_squad)
    simulated = _squad_metrics(simulated_squad)
    delta = {
        "avg_age": (
            round(simulated["avg_age"] - baseline["avg_age"], 1)
            if simulated["avg_age"] is not None and baseline["avg_age"] is not None
            else None
        ),
        "avg_score": (
            round(simulated["avg_score"] - baseline["avg_score"], 2)
            if simulated["avg_score"] is not None and baseline["avg_score"] is not None
            else None
        ),
        "budget_impact": (
            simulated["total_market_value"] - baseline["total_market_value"]
            if simulated["total_market_value"] is not None and baseline["total_market_value"] is not None
            else None
        ),
        "squad_size": simulated["squad_size"] - baseline["squad_size"],
    }
    return {
        "baseline": baseline,
        "simulated": simulated,
        "delta": delta,
        "proposed_changes": changes,
        "simulated_squad": PlayerListSerializer(simulated_squad, many=True).data,
    }
