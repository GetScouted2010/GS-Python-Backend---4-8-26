# Phase 12: Bidirectional Matching - Replacements & Player-Club Fit - Research

**Researched:** 2026-07-26
**Domain:** Internal scoring-service composition (Django + pandas), no new external library
**Confidence:** HIGH (all claims below verified by reading the actual current source, not from training-data assumptions)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **"AI-suggested" (PLAN-02's wording) means algorithmically ranked, not an LLM call.** Replacement-player suggestions are computed entirely via existing deterministic scoring (RMM/CS/TFM) — no `ReportGenerator`, no Anthropic call, no narrative text.
- **The two ranking directions have genuinely asymmetric computational cost.** Both share one underlying scoring primitive invoked through a single service module, but NOT via the same call pattern:
  - **Replacements for a weak position** (`PLAN-02`, many-players × one-club): reuses `scoring/services/population.py::score_population(pop, club_name)` directly — the "arbitrary-other-club" live path Phase 6 deferred to this phase. Scores the whole ~41,708-player population against one target club, filters to the weak position, ranks by RMM/CS/TFM — accepted as a multi-second live operation, bounded to top-N.
  - **Club fit for a player** (`PLAN-04`, one-player × many-clubs): does NOT call `score_population` once per candidate club (would replay the expensive full-population pass ~1,060 times). Instead slices to the target player's row and loops a cheap per-club computation, since `compute_cs_tp_for_pairs`'s cost scales with player-row count, not club count.
  - "One shared underlying service" (success criterion 3) is satisfied at the level of the scoring math (both directions call the same `compute_cs_tp_for_pairs`/RMM primitives) — not by forcing an identical, direction-blind code path.
- **Both endpoints exclude the "already there" case and return a bounded top-N, not a full paginated list.** Replacement suggestions exclude players already on the target club's current squad. Club-fit suggestions exclude the player's own current club. Both return top-N (e.g. top 10), not a paginated browse.
- **Reuses Phase 11's Position Needs classification to identify "weak" — doesn't re-derive it.** The replacement-suggestion endpoint takes an explicit `position` parameter; the caller is expected to have already consulted `GET /api/clubs/{id}/position-needs/`. This phase does not wrap or re-implement Phase 11's classification.

### Claude's Discretion

- Exact top-N bound for both ranked lists (10 is a reasonable default).
- Exact response JSON shape (field names, whether score breakdowns are included, matching the project's "never hide the numbers" transparency pattern from Phase 10).
- Whether replacement suggestions apply any additional guard (e.g. minimum RMM threshold) beyond the position filter.
- Exact candidate-club set for Player→Club matching (all ~1,060 real clubs vs. some subset) — default to all real clubs unless research indicates a real reason to bound it further.

### Deferred Ideas (OUT OF SCOPE)

- One-click "add this suggested replacement to my Squad Plan" integration.
- Caching/precomputing replacement-player rankings per club — not built unless live cost proves unacceptable.
- Bounding the Player→Club candidate-club set below "all real clubs" as a default.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-------------------|
| PLAN-02 | User can get AI-suggested replacement players for a weak position, ranked by RMM/CS/TFM fit | `score_population(pop, club_name)` verified to return `(scored, cs_tp)` with exactly the columns needed (Position, Team, player_id, Player Impact, compatibility_score, financial_score, transfer_probability); position filtering maps directly to the DataFrame's `Position` column (== `Player.position`, the clean 10-value CRUD group); "already there" exclusion maps to `Team == club_name`; historical live-timing evidence (44.6s) gives a concrete cost expectation for the phase gate/plan's non-functional acceptance. |
| PLAN-04 | User can get a ranked list of clubs that fit a given player (Player → Club Matching), scored by CS/TFM | Verified that a literal single-row slice into `compute_cs_tp_for_pairs` (as CONTEXT.md's decision literally describes) silently breaks the Financial Score term for every candidate club — a real correctness bug, not a style choice. Research provides a corrected, verified-safe design (Pattern 2 below) that reuses the exact same low-level scoring primitives without that bug, and stays cheap (est. low seconds for ~1,060 clubs) because `calculate_subjective_role_fit_for_player_to_team` only needs `team_styles_df` (small, ~1,060 rows) + one player row — never the full population. |
</phase_requirements>

## Summary

This phase adds no new library, framework, or infrastructure — it is pure composition of scoring primitives Phases 3-6 already built and proved correct. The real work is in the *orchestration*: how to run "many players vs. one club" (PLAN-02) and "one player vs. many clubs" (PLAN-04) safely and at acceptable latency without duplicating `compute_cs_tp_for_pairs`'s scoring math.

Verifying CONTEXT.md's design against the real code surfaced two load-bearing findings CONTEXT.md's own decisions did not fully account for, both of which change how the planner should scope tasks:

1. **CONTEXT.md's literal "slice `players_df` to one player row, then call `compute_cs_tp_for_pairs` per candidate club" plan for PLAN-04 is functionally broken.** `compute_cs_tp_for_pairs` derives its Financial Score baseline (`avg_age`/`avg_mv`) from a `groupby("Team")` computed over whatever frame it's given. A one-row slice means that groupby only ever has an entry for the *player's own current club* — every other candidate club's lookup misses, and `financial_score` (and therefore `transfer_probability`) is silently `NaN` for every club except the player's own. This is exactly the kind of "confidently wrong vs. honestly NaN" bug this project has caught and fixed multiple times before (see role_fit.py's own `APPLIED_FIXES`). **Corrected design:** slice `players_df` to the target player's row PLUS the full current squad of whichever club is being evaluated for that iteration (Pattern 2 below), which makes `compute_cs_tp_for_pairs`'s internal `groupby` produce the exact same average it would over the full population, at negligible per-call cost (~30-40 rows, not 41,708).
2. **"TFM" is a loaded, previously-disambiguated term in this project, and PLAN-02/PLAN-04's "RMM/CS/TFM" wording does not obviously match what CONTEXT.md's decision actually reuses.** Everywhere else in this project (`SCORE-03`, Phase 4's ROADMAP entry, PROJECT.md's own Key Decisions table), "TFM" means the trained sklearn Financial Fit pipeline exposed via `scoring/services/financial_fit.py` (`predicted_fee`, `value_verdict`) — NOT `compute_cs_tp_for_pairs`'s internal `financial_score` column (a cheap 0-100 age/market-value-fit label average, used only as an input term to the deterministic Transfer Probability formula). CONTEXT.md's locked design reuses only the latter. PROJECT.md even has an explicit Phase 4 decision entry framing the *real* TFM's club-context override as "required for Phase 12's planned 'rank clubs by fit for this player' feature to make sense at all" — strongly suggesting the real ML-based Financial Fit was the intended "TFM" all along. This is flagged as an Open Question below with a concrete, cheap way to satisfy either reading.

Neither of these findings requires abandoning CONTEXT.md's core architecture (shared scoring primitives, asymmetric call patterns, top-N bounding) — they refine *how* the "one-player × many-clubs" direction should be implemented and flag one real ambiguity in the requirement wording for the planner/user to resolve before task-level specs are written.

**Primary recommendation:** Build one new module, `scoring/services/matching.py`, with two functions — `rank_replacement_players(club_id, position, top_n)` (thin wrapper around `score_population(pop, club_name)`, Pattern 1) and `rank_clubs_for_player(player_id, top_n)` (a new thin per-club loop reusing `role_fit.py`'s and `deterministic_scores.py`'s low-level pure functions directly plus a once-computed squad-stats table, Pattern 2) — exposed via two new thin `APIView`s under `/api/clubs/{id}/replacements/` and `/api/players/{id}/club-matches/`, following the exact permission/response conventions Phases 7-11 already established.

## Standard Stack

No new packages. This phase is 100% composition of already-installed, already-proven code:

| Component | Location | Role in this phase |
|-----------|----------|---------------------|
| pandas | already installed | All scoring DataFrames |
| Django REST Framework | already installed | Two new thin `APIView`s |
| `scoring/services/population.py` | existing | `score_population`, `reconstruct_population`, `resolve_club_name` |
| `scoring/characterization/deterministic_scores.py` | existing | `compute_cs_tp_for_pairs` and its pure helpers (`financial_score`, `classify_age_fit`, `classify_fit`, `contract_fit`, `transfer_probability`) |
| `scoring/characterization/role_fit.py` | existing | `calculate_subjective_role_fit_for_player_to_team`, `compatibility_score`, `get_player_own_best_role` |

**No installation step needed.** Do not add a new app; add `matching.py` to the existing `scoring` app's `services/` package (matches `compatibility.py`/`financial_fit.py`/`rmm.py`/`transfer_probability.py`'s one-file-per-concern convention).

## Architecture Patterns

### Verified contract: `score_population(pop, club_name)`

```python
# scoring/services/population.py (verified verbatim, current signature)
def score_population(pop: Population, club_name: str | None) -> tuple[pd.DataFrame, pd.DataFrame]:
    ...
    # Returns:
    #   scored -- pop.players_df + RMM breakdown columns (from add_player_impact):
    #             player_id, Team, Position, Main_Position, Age, Market value,
    #             Contract expires, ... , "Player Impact", "Player Impact Positive",
    #             "Player Impact Negative", "Impact Reliability", "Impact Comp - <role>"...
    #   cs_tp  -- compute_cs_tp_for_pairs' result, INDEXED BY player_id, columns:
    #             club_context, compatibility_score, financial_score, performance_score,
    #             contract_fit, role_pct, transfer_probability
```

Confirmed: `Position` (capital P, DataFrame column) == `Player.position` (the clean 10-value CRUD group: AM/CB/CM/DM/FWD/GK/LB/LW/RB/RW — verified via `reconstruct.py`'s `_IDENTIFIER_RENAME = {"position": "Position", "main_position": "Main_Position", ...}`). `Team` == the club's `name` string (via `club__name`), matching what `resolve_club_name()` returns and what `compute_cs_tp_for_pairs`'s `club_context` parameter expects. This means PLAN-02's `position` query parameter can filter `scored["Position"] == position` directly with zero translation — it is the same enum `PlayerFilter.position` already validates against.

`get_own_club_id`/`is_own_club` (also in `population.py`) are NOT relevant to either new endpoint's live path (neither direction has an "own-club fast path" — PLAN-02 is inherently an arbitrary-club query, PLAN-04 is inherently arbitrary-club-by-definition) but ARE relevant to the exclusion logic: "already there" for PLAN-02 is `Team == club_name` (player's current club matches the target), and for PLAN-04 is `club_name == player's own Team`.

### Pattern 1 — PLAN-02 (replacements for a weak position): direct reuse, no new scoring logic

```python
# scoring/services/matching.py (new)
from scoring.services.population import reconstruct_population, resolve_club_name, score_population

def rank_replacement_players(club_id, position: str, top_n: int = 10) -> dict:
    club_name = resolve_club_name(club_id)  # Http404 on unknown club
    pop = reconstruct_population()
    scored, cs_tp = score_population(pop, club_name)  # ~40-50s live (see Performance below)

    scored = scored.copy()
    scored["_pid_str"] = scored["player_id"].astype(str)
    candidates = scored[
        (scored["Position"] == position) &          # weak-position filter (caller already knows it's weak, Phase 11)
        (scored["Team"] != club_name)                # exclude "already there"
    ]
    if candidates.empty:
        return {"club": club_name, "position": position, "results": []}

    cs_tp_str = cs_tp.set_axis(cs_tp.index.astype(str))
    ranked = candidates.merge(
        cs_tp_str.reset_index().rename(columns={"index": "_pid_str", "player_id": "_pid_str"}),
        on="_pid_str", how="left",
    )
    ranked = ranked.sort_values(
        ["Player Impact", "compatibility_score", "financial_score"],  # RMM/CS/TFM fit, see Open Questions re: "TFM"
        ascending=False, na_position="last",
    ).head(top_n)
    return {"club": club_name, "position": position, "results": ranked.to_dict("records")}
```

This is a literal reuse of `score_population` — no new scoring math, satisfying success criterion 3 trivially for this direction.

### Pattern 2 — PLAN-04 (clubs that fit a player): corrected thin per-club loop, NOT a literal single-row `compute_cs_tp_for_pairs` slice

**Why not the literal slice CONTEXT.md describes:** verified against `deterministic_scores.py:358-362` —

```python
squad_stats = (
    merged.groupby("Team")[["Age", "Market value"]].mean().rename(...)
)
...
avg_age = squad["_squad_avg_age"].iloc[0] if target_team in squad_stats.index else np.nan
```

If `merged` is sliced to just the one target player's row, `squad_stats.index` contains only that player's *own* current club. For every OTHER candidate club (the entire point of PLAN-04), `target_team not in squad_stats.index` → `avg_age`/`avg_mv` are `NaN` → `financial_score` is `NaN` for every non-own-club candidate, every time. This would make Player→Club matching silently return a `financial_score`/`transfer_probability` of `NaN` for literally every real candidate — the opposite of a working feature.

**Corrected design — reuse the pure primitives directly, not the monolithic `compute_cs_tp_for_pairs`:**

Everything in `compute_cs_tp_for_pairs`'s per-row loop that is genuinely **club-independent** (computed once, reused for all clubs): `player_impact` (RMM, already club-independent per Phase 6), `performance_score` (only takes `player_impact` as an argument in this codebase — the percentile terms are always `NaN`/unwired per `deterministic_scores.py`'s module docstring), `own_best_role`/`role_pct` (from the player's own role scores), `contract_fit` (from the player's own `Contract expires`, no club involved). Only two things vary per candidate club: `calculate_subjective_role_fit_for_player_to_team(player_row, club_name, team_styles_df)` (role fit / compatibility) and the `avg_age`/`avg_mv` squad-stats lookup (financial score baseline).

