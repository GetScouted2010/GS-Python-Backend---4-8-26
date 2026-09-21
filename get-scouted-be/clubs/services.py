"""Club-scoped AI orchestration (AI-04, 10-04-PLAN.md).

`position_needs_aggregate` is a deliberately NARROW, internal-only grounding
aggregation for club insights -- it is NOT Phase 11's full canonical Position
Needs feature (no strong/weak/at-risk labels, no public endpoint). It is a
single bounded ORM `.values("position").annotate(...)` query scoped to one
club's squad (via `Player.club`'s `related_name="players"`), matching Phase
6's SCORE-07 precedent of never running a full-dataset pandas operation
inside a request cycle -- see 10-RESEARCH.md Pattern 4.

`generate_club_insights` combines that aggregation with
`ClubDetailSerializer.get_transfer_aggregates` (reused, not re-derived) into
a single grounding dict, then generates narrative prose via the
provider-agnostic `players.ai.report_factory.get_report_generator()` --
mirroring `clubs/serializers.py`'s existing cross-app-import precedent
(`from players.serializers import PlayerListSerializer`).

`ReportGeneratorError` is deliberately NOT caught here -- the calling view
(`ClubInsightsView`) maps it to a clean 503, never a fabricated report.
"""

from datetime import date, timedelta

from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404

from clubs.models import Club
from clubs.serializers import ClubDetailSerializer
from players.ai.report_factory import get_report_generator
from players.season import scope_to_season


def position_needs_aggregate(club, season: str | None = None) -> dict:
    """Internal-only grounding aggregation for AI-04. Deliberately NARROWER
    than Phase 11's PLAN-01 (no strong/weak/at-risk labels, no public
    endpoint): a single bounded ORM query, never pandas, bounded to one
    club's ~few-dozen-row squad via `related_name="players"`.

    Scoped to ONE season (players/season.py) -- `club.players` holds a row per
    player PER SEASON, so an unscoped count pools every season and reports a
    squad several times its real size (Arsenal showed 12 centre-backs; one
    season has 3). `season=None` means the default season.

    Returns a dict keyed by position, each value:
    {squad_depth, avg_age, contracts_expiring_within_12mo}.
    """
    cutoff = date.today() + timedelta(days=365)
    squad = scope_to_season(club.players.exclude(position__isnull=True), season)
    rows = (
        squad.values("position").annotate(
            squad_depth=Count("id"),
            avg_age=Avg("age"),
            expiring_within_12mo=Count(
                "id",
                filter=Q(contract_expires__lte=cutoff, contract_expires__isnull=False),
            ),
        ).order_by("position")
    )
    return {
        row["position"]: {
            "squad_depth": row["squad_depth"],
            "avg_age": round(row["avg_age"], 1) if row["avg_age"] is not None else None,
            "contracts_expiring_within_12mo": row["expiring_within_12mo"],
        }
        for row in rows
    }


def classify_position_needs(club, season: str | None = None) -> dict:
    """PLAN-01 (11-01-PLAN.md): layers strong/weak/at-risk classification
    onto position_needs_aggregate's existing numbers. Never recomputes the
    underlying aggregation -- reuses it as-is (see module docstring / the
    Phase-10-vs-Phase-11 scoping decision)."""
    needs = position_needs_aggregate(club, season)
    result = {}
    for position, stats in needs.items():
        depth = stats["squad_depth"]
        avg_age = stats["avg_age"]
        expiring = stats["contracts_expiring_within_12mo"]
        if depth < 2:
            label = "weak"
        elif (avg_age is not None and avg_age > 30) or expiring >= depth / 2:
            label = "at-risk"
        else:
            label = "strong"
        result[position] = {**stats, "classification": label}
    return result


def generate_club_insights(club_id) -> dict:
    """AI-04 orchestration: grounding = position needs (this module) +
    reused transfer aggregates (`ClubDetailSerializer.get_transfer_aggregates`);
    narrative comes from the provider-agnostic `get_report_generator()`.
    `ReportGeneratorError` deliberately NOT caught here -- the view maps it
    to a clean 503."""
    club = get_object_or_404(Club, pk=club_id)
    grounding = {
        "club": {"name": club.name, "league": club.league},
        "position_needs": position_needs_aggregate(club),
        # Call directly on a bare serializer instance so the heavy squad
        # serialization (get_squad) is NOT triggered -- get_transfer_aggregates
        # takes club as an arg and needs no instance/context.
        "transfer_aggregates": ClubDetailSerializer().get_transfer_aggregates(club),
    }
    report = get_report_generator().generate(grounding, "club_insights")
    return {"narrative": report.narrative, "grounding": report.grounding}
