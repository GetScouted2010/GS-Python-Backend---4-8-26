from rest_framework import serializers

from workspace.models import Watchlist


class WatchlistSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Watchlist
        fields = ["id", "user", "player", "added_at"]
        read_only_fields = ["id", "added_at"]