```python
# scoring/services/matching.py (new)
from scoring.characterization.deterministic_scores import (
    classify_age_fit, classify_fit, financial_score, contract_fit,
    transfer_probability, _years_left_from_contract_expires,
)
from scoring.characterization.role_fit import (
    calculate_subjective_role_fit_for_player_to_team, compatibility_score,
    get_player_own_best_role, normalise_position,
)
from scoring.services.population import get_scored_population, reconstruct_population

def rank_clubs_for_player(player_id, top_n: int = 10) -> dict:
    pop = reconstruct_population()
    scored, _ = get_scored_population()  # memoized own-club RMM pass -- O(1) warm

    players_with_roles = pop.players_df.merge(
        pop.role_scores_wide, on="player_id", how="left", suffixes=("", "_role")
    )
    players_with_roles["_pid_str"] = players_with_roles["player_id"].astype(str)
    match = players_with_roles[players_with_roles["_pid_str"] == str(player_id)]
    if match.empty:
        raise Http404(f"Player {player_id} not found")
    player_row = match.iloc[0]
    own_club_name = player_row.get("Team")

    scored_str = scored.copy()
    scored_str["_pid_str"] = scored_str["player_id"].astype(str)
    impact_row = scored_str[scored_str["_pid_str"] == str(player_id)]
    player_impact_val = impact_row["Player Impact"].iloc[0] if not impact_row.empty else np.nan
    performance_val = performance_score(player_impact_val)  # club-independent -- computed ONCE

    position = normalise_position(player_row.get("Main_Position", player_row.get("Position", "")))
    own_best_role, own_best_score = get_player_own_best_role(player_row, position)
    role_pct = round(own_best_score, 2) if pd.notna(own_best_score) else np.nan

    years_left = _years_left_from_contract_expires(player_row.get("Contract expires"), datetime.date.today().year)
    contract_fit_val = contract_fit(years_left)  # club-independent -- computed ONCE

    # squad_stats computed ONCE over the FULL population -- correct averages for every club
    squad_stats = (
        pop.players_df.groupby("Team")[["Age", "Market value"]].mean()
        .rename(columns={"Age": "_avg_age", "Market value": "_avg_mv"})
    )

    rows = []
    for _, team_row in pop.team_styles_df.iterrows():   # ~1,060 rows -- cheap
        club_name = team_row["Team"]
        if club_name == own_club_name:
            continue  # exclude "already there"

        role_fit_info = calculate_subjective_role_fit_for_player_to_team(
            player_row, club_name, pop.team_styles_df
        )
        if pd.isna(role_fit_info.get("Role Fit Score", np.nan)):
            compat_val = np.nan
        else:
            bonus = 100.0 if (
                role_fit_info.get("Best Team Fit Role", "") == own_best_role
                and own_best_role not in (None, "")
            ) else 70.0
            compat_val = compatibility_score(role_fit_info["Role Fit Score"], np.nan, bonus)

        if club_name in squad_stats.index:
            avg_age = squad_stats.loc[club_name, "_avg_age"]
            avg_mv = squad_stats.loc[club_name, "_avg_mv"]
        else:
            avg_age, avg_mv = np.nan, np.nan

        age_fit_label = classify_age_fit(player_row.get("Age"), avg_age)
        mv_fit_label = (
            classify_fit(player_row.get("Market value"), avg_mv, avg_mv * 0.25, avg_mv * 0.5)
            if pd.notna(avg_mv) else "Unknown"
        )
        financial_val = financial_score(age_fit_label, mv_fit_label)
        tp_val = transfer_probability(compat_val, performance_val, financial_val, contract_fit_val)

        rows.append({
            "club": club_name, "compatibility_score": compat_val,
            "financial_score": financial_val, "transfer_probability": tp_val,
        })

    ranked = pd.DataFrame(rows).sort_values(
        ["compatibility_score", "financial_score"], ascending=False, na_position="last"
    ).head(top_n)
    return {"player_id": str(player_id), "results": ranked.to_dict("records")}
```

