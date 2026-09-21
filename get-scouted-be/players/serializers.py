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

A3 fix (2026-09-09): `league` on BOTH serializers resolves through
`Player.club.league` (the clean, mode-derived canonical value -- always one
of clubs.leagues.REAL_LEAGUES), NEVER the raw `Player.league` DB column.
That raw column is per-STAT-ROW source data (which competition file this
row's minutes/stats came from) and is confirmed contaminated for ~8.7% of
rows -- e.g. a West Bromwich Albion player's row can carry
`league="Serie A (Italy)"` from a spell at a prior club, while
`club.league` correctly says "EFL Championship". Exposing the raw column
directly is exactly the "random leagues leaking in" bug. The raw column
itself is left untouched in the DB (still real per-row source history, not
deleted) -- only what the API serves/filters on changed.

Exception: seasons in `players.season.ROW_LEAGUE_SEASONS` (2025-2026), whose
per-row league is clean (99.24% self-consistent) and, unlike the single
per-club value, correct for clubs that changed division. See `effective_league`.
"""

from rest_framework import serializers

from players.models import Player
from players.season import effective_league


class PlayerListSerializer(serializers.ModelSerializer):
    """Lightweight list/squad/multi-fetch shape: identity + position/league/club
    + market value + the 4 Phase-6 denormalized own-club scores. No stat block."""

    club_name = serializers.SerializerMethodField()
    league = serializers.SerializerMethodField()

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

    def get_league(self, obj):
        # A3 fix: canonical club league, not the noisy per-row raw column
        # (see module docstring) -- except for seasons whose per-row league
        # is known-clean (players.season.ROW_LEAGUE_SEASONS). Falls back to
        # the raw value only for a player with no resolved club.
        return effective_league(obj)


class PlayerDetailSerializer(serializers.ModelSerializer):
    """Full profile: every model field (all ~99 stats + profile + season +
    denormalized scores + extended_stats). Score BREAKDOWNS are attached by
    the view via get_summary, not by this serializer."""

    club_name = serializers.SerializerMethodField()
    league = serializers.SerializerMethodField()

    class Meta:
        model = Player
        fields = "__all__"

    def get_club_name(self, obj):
        return obj.club.name if obj.club_id else None

    def get_league(self, obj):
        # A3 fix -- see PlayerListSerializer.get_league / module docstring.
        return effective_league(obj)
