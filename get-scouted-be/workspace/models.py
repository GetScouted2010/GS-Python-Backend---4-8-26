import uuid

from django.conf import settings
from django.db import models


class Watchlist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlist")
    player = models.ForeignKey("players.Player", on_delete=models.CASCADE, related_name="watchlisted_by")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "player"], name="uniq_user_player_watchlist")
        ]
        indexes = [models.Index(fields=["user", "-added_at"])]


class Shortlist(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="shortlists")
    name = models.CharField(max_length=255)
    club = models.ForeignKey("clubs.Club", on_delete=models.CASCADE, related_name="shortlists")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-created_at"])]


class ShortlistEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shortlist = models.ForeignKey(Shortlist, on_delete=models.CASCADE, related_name="entries")
    player = models.ForeignKey("players.Player", on_delete=models.CASCADE, related_name="shortlist_entries")
    note = models.TextField(blank=True, default="")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["shortlist", "player"], name="uniq_shortlist_player_entry")
        ]
        indexes = [models.Index(fields=["shortlist", "-added_at"])]


class SquadPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="squad_plans")
    club = models.ForeignKey("clubs.Club", on_delete=models.CASCADE, related_name="squad_plans")
    name = models.CharField(max_length=255)
    formation = models.CharField(max_length=50, blank=True, default="")
    proposed_changes = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-updated_at"])]


class RecentActivity(models.Model):
    class ActivityType(models.TextChoices):
        VIEWED_PLAYER = "viewed_player"
        VIEWED_CLUB = "viewed_club"
        SEARCHED = "searched"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=20, choices=ActivityType.choices)
    target_id = models.UUIDField(null=True, blank=True)  # bare UUID, NOT a FK (Pitfall 2)
    query_text = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "-created_at"])]
