"""Season-dimension resolution for the CRUD/display layer (A1 fix).

Player rows are player-SEASON records (`Player.season`) -- one row per
player per season pull, NOT one row per real person. Listing
`Player.objects.all()` unfiltered returns up to 4 rows for the same real
person (plus, for shared names, a genuine mix of DIFFERENT real people
across seasons -- confirmed against production data: "Paulinho" alone has
7 distinct real players in the 2022-2023 season). This module exists so
every CRUD-facing list/squad view scopes to ONE season consistently
instead of re-deciding it ad hoc.

SEASON_ORDER is an explicit, hand-maintained list -- NOT derived by sorting
the `season` strings (string-sorting would put "Last Calendar Year" in the
wrong place). "Last Calendar Year" is a ROLLING window that in practice
tracks/overlaps the most recent fixed season most closely (confirmed:
its stat lines are near-identical to "2024-2025" for the same players) --
treated as the freshest/default season per product decision (2026-09-09).

"2025-2026" (added via `import_wyscout_season`) is listed second, i.e. it is
SELECTABLE but not the default. The default deliberately stays "Last
Calendar Year" until 2025-2026 players have scores -- see UNSCORED_SEASONS.

The scoring engine (`scoring.characterization.reconstruct`,
`scoring.services.population`) intentionally reconstructs the FULL
cross-season population for RMM/CS/TP computation. Whether the scoring
pipeline should also be season-scoped is a separate, larger question; the
only season-awareness it has is UNSCORED_SEASONS below.
"""

from __future__ import annotations

SEASON_ORDER: list[str] = [
    "Last Calendar Year",
    "2025-2026",
    "2024-2025",
    "2023-2024",
    "2022-2023",
]

DEFAULT_SEASON: str = SEASON_ORDER[0]

# Seasons whose Player rows exist but are held OUT of the scoring population
# (`build_players_df`). Impact is a pooled percentile rank (`rank(pct=True)`
# over every Player row), so letting ~18k new rows in would silently shift
# EVERY existing player's score, and 2025-2026 rows have no role-score /
# compatibility source data yet. Their four denormalized scores therefore
# stay NULL. Remove a season from this set only as a deliberate, reviewed
# change -- it changes existing players' numbers.
UNSCORED_SEASONS: frozenset[str] = frozenset({"2025-2026"})

# Seasons whose per-row `Player.league` is CLEAN and authoritative, so the API
# serves and filters on it directly instead of on `club.league`. Two reasons
# it beats club.league for these seasons, both measured on the real file:
#   - 99.24% of 2025-2026 rows carry the same league as their club's dominant
#     league in that file (the older data is only 90.67% -- the ~8.7%
#     contamination that made the A3 fix prefer club.league for old seasons);
#   - Club.league is one value per club, so it cannot describe a club that
#     changed division (Metz, Pisa, Clermont: promoted/relegated) and is
#     plain wrong for ~62 clubs from leagues the older data never covered
#     (e.g. Panathinaikos stored as "La Liga (Spain)").
# Old seasons are untouched: they still resolve through club.league.
ROW_LEAGUE_SEASONS: frozenset[str] = frozenset({"2025-2026"})

_VALID_SEASONS = set(SEASON_ORDER)


def resolve_season(requested: str | None) -> str:
    """Return the season to filter on: `requested` if it's a recognized
    season value, else `DEFAULT_SEASON`. Never raises -- an unrecognized or
    blank `requested` silently falls back to the default rather than
    erroring or returning an empty result set."""
    if requested and requested in _VALID_SEASONS:
        return requested
    return DEFAULT_SEASON


def scope_to_season(queryset, requested: str | None = None):
    """Filter a Player queryset down to one resolved season."""
    return queryset.filter(season=resolve_season(requested))


def request_season(request) -> str | None:
    """Pull the raw `?season=` value off a DRF request, or None if there's
    no request in context (e.g. a serializer used outside a view)."""
    if request is None:
        return None
    return request.query_params.get("season")


def effective_league(player) -> str | None:
    """The league to SHOW for a Player row (see ROW_LEAGUE_SEASONS).

    `players.filters.PlayerFilter.filter_league` implements the same rule in
    SQL -- keep the two in step.
    """
    if player.season in ROW_LEAGUE_SEASONS and player.league:
        return player.league
    return player.club.league if player.club_id else player.league
