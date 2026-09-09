"""Pure-Python unit tests for players/filters.py's PlayerFilter (07-02-PLAN.md).

No DB access -- these lock in the FilterSet's field bindings directly,
guarding against a regression back onto Player.main_position (22
fine-grained values + a garbage '0' row) instead of the clean 10-value
Player.position group.
"""

from players.filters import PlayerFilter


def test_position_filter_binds_to_position_field():
    assert PlayerFilter.base_filters["position"].field_name == "position"


def test_score_threshold_filters_use_gte():
    assert PlayerFilter.base_filters["impact_score_min"].lookup_expr == "gte"


def test_season_filter_binds_to_season_field():
    assert PlayerFilter.base_filters["season"].field_name == "season"
