---
gsd_state_version: 1.0
milestone: v4.1
milestone_name: milestone
status: unknown
stopped_at: Completed 09-04-PLAN.md
last_updated: "2026-07-25T10:26:39.076Z"
progress:
  total_phases: 12
  completed_phases: 9
  total_plans: 49
  completed_plans: 49
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-20)

**Core value:** The backend must serve accurate, real scouting data and real (not approximated) Impact RMM scoring — the product's credibility rests on the scores being right, not just on the API being reachable.
**Current focus:** Phase 09 — ai-provider-interface-natural-language-search

## Current Position

Phase: 09 (ai-provider-interface-natural-language-search) — Phase complete — ready for verification
Plan: 4 of 4 (09-04 complete: POST /api/players/search/ wires the 3-tier degradation (LLM parser -> deterministic keyword fallback -> unfiltered list), always HTTP 200, with fallback_used honestly reporting which tier served the request and exactly one RecentActivity(activity_type="searched") logged per call, completing the Phase 8-reserved producer contract; full suite 174 passed/315 skipped/0 failed, all 7 Phase 9 AI test files collected)

## Performance Metrics

**Velocity:**

- Total plans completed: 5
- Average duration: 17.6 min
- Total execution time: 1.43 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| Phase 01 P01 | 25min | 2 tasks | 24 files |

**Recent Trend:**

- Last 5 plans: 25min, 20min, 18min
- Trend: stable

