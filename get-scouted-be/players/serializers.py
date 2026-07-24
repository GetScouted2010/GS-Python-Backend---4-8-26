"""Player read-layer serializers (07-02-PLAN.md).

Two shapes, split by depth:

- `PlayerListSerializer` -- the lightweight list/squad/multi-fetch shape
  (identity + position/league/club + market value + the 4 Phase-6
  denormalized own-club scores). No stat block. This is the shape 07-03's
  Club detail squad-overview component reuses directly.
- `PlayerDetailSerializer` -- the full profile (every model field: all
  ~99 stats + profile + season + denormalized scores + extended_stats).
  Score BREAKDOWNS (rmm/compatibility/financial_fit/transfer_probability)
  are attached by the view via `scoring.services.summary.get_summary` /
  `rmm.get_rmm`, not by this serializer.
"""

from rest_framework import serializers

from players.models import Player


class PlayerListSerializer(serializers.ModelSerializer):
    """Lightweight list/squad/multi-fetch shape: identity + position/league/club
    + market value + the 4 Phase-6 denormalized own-club scores. No stat block."""

    club_name = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = [
            "id", "player", "position", "main_position", "league",
            "club", "club_name", "age", "market_value",
            "impact_score", "compatibility_score",
            "financial_fit_score", "transfer_probability_score",
        ]

    def get_club_name(self, obj):
        return obj.club.name if obj.club_id else None


class PlayerDetailSerializer(serializers.ModelSerializer):
    """Full profile: every model field (all ~99 stats + profile + season +
    denormalized scores + extended_stats). Score BREAKDOWNS are attached by
    the view via get_summary, not by this serializer."""

    club_name = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = "__all__"

    def get_club_name(self, obj):
        return obj.club.name if obj.club_id else None
