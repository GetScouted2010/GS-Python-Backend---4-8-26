"""Club read-layer serializers (07-03-PLAN.md).

Two shapes, split by depth:

- `ClubListSerializer` -- the lightweight list/multi-fetch shape: identity +
  league/country/manager/formation + the 8 playing-style floats (nullable,
  ~22.6% coverage -- nulls are expected, not a data quality failure).
- `ClubDetailSerializer` -- the full club profile PLUS a squad overview
  (reusing 07-02's `players.serializers.PlayerListSerializer` over
  `club.players.all()`) PLUS transfer-behaviour aggregates.

CRITICAL: transfer aggregates read `Transfer.market_value_at_transfer`
(clean BigIntegerField, 0 nulls across 47,201 rows) ONLY -- never
`Transfer.fee` (free-text "Free"/"loan"/currency strings that are not
aggregatable). A club with zero transfers yields `None` averages via
Django's Avg/Sum on an empty queryset: correct "null means null", not a bug
to paper over.
"""

from django.db.models import Avg, Count, Sum
from rest_framework import serializers

from clubs.models import Club
from players.season import request_season, scope_to_season
from players.serializers import PlayerListSerializer
from transfers.models import Transfer


class ClubListSerializer(serializers.ModelSerializer):
    """Lightweight list/multi-fetch shape: identity + league/country/manager/
    formation + the 8 playing-style floats (nullable, ~22.6% coverage)."""

    class Meta:
        model = Club
        fields = [
            "id", "name", "league", "country", "manager", "formation",
            "control_possession", "gegenpressing", "direct_play",
            "defensive_counter_attack", "tiki_taka", "counter_attack",
            "wing_play", "low_block",
        ]


class ClubDetailSerializer(serializers.ModelSerializer):
    """Full club profile + squad overview + transfer-behaviour aggregates.

    Aggregates read Transfer.market_value_at_transfer (clean BigInteger, 0
    nulls) ONLY -- never Transfer.fee (free-text, un-aggregatable). A club
    with zero transfers yields None averages: correct null-means-null, not a
    bug to paper over.
    """

    squad = serializers.SerializerMethodField()
    transfer_aggregates = serializers.SerializerMethodField()

    class Meta:
        model = Club
        fields = [
            "id", "name", "league", "country", "manager", "formation",
            "control_possession", "gegenpressing", "direct_play",
            "defensive_counter_attack", "tiki_taka", "counter_attack",
            "wing_play", "low_block",
            "squad", "transfer_aggregates",
        ]

    def get_squad(self, club):
        # related_name="players" (verified); reuse 07-02's lightweight shape.
        # A1 fix (players/season.py): scope to one resolved season -- a
        # club's roster otherwise shows each real player once per season
        # pull (up to 4x). ?season= on the request overrides the default.
        season = request_season(self.context.get("request"))
        return PlayerListSerializer(scope_to_season(club.players.all(), season), many=True).data

    def get_transfer_aggregates(self, club):
        qs = Transfer.objects.filter(club=club)  # related_name="transfers"
        return {
            "total_transfers": qs.count(),
            "arrivals": qs.filter(movement="arrival").count(),
            "departures": qs.filter(movement="departure").count(),
            "avg_market_value_at_transfer": qs.aggregate(v=Avg("market_value_at_transfer"))["v"],
            "total_market_value_at_transfer": qs.aggregate(v=Sum("market_value_at_transfer"))["v"],
            "by_window": list(qs.values("window").annotate(count=Count("id"))),
        }