*Updated after each plan completion*
| Phase 01-data-foundation P03 | 10min | 2 tasks | 6 files |
| Phase 01 P04 | 12min | 2 tasks | 10 files |
| Phase 01-data-foundation P05 | 25min | 2 tasks | 6 files |
| Phase 01-data-foundation P06 | 18min | 2 tasks | 3 files |
| Phase 01-data-foundation P08 | 12min | 2 tasks | 5 files |
| Phase 01-data-foundation P07 | 35min | 2 tasks | 4 files |
| Phase 01-data-foundation P09 | 100min | 2 tasks | 6 files |
| Phase 02 P01 | 25min | 3 tasks | 12 files |
| Phase 02 P02 | 20min | 2 tasks | 8 files |
| Phase 02 P03 | 18min | 2 tasks | 5 files |
| Phase 03 P01 | 25min | 2 tasks | 10 files |
| Phase 03 P02 | 20min | 2 tasks | 2 files |
| Phase 03-scoring-engine-curation-correctness-oracle P04 | 15min | 2 tasks | 2 files |
| Phase 03-scoring-engine-curation-correctness-oracle P05 | 25min | 2 tasks | 3 files |
| Phase 03-scoring-engine-curation-correctness-oracle P03 | 18min | 2 tasks | 1 files |
| Phase 03 P07 | 35min | 2 tasks | 6 files |
| Phase 04-scoring-engine-port P01 | 18min | 2 tasks | 4 files |
| Phase 04-scoring-engine-port P04 | 30min | 2 tasks | 2 files |
| Phase 04-scoring-engine-port P02 | 24min | 2 tasks | 2 files |
| Phase 04-scoring-engine-port P06 | 16min | 2 tasks | 4 files |
| Phase 05-scoring-parity-testing P01 | 15min | 2 tasks | 3 files |
| Phase 05 P04 | 45min | 2 tasks | 1 files |
| Phase 05 P02 | 25min | 2 tasks | 1 files |
| Phase 05 P03 | 55min | 2 tasks | 1 files |
| Phase 06 P02 | 15min | 2 tasks | 2 files |
| Phase 06 P01 | 7min | 3 tasks | 4 files |
| Phase 06 P03 | 17min | 2 tasks | 2 files |
| Phase 06 P04 | 12min | 1 tasks | 1 files |
| Phase 06 P05 | 25min | 2 tasks | 6 files |
| Phase 06-scoring-performance-caching-layer P06 | 25min | 2 tasks | 4 files |
| Phase 06 P07 | 25min | 2 tasks | 3 files |
| Phase 07-core-crud-players-clubs P01 | 3min | 3 tasks | 5 files |
| Phase 07 P02 | 7min | 3 tasks | 7 files |
| Phase 07 P03 | 5min | 3 tasks | 6 files |
| Phase 08-user-workspace-crud P01 | 10min | 3 tasks | 9 files |
| Phase 08 P02 | 5min | 2 tasks | 5 files |
| Phase 08 P03 | 4min | 2 tasks | 4 files |
| Phase 08 P04 | 6min | 2 tasks | 4 files |
| Phase 08 P05 | 8min | 3 tasks | 6 files |
| Phase 08 P06 | 8min | 3 tasks | 5 files |
| Phase 09 P01 | 12min | 3 tasks | 8 files |
| Phase 09 P02 | 10min | 2 tasks | 4 files |
| Phase 09 P03 | 15min | 2 tasks | 4 files |
| Phase 09 P04 | 14min | 3 tasks | 3 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Phase 3-6 split scoring engine port into curation → port → parity testing → caching, matching the "fine" granularity target and treating the 15,700-line untested port as the project's highest-risk work needing its own verification step at each stage.
- Phase 3 (Curation) carries no directly-owned v1 requirement — it is prerequisite risk-mitigation work (snapshot oracle, de-dup map) that Phases 4-6 depend on to satisfy SCORE-01 through SCORE-07.
- [Phase 01]: Django field names mirror CSV column names verbatim (locked naming decision); Player.club FK sourced from Team_within_selected_timeframe not Team; Total_Score renamed legacy_total_score; 14 movement columns isolated into Player.extended_stats JSONField
- [Phase 01-data-foundation]: Player model's ~99 stat FloatFields keep exact CSV casing for parity traceability; identifier/profile fields use lowercase Django-conventional names per plan's explicit field list
- [Phase 01-data-foundation]: clubs_with_ambiguous_league counts any club with >1 distinct League value (matches 01-RESEARCH.md's verified 525/1059), tracked separately from genuine mode ties
- [Phase 01-data-foundation]: Added a repo-root get-scouted-be/conftest.py re-exporting fixture_dir so every app's test dir (sibling of core/tests/, not descendant) can use the shared fixture-path fixture
- [Phase 01-data-foundation]: Removed the redundant flagged_uids param from _build_player_kwargs -- report.add_field_issue is monkey-patched once in Command.handle() to track flagged rows, so per-row helpers only need a report reference
- [Phase 01-data-foundation]: Contract_expires' 18% 'missing' rate in the real Players.csv is encoded as the literal string '0', not a blank cell -- correctly flagged via the unparseable/strptime branch with identical null+flagged effect
- [Phase 01-data-foundation]: import_position_roles: switched UniqueID dtype from int64 to nullable Int64 -- 3 real Positions/*.csv files (CM/LB/RB) have blank all-NaN trailing rows that crashed a plain int64 parse; now flagged+skipped per row instead
- [Phase 01-data-foundation]: PlayerRoleScore full-scale row count is 230,139 (long format, one row per player-role), not the ~38,600 estimate in 01-RESEARCH.md/the plan's verification note -- that figure described the wide-format row sum across the 9 files, not the melted long-format total the must_haves truths require
- [Phase 01-data-foundation]: Transfer.club resolved strictly via transferdata's Club NAME column; UniqueID stored only as source_unique_id for cross-source confirmation, never joined to Player.unique_id
- [Phase 01-data-foundation]: Transfer player-name matching excludes non-unique (ambiguous) names from the match map entirely -- ambiguous treated identically to unmatched (player=None, logged), never guessed
- [Phase 01-data-foundation]: PlayerClubCompatibility's idempotent upsert conflict target is (player, club_name_raw), never (player, club) -- club is null for unresolved headers and Postgres treats multiple NULLs as non-conflicting, so club_name_raw is mandatory to avoid duplicating null-club rows on re-run
- [Phase 01-data-foundation]: Full-scale import_compatibility_scores run confirmed 8,188,712 PlayerClubCompatibility rows (9 files x ~212 club columns each), only 1 distinct unresolved club header ("St_DOT_ Louis City", not present in cs_field_mapping.json), 0 unmatched players; idempotent re-run left row count unchanged
- [Phase 01-data-foundation]: import_all reconciliation delegates Club/Transfer expected counts to each sub-command's own report section (club_derivation.distinct_clubs; transfer_import.duplicate_event_keys_collapsed) rather than recomputing independently, so the two calculations cannot drift apart
- [Phase 01-data-foundation]: import_transfers now collapses same-composite-event-key rows within a chunk before bulk_create (last occurrence wins, logged) -- real transferdata final.csv has ~51 genuinely-duplicated rows that otherwise crash Postgres's ON CONFLICT DO UPDATE with a CardinalityViolation
- [Phase 01-data-foundation]: Full real-dataset import_all phase-gate run reconciled to PASS: Club=1060, Player=41708, Transfer=47201 (47252 raw minus 51 collapsed duplicates), PlayerRoleScore=230139, PlayerClubCompatibility=8188712; Transfer.player unmatched rate is ~98% (46391/47252) by design given Player's per-season row granularity plus the never-guess-ambiguous-names policy
- [Phase 02-auth-access-control]: Fully custom accounts.User(AbstractBaseUser, PermissionsMixin) with UUID PK, email login, role field is AUTH_USER_MODEL; required a one-time dev-DB reset (dropdb/createdb + fresh migrate) since Phase 1's migrate had already applied django.contrib.auth's own migrations creating a stock auth_user table
- [Phase 02-auth-access-control]: DRF wired deny-by-default (JWTAuthentication only, IsAuthenticated only); simplejwt 5.5.1 pinned (patches CVE-2024-22513) with rotation+blacklist; full Phase 1 dataset re-imported post-reset with PASS reconciliation
- [Phase 02-auth-access-control]: /api/auth/* account lifecycle endpoints live -- register (admin excluded from self-service), login (JWT with embedded role+email claims, generic 401 on bad creds), refresh (rotate+blacklist prior token), logout (TokenBlacklistView revocation), password-reset request/confirm (Django's default_token_generator, console email, generic 200 on request regardless of email match)
- [Phase 02-auth-access-control]: AUTH_PASSWORD_VALIDATORS was missing entirely from this hand-written config/settings/base.py (not auto-seeded outside Django's startproject template) -- added the standard 4-validator list so validate_password() actually enforces password strength on registration and password-reset-confirm instead of being a silent no-op
- [Phase 02-auth-access-control]: Additive role hierarchy encoded in exactly one place -- ROLE_RANK dict + MinimumRole(role) permission-class factory in accounts/permissions.py (scout=analyst=1 < director=2 < admin=3) -- no bespoke per-role permission classes; this is the primitive Phase 7/8 will import for Watchlist/Shortlist/SquadPlan role gating
- [Phase 02-auth-access-control]: /api/auth/me/ makes self-role-escalation structurally impossible (role is a read_only_field on ProfileSerializer, not just an app-logic check); /api/auth/admin/users/ gives director read-only org-wide visibility and admin-only role-change/soft-deactivation with zero destroy route ever registered (no hard delete at the API layer)
- [Phase 02-auth-access-control]: Role/deactivation immediacy (no re-login required) verified against a real endpoint end-to-end, not just the permission class in isolation -- confirms JWTAuthentication's per-request DB refetch + DB-fresh permission reads compose correctly as researched
- [Phase 02-auth-access-control]: All 3 plans executed, full suite 47/47 passing; Phase 2 pending goal-backward verification before being marked complete
- [Phase 03-01]: scikit-learn/joblib installed, `scoring` Django app skeleton registered; `reconstruct.py` bridges real migrated Postgres data (Player/PlayerRoleScore/Club/Transfer) into the four script-literal-column-named DataFrames impact_model_v4.1.py's ported functions expect, using FIELD_MAPPING.md's reverse rename; club playing-style NaNs preserved (never zero-filled); role-score pivot logs (not fabricates) coverage gaps against ROLE_COLUMNS_BY_POSITION
- [Phase 03-02]: DUPLICATE_FUNCTIONS.md catalogues all 20 duplicate top-level names in impact_model_v4.1.py; 18 two-definition names mechanically resolved via last-wins (cross-checked against get_export_columns_for_position's byte-identical bodies; build_transfer_value_dataset and export_team_shortlist_xlsx directly confirmed to have provably-dead first definitions); pick_first_existing (required=True->False) and format_financial (value=->x=) signature drifts flagged for Phase 4 verification; prepare_team_and_transfer_signal and player_transfer_history (4 defs each) left ESCALATION PENDING for Plan 03; financial_fit_label documented as nested duplicated-logic, out of scope for last-wins
- [Phase 03-scoring-engine-curation-correctness-oracle]: [Phase 03-04]: RMM (Player Impact) characterized as a faithful verbatim port -- 8 position calculators + add_player_impact + compute_rmm_column(players_df); only fix applied was replacing the whole-column Minutes silent-default-to-0 with a ValueError guard (APPLIED_FIXES); verified against real 41,708-player population via manage.py shell: 99.998% RMM coverage, all 10 position groups covered, all values in [0.01,100.0]
- [Phase 03-scoring-engine-curation-correctness-oracle]: [Phase 03-05]: Compatibility Score's role-fit guard now returns NaN (not the source's silent zero-fill) for clubs with all-NaN playing-style vectors; Transfer Probability confirmed as the deterministic 0.30/0.20/0.20/0.30 weighted formula (not the RandomForestRegressor, which is TFM); performance_score() takes Plan 04's player_impact (RMM) as a required anchor, NaN-propagating rather than zero-filling
- [Phase 03-scoring-engine-curation-correctness-oracle]: [Phase 03-03]: Escalated duplicate-function human decision: prepare_team_and_transfer_signal authoritative version is line 12192 (3-way functional majority); player_transfer_history authoritative version is line 12329 (3-way functional majority; 11488's extra length traced to formatting/docstring, not added logic) -- both Minutes->0 silent defaults deferred to the existing fix-threshold mechanism, not re-litigated here
- [Phase 03-scoring-engine-curation-correctness-oracle]: [Phase 03-06]: TFM (Financial Fit) sklearn artifact trained and versioned -- RandomForestRegressor(n_estimators=300,max_depth=12,min_samples_leaf=3,random_state=42) faithfully reproduced, joblib-dumped to scoring/ml_artifacts/tfm_value_model_v1.joblib (gitignored, regenerable via `manage.py train_tfm_model`); management command explicitly merges Plan 04's player_impact and Plan 05's compatibility_score/performance_score/role_pct onto players_df before feature-building, closing the cross-plan wiring gap the plan-checker flagged during planning; verified against real dev data: R²=0.921, MAE=~€2.34M, 1477 usable transfer rows, all 4 cross-plan features confirmed present in the trained feature set
- [Phase 03-07]: TFM oracle predictions use the player's current club as both buying-club and selling-club aggregate context (no real transfer event exists for a non-moving player); CSV oracle snapshot is committed to the repo (not gitignored) since it is Phase 5's ground truth
- [Phase 04-scoring-engine-port]: [Phase 04-01]: score_population uses add_player_impact (full RMM breakdown) not compute_rmm_column, so downstream summary/RMM (04-06) gets Impact component columns for free; get_tfm_pipeline resolves artifact/sidecar paths via settings.BASE_DIR (matching tfm_model.py's existing convention) rather than a __file__-relative path
- [Phase 04-scoring-engine-port]: [Phase 04-04]: TFM's requested-club-context override is scoped to club-aggregate features only (club_pos_avg_in_fee, seller_hist_*, etc); the 4 upstream RMM/CS/TP features stay computed against each player's own club, matching oracle/training methodology; np.expm1 unwraps the confirmed log-scale pipeline.predict output, verified against real data (fees ~€597K-€1.29M across different requested clubs for the same player, not the log-scale [0,20] range)
- [Phase 04-scoring-engine-port]: [Phase 04-02]: rmm.py's get_rmm/rmm_breakdown_from_scored read the breakdown strictly off add_player_impact's output (never compute_rmm_column); Impact Reliability is a categorical string (Very Low/Low/Medium/High), not numeric -- passed through as-is rather than float()-coerced
- [Phase 04-scoring-engine-port]: [Phase 04-03]: get_compatibility merges pop.players_df with pop.role_scores_wide (on='player_id') BEFORE slicing player_row, replicating compute_cs_tp_for_pairs' own internal merge -- fixes a plan-checker-caught bug where role_fit_score/bonus would silently disagree with the real compatibility_score (a bare players_df row has no role-score columns, so calculate_subjective_role_fit_for_player_to_team/get_player_own_best_role would always degenerate to None/70.0); a new regression test asserts the breakdown mathematically reconstructs the score. get_transfer_probability re-exposes compute_cs_tp_for_pairs' 4 weighted terms directly (no reimplementation), contract_fit scaled *100 for display parity.
- [Phase 04-scoring-engine-port]: [Phase 04-05]: get_summary reconstructs the population exactly once (verified by a mocked call_count==1 test) and reuses Plans 02-04's breakdown helpers, replicating Plan 03's role_scores_wide merge fix for its compatibility sub-object; financial_fit's 4 upstream TFM features are computed in the summary's shared club context rather than each player's own club (an accepted, documented efficiency tradeoff vs the standalone /financial-fit/ endpoint). serializers.py defines 5 thin DictField/JSONField-based serializers (RMM/Compatibility/FinancialFit/TransferProbability/Summary) with a nullable score + optional reason on every one. Verified end-to-end against one real player/club pair: CS breakdown reconstructed its own score exactly ((87.23+70.0)/2=78.62); TP's 4 contributions summed exactly to the reported transfer_probability (87.5).
- [Phase 04-scoring-engine-port]: [Phase 04-06]: All 5 scoring endpoints wired thin under /api/scoring/ -- views call Response(service_function(...)) directly (no serializers.py class instantiated, per the plan's literal task-2 code); service calls never wrapped in try/except so Http404 (unknown player/club) and reconstruction ValueError both propagate naturally (404/500), never swallowed into a fabricated null; verified end-to-end against the real 41,708-player dev DB via manage.py shell (real RMM score, 401 unauthenticated, 404 unknown player, 400 missing club_id on /summary/)
- [Phase 05-scoring-parity-testing]: [05-01]: _parity_helpers.py centralizes oracle discovery/load, the UUID->str port-id-cast convention, and a both-null-aware tolerance comparator (both-null=pass, one-null=hard fail, abs 0.01 RMM/CS/TP, rel 0.1% TFM); compare_tfm_series reconciles the oracle's verified log-scale tfm column to money scale via np.expm1 before applying the relative tolerance -- single source of truth Plans 02-04 import from rather than each re-implementing
- [Phase 05]: [Phase 05-scoring-parity-testing]: [05-04]: 7 dynamically-mined edge-case parity tests (zero-minutes, missing market_value, missing club, youngest/oldest age boundary, age==0 placeholder, invalid main_position=='0') all live-verified exact-match against the real 41,708-player dev DB via manage.py shell (pytest's own test DB is empty so the file skips cleanly there, matching the established real-data-test pattern); missing-club CS parity reads directly off score_population(pop, None) rather than a per-request service since a club-less player has no valid own-club id to drive one
- [Phase 05-scoring-parity-testing]: [05-02]: test_parity_bulk.py runs score_population(pop, None) exactly once (module-scope django_db_blocker.unblock() fixture) and diffs against the oracle CSV parametrized over the 10 real position groups for RMM/CS/TP (30 tests) plus one whole-population TFM check (raw log-scale pipeline.predict, replicating generate_scoring_oracle.py Steps 3-4 exactly); GK/LB/RB CS/TP explicitly asserted both-sides-null, not just incidentally passing; verified against the real dev DB via the project's own .venv (ambient pyenv Python lacks scikit-learn): 31/31 passed
- [Phase 05]: 05-02: test_parity_bulk.py runs score_population(pop, None) once (module-scope django_db_blocker.unblock() fixture) and diffs against the oracle CSV parametrized over the 10 real position groups for RMM/CS/TP (30 tests) plus one whole-population raw-log-scale TFM check replicating generate_scoring_oracle.py Steps 3-4; GK/LB/RB CS/TP explicitly asserted both-sides-null; verified against the real dev DB via the project's .venv (ambient interpreter lacks scikit-learn): 31/31 passed
- [Phase 05]: [Phase 05-scoring-parity-testing]: [05-03]: test_parity_api_sample.py's per-player sample MUST be built inside a django_db_setup-gated module-scope fixture, never at collection time -- pytest-django repoints the ORM connection from the dev DB to a separate (usually empty) test DB the moment the first django_db_setup-dependent fixture runs, so a collection-time-built sample silently diffs against ids the real test-time connection can no longer see; per-player fan-out uses pytest.mark.parametrize(indirect=True) over a fixed static slot range resolved lazily against the real sample so a single mismatching player is still a single failing test case. Live-verified against the real dev DB via manage.py shell (pytest's own test DB is empty here, matching the rest of the suite): 6 service-level players (GK/LB/RB/CB x3) and 5 endpoint-level players (GK + CB x4, plus 401 unauthenticated) all passed RMM/CS/TP/TFM/summary/endpoint parity.
- [Phase 06]: [Phase 06-02]: get_scored_population() wraps score_population(reconstruct_population(), None) as a new function rather than adding lru_cache directly to score_population, since score_population's pop argument is an unhashable Population(DataFrames) tuple; clear_scoring_caches() intentionally excludes get_tfm_pipeline since the TFM artifact's lifecycle is tied to train_tfm_model, not a data refresh
- [Phase 06-01]: Denormalized 4 own-club scores as nullable indexed Player FloatFields; transfer_probability_score left unindexed; no RunPython backfill (Plan 03 populates); build_players_df() hardened with a _DENORMALIZED_SCORE_FIELDS exclusion set to prevent the compatibility_score column-name collision from corrupting the oracle/TFM/financial_fit merge sites
- [Phase 06-03]: recompute_scores management command reuses generate_scoring_oracle.py's raw build_*/compute_* functions directly (not Plan 02's Population/score_population wrapper), only reusing get_tfm_pipeline(); financial_fit_score written money-scale via np.expm1; atomic bulk_update with NaN coerced to None; caches cleared before and after; live-verified against real 41,708-player dev DB: impact_score 41707 non-null, compatibility_score/transfer_probability_score 15051 non-null (26657 null by design, GK/LB/RB), financial_fit_score 41708 non-null ranging ~€496K-€26.4M
- [Phase 06]: [Phase 06-04]: test_scoring_performance.py hard-asserts SCORE-07's flat/O(1) retrieval claim; pytest itself skips cleanly against the empty test DB (Django tears down test_getscouted each session), so real timings were live-verified via manage.py shell against the dev DB: cold get_scored_population() 92.04s vs warm 0.0000s (~58M x speedup), denormalized PK read 0.569ms/read, flatness ratio 0.87x across N=100/1000/10000
- [Phase 06]: [Phase 06-05 gap-closure]: get_own_club_id/is_own_club helpers added to population.py; get_rmm now unconditionally reads the memoized get_scored_population() aggregate (no club context needed); get_compatibility/get_transfer_probability branch is_own_club() -> memoized get_scored_population() vs arbitrary-club live score_population(pop, club_name) fallback (Phase 12's future "rank clubs for a player" preserved). Live-verified against the real 41,708-player dev DB via manage.py shell: get_rmm 9.15s -> 0.05s, get_compatibility(own club) 44.2s -> 0.15s, both byte-identical to a fresh live computation for the same player/club; arbitrary-other-club fallback confirmed still functional (44.6s, correctly returned null envelope). SCORE-07 still NOT marked complete -- 06-06 (financial_fit/summary wiring) and 06-07 (regression test) remain before phase re-verification.
- [Phase 06-scoring-performance-caching-layer]: [Phase 06-06 gap-closure]: _financial_fit_own_club(player_id, club_name) added to financial_fit.py -- O(1) indexed read of the denormalized money-scale Player.financial_fit_score (first production consumer of the field Plans 06-01/06-03 built), re-deriving value_verdict via the same add_value_labels logic. get_financial_fit/get_summary both branch is_own_club(): own-club reads the denormalized field / memoized get_scored_population(); arbitrary-other-club keeps the live score_population(pop, club_name) fallback (Phase 12 preserved). Live-verified against the real 41,708-player dev DB via manage.py shell: get_financial_fit(own club) 0.0059s cold / 0.0024s warm (exact match to denormalized field); get_summary(own club) 0.2324s cold / 0.198s warm; strict negative-control confirmed neither call ever invokes build_oracle_player_features or the TFM pipeline for own-club. SCORE-07 still NOT marked complete -- 06-07 (regression test) and phase re-verification remain.
- [Phase 06]: [Phase 06-07 gap-closure]: test_live_scoring_performance.py proves the 5 live services (get_rmm/get_compatibility/get_transfer_probability/get_financial_fit/get_summary) are sub-second warm AND structurally never invoke add_player_impact/score_population/build_oracle_player_features per own-club request. Corrected the plan's own verbatim mock patch targets from the definition modules (scoring.characterization.impact/tfm_model, which are silent no-ops) to the caller's own import bindings (scoring.services.population/financial_fit) -- verified via live object-identity checks and two simulated-regression runs against the real dev DB that only the corrected targets actually intercept the call. Also fixed a latent 06-06 regression in test_services_summary.py's synthetic test (is_own_club now mocked). 06-live-wiring-DECISIONS.md records the own-club/arbitrary-club design + explicit Yes answer to 06-VERIFICATION.md's flagged scope question. SCORE-07 still NOT marked complete -- phase re-verification is the next step.
- [Phase 07-core-crud-players-clubs]: [Phase 07-01]: django-filter + capped DRF pagination (25/page, 100 max, ?ids= bypass variant) wired additively into REST_FRAMEWORK, preserving Phase 2's deny-by-default auth posture; per-app real_data_available fixtures added to players/tests and clubs/tests since pytest only auto-discovers conftest fixtures within their own dir or descendants
- [Phase 07]: [Phase 07-core-crud-players-clubs]: [Phase 07-02]: Players CRUD list/detail/ids wired -- PlayerListView (filter/sort/paginate via PlayerFilter + IdsBypassPagination) and PlayerDetailView (full profile + get_summary breakdowns) live under /api/players/; position filter strictly bound to Player.position (not main_position); PlayerDetailView branches explicitly on club_id is None before calling get_summary (which would raise a misleading Http404), instead computing RMM via rmm.get_rmm and returning null_with_reason(..., "player_has_no_club") for the 3 club-dependent scores; PlayerListSerializer confirmed reusable as 07-03's Club squad-overview shape
- [Phase 07]: [Phase 07-core-crud-players-clubs]: [Phase 07-03]: Clubs CRUD list/detail/squad/transfer-aggregates/ids wired -- ClubListView (filter by league/country/playing-style thresholds via ClubFilter + IdsBypassPagination) and ClubDetailView (full profile + squad via players.serializers.PlayerListSerializer over club.players.all() + transfer_aggregates) live under /api/clubs/, appended after (not replacing) 07-02's api/players/ include; transfer_aggregates strictly sourced from Transfer.market_value_at_transfer (clean BigInteger), never Transfer.fee (free-text) -- live-verified against the real dev DB (avg_market_value_at_transfer returned a real numeric average without raising). CRUD-02/04/05 functionally complete; requirements-mark-complete deferred to the phase verifier per this plan's explicit instruction. Pre-existing unrelated test failure discovered (accounts/tests/test_permissions.py::test_director_read_only_visibility, caused by 07-01's project-wide pagination change, confirmed to predate 07-03) logged to 07-core-crud-players-clubs/deferred-items.md, not fixed (out of scope).
- [Phase 08-user-workspace-crud]: [Phase 08-01]: workspace app scaffolded with 5 UUID-keyed models (Watchlist/Shortlist/ShortlistEntry/SquadPlan/RecentActivity) using UniqueConstraint/Index Meta convention; RecentActivity.target_id is a bare nullable UUIDField (not FK) to survive future Player/Club deletion; IsOwner permission resolves ownership via obj.user with a shortlist.user fallback for ShortlistEntry
- [Phase 08]: [Phase 08-02]: WatchlistViewSet.permission_classes must explicitly include IsAuthenticated alongside IsOwner -- overriding permission_classes drops the global default and lets AnonymousUser crash get_queryset() instead of returning 401
- [Phase 08]: [Phase 08-03]: Shortlist CRUD + nested entries (CRUD-07) live under /api/workspace/shortlists/, using a self.get_object()-based @action nested-resource pattern for entries/delete_entry that inherits IsOwner from the parent Shortlist without drf-nested-routers; 08-02's permission_classes=[IsAuthenticated, IsOwner] fix applied proactively this time, no deviation needed
- [Phase 08]: [Phase 08-04]: SquadPlan CRUD (CRUD-08) live under /api/workspace/squad-plans/, establishing the list/detail serializer split (SquadPlanListSerializer lightweight vs SquadPlanDetailSerializer with a SerializerMethodField current_squad derived live via PlayerListSerializer(obj.club.players.all()) -- never frozen, setting up Phase 11's simulation); proposed_changes JSONField validated at write time (list of dicts, action in {add,remove,swap}, swap requires incoming_player_id) via validate_proposed_changes on the detail serializer, which runs on create since create uses the detail serializer; permission_classes=[IsAuthenticated, IsOwner] applied per the 08-02/08-03 established pattern (plan's literal [IsOwner] auto-corrected, Rule 1)
- [Phase 08-user-workspace-crud]: [Phase 08-05]: RecentActivity auto-logged via explicit writes inside PlayerDetailView.get (post-get_object_or_404) and a new ClubDetailView.retrieve() override (RetrieveAPIView had no prior hook); RecentActivityListView needs no permission_classes override (get_queryset scoping + global IsAuthenticated default already deny anonymous with 401); test suite monkeypatches players.views.rmm.get_rmm for club=None PlayerFactory rows to avoid a real scoring-engine reconstruction against the empty pytest test DB, mirroring players/tests/test_views.py's established pattern; full suite (112 passed, 305 skipped, 0 failed) plus a live manage.py shell check against the real 41,708-player/1,060-club dev DB confirmed zero regression in Phase 7's player/club detail response contracts
- [Phase 08-user-workspace-crud]: [Phase 08-06]: CRUD-10 CSV export complete -- ShortlistViewSet.export @action (IsOwner-gated via get_object()) streams shortlist players via StreamingHttpResponse+Echo+csv.writer, columns pinned to PLAYER_EXPORT_COLUMNS (drawn from PlayerListSerializer's fields so exports never drift from the read API); ClubExportView (new APIView, IsAuthenticated-only -- club data isn't user-owned) streams club profile + transfer_aggregates reusing ClubDetailSerializer, with its own local Echo copy (per-app duplication over cross-app import, per plan). Discovered and fixed a real Phase-8-wide gap while satisfying this plan's own full-suite verification requirement: pyproject.toml's pytest testpaths never included "workspace" since the app was scaffolded in 08-01, so all of workspace/tests/ (every prior Phase 8 plan's tests) was silently excluded from every "full suite green" claim to date. Fixed by adding "workspace" to testpaths; full suite now correctly reports 144 passed, 305 skipped, 0 failed (up from the previously-undercounted 112 passed). Phase 8 is now feature-complete pending goal-backward verification.
- [Phase 09]: [Phase 09-01]: anthropic SDK pinned to a narrow 0.x minor-band (>=0.120,<0.130); ANTHROPIC_MODEL default claude-haiku-4-5 build-time verified via the installed SDK's own ModelParam Literal type (no local API key available to hit the live /v1/models endpoint); test isolation for ANTHROPIC_API_KEY implemented as an autouse monkeypatch guard in players/tests/conftest.py rather than a test-settings module
- [Phase 09]: [Phase 09-02]: AnthropicNLQueryParser catches parent anthropic.APIError (not a narrow subclass); ANTHROPIC_MODEL read exclusively from settings; _validate() drops hallucinated position/league enums + unknown keys before ORM; get_nl_query_parser() factory dispatches on settings.LLM_PROVIDER with lazy in-branch import
- [Phase 09]: [Phase 09-03]: search_players splits filters into player_filter_data (passed to PlayerFilter) and style_filters (club__<field>_min, applied via a separate manual .filter(club__<field>__gte=...) step) because PlayerFilter silently ignores undeclared club__ keys instead of erroring; league ambiguity in keyword_extract resolved via explicit qualifier-required regex groups for the 5 shared base terms (bundesliga/serie/la liga/ligue/efl)
- [Phase 09]: [Phase 09-04]: PlayerSearchView wraps ONLY the tier-1 get_nl_query_parser().parse() call in try/except NLQueryParserError (search_players() stays outside, so a genuine DB error is a real 500, never masked as a fallback); fallback_used=False means the LLM's real answer even if empty/partial, only flips True when the LLM CALL itself failed; live-verified all 3 tiers + RecentActivity 'searched' logging against the real 41,708-player dev DB (tier-2 'strikers under 5m' -> 4,504 matches, tier-3 unparseable query -> full 41,708 unfiltered, tier-1 mocked success -> 25 real CB results); full suite 174 passed/315 skipped/0 failed, phase complete

### Pending Todos

- Fix accounts/tests/test_permissions.py::test_director_read_only_visibility (paginated response.data["results"] indexing) -- pre-existing regression from 07-01's pagination wiring, tracked in .planning/phases/07-core-crud-players-clubs/deferred-items.md
- Phase 07 goal-backward verification (all 3 plans executed; CRUD-02/04/05 completion in REQUIREMENTS.md is the verifier's call)

### Blockers/Concerns

- Scoring engine curation (Phase 3) requires direct manual review of impact_model_v4.1.py to identify authoritative duplicated functions — no external pattern to follow, flagged by research as needing deeper analysis during planning.
- RESOLVED (03-05): Transfer Probability (SCORE-04) is confirmed a fully deterministic, non-ML weighted formula (0.30*compat + 0.20*perf + 0.20*financial + 0.30*contract_fit) — the RandomForestRegressor in impact_model_v4.1.py is the Financial Fit (TFM) artifact instead (Plan 06's concern), not Transfer Probability. No sklearn-parity risk for SCORE-04 itself; TFM (financial_score's ML sibling) still needs Phase 5 parity/quality validation.
- RESOLVED (09-01): AI layer LLM library/API surface checked fresh at build time -- anthropic==0.120.0 installed 2026-07-25, ANTHROPIC_MODEL default claude-haiku-4-5 confirmed current via the SDK's own bundled ModelParam Literal type (no local API key to hit the live /v1/models endpoint). Phase 10 (if it adds further Anthropic usage) should re-verify if executed much later, since 0.x SDK minors can drift.
- RESOLVED (06-01): The migration get-scouted-be/players/migrations/0002_denormalized_scores.py (from Plan 06-01's Player model change) was briefly knocked untracked by a git race between the two parallel wave-1 executors (06-01/06-02); committed cleanly as 5d71090, manage.py showmigrations confirms it applied. See 06-scoring-performance-caching-layer/deferred-items.md.

## Session Continuity

Last session: 2026-07-25T10:15:39.874Z
Stopped at: Completed 09-04-PLAN.md
Resume file: None
