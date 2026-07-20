from django.db import models


class Transfer(models.Model):
    """A single transfer event from transferdata final.csv.

    CRITICAL: transferdata.UniqueID is a CLUB identifier (207 distinct values,
    1:1 with Club), NOT a player identifier, despite sharing an identical
    column name with Players.csv's player-level UniqueID. It must never be
    joined against Player.unique_id (see FIELD_MAPPING.md section 4).
    """

    club = models.ForeignKey(
        "clubs.Club",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers",
    )
    # transferdata.UniqueID (a CLUB id) — captured for cross-source
    # confirmation only, never used to resolve Transfer.player.
    source_unique_id = models.IntegerField(null=True, blank=True)

    player = models.ForeignKey(
        "players.Player",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers",
    )
    player_name_raw = models.CharField(max_length=255)

    age_at_transfer = models.IntegerField(null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    position = models.CharField(max_length=50, null=True, blank=True)
    short_position = models.CharField(max_length=20, null=True, blank=True)
    market_value_at_transfer = models.BigIntegerField(null=True, blank=True)

    # Plain string, NOT a FK — 2,909 distinct counterparty values, a much
    # larger/lower-league universe than the 1,059-club Players.csv universe.
    dealing_club = models.CharField(max_length=255)
    dealing_country = models.CharField(max_length=100, null=True, blank=True)

    # Fees are non-numeric strings ("Free", "loan", etc.) — keep raw.
    fee = models.CharField(max_length=100, null=True, blank=True)
    movement = models.CharField(max_length=20)
    window = models.CharField(max_length=20)
    league_name = models.CharField(max_length=255, null=True, blank=True)
    year = models.IntegerField()
    is_loan = models.BooleanField(null=True, blank=True)
    loan_status = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "player_name_raw",
                    "year",
                    "window",
                    "movement",
                    "club",
                    "dealing_club",
                ],
                name="uniq_transfer_event",
            )
        ]
        indexes = [
            models.Index(fields=["club"]),
        ]

    def __str__(self):
        return f"{self.player_name_raw} ({self.movement}, {self.year})"
