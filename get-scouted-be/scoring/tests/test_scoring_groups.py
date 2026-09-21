"""Scoring populations (players/season.py): the legacy pool of older seasons
and 2025-2026 on its own.

Impact is a percentile rank over a population, so which players share one
decides every number. Scoring 2025-2026 against its own season reproduces the
data provider's exported impact almost exactly (mean difference 0.00,
correlation 0.99); pools including older seasons drift 1.4-3.1 points away.
Keeping the legacy pool as it was is what leaves every existing score unchanged.
"""

from __future__ import annotations

import itertools

import pytest

from clubs.models import Club
from players.models import Player
from players.season import (
    LEGACY_SCORING_GROUP,
    OWN_POPULATION_SEASONS,
    filter_to_scoring_group,
    scoring_group,
    scoring_groups,
)
from scoring.characterization.reconstruct import build_players_df, build_role_scores_wide
from scoring.services import population

pytestmark = pytest.mark.django_db

_seq = itertools.count(1_800_000_001)


def _player(season, club=None, **kw):
    return Player.objects.create(
        unique_id=next(_seq), player=f"P {season}", season=season, club=club, **kw
    )


@pytest.fixture(autouse=True)
def _fresh_caches():
    population.clear_scoring_caches()
    yield
    population.clear_scoring_caches()


# ---------------------------------------------------------------------------
# Group membership
# ---------------------------------------------------------------------------


def test_2025_2026_is_its_own_group_and_every_other_season_is_legacy():
    assert scoring_group("2025-2026") == "2025-2026"
    for season in ("Last Calendar Year", "2024-2025", "2023-2024", "2022-2023", None):
        assert scoring_group(season) == LEGACY_SCORING_GROUP


def test_groups_are_listed_legacy_first():
    assert scoring_groups()[0] == LEGACY_SCORING_GROUP
    assert set(scoring_groups()) == {LEGACY_SCORING_GROUP, *OWN_POPULATION_SEASONS}


def test_a_player_is_in_exactly_one_population():
    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    current = _player("2025-2026", club)
    older = _player("2024-2025", club)
    no_season = _player(None, club)

    legacy = set(build_players_df(LEGACY_SCORING_GROUP)["player_id"].astype(str))
    own = set(build_players_df("2025-2026")["player_id"].astype(str))

    assert legacy == {str(older.id), str(no_season.id)}  # NULL-season rows stay legacy
    assert own == {str(current.id)}
    assert not (legacy & own)


def test_default_population_is_the_legacy_one():
    # The oracle and the TFM training call build_players_df() with no argument;
    # they must keep getting the population they were built and validated on.
    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    _player("2025-2026", club)
    older = _player("2023-2024", club)

    assert set(build_players_df()["player_id"].astype(str)) == {str(older.id)}


def test_an_unknown_group_has_no_members_rather_than_everyone():
    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    _player("2025-2026", club)
    _player("2024-2025", club)

    assert filter_to_scoring_group(Player.objects.all(), "no-such-group").count() == 0
    assert population.group_has_players("no-such-group") is False


def test_role_scores_are_restricted_to_the_group():
    from players.models import PlayerRoleScore

    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    current, older = _player("2025-2026", club), _player("2024-2025", club)
    for player in (current, older):
        PlayerRoleScore.objects.create(
            player=player, position_group="CB", role_name="libero",
            role_name_raw="Libero", score=50.0,
        )

    assert set(build_role_scores_wide(LEGACY_SCORING_GROUP)["player_id"].astype(str)) == {str(older.id)}
    assert set(build_role_scores_wide("2025-2026")["player_id"].astype(str)) == {str(current.id)}


