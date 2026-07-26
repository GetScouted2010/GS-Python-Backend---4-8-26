"""Wave 0 RED scaffold for scoring.services.matching (12-01-PLAN.md).

Pins PLAN-02 (`rank_replacement_players`) and PLAN-04 (`rank_clubs_for_player`)
behavior BEFORE either implementation lands (12-02-PLAN.md / 12-03-PLAN.md).
These tests are expected to fail/error today -- the two ranking functions
currently raise `NotImplementedError` -- and turn green once those plans wire
the real implementation.

Real-data convention (matches every other scoring/tests/test_services_*.py
file): pytest's own test DB is EMPTY, so DB-backed assertions gate on the
`real_data_available` fixture (scoring/tests/conftest.py) and skip cleanly
when empty.
"""

from __future__ import annotations

import ast
import inspect
from unittest.mock import patch

import pytest

from scoring.services import matching


# ---------------------------------------------------------------------------
# PLAN-02: rank_replacement_players
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_rank_replacement_players_excludes_current_squad(real_data_available):
    from clubs.models import Club

    club = Club.objects.first()
    result = matching.rank_replacement_players(club.id, "CB")

    for entry in result["results"]:
        assert entry.get("club") != club.name
        assert entry.get("Team") != club.name


@pytest.mark.django_db
def test_rank_replacement_players_filters_position(real_data_available):
    from clubs.models import Club

    club = Club.objects.first()
    result = matching.rank_replacement_players(club.id, "CB")

    for entry in result["results"]:
        assert entry.get("position") == "CB" or entry.get("Position") == "CB"


@pytest.mark.django_db
def test_rank_replacement_players_bounds_top_n(real_data_available):
    from clubs.models import Club

    club = Club.objects.first()
    top_n = 5
    result = matching.rank_replacement_players(club.id, "CB", top_n=top_n)

    assert len(result["results"]) <= top_n


# ---------------------------------------------------------------------------
# PLAN-04: rank_clubs_for_player
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_rank_clubs_for_player_excludes_own_club(real_data_available):
    from players.models import Player

    player = Player.objects.filter(club__isnull=False).first()
    result = matching.rank_clubs_for_player(player.id)

    own_club_name = player.club.name
    for entry in result["results"]:
        assert entry.get("club") != own_club_name
        assert entry.get("Team") != own_club_name


@pytest.mark.django_db
def test_rank_clubs_for_player_financial_score_not_systematically_null(real_data_available):
    """REGRESSION GUARD for the squad_stats one-row-slice bug: financial_score
    must be non-null for MORE THAN JUST the player's own club -- i.e. not
    every non-own candidate degenerates to NaN."""
    from players.models import Player

    player = Player.objects.filter(club__isnull=False).first()
    result = matching.rank_clubs_for_player(player.id)

    non_null_financial_scores = [
        entry for entry in result["results"] if entry.get("financial_score") is not None
    ]
    non_own_non_null = [
        entry
        for entry in non_null_financial_scores
        if entry.get("club") != player.club.name and entry.get("Team") != player.club.name
    ]
    assert len(non_own_non_null) > 0


@pytest.mark.django_db
def test_rank_clubs_for_player_bounds_top_n(real_data_available):
    from players.models import Player

    player = Player.objects.filter(club__isnull=False).first()
    top_n = 5
    result = matching.rank_clubs_for_player(player.id, top_n=top_n)

    assert len(result["results"]) <= top_n


# ---------------------------------------------------------------------------
# Structural guards (no DB required)
# ---------------------------------------------------------------------------
def test_matching_reuses_shared_primitives():
    """STRUCTURAL: proves both ranking directions reuse the SAME low-level
    scoring primitives already proven by Phase 3-6 via real `from ... import
    ...` statements -- not merely mentioned in prose/docstrings -- never a
    re-derived formula (success criterion 3)."""
    source = inspect.getsource(matching)
    tree = ast.parse(source)

    imported_names_by_module: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_names_by_module.setdefault(node.module, set()).update(
                alias.name for alias in node.names
            )

    role_fit_imports = [
        names for module, names in imported_names_by_module.items() if "role_fit" in module
    ]
    deterministic_scores_imports = [
        names for module, names in imported_names_by_module.items() if "deterministic_scores" in module
    ]

    assert any("compatibility_score" in names for names in role_fit_imports), (
        "expected an actual `from ...role_fit import compatibility_score` (or similar) "
        "import statement in scoring/services/matching.py"
    )
    assert any(
        {"financial_score", "transfer_probability"} <= names
        for names in deterministic_scores_imports
    ), (
        "expected an actual `from ...deterministic_scores import financial_score, "
        "transfer_probability` (or similar) import statement in scoring/services/matching.py"
    )


def test_real_tfm_called_only_for_top_n():
    """The number of real-TFM calls equals len(entries) == top_n by
    construction -- never the full candidate set."""
    top_n = 3
    entries = [{} for _ in range(top_n)]
    pairs = [(f"player-{i}", f"club-{i}") for i in range(top_n)]

    with patch("scoring.services.matching.get_financial_fit") as mock_get_financial_fit:
        mock_get_financial_fit.return_value = {"predicted_fee": 1.0, "value_verdict": "Fair Value"}
        matching._attach_real_tfm(entries, pairs)

    assert mock_get_financial_fit.call_count == top_n
