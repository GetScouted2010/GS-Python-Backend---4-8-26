import factory
import pytest

from accounts.tests.conftest import UserFactory, authenticated_client, user_factory  # re-export
from clubs.models import Club
from players.models import Player
from players.season import DEFAULT_SEASON


class ClubFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Club
        django_get_or_create = ("name",)

    name = factory.Sequence(lambda n: f"Test Club {n}")


class PlayerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Player

    # unique_id: required, unique IntegerField with NO default/null=True
    # (players/models.py line 18) — omitting it makes PlayerFactory() raise
    # IntegrityError. Sequence guarantees the required uniqueness.
    unique_id = factory.Sequence(lambda n: n)
    player = factory.Sequence(lambda n: f"Test Player {n}")
    # A1 fix (players/season.py): every real Player row has a season; squad
    # listings now scope to the default season, so factory players need one
    # too or they silently vanish from club.players queries in tests.
    season = DEFAULT_SEASON


@pytest.fixture
def club_factory():
    return ClubFactory


@pytest.fixture
def player_factory():
    return PlayerFactory
