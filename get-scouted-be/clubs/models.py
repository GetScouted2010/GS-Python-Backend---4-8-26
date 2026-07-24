import uuid

from django.db import models


class Club(models.Model):
    """
    A football club.

    No dedicated source CSV exists for clubs — this table is derived from the
    union of Players.csv's Team_within_selected_timeframe values and
    Playstyles.csv's Team values (see FIELD_MAPPING.md section 3).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    league = models.CharField(max_length=255, null=True, blank=True)
    country = models.CharField(max_length=255, null=True, blank=True)
    manager = models.CharField(max_length=255, null=True, blank=True)
    formation = models.CharField(max_length=50, null=True, blank=True)

    # The transferdata/Playstyles club-scoped UniqueID, kept for cross-source
    # confirmation only. NOT a player id (see FIELD_MAPPING.md section 4).
    source_unique_id = models.IntegerField(null=True, blank=True)

    # 8 playing-style floats from Playstyles.csv. Only ~22.6% of clubs have
    # coverage here — nulls are expected, not a data quality failure.
    control_possession = models.FloatField(null=True, blank=True)
    gegenpressing = models.FloatField(null=True, blank=True)
    direct_play = models.FloatField(null=True, blank=True)
    defensive_counter_attack = models.FloatField(null=True, blank=True)
    tiki_taka = models.FloatField(null=True, blank=True)
    counter_attack = models.FloatField(null=True, blank=True)
    wing_play = models.FloatField(null=True, blank=True)
    low_block = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name
