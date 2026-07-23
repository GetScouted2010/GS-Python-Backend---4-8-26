---
gsd_state_version: 1.0
milestone: v4.1
milestone_name: milestone
status: unknown
stopped_at: Completed 04-06-PLAN.md
last_updated: "2026-07-23T22:19:55.824Z"
progress:
  total_phases: 12
  completed_phases: 4
  total_plans: 25
  completed_plans: 25
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-20)

**Core value:** The backend must serve accurate, real scouting data and real (not approximated) Impact RMM scoring — the product's credibility rests on the scores being right, not just on the API being reachable.
**Current focus:** Phase 04 — scoring-engine-port

## Current Position

Phase: 04 (scoring-engine-port) — All plans executed, pending goal-backward verification
Plan: 6 of 6 — Waves 1-4 complete (04-01 through 04-06); DRF API surface for all 5 scoring endpoints live under /api/scoring/

## Performance Metrics

**Velocity:**

- Total plans completed: 3
- Average duration: 21 min
- Total execution time: 1.05 hours

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

### Pending Todos

None yet.

### Blockers/Concerns

- Scoring engine curation (Phase 3) requires direct manual review of impact_model_v4.1.py to identify authoritative duplicated functions — no external pattern to follow, flagged by research as needing deeper analysis during planning.
- RESOLVED (03-05): Transfer Probability (SCORE-04) is confirmed a fully deterministic, non-ML weighted formula (0.30*compat + 0.20*perf + 0.20*financial + 0.30*contract_fit) — the RandomForestRegressor in impact_model_v4.1.py is the Financial Fit (TFM) artifact instead (Plan 06's concern), not Transfer Probability. No sklearn-parity risk for SCORE-04 itself; TFM (financial_score's ML sibling) still needs Phase 5 parity/quality validation.
- AI layer (Phases 9-10) LLM library/API surface should get a fresh check at build time given how fast that space moves.

## Session Continuity

Last session: 2026-07-23T22:19:55.822Z
Stopped at: Completed 04-06-PLAN.md
Resume file: None
