"""Single source of truth for normalizing a raw club-name string before it's
used as a Club identity key or looked up against one (A3 fix).

Every import command that resolves a club by name (import_clubs_playstyles,
import_players, import_transfers) MUST run the raw CSV value through this
function first -- never compare/lookup a raw, un-normalized name. Skipping
this anywhere reintroduces the exact bug this fixes: a whitespace/encoding
variant of a real club silently becoming (or failing to match) a second
identity.

Two normalizations, both confirmed necessary against real data 2026-09-09:

1. `.strip()` -- whitespace-padded names (e.g. "LASK ", " Esenler Erokspor")
   were creating real duplicate Club rows.
2. `CLUB_NAME_ALIASES` -- an explicit, hand-verified, SMALL alias map for
   names that differ by more than whitespace but are confirmed the same
   real club. Currently one entry: Playstyles.csv AND
   "transferdata final.csv" both spell Borussia Mönchengladbach as
   "Borussia M_gladbach" (encoding artifact, underscore standing in for the
   apostrophe/umlaut), while Players.csv spells it "Borussia M'gladbach".
   Deliberately NOT a broad fuzzy-matching pass -- false-positive merges
   (e.g. a reserve/B team merged into its first team) are worse than
   leaving an unconfirmed variant alone. Add a new entry here ONLY after
   confirming it's the same real club, never as a guess.
"""

from __future__ import annotations

CLUB_NAME_ALIASES: dict[str, str] = {
    "Borussia M_gladbach": "Borussia M'gladbach",
}


def normalize_club_name(raw: str) -> str:
    name = raw.strip()
    return CLUB_NAME_ALIASES.get(name, name)
