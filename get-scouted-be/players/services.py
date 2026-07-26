"""Search composition service (09-03-PLAN.md, AI-01).

`search_players(filters, request)` is the shared composition both the
natural-language search view (Plan 04) and any future caller use. It
composes Phase 7's existing, tested filter/pagination/serializer primitives
against a plain filter dict -- it does NOT reuse the read-layer list view's
bound methods (those expect `request.query_params`, not an arbitrary
filters dict; 09-RESEARCH.md Pattern 3).

CRITICAL trap this protects against: `players.filters.PlayerFilter` has no
`club__` filters and SILENTLY IGNORES any undeclared keys in its `data=`
dict (django_filters does not raise on unknown keys). Style filters
(`club__<field>_min`, the 8 real ClubFilter style fields) must therefore be
split out and applied as a SEPARATE manual `.filter(club__<field>__gte=...)`
step -- never passed through PlayerFilter's own data, or they would be
silently dropped and the caller would get unfiltered (wrong) results without
any error.
"""

from __future__ import annotations

from core.pagination import IdsBypassPagination
from players.ai.report_factory import get_report_generator
from players.filters import PlayerFilter
from players.models import Player
from players.serializers import PlayerListSerializer
from scoring.services.summary import get_summary

# The 8 real style fields (clubs/filters.py), addressed here as
# club__<field>_min in the incoming filters dict.
STYLE_FIELDS = {
    "control_possession",
    "gegenpressing",
    "direct_play",
    "tiki_taka",
    "counter_attack",
    "wing_play",
    "low_block",
    "defensive_counter_attack",
}


def search_players(filters: dict, request) -> dict:
    """Compose PlayerFilter + a separate manual style-filter step +
    IdsBypassPagination + PlayerListSerializer into the standard paginated
    envelope (same shape as GET /api/players/).

    `filters` (a plain dict, e.g. from the tier-2 keyword extractor or an
    LLM parser) drives PlayerFilter and the manual style step. `request`
    (the real DRF request) drives pagination -- the two are never
    conflated (09-RESEARCH.md Pitfall 3).
    """
    # Split style filters (club__<field>_min) out -- PlayerFilter has no
    # club__ filters and would SILENTLY IGNORE them (no error). They must
    # be applied as a separate manual ORM step.
    style_filters, player_filter_data = {}, {}
    for key, value in filters.items():
        if key.startswith("club__") and key.removeprefix("club__").removesuffix("_min") in STYLE_FIELDS:
            style_filters[key] = value
        else:
            player_filter_data[key] = value

    qs = PlayerFilter(data=player_filter_data, queryset=Player.objects.all()).qs
    for key, value in style_filters.items():
        field = key.removesuffix("_min")  # e.g. "club__control_possession"
        qs = qs.filter(**{f"{field}__gte": value})  # -> club__control_possession__gte=value
    qs = qs.order_by("-impact_score")  # match the read-layer list view's deterministic default

    paginator = IdsBypassPagination()
    page = paginator.paginate_queryset(qs, request, view=None)
    serialized = PlayerListSerializer(page, many=True).data
    return paginator.get_paginated_response(serialized).data


def generate_scouting_report(player_id, club_id) -> dict:
    """AI-03 orchestration for the player scouting-report slice.

    Grounding comes ONLY from `scoring.services.summary.get_summary` --
    never re-derived or re-computed here. The narrative comes from the
    provider-agnostic `players.ai.report_factory.get_report_generator()`
    (imported at module top so tests can patch `players.services.
    get_report_generator`, matching test_search_view.py's binding-patch
    convention).

    `ReportGeneratorError` is deliberately NOT caught here -- the calling
    view maps it to a clean 503, so a fabricated/template report is
    structurally impossible at this layer. `get_summary` may raise
    `Http404` for an unresolvable player/club; the caller (the view) is
    responsible for resolving `club_id` (never None) before calling this.
    """
    grounding = get_summary(player_id, club_id)
    report = get_report_generator().generate(grounding, "player_scouting_report")
    return {"narrative": report.narrative, "grounding": report.grounding}