def test_filter_helper_works_through_a_relation():
    from players.models import PlayerRoleScore

    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    current = _player("2025-2026", club)
    PlayerRoleScore.objects.create(
        player=current, position_group="CB", role_name="libero", role_name_raw="Libero", score=1.0
    )

    own = filter_to_scoring_group(PlayerRoleScore.objects.all(), "2025-2026", season_field="player__season")
    legacy = filter_to_scoring_group(PlayerRoleScore.objects.all(), LEGACY_SCORING_GROUP, season_field="player__season")

    assert own.count() == 1
    assert legacy.count() == 0


# ---------------------------------------------------------------------------
# group_for_player
# ---------------------------------------------------------------------------


def test_group_for_player_follows_the_players_season():
    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    assert population.group_for_player(_player("2025-2026", club).id) == "2025-2026"
    assert population.group_for_player(_player("2022-2023", club).id) == LEGACY_SCORING_GROUP
    assert population.group_for_player(_player(None, club).id) == LEGACY_SCORING_GROUP


def test_group_for_an_unknown_player_is_legacy_so_the_service_raises_its_own_404():
    assert population.group_for_player("00000000-0000-0000-0000-000000000000") == LEGACY_SCORING_GROUP


# ---------------------------------------------------------------------------
# Per-group caching
# ---------------------------------------------------------------------------


def test_each_group_is_built_once_and_independently(monkeypatch):
    calls: list[str] = []

    def fake_build_players_df(group=LEGACY_SCORING_GROUP):
        calls.append(group)
        import pandas as pd

        return pd.DataFrame({"player_id": [group]})

    import pandas as pd

    monkeypatch.setattr(population, "build_players_df", fake_build_players_df)
    monkeypatch.setattr(population, "build_role_scores_wide", lambda group=LEGACY_SCORING_GROUP: pd.DataFrame())
    monkeypatch.setattr(population, "build_team_styles_df", lambda: pd.DataFrame())
    monkeypatch.setattr(population, "build_transfers_df", lambda: pd.DataFrame())

    legacy_a = population.reconstruct_population(LEGACY_SCORING_GROUP)
    legacy_b = population.reconstruct_population()  # default argument == legacy
    own = population.reconstruct_population("2025-2026")
    own_again = population.reconstruct_population("2025-2026")

    assert legacy_a is legacy_b and own is own_again
    assert own is not legacy_a
    assert calls == [LEGACY_SCORING_GROUP, "2025-2026"]  # each built exactly once
    assert legacy_a.players_df["player_id"].tolist() == [LEGACY_SCORING_GROUP]
    assert own.players_df["player_id"].tolist() == ["2025-2026"]


def test_clear_scoring_caches_clears_every_group():
    assert population.reconstruct_population.cache_info().currsize == 0
    assert population.get_scored_population.cache_info().currsize == 0
    population.clear_scoring_caches()  # idempotent on an empty cache
    assert population.reconstruct_population.cache_info().currsize == 0


def _stub_warm_targets(monkeypatch, warmed):
    def fake_scored(group=LEGACY_SCORING_GROUP):
        warmed.append(group)

    fake_scored.cache_clear = lambda: None  # clear_scoring_caches() calls it at teardown
    monkeypatch.setattr(population, "get_scored_population", fake_scored)
    monkeypatch.setattr(population, "get_tfm_pipeline", lambda: warmed.append("tfm"))


def test_warming_covers_every_group_that_has_players(monkeypatch):
    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    _player("2025-2026", club)
    _player("2024-2025", club)
    warmed: list[str] = []
    _stub_warm_targets(monkeypatch, warmed)

    population.warm_scoring_caches()

    assert warmed == [*scoring_groups(), "tfm"]


def test_warming_skips_a_group_with_no_players_instead_of_crashing_the_worker(monkeypatch):
    # e.g. a fresh environment where 2025-2026 has not been imported yet.
    club = Club.objects.create(name="Pop FC", league="Serie A (Italy)")
    _player("2024-2025", club)
    warmed: list[str] = []
    _stub_warm_targets(monkeypatch, warmed)

    population.warm_scoring_caches()

    assert warmed == [LEGACY_SCORING_GROUP, "tfm"]
