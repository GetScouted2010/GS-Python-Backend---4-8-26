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

"2025-2026" (added via `import_wyscout_season`) is the DEFAULT season: it is the
newest data, is scored, and its per-row leagues are clean (ROW_LEAGUE_SEASONS).
"Last Calendar Year" is listed second and remains selectable.

The scoring engine (`scoring.characterization.reconstruct`,
`scoring.services.population`) ranks players against a POPULATION: impact is a
percentile rank within position over every Player row in that population. Two
kinds exist -- see OWN_POPULATION_SEASONS below.
"""

from __future__ import annotations

SEASON_ORDER: list[str] = [
    "2025-2026",
    "Last Calendar Year",
    "2024-2025",
    "2023-2024",
    "2022-2023",
]

DEFAULT_SEASON: str = SEASON_ORDER[0]

# Seasons whose Player rows exist but are held OUT of the scoring population
# (`build_players_df`) and therefore have NULL scores. Empty now that
# 2025-2026 is scored; the mechanism (this set, `players.views._is_unscored`,
# the "season_not_scored" reason) stays for the next season that is imported
# before it is scored. Impact is a pooled percentile rank (`rank(pct=True)`
# over every Player row), so ADDING a season to scoring shifts every existing
# player's score -- do it only as a deliberate, reviewed change.
UNSCORED_SEASONS: frozenset[str] = frozenset()

# Scoring populations. Impact is a percentile rank (`rank(pct=True)`) within
# position over a POPULATION, so which players share a population decides every
# number. Two kinds:
#
#   * LEGACY_SCORING_GROUP -- the four older seasons (+ rows with no season),
#     ranked together exactly as they always were. Keeping this pool untouched
#     is what keeps every existing player's score byte-identical (verified
#     against the pre-2025-2026 scores: 0 of 41,010 changed).
#   * a season in OWN_POPULATION_SEASONS -- ranked ONLY against itself. This is
#     how the data provider computes 2025-2026: scoring those players against
#     the 2025-2026 pool alone reproduces the provider's exported impact almost
#     exactly (mean difference 0.00, correlation 0.99), while pools that
#     include older seasons drift away from it by 1.4-3.1 points.
#
# Adding a season here does not move any other population's scores.
LEGACY_SCORING_GROUP: str = "legacy"
OWN_POPULATION_SEASONS: frozenset[str] = frozenset({"2025-2026"})


def scoring_group(season: str | None) -> str:
    """The scoring population a season's players are ranked in."""
    return season if season in OWN_POPULATION_SEASONS else LEGACY_SCORING_GROUP


def scoring_groups() -> list[str]:
    """Every scoring population, legacy first (the order caches are warmed)."""
    return [LEGACY_SCORING_GROUP, *sorted(OWN_POPULATION_SEASONS)]


def filter_to_scoring_group(queryset, group: str, season_field: str = "season"):
    """Restrict a Player (or Player-related) queryset to one scoring group.

    Seasons in UNSCORED_SEASONS belong to no group. `.exclude()` keeps rows
    whose season is NULL, so they stay in the legacy group.
    """
    if group == LEGACY_SCORING_GROUP:
        held_out = OWN_POPULATION_SEASONS | UNSCORED_SEASONS
        return queryset.exclude(**{f"{season_field}__in": held_out})
    if group in OWN_POPULATION_SEASONS and group not in UNSCORED_SEASONS:
        return queryset.filter(**{season_field: group})
    return queryset.none()


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
