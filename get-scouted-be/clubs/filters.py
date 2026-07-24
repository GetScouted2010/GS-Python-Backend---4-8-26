"""ClubFilter -- CRUD-02 (filter dimensions: league/country/playing-style
thresholds) + CRUD-05 (?ids= multi-fetch, club half).
"""

import django_filters as filters
from rest_framework.exceptions import ValidationError

from clubs.models import Club


class IdsInFilter(filters.BaseInFilter, filters.UUIDFilter):
    """?ids=<uuid1>,<uuid2>,... -- CRUD-05 multi-fetch."""


class ClubFilter(filters.FilterSet):
    ids = IdsInFilter(field_name="id")
    league = filters.CharFilter(field_name="league")
    country = filters.CharFilter(field_name="country")
    # Playing-style thresholds. NOTE: filtering any style field inherently
    # EXCLUDES the ~77.4% of clubs with no Playstyles coverage (nulls) --
    # that is a correct data-coverage artifact, not a bug (Pitfall 5).
    control_possession_min = filters.NumberFilter(field_name="control_possession", lookup_expr="gte")
    gegenpressing_min = filters.NumberFilter(field_name="gegenpressing", lookup_expr="gte")
    direct_play_min = filters.NumberFilter(field_name="direct_play", lookup_expr="gte")
    tiki_taka_min = filters.NumberFilter(field_name="tiki_taka", lookup_expr="gte")
    counter_attack_min = filters.NumberFilter(field_name="counter_attack", lookup_expr="gte")
    wing_play_min = filters.NumberFilter(field_name="wing_play", lookup_expr="gte")
    low_block_min = filters.NumberFilter(field_name="low_block", lookup_expr="gte")
    defensive_counter_attack_min = filters.NumberFilter(field_name="defensive_counter_attack", lookup_expr="gte")

    class Meta:
        model = Club
        fields = [
            "ids", "league", "country",
            "control_possession_min", "gegenpressing_min", "direct_play_min",
            "tiki_taka_min", "counter_attack_min", "wing_play_min",
            "low_block_min", "defensive_counter_attack_min",
        ]

    def filter_queryset(self, queryset):
        raw_ids = self.data.get("ids")
        if raw_ids and len([x for x in raw_ids.split(",") if x]) > 100:
            raise ValidationError({"ids": "A maximum of 100 ids may be requested at once."})
        return super().filter_queryset(queryset)
