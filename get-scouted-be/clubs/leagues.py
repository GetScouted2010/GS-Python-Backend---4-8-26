"""The whitelist of in-scope leagues (A3 fix).

This is the single source of truth for "which leagues does this product
support" -- previously duplicated as a private copy inside
`players/ai/anthropic_parser.py` (that parser now imports it from here).

Verified 2026-09-09: this set is an EXACT match (0 diff either direction)
for `SELECT DISTINCT league FROM clubs_club` -- Club.league is derived as
the mode of the (very noisy, per-player-row) League column across each
club's rows (clubs/management/commands/import_clubs_playstyles.py), and
that mode-selection already lands on a real, in-scope league every time; no
noise/garbage league value has ever won a club's mode. So this whitelist is
not a new business decision layered on top of messy data -- it already
describes the real, current output faithfully. It exists here explicitly
so (a) it stops silently drifting out of sync with the AI parser's copy,
and (b) it can be asserted against future data pulls (a new value appearing
in this diff is a real signal worth a human look, not something to guess at
silently).
"""

from __future__ import annotations

REAL_LEAGUES: frozenset[str] = frozenset(
    {
        "Allsvenskan (Sweden)",
        "Bundesliga (Austria)",
        "Bundesliga (Germany)",
        "Bundesliga 2",
        "Challenger Pro League",
        "EFL Championship",
        "EFL League One",
        "Eerste Divisie",
        "Eliteserien",
        "Eredivisie (Netherlands)",
        "La Liga (Spain)",
        "La Liga 2",
        "Liga Portugal 2",
        "Ligue 1 (France)",
        "Ligue 2 (France)",
        "MLS (USA)",
        "Premier League (England)",
        "Primeira Liga (Portugal)",
        "Pro League (Belgium)",
        "SPL",
        "Serie A (Brazil)",
        "Serie A (Italy)",
        "Serie B",
        "Super Lig (Turkey)",
        "Superliga (Denmark)",
    }
)
