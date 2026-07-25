from rest_framework import serializers

from workspace.models import Shortlist, ShortlistEntry, Watchlist


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
