"""PlayerFilter -- CRUD-01 (filter dimensions) + CRUD-05 (?ids= multi-fetch).

`position` binds to `Player.position` (the CLEAN 10-value group: AM/CB/CM/
DM/FWD/GK/LB/LW/RB/RW), NEVER `Player.main_position` (22 fine-grained
values + a garbage '0' row) -- verified against `PlayerRoleScore
.position_group` and `Player.Meta.indexes` during planning. This is one of
the two highest-risk correctness pivots this plan protects.

A2 fix (min/max range filters): age, market_value, the 4 scores, and
minutes are all covered as `_min`/`_max` pairs below. "Position metrics"
(the ~99 raw per-position stat columns -- goals, xG, duels won %, etc.) is
NOT covered -- none of them are exposed as filters at all today, and which
specific ones matter is a product call, not something to guess at broadly.
Flag which stats you actually want range-filterable and they can be added
the same way.
"""

import django_filters as filters
from django.db.models import Q
from rest_framework.exceptions import ValidationError

from players.models import Player
from players.season import ROW_LEAGUE_SEASONS, resolve_season


class IdsInFilter(filters.BaseInFilter, filters.UUIDFilter):
    """?ids=<uuid1>,<uuid2>,... -- CRUD-05 multi-fetch (CSV of UUIDs)."""


class PlayerFilter(filters.FilterSet):
    # CRUD-05 multi-fetch (bounded set by id)
    ids = IdsInFilter(field_name="id")
    # CRUD-01 exact-match dimensions. position = the CLEAN 10-value group
    # (AM/CB/CM/DM/FWD/GK/LB/LW/RB/RW), NOT main_position (22 fine-grained
    # values + a '0' garbage row). Verified against PlayerRoleScore.position_group
    # and Player.Meta.indexes.
    position = filters.CharFilter(field_name="position")
    # A3 fix: filter by the player's CLUB's canonical league, never the raw
    # per-row Player.league column -- that column is contaminated for ~8.7%
    # of rows (a player's row can carry a PRIOR club's league; see
    # players/serializers.py's PlayerListSerializer.get_league docstring),
    # which would silently include/exclude players from the wrong league.
    # Exception (players/season.py::ROW_LEAGUE_SEASONS): for seasons whose
    # per-row league is clean, match the row's own league instead -- the same
    # rule `effective_league` applies for display. `~Q(season__in=...)` also
    # keeps NULL-season rows on the club-league path.
    league = filters.CharFilter(method="filter_league")
    # A1 fix (players/season.py): explicit season pass-through, for docs/
    # discoverability. The actual DEFAULT enforcement (when this param is
    # absent) happens in filter_queryset below, not here -- django-filter
    # fields simply no-op when their query param is missing.
    season = filters.CharFilter(field_name="season")
    # CRUD-01 range/threshold dimensions
    age_min = filters.NumberFilter(field_name="age", lookup_expr="gte")
    age_max = filters.NumberFilter(field_name="age", lookup_expr="lte")
    market_value_min = filters.NumberFilter(field_name="market_value", lookup_expr="gte")
    market_value_max = filters.NumberFilter(field_name="market_value", lookup_expr="lte")
    impact_score_min = filters.NumberFilter(field_name="impact_score", lookup_expr="gte")
    impact_score_max = filters.NumberFilter(field_name="impact_score", lookup_expr="lte")
    compatibility_score_min = filters.NumberFilter(field_name="compatibility_score", lookup_expr="gte")
    compatibility_score_max = filters.NumberFilter(field_name="compatibility_score", lookup_expr="lte")
    financial_fit_score_min = filters.NumberFilter(field_name="financial_fit_score", lookup_expr="gte")
    financial_fit_score_max = filters.NumberFilter(field_name="financial_fit_score", lookup_expr="lte")
    transfer_probability_score_min = filters.NumberFilter(field_name="transfer_probability_score", lookup_expr="gte")
    transfer_probability_score_max = filters.NumberFilter(field_name="transfer_probability_score", lookup_expr="lte")
    # A2 fix: minutes range, the one other dimension the requirement named
    # explicitly alongside age/market_value ("position metrics" beyond this
    # is NOT covered here -- see players/filters.py's module note below).
    minutes_min = filters.NumberFilter(field_name="Minutes_played", lookup_expr="gte")
    minutes_max = filters.NumberFilter(field_name="Minutes_played", lookup_expr="lte")

    class Meta:
        model = Player
        fields = [
            "ids", "position", "league", "season",
            "age_min", "age_max",
            "market_value_min", "market_value_max",
            "impact_score_min", "impact_score_max",
            "compatibility_score_min", "compatibility_score_max",
            "financial_fit_score_min", "financial_fit_score_max",
            "transfer_probability_score_min", "transfer_probability_score_max",
            "minutes_min", "minutes_max",
        ]

    def filter_league(self, queryset, name, value):
        return queryset.filter(
            Q(season__in=ROW_LEAGUE_SEASONS, league=value)
            | (~Q(season__in=ROW_LEAGUE_SEASONS) & Q(club__league=value))
        )

    def filter_queryset(self, queryset):
        # Discretionary cap (07-CONTEXT.md open item): reject an accidentally
        # enormous unpaginated ?ids= multi-fetch.
        raw_ids = self.data.get("ids")
        if raw_ids and len([x for x in raw_ids.split(",") if x]) > 100:
            raise ValidationError({"ids": "A maximum of 100 ids may be requested at once."})

        # A1 fix: Player rows are player-SEASON records (players/season.py)
        # -- without this, an unfiltered list returns up to 4 rows for the
        # same real person (plus genuine cross-season name collisions).
        # Skipped for ?ids= multi-fetch: that endpoint is documented as
        # fetching an EXACT set of rows by primary key (e.g. side-by-side
        # comparison across specific season-rows) -- forcing the default
        # season on top would silently drop requested ids that aren't in
        # that season.
        if not raw_ids:
            queryset = queryset.filter(season=resolve_season(self.data.get("season")))

        return super().filter_queryset(queryset)
