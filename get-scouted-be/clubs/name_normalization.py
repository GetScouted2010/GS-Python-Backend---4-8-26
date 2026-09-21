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
   real club. Two sources so far:

   - Playstyles.csv AND "transferdata final.csv" both spell Borussia
     Mönchengladbach as "Borussia M_gladbach" (encoding artifact,
     underscore standing in for the apostrophe/umlaut), while Players.csv
     spells it "Borussia M'gladbach".
   - The 2025-2026 Wyscout pull (players/wyscout_season.py) spells 8 clubs
     without diacritics ("Besiktas", "Lech Poznan", ...). Each was confirmed
     by matching against the real Club table with an accent-folding key. The
     canonical side is always the spelling ALREADY in the Club table, so
     nothing existing is renamed.

   Deliberately NOT a broad fuzzy-matching pass -- false-positive merges
   (e.g. a reserve/B team merged into its first team) are worse than
   leaving an unconfirmed variant alone. The 2025-2026 scan surfaced
   several such traps that must stay separate: "Gent II" vs "Gent"/"Genk
   II", "Real Sociedad B" vs "Real Sociedad", "Boulogne" vs "Bologna",
   "Juventud" vs "Juventude". Add a new entry here ONLY after confirming
   it's the same real club, never as a guess.
"""

from __future__ import annotations

CLUB_NAME_ALIASES: dict[str, str] = {
    "Borussia M_gladbach": "Borussia M'gladbach",
    # 2025-2026 Wyscout pull -> spelling already present in the Club table.
    "Besiktas": "Beşiktaş",
    "Istanbul Basaksehir": "İstanbul Başakşehir",
    "Jagiellonia Bialystok": "Jagiellonia Białystok",
    "Kasimpasa": "Kasımpaşa",
    "Lech Poznan": "Lech Poznań",
    "Raków Czestochowa": "Raków Częstochowa",
    "Sønderjyske": "SønderjyskE",
    "Zaglebie Lubin": "Zagłębie Lubin",
}


def normalize_club_name(raw: str) -> str:
    name = raw.strip()
    return CLUB_NAME_ALIASES.get(name, name)


# A NAME alone is not always enough to identify a club: in the 2025-2026 pull
# "Athletic Club" is BOTH Athletic Bilbao (La Liga, 24 rows) AND an unrelated
# Brazilian Serie B club (21 rows). Aliasing it by name would have silently
# merged the two, so this alias is keyed on (name, league) instead. Consulted
# only for names that appear under more than one league in a season file
# (players/wyscout_season.py::resolve_club_identities); the league is the
# already-normalized canonical label.
CLUB_NAME_LEAGUE_ALIASES: dict[tuple[str, str], str] = {
    ("Athletic Club", "La Liga (Spain)"): "Athletic Bilbao",
}
