"""PlayerFilter -- CRUD-01 (filter dimensions) + CRUD-05 (?ids= multi-fetch).

`position` binds to `Player.position` (the CLEAN 10-value group: AM/CB/CM/
DM/FWD/GK/LB/LW/RB/RW), NEVER `Player.main_position` (22 fine-grained
values + a garbage '0' row) -- verified against `PlayerRoleScore
.position_group` and `Player.Meta.indexes` during planning. This is one of
the two highest-risk correctness pivots this plan protects.
"""

import django_filters as filters
from rest_framework.exceptions import ValidationError

from players.models import Player


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
    league = filters.CharFilter(field_name="league")
    # CRUD-01 range/threshold dimensions
    age_min = filters.NumberFilter(field_name="age", lookup_expr="gte")
    age_max = filters.NumberFilter(field_name="age", lookup_expr="lte")
    market_value_min = filters.NumberFilter(field_name="market_value", lookup_expr="gte")
    market_value_max = filters.NumberFilter(field_name="market_value", lookup_expr="lte")
    impact_score_min = filters.NumberFilter(field_name="impact_score", lookup_expr="gte")
    compatibility_score_min = filters.NumberFilter(field_name="compatibility_score", lookup_expr="gte")
    financial_fit_score_min = filters.NumberFilter(field_name="financial_fit_score", lookup_expr="gte")
    transfer_probability_score_min = filters.NumberFilter(field_name="transfer_probability_score", lookup_expr="gte")

    class Meta:
        model = Player
        fields = [
            "ids", "position", "league",
            "age_min", "age_max",
            "market_value_min", "market_value_max",
            "impact_score_min", "compatibility_score_min",
            "financial_fit_score_min", "transfer_probability_score_min",
        ]

    def filter_queryset(self, queryset):
        # Discretionary cap (07-CONTEXT.md open item): reject an accidentally
        # enormous unpaginated ?ids= multi-fetch.
        raw_ids = self.data.get("ids")
        if raw_ids and len([x for x in raw_ids.split(",") if x]) > 100:
            raise ValidationError({"ids": "A maximum of 100 ids may be requested at once."})
        return super().filter_queryset(queryset)
