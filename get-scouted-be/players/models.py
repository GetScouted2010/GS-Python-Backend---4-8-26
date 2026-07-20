from django.db import models


class Player(models.Model):
    """A player row from Players.csv.

    Field naming mirrors the CSV column names verbatim wherever the column is
    a valid Python identifier (locked decision, see FIELD_MAPPING.md) so that
    Phase 5 parity testing traces 1:1 back to impact_model_v4.1.py inputs.
    Identifier/meta/profile fields below use lowercase Django names per this
    plan's explicit field list; the ~99 stat columns keep exact CSV casing.
    """

    # --- Identifiers / natural key ---
    unique_id = models.IntegerField(unique=True)
    player = models.CharField(max_length=255)
    season = models.CharField(max_length=32, null=True, blank=True)
    club = models.ForeignKey(
        "clubs.Club",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="players",
    )

    # Pre-existing score from the OLD (pre-Django) system. NOT the Impact RMM
    # output Phase 4-6 computes. Kept as a Phase 5 parity sanity-check baseline.
    legacy_total_score = models.FloatField(null=True, blank=True)

    # --- Profile fields ---
    league = models.CharField(max_length=255, null=True, blank=True)
    positions = models.CharField(max_length=255, null=True, blank=True)
    main_position = models.CharField(max_length=8, null=True, blank=True)
    position = models.CharField(max_length=50, null=True, blank=True)
    age = models.IntegerField(null=True, blank=True)
    market_value = models.BigIntegerField(null=True, blank=True)
    contract_expires = models.DateField(null=True, blank=True)
    birth_country = models.CharField(max_length=100, null=True, blank=True)
    passport_country = models.CharField(max_length=100, null=True, blank=True)
    foot = models.CharField(max_length=20, null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    weight = models.IntegerField(null=True, blank=True)
    on_loan = models.BooleanField(null=True, blank=True)

    # --- ~99 numeric per-90/percentage stat columns, mirroring Players.csv
    # column names 1:1 (do not invent names — see FIELD_MAPPING.md section 1b) ---
    Matches_played = models.FloatField(null=True, blank=True)
    Minutes_played = models.FloatField(null=True, blank=True)
    Goals = models.FloatField(null=True, blank=True)
    xG = models.FloatField(null=True, blank=True)
    Assists = models.FloatField(null=True, blank=True)
    xA = models.FloatField(null=True, blank=True)
    Duels_per_90 = models.FloatField(null=True, blank=True)
    Duels_won_percentage = models.FloatField(null=True, blank=True)
    Successful_defensive_actions_per_90 = models.FloatField(null=True, blank=True)
    Defensive_duels_per_90 = models.FloatField(null=True, blank=True)
    Defensive_duels_won_percentage = models.FloatField(null=True, blank=True)
    Aerial_duels_per_90 = models.FloatField(null=True, blank=True)
    Aerial_duels_won_percentage = models.FloatField(null=True, blank=True)
    Sliding_tackles_per_90 = models.FloatField(null=True, blank=True)
    PAdj_Sliding_tackles = models.FloatField(null=True, blank=True)
    Shots_blocked_per_90 = models.FloatField(null=True, blank=True)
    Interceptions_per_90 = models.FloatField(null=True, blank=True)
    PAdj_Interceptions = models.FloatField(null=True, blank=True)
    Fouls_per_90 = models.FloatField(null=True, blank=True)
    Yellow_cards = models.FloatField(null=True, blank=True)
    Yellow_cards_per_90 = models.FloatField(null=True, blank=True)
    Red_cards = models.FloatField(null=True, blank=True)
    Red_cards_per_90 = models.FloatField(null=True, blank=True)
    Successful_attacking_actions_per_90 = models.FloatField(null=True, blank=True)
    Goals_per_90 = models.FloatField(null=True, blank=True)
    Non_penalty_goals = models.FloatField(null=True, blank=True)
    Non_penalty_goals_per_90 = models.FloatField(null=True, blank=True)
    xG_per_90 = models.FloatField(null=True, blank=True)
    Head_goals = models.FloatField(null=True, blank=True)
    Head_goals_per_90 = models.FloatField(null=True, blank=True)
    Shots = models.FloatField(null=True, blank=True)
    Shots_per_90 = models.FloatField(null=True, blank=True)
    Shots_on_target_percentage = models.FloatField(null=True, blank=True)
    Goal_conversion_percentage = models.FloatField(null=True, blank=True)
    Assists_per_90 = models.FloatField(null=True, blank=True)
    Crosses_per_90 = models.FloatField(null=True, blank=True)
    Accurate_crosses_percentage = models.FloatField(null=True, blank=True)
    Crosses_from_left_flank_per_90 = models.FloatField(null=True, blank=True)
    Accurate_crosses_from_left_flank_percentage = models.FloatField(null=True, blank=True)
    Crosses_from_right_flank_per_90 = models.FloatField(null=True, blank=True)
    Accurate_crosses_from_right_flank_percentage = models.FloatField(null=True, blank=True)
    Crosses_to_goalie_box_per_90 = models.FloatField(null=True, blank=True)
    Dribbles_per_90 = models.FloatField(null=True, blank=True)
    Successful_dribbles_percentage = models.FloatField(null=True, blank=True)
    Offensive_duels_per_90 = models.FloatField(null=True, blank=True)
    Offensive_duels_won_percentage = models.FloatField(null=True, blank=True)
    Touches_in_box_per_90 = models.FloatField(null=True, blank=True)
    Progressive_runs_per_90 = models.FloatField(null=True, blank=True)
    Accelerations_per_90 = models.FloatField(null=True, blank=True)
    Received_passes_per_90 = models.FloatField(null=True, blank=True)
    Received_long_passes_per_90 = models.FloatField(null=True, blank=True)
    Fouls_suffered_per_90 = models.FloatField(null=True, blank=True)
    Passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_passes_percentage = models.FloatField(null=True, blank=True)
    Forward_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_forward_passes_percentage = models.FloatField(null=True, blank=True)
    Back_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_back_passes_percentage = models.FloatField(null=True, blank=True)
    Lateral_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_lateral_passes_percentage = models.FloatField(null=True, blank=True)
    Short_medium_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_short_medium_passes_percentage = models.FloatField(null=True, blank=True)
    Long_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_long_passes_percentage = models.FloatField(null=True, blank=True)
    Average_pass_length_m = models.FloatField(null=True, blank=True)
    Average_long_pass_length_m = models.FloatField(null=True, blank=True)
    xA_per_90 = models.FloatField(null=True, blank=True)
    Shot_assists_per_90 = models.FloatField(null=True, blank=True)
    Second_assists_per_90 = models.FloatField(null=True, blank=True)
    Third_assists_per_90 = models.FloatField(null=True, blank=True)
    Smart_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_smart_passes_percentage = models.FloatField(null=True, blank=True)
    Key_passes_per_90 = models.FloatField(null=True, blank=True)
    Passes_to_final_third_per_90 = models.FloatField(null=True, blank=True)
    Accurate_passes_to_final_third_percentage = models.FloatField(null=True, blank=True)
    Passes_to_penalty_area_per_90 = models.FloatField(null=True, blank=True)
    Accurate_passes_to_penalty_area_percentage = models.FloatField(null=True, blank=True)
    Through_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_through_passes_percentage = models.FloatField(null=True, blank=True)
    Deep_completions_per_90 = models.FloatField(null=True, blank=True)
    Deep_completed_crosses_per_90 = models.FloatField(null=True, blank=True)
    Progressive_passes_per_90 = models.FloatField(null=True, blank=True)
    Accurate_progressive_passes_percentage = models.FloatField(null=True, blank=True)
    Conceded_goals = models.FloatField(null=True, blank=True)
    Conceded_goals_per_90 = models.FloatField(null=True, blank=True)
    Shots_against = models.FloatField(null=True, blank=True)
    Shots_against_per_90 = models.FloatField(null=True, blank=True)
    Clean_sheets = models.FloatField(null=True, blank=True)
    Save_rate_percentage = models.FloatField(null=True, blank=True)
    xG_against = models.FloatField(null=True, blank=True)
    xG_against_per_90 = models.FloatField(null=True, blank=True)
    Prevented_goals = models.FloatField(null=True, blank=True)
    Prevented_goals_per_90 = models.FloatField(null=True, blank=True)
    Back_passes_received_as_GK_per_90 = models.FloatField(null=True, blank=True)
    Exits_per_90 = models.FloatField(null=True, blank=True)
    # NOTE: Aerial_duels_per_90 appears twice in the raw Players.csv header
    # (outfield block col 31 and GK block col 115) — modeled as a single
    # field above; import code must resolve which raw occurrence wins.
    Free_kicks_per_90 = models.FloatField(null=True, blank=True)
    Direct_free_kicks_per_90 = models.FloatField(null=True, blank=True)
    Direct_free_kicks_on_target_percentage = models.FloatField(null=True, blank=True)
    Corners_per_90 = models.FloatField(null=True, blank=True)
    Penalties_taken = models.FloatField(null=True, blank=True)
    Penalty_conversion_percentage = models.FloatField(null=True, blank=True)

    # 14 movement/physical tracking columns (not valid Python identifiers,
    # not referenced by impact_model_v4.1.py) — see FIELD_MAPPING.md section 2.
    extended_stats = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["position"]),
            models.Index(fields=["age"]),
            models.Index(fields=["market_value"]),
            models.Index(fields=["club"]),
        ]

    def __str__(self):
        return self.player


