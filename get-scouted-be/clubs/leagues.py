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

NOTE (2025-2026 season import): once `import_wyscout_season` has run, the
Club table also contains ~20 leagues that are NOT in this set (Liga MX,
Argentine Primera, J1 League, Ekstraklasa, ...) -- the 2025-2026 Wyscout
pull covers 45 leagues vs the older data's 25. They are deliberately NOT
added here yet: this set gates the natural-language search parser, and
widening the product's in-scope league list is a product decision, not an
import side effect. Until that decision is made the "exact match with
DISTINCT clubs_club.league" property above no longer holds on a database
that has the 2025-2026 season loaded.
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


# ---------------------------------------------------------------------------
# League-label aliases (2025-2026 Wyscout pull)
# ---------------------------------------------------------------------------
# The 2025-2026 file names the SAME competitions differently from
# Players.csv ("Scottish Premiership (Scotland)" vs "SPL"). Left as-is, one
# league would exist under two labels -- the same "single entity" bug the
# club-name normalization fixed for clubs. The canonical side is always the
# label ALREADY in the Club table, so no existing row changes.
#
# Every alias below was confirmed against data, not assumed: for each
# 2025-2026 label, the existing label sharing the most clubs was checked
# (e.g. "2. Bundesliga (Germany)" -> "Bundesliga 2": 18 of 18 clubs shared;
# "Scottish Premiership (Scotland)" -> "SPL": 12 of 12). The one non-obvious
# case, "Belgian Pro League (Belgium)", overlaps the old "Challenger Pro
# League" label by club count only because of the known league-contamination
# in old Player.league values; the old data has 355 + 289 rows labelled
# "Pro League (Belgium)" for those same clubs in the two most recent seasons,
# and the 2025-2026 file's own `Original League` column says
# "Pro League (Belgium)".
#
# "Primera Divisio´n" / "Segunda Divisio´n" carry a stray U+00B4 acute
# accent (mojibake in the source file) -- normalized here so a NEW league
# doesn't get a corrupt display label.
LEAGUE_ALIASES: dict[str, str] = {
    "2. Bundesliga (Germany)": "Bundesliga 2",
    "Austrian Bundesliga (Austria)": "Bundesliga (Austria)",
    "Belgian Pro League (Belgium)": "Pro League (Belgium)",
    "Brazil Serie A (Brazil)": "Serie A (Brazil)",
    "Challenger Pro League (Belgium)": "Challenger Pro League",
    "Danish Superliga (Denmark)": "Superliga (Denmark)",
    "EFL Championship (England)": "EFL Championship",
    "EFL League One (England)": "EFL League One",
    "Eerste Divisie (Netherlands)": "Eerste Divisie",
    "Eliteserien (Norway)": "Eliteserien",
    "MLS (USA/Canada)": "MLS (USA)",
    "Scottish Premiership (Scotland)": "SPL",
    "Segunda Divisio´n (Spain)": "La Liga 2",
    "Serie B (Italy)": "Serie B",
    "Turkish Super Lig (Turkey)": "Super Lig (Turkey)",
    # Not an alias of an existing league -- a corrupt-accent fix for a NEW one.
    "Primera Divisio´n (Uruguay)": "Primera Division (Uruguay)",
}


def normalize_league_name(raw: str) -> str:
    """Strip whitespace, then map a known alias onto the canonical label."""
    name = raw.strip()
    return LEAGUE_ALIASES.get(name, name)