This reuses every scoring primitive `compute_cs_tp_for_pairs` itself uses (no re-derived formulas — satisfies success criterion 3 at the math level) while being both **correct** (squad_stats computed once, over the correct population) and **cheap** (the per-club loop does a small vectorized DataFrame filter inside `calculate_subjective_role_fit_for_player_to_team`, ~1,060 times, plus trivial scalar arithmetic — no full-population iterrows repeated per club).

**Simpler, safer, but slower fallback (if the planner prefers minimal new code over the thin-wrapper above):** slice `players_df` to `[target player row] + [rows where Team == candidate_club_name]` (the candidate club's real current squad, not just the target player) before calling `compute_cs_tp_for_pairs` unmodified — this makes its internal `groupby("Team")` produce the exact same club average it would over the full population, since every row for that club is present. Cost per call is `O(squad size)` (~30-40 rows on this dataset), not `O(1)`, so total cost across ~1,060 clubs is higher than Pattern 2 but still far cheaper than 1,060 full-population passes, and the code is a much smaller diff (no need to import 6 individual pure helpers). Either approach is correctness-safe; Pattern 2 is faster and is the recommended default.

### Recommended file/URL layout (matches Phases 7-11 exactly)

```
scoring/services/matching.py       # rank_replacement_players, rank_clubs_for_player
clubs/views.py                     # + ReplacementsView (APIView) — verified pattern: PositionNeedsView/ClubInsightsView
clubs/urls.py                      # + path("<uuid:pk>/replacements/", ...) ABOVE the "<uuid:pk>/" catch-all
players/views.py                   # + ClubMatchesView (APIView) — verified pattern: PlayerScoutingReportView
players/urls.py                    # + path("<uuid:pk>/club-matches/", ...) ABOVE the "<uuid:pk>/" catch-all
```

Verified URL-ordering convention (both `clubs/urls.py` and `players/urls.py`): every specific sub-resource path (`export/`, `insights/`, `position-needs/`, `scouting-report/`) is registered BEFORE the generic `<uuid:pk>/` detail route. The new routes must follow this same ordering or Django will never reach them.

Verified view convention: no explicit `permission_classes` needed — the project's global `DEFAULT_PERMISSION_CLASSES = [IsAuthenticated]` already denies anonymous (matching `PositionNeedsView`, `ClubExportView`, `ClubInsightsView` — none of which set `permission_classes` either, since this data isn't user-owned, unlike Watchlist/Shortlist/SquadPlan's `IsOwner`). Use `GET` (not `POST`) for both new endpoints — like `PositionNeedsView`, these are deterministic reads with no LLM/503 path, matching the "GET for deterministic scores, POST only for LLM generation" convention already established (`ClubInsightsView`/`PlayerScoutingReportView` are POST only because they call an LLM).

### Response shape convention ("never hide the numbers")

Every existing score service (`get_compatibility`, `get_financial_fit`, `get_rmm`) returns the final score PLUS a `components`/breakdown dict, never just a bare number (SCORE-05, reaffirmed by Phase 10's grounding pattern). The new ranking endpoints should follow suit: each ranked entry should expose its RMM/CS/(financial_score or TFM)/transfer_probability components, not just a single combined "fit score" — consistent with this project's repeated "transparency, not a black-box ranking" pattern. `null_with_reason` (`scoring/exceptions.py`) should be used for genuinely unresolvable per-candidate values (e.g. a club with no playing-style data → `compatibility_score: null`), not silently dropped from the ranked list — dropping would make weak-scoring but present-and-real candidates indistinguishable from "we don't know."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| RMM (player impact) score | A new club-agnostic scoring pass | `add_player_impact`/`Player.impact_score` (already denormalized) | Club-independent by design; Phase 6 already made this O(1) |
| Role-fit / Compatibility Score math | A simplified "similarity" heuristic between player and club | `calculate_subjective_role_fit_for_player_to_team` + `compatibility_score` (`role_fit.py`) | The exact ROLE_STYLE_WEIGHTS-driven overlap-score math is the proven, oracle-verified formula; re-deriving it risks silently disagreeing with every other score endpoint (the exact bug class `compatibility.py`'s docstring warns about) |
| Financial fit baseline (age/MV vs. squad) | A per-request `Player.objects.filter(club=...).aggregate(Avg(...))` ORM query per candidate club | The vectorized `groupby("Team")` squad_stats table (computed once) | An ORM aggregate per candidate club is 1,060 round trips to Postgres; the in-memory pandas groupby is one query, computed once, then O(1) lookups |
| Position-needs "weak" classification | Any re-derivation of weak/at-risk/strong | `clubs/services.py::classify_position_needs` (Phase 11, consumed not re-derived) | Locked by CONTEXT.md; PLAN-02 takes an explicit `position` param instead |

**Key insight:** every piece of scoring math this phase needs already exists and is oracle-verified (Phase 5). The only genuinely new code is the *orchestration loop* (which rows to iterate, in which direction, with which exclusions) — never a new formula.

## Common Pitfalls

### Pitfall 1: Slicing `players_df` to one row before calling `compute_cs_tp_for_pairs` silently breaks Financial Score
**What goes wrong:** every candidate club except the player's own current club gets `financial_score = NaN` (and therefore `transfer_probability = NaN`), because `compute_cs_tp_for_pairs`'s internal `squad_stats` groupby only sees whatever rows you passed in.
**Why it happens:** the function was designed for "many players vs. one club" (where the full population naturally contains every club's real squad), not "one player vs. many clubs."
**How to avoid:** use Pattern 2 (precompute `squad_stats` once over the full population, reuse per club) or the squad-inclusive-slice fallback described above — never a bare single-row slice.
**Warning signs:** if a quick manual test shows `financial_score`/`transfer_probability` is `NaN` for every candidate club except the player's current one, this bug has reappeared.

### Pitfall 2: Conflating `compute_cs_tp_for_pairs`'s `financial_score` column with "TFM" (Financial Fit)
**What goes wrong:** silently using the cheap 0-100 age/MV-fit label average as "the TFM score" in the API response, when every other part of this project (SCORE-03, Phase 4, PROJECT.md's Key Decisions) uses "TFM" to mean the trained ML Financial Fit pipeline's `predicted_fee`/`value_verdict`.
**Why it happens:** both are literally named "financial" in code, and CONTEXT.md's decision text conflates them without flagging it (see Open Questions).
**How to avoid:** the planner must make an explicit, documented choice (see Open Questions) — and if the real TFM predicted-fee is wanted, only call `get_financial_fit`/`financial_fit_from_population` for the already-ranked top-N (not all 1,060 candidates or all replacement candidates), to keep cost bounded.
**Warning signs:** a reviewer asking "why does 'TFM' in this response not match the `predicted_fee` shown on `/api/scoring/financial-fit/`?"

### Pitfall 3: Forgetting the URL route-ordering convention
**What goes wrong:** a new `<uuid:pk>/replacements/` or `<uuid:pk>/club-matches/` route registered AFTER the generic `<uuid:pk>/` detail route never matches — Django resolves the catch-all first and 404s (or worse, misroutes) the sub-resource path.
**Why it happens:** Django's `path()` list is matched top-to-bottom; this project's own `urls.py` files already had to get this right for `export/`, `insights/`, `position-needs/`, `scouting-report/`.
**How to avoid:** insert new specific paths above the `<uuid:pk>/` line, mirroring the existing files exactly.

### Pitfall 4: Treating `score_population(pop, club_name)`'s cost as negligible
**What goes wrong:** underestimating PLAN-02's real latency (~40-50s on this dataset, see Performance below) and either timing out a synchronous request or writing a test with an unrealistically tight ceiling.
**Why it happens:** every OTHER score endpoint in this project is now sub-second (Phase 6's own-club caching) — it's easy to forget the "arbitrary other club" path was explicitly and intentionally left live/uncached, deferred to this exact phase.
**How to avoid:** budget for a multi-second-to-under-a-minute response in both the plan's non-functional expectations and the phase's test timeouts; do not add caching preemptively unless a live benchmark during Wave 0 shows it's genuinely unacceptable (CONTEXT.md's Deferred Ideas already anticipates and defers this).

### Pitfall 5: `players_df.merge(role_scores_wide, ...)` fan-out
**What goes wrong:** if `role_scores_wide` ever has more than one row per `player_id` (it shouldn't, per `build_role_scores_wide`'s `pivot_table(index="player_id", ...)`), a merge silently duplicates rows.
**Why it happens:** not currently a real risk (verified `build_role_scores_wide` pivots to exactly one row per player_id), but any future change to that pivot would silently break every merge pattern this phase (and `get_compatibility`) depends on.
**How to avoid:** no new code needed here — just don't "simplify" the merge pattern away from what `get_compatibility`/`compute_cs_tp_for_pairs` already do.

## Code Examples

### Excluding "already there" (verified field names)
```python
# PLAN-02: exclude players already on the target club
candidates = scored[scored["Team"] != club_name]

# PLAN-04: exclude the player's own current club
for _, team_row in pop.team_styles_df.iterrows():
    if team_row["Team"] == own_club_name:
        continue
```

### Position filter (verified: DataFrame `Position` == `Player.position`)
```python
# scoring/characterization/reconstruct.py's rename map (verified):
#   _IDENTIFIER_RENAME = {"position": "Position", "main_position": "Main_Position", ...}
candidates = scored[scored["Position"] == position]  # position e.g. "CB", matches PlayerFilter's enum exactly
```

### Existing null-envelope convention (reuse, don't invent a new shape)
```python
# scoring/exceptions.py (verified, already used identically by all 4 score services)
from scoring.exceptions import null_with_reason
null_with_reason("compatibility_score", "club_style_data_unavailable")
# -> {"compatibility_score": None, "reason": "club_style_data_unavailable"}
```

## State of the Art

| Old Approach (pre-Phase-12) | Current/Planned Approach | When Changed | Impact |
|-------------------------------|---------------------------|---------------|--------|
| Arbitrary-other-club scoring is live/uncached (Phase 6 explicitly deferred it) | Stays live/uncached for both new directions — no new caching infra | Phase 12 (this phase) | Matches the project's consistent "no caching without a forcing reason" pattern; both endpoints are non-hot-path "suggestions" surfaces |
| Every other score endpoint's "other club" path exists only for a single player/club pair (`get_compatibility`, `get_financial_fit`, `get_transfer_probability`) | This phase is the first to rank an entire population/club-set by that same "other club" computation | Phase 12 | This is genuinely new orchestration, not a new formula — the risk surface is entirely in the loop/exclusion/top-N logic, not the scoring math |

**No formulas are deprecated or replaced by this phase.** This is purely an additive composition phase.

## Open Questions

1. **Does "TFM" in PLAN-02 ("RMM/CS/TFM fit") and PLAN-04 ("scored by CS/TFM") mean the real ML Financial Fit pipeline (`get_financial_fit`/`predicted_fee`) or `compute_cs_tp_for_pairs`'s internal `financial_score` field?**
   - What we know: everywhere else in this project (REQUIREMENTS.md's SCORE-03, ROADMAP's Phase 4 entry, PROJECT.md's Key Decisions table — including an entry explicitly framing the real TFM's club-context override as required "for Phase 12's planned 'rank clubs by fit for this player' feature to make sense at all") "TFM" means the trained sklearn pipeline's money-scale `predicted_fee`. CONTEXT.md's locked design for this phase only reuses `compute_cs_tp_for_pairs`'s differently-named `financial_score` (a cheap 0-100 label average, not the ML pipeline).
   - What's unclear: whether CONTEXT.md's author treated "financial_score" and "TFM/Financial Fit" as interchangeable by oversight, or made a deliberate (unstated) simplification given the ML pipeline's extra cost.
   - Recommendation: if the real TFM is wanted (matching the project's established terminology and the PROJECT.md decision entry), don't call it for every candidate — rank cheaply first using `compute_cs_tp_for_pairs`'s RMM/CS/financial_score (as Patterns 1-2 already do), narrow to top-N, THEN call `get_financial_fit`/`financial_fit_from_population` only for those top-N results to attach a real `predicted_fee`/`value_verdict`. `build_oracle_player_features` (verified: fully vectorized, no per-row Python loop) makes this affordable for a bounded top-N even though it processes the whole population's club-aggregate profiles per call — 10 calls is cheap, 1,060 or 41,708 calls would not be. This needs an explicit decision recorded before task-level plans are written, since it changes both endpoints' response shape and latency.

2. **What should the actual ranking/sort key be for each direction, precisely?**
   - What we know: success criteria say "ordered by RMM/CS/TFM fit" (PLAN-02) and "scored by CS/TFM" (PLAN-04) — plural criteria, no combination formula specified anywhere in ROADMAP/REQUIREMENTS.
   - What's unclear: whether to sort by a single composite score (and if so, what weights) or by a tuple/priority order (e.g. RMM first, CS as tiebreaker), and whether `transfer_probability` (which already blends CS/perf/financial/contract via the existing deterministic formula) is a more natural single ranking key than inventing a new weighted blend.
   - Recommendation: default to sorting by `transfer_probability` (already the project's existing "how good a fit, blended" deterministic number, per `deterministic_scores.py`) as the primary key, exposing RMM/CS/financial_score as visible secondary/breakdown fields — avoids inventing a new, unproven weighting formula. This is a "Claude's Discretion" item per CONTEXT.md; document whichever choice is made in the plan.

3. **Pattern 2's real-world latency is estimated, not benchmarked.**
   - What we know: `calculate_subjective_role_fit_for_player_to_team` only touches `team_styles_df` (~1,060 rows) and one player row per call — no full-population operation — so the per-club loop should be cheap (rough estimate: low single-digit seconds for ~1,060 clubs).
   - What's unclear: no existing test or benchmark exercises this exact usage pattern (it's new orchestration, not existing code), so this estimate is unverified against the real dev DB.
   - Recommendation: the plan's Wave 0 (or an early task) should include a live `manage.py shell` timing spike against the real 41,708-player/1,060-club dataset, mirroring the project's established "live-verify against real data, don't trust estimates" pattern (every prior phase's STATE.md entries did exactly this for their own new code paths).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-django (already configured, `pyproject.toml`) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` — `testpaths` already includes `scoring`, `clubs`, `players` |
| Quick run command | `.venv/bin/pytest scoring/tests/test_services_matching.py -x` (new file) |
| Full suite command | `.venv/bin/pytest` (project-wide; ambient interpreter lacks scikit-learn — MUST use the project's own `.venv`, per every prior phase's STATE.md note) |

Both new services' tests will **skip cleanly on the empty pytest test DB** (pytest-django's own test DB has zero rows) and must instead be **live-verified against the real dev DB** via `manage.py shell`, exactly like every other `scoring/tests/test_services_*.py` file (`real_data_available` fixture pattern, verified in `scoring/tests/conftest.py`). This is not a gap to close — it is this project's established, deliberate real-data-testing convention (03-VALIDATION.md "Wave 0 Requirements", reused unchanged by every phase since).

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| PLAN-02 | Replacement ranking excludes players already on the target club | unit | `pytest scoring/tests/test_services_matching.py::test_rank_replacement_players_excludes_current_squad -x` | ❌ Wave 0 |
| PLAN-02 | Replacement ranking filters to the requested position only | unit | `pytest scoring/tests/test_services_matching.py::test_rank_replacement_players_filters_position -x` | ❌ Wave 0 |
| PLAN-02 | Replacement ranking returns top-N, not the full candidate set | unit | `pytest scoring/tests/test_services_matching.py::test_rank_replacement_players_bounds_top_n -x` | ❌ Wave 0 |
| PLAN-02 | `GET /api/clubs/{id}/replacements/?position=CB` returns 200 + ranked list against real data | integration | `pytest clubs/tests/test_replacements_view.py -x` | ❌ Wave 0 |
| PLAN-02 | Unknown club_id → clean 404 | integration | `pytest clubs/tests/test_replacements_view.py::test_unknown_club_404 -x` | ❌ Wave 0 |
| PLAN-04 | Club-fit ranking excludes the player's own current club | unit | `pytest scoring/tests/test_services_matching.py::test_rank_clubs_for_player_excludes_own_club -x` | ❌ Wave 0 |
| PLAN-04 | Club-fit ranking does NOT silently NaN financial_score for non-own clubs (regression guard for the squad_stats bug found in this research) | unit | `pytest scoring/tests/test_services_matching.py::test_rank_clubs_for_player_financial_score_not_systematically_null -x` | ❌ Wave 0 |
| PLAN-04 | Club-fit ranking returns top-N, not all ~1,060 clubs | unit | `pytest scoring/tests/test_services_matching.py::test_rank_clubs_for_player_bounds_top_n -x` | ❌ Wave 0 |
| PLAN-04 | `GET /api/players/{id}/club-matches/` returns 200 + ranked list against real data | integration | `pytest players/tests/test_club_matches_view.py -x` | ❌ Wave 0 |
| PLAN-04 | Unknown player_id → clean 404 | integration | `pytest players/tests/test_club_matches_view.py::test_unknown_player_404 -x` | ❌ Wave 0 |
| Both (success criterion 3) | Both directions call into the same low-level scoring primitives (no duplicated formula) | unit (structural) | a test asserting `matching.py` imports `compatibility_score`/`financial_score`/`transfer_probability` from `role_fit.py`/`deterministic_scores.py` rather than reimplementing them (grep-style or mock-call-count assertion, mirroring `test_services_summary.py`'s existing `call_count==1` pattern) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** run the new `scoring/tests/test_services_matching.py` file only (`pytest scoring/tests/test_services_matching.py -x`).
- **Per wave merge:** run `scoring/`, `clubs/`, `players/` test dirs together (`pytest scoring clubs players`).
- **Phase gate:** full suite green (`.venv/bin/pytest`) before `/gsd:verify-work`, PLUS a live `manage.py shell` timing/correctness spike against the real 41,708-player/1,060-club dev DB for both new endpoints (mirrors every prior phase's STATE.md entries — pytest's own test DB is always empty, so real-data correctness/perf claims are always verified live, not just via pytest).

### Wave 0 Gaps
- [ ] `scoring/tests/test_services_matching.py` — new file, covers PLAN-02/PLAN-04 unit-level ranking/exclusion/top-N behavior against real data (`real_data_available` fixture, matching every existing `scoring/tests/test_services_*.py`).
- [ ] `clubs/tests/test_replacements_view.py` — new file, integration test for `GET /api/clubs/{id}/replacements/`.
- [ ] `players/tests/test_club_matches_view.py` — new file, integration test for `GET /api/players/{id}/club-matches/`.
- [ ] No new fixtures/conftest needed — `real_data_available` already exists in both `scoring/tests/conftest.py` and `clubs/tests/conftest.py`; `players/tests/conftest.py` should be checked for an equivalent (if absent, add one mirroring the existing two, a one-line addition).
- [ ] Framework install: none — pytest/pytest-django already configured project-wide.

## Performance Notes (verified against real historical benchmarks, not estimated)

These are the ONLY directly-relevant real numbers on this exact dataset (41,708 players / 1,060 clubs) found in the project's own history (STATE.md, phase 06-05/06-07 gap-closure entries, live-verified via `manage.py shell` against the real dev DB, not synthetic):

| Call | Measured latency | Source |
|------|-------------------|--------|
| `score_population(pop, arbitrary_club_name)` (full population, one club — exactly PLAN-02's core call) | ~44.6s | STATE.md Phase 06-05 gap-closure: "arbitrary-other-club fallback confirmed still functional (44.6s, correctly returned null envelope)" |
| `get_scored_population()` cold build (full population, club_context=None — RMM+CS/TP combined) | 92.04s | STATE.md Phase 06 test_scoring_performance.py entry |
| `get_scored_population()` warm (memoized) | ~0.0000s (in-process cache hit) | same |
| `build_oracle_player_features` (TFM feature build) | not separately benchmarked, but verified via source reading to be fully vectorized pandas (`groupby`/`agg`/`merge`, zero `iterrows`/`apply`-per-row) — expected sub-second-to-low-seconds on the full population, much cheaper than `compute_cs_tp_for_pairs`'s Python-level `iterrows` loop | direct code reading, `scoring/characterization/tfm_model.py` |

**Conclusion for PLAN-02:** expect each `GET /api/clubs/{id}/replacements/` request to take roughly 40-50 seconds on the real dataset — a genuine live, non-cached, multi-second-to-under-a-minute operation, exactly as CONTEXT.md anticipated and explicitly accepted. Do not build caching preemptively (per CONTEXT.md's Deferred Ideas); do budget realistic test timeouts and, if this ships to a real HTTP client, consider documenting the expected latency in the endpoint's own docstring so it isn't mistaken for a bug later (matches this project's own pattern of documenting known-slow-but-accepted paths, e.g. `get_financial_fit`'s and `get_compatibility`'s own-club-vs-other-club docstrings).

**Conclusion for PLAN-04:** Pattern 2's per-club loop cost is NOT covered by any existing benchmark (it's new orchestration) — budget a live timing spike during planning/Wave 0 rather than assuming either the optimistic (~seconds) or pessimistic (~a minute, if `iterrows` overhead on `team_styles_df` turns out higher than expected) estimate.

## Sources

### Primary (HIGH confidence — direct source reading, current code)
- `get-scouted-be/scoring/services/population.py` — `score_population`, `reconstruct_population`, `get_scored_population`, `resolve_club_name`, `get_own_club_id`, `is_own_club` signatures and docstrings read in full.
- `get-scouted-be/scoring/characterization/deterministic_scores.py` — `compute_cs_tp_for_pairs` full implementation read line-by-line, including the `squad_stats` groupby that motivates Pattern 2's correction.
- `get-scouted-be/scoring/characterization/role_fit.py` — `calculate_subjective_role_fit_for_player_to_team`, `compatibility_score`, `get_player_own_best_role`, `ROLE_COLUMNS_BY_POSITION`/`ROLE_STYLE_WEIGHTS` read in full; confirmed no full-population dependency.
- `get-scouted-be/scoring/characterization/tfm_model.py` — `build_oracle_player_features` read in full; confirmed fully vectorized (no `iterrows`/row-wise `.apply`).
- `get-scouted-be/scoring/services/compatibility.py`, `financial_fit.py`, `rmm.py` — existing single-pair service response-shape conventions, own-club/other-club branching pattern.
- `get-scouted-be/scoring/characterization/reconstruct.py` — `build_players_df`/`build_team_styles_df`/`build_role_scores_wide`, confirming `Position`==`Player.position`, `Team`==`Club.name`.
- `get-scouted-be/clubs/services.py`, `clubs/views.py`, `clubs/urls.py`, `players/views.py`, `players/urls.py`, `players/filters.py`, `players/serializers.py`, `clubs/serializers.py` — URL ordering, permission-class, response-shape, and serializer-reuse conventions from Phases 7-11.
- `get-scouted-be/workspace/services.py` — bulk-fetch/in-memory-simulation exclusion pattern (`simulate_squad_change`).
- `get-scouted-be/scoring/tests/test_live_scoring_performance.py`, `test_services_compatibility.py`, `conftest.py` — real-data test conventions, `real_data_available` fixture.
- `.planning/STATE.md` — historical live-verified performance numbers (44.6s, 92.04s) cited directly, not re-derived.
- `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` — "TFM" terminology cross-check that surfaced Open Question 1.

### Secondary / Tertiary
None used — this phase required no external library research; all authoritative sources were the project's own already-verified code and planning history.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependency, pure internal reuse, every function signature read directly.
- Architecture (Pattern 1): HIGH — literal existing function reuse, already exercised by other services for the "arbitrary club" case.
- Architecture (Pattern 2): MEDIUM-HIGH — the correctness fix (squad_stats bug) is verified by direct code reading; the exact latency of the new per-club loop is an informed estimate, not a live-verified number (flagged in Open Questions/Performance Notes).
- Pitfalls: HIGH — Pitfall 1 (squad_stats bug) and Pitfall 2 (TFM terminology conflict) are both direct, reproducible findings from reading the real code and the project's own planning documents, not speculation.

**Research date:** 2026-07-26
**Valid until:** No external dependency to go stale; valid until the underlying scoring code (`deterministic_scores.py`, `role_fit.py`, `population.py`) changes. Re-verify if any of those files are touched by a future phase (none currently planned — this is the final v1 phase).

---
*Phase: 12-bidirectional-matching-replacements-player-club-fit*
*Research completed: 2026-07-26*