class PlayerRoleScore(models.Model):
    """A per-role score for a player (e.g. how well they fit 'wide_centre_back_lcb')."""

    player = models.ForeignKey(
        "players.Player", on_delete=models.CASCADE, related_name="role_scores"
    )
    position_group = models.CharField(max_length=8)
    role_name = models.CharField(max_length=100)
    role_name_raw = models.CharField(max_length=150)
    score = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["player", "role_name"], name="uniq_player_role"
            )
        ]

    def __str__(self):
        return f"{self.player_id}:{self.role_name}"


class PlayerClubCompatibility(models.Model):
    """A player's compatibility score against a given club's playing style.

    Unique on (player, club_name_raw) — NOT (player, club) — because `club`
    is null for unresolved headers and Postgres treats multiple NULLs as
    non-conflicting, which would break bulk_create(update_conflicts=True)
    idempotency if club were part of the conflict target (RESEARCH.md Open
    Question 2).
    """

    player = models.ForeignKey(
        "players.Player", on_delete=models.CASCADE, related_name="compatibilities"
    )
    club = models.ForeignKey(
        "clubs.Club",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="compatibilities",
    )
    club_name_raw = models.CharField(max_length=255)
    position_group = models.CharField(max_length=8)
    score = models.FloatField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["player", "club_name_raw"], name="uniq_player_clubname"
            )
        ]
        indexes = [
            models.Index(fields=["club", "-score"]),
            models.Index(fields=["player", "-score"]),
        ]

    def __str__(self):
        return f"{self.player_id}:{self.club_name_raw}"
