from rest_framework import serializers

from players.serializers import PlayerListSerializer
from workspace.models import Shortlist, ShortlistEntry, SquadPlan, Watchlist


class WatchlistSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Watchlist
        fields = ["id", "user", "player", "added_at"]
        read_only_fields = ["id", "added_at"]


class ShortlistSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Shortlist
        fields = ["id", "user", "name", "club", "created_at"]
        read_only_fields = ["id", "created_at"]


class ShortlistEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShortlistEntry
        # `shortlist` is read_only here because the view injects it via
        # serializer.save(shortlist=shortlist) from the URL, not the request body.
        fields = ["id", "shortlist", "player", "note", "added_at"]
        read_only_fields = ["id", "shortlist", "added_at"]


class SquadPlanListSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = SquadPlan
        fields = ["id", "user", "club", "name", "formation", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class SquadPlanDetailSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())
    current_squad = serializers.SerializerMethodField()

    class Meta:
        model = SquadPlan
        fields = [
            "id", "user", "club", "name", "formation", "proposed_changes",
            "created_at", "updated_at", "current_squad",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_current_squad(self, obj):
        # Live, never frozen -- exact ClubDetailSerializer.get_squad pattern.
        return PlayerListSerializer(obj.club.players.all(), many=True).data

    def validate_proposed_changes(self, value):
        allowed = {"add", "remove", "swap"}
        if not isinstance(value, list):
            raise serializers.ValidationError("proposed_changes must be a list.")
        for entry in value:
            if not isinstance(entry, dict) or entry.get("action") not in allowed:
                raise serializers.ValidationError(f"each entry needs action in {allowed}.")
            if entry["action"] == "swap" and not entry.get("incoming_player_id"):
                raise serializers.ValidationError("swap entries require incoming_player_id.")
        return value
