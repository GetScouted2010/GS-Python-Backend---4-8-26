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

Does NOT touch the scoring engine (`scoring.characterization.reconstruct`,
`scoring.services.population`) -- that intentionally reconstructs the FULL
cross-season population for RMM/CS/TP computation today. Whether the
scoring pipeline should also be season-scoped is a separate, larger
question, deliberately out of scope here.
"""

from __future__ import annotations

SEASON_ORDER: list[str] = [
    "Last Calendar Year",
    "2024-2025",
    "2023-2024",
    "2022-2023",
]

DEFAULT_SEASON: str = SEASON_ORDER[0]

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
