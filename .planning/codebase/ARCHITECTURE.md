# Architecture

**Analysis Date:** 2026-07-20

## Overview

GetScouted is a multi-tier scouting platform composed of three interconnected sub-projects and a scoring engine. The architecture spans **legacy REST API** (Node.js/Express + MongoDB), **legacy frontend** (React/Vite), **modern frontend prototype** (React/TanStack Start + Supabase), and a **Python-based impact scoring engine**. The upcoming Django backend will unify the data layer and port the scoring logic into a production service.

---

## Sub-Project Architectures

### 1. API-Updated- (Legacy Node.js REST API)

**Overall Pattern:** REST API with MongoDB persistence and position-specific models

**Key Characteristics:**
- Express.js HTTP server on port 3000
- MongoDB via Mongoose ODM
- Position-stratified data models (per-position stat schemas)
- Route-based organization by resource
- Middleware pipeline: API key validation → request logging → error handling

**Layers:**

**HTTP/Express Layer:**
- Location: `index.js`
- Entries: Health check (`/healthcheck`), all routes mounted at root
- Middleware: CORS, JSON parsing, trust proxy (Nginx), API key validation (currently disabled), request logging
- Error handling: Centralized middleware that converts errors to JSON responses

**Routes Layer:**
- Location: `routes/` (playerRoutes.js, compatibilityRoutes.js, transferRoutes.js, positionRoutes.js, playstyleRoutes.js, shortlistRoutes.js, userRoutes.js)
- Endpoints:
  - `/players` → search, getAll, get by ID, find with query, filter, list roles/seasons/leagues
  - `/compatibility` → retrieve compatibility scores between players
  - `/transfers` → transfer data and averages
  - `/positions` → per-position player lists and stats
  - `/playstyles` → player playstyle/role information
  - `/shortlists` → user shortlist management
  - `/users` → user auth and profile
- Pattern: Each route file imports relevant models and implements CRUD operations

**Models Layer:**
- Location: `models/`
- Core models:
  - `player.js` — Main player schema with 100+ stat fields (goals, assists, defensive actions, duel stats, pass accuracy, card rates, etc.)
  - Position-specific models: `AM.js`, `CB.js`, `CM.js`, `DM.js`, `FWD.js`, `LB.js`, `LW.js`, `RB.js`, `RW.js` — Each contains position-specific performance metrics
  - `compatibilityScores.js` — Player compatibility matrix
  - `transferData.js` — Historical transfer records
  - `playstyles.js` — Role/style classification
  - `shortlist.js` — User-created shortlists
  - `users.js` — User accounts and authentication
- Pattern: Mongoose schemas define field types and constraints; models are imported into routes for queries

**Data/Dataset Layer:**
- Location: `dataset/`
- Files:
  - `Players.csv` (~25MB) — Comprehensive player statistics
  - `Playstyles.csv` — Role classification data
  - `Positions/` directory with per-position CSVs (AM, CB, CM, DM, FWD, LB, LW, RB, RW)
  - `Compatability Scores/` directory with compatibility matrices
  - `transferdata final.csv` (~6.7MB) — Historical transfer records
- Pattern: CSV files loaded into MongoDB on initialization; serve as source-of-truth for data seeding

**Utility Layer:**
- Location: `utils/fieldMapper.js`
- Exports: `getOriginalFieldName()`, `getSanitizedFieldName()` — Map between CSV column names and model field names

**Data Flow - Player Search:**
1. Frontend (RT-Tool-Frontend) sends GET `/players/search?value=playerName` with bearer token
2. API key validation middleware checks header (currently disabled)
3. JWT auth middleware (TODO: not yet implemented) verifies token
4. Route handler in `playerRoutes.js` queries Player model with fuzzy/exact match
5. Result serialized to JSON, sent to frontend

**Data Flow - Position-Specific Stats:**
1. Frontend requests `/positions/{position}?filters=...`
2. Route handler maps position name (e.g., "CB") to model import
3. Queries position-specific model (e.g., CB.js) with filter params
4. Aggregates stats from Player + Position model joined documents
5. Returns position-stratified metrics

---

### 2. RT-Tool-Frontend (Legacy React/Vite)

**Overall Pattern:** Multi-page React SPA with centralized state management and service layer

**Key Characteristics:**
- Vite build tool for fast dev/prod bundling
- React 18 with hooks
- Redux (react-redux) for global state
- TanStack Query (React Query) for server state caching
- Radix UI component library
- React Router v6 for navigation
- Axios HTTP client with interceptors

**Layers:**

**Routing Layer:**
- Location: `src/routes/`
- Contains: `AuthenticationRoutes.tsx`, `Layout.tsx`
- Pattern: Wraps entire app with AccessibleNav; uses React Router Outlet for child routes

**Pages Layer:**
- Location: `src/pages/`
- Components: Dashboard, PlayerRecommendation, DetailedPlayerProfiles, ClubSpecificCriteriaInput, PlayerComparison, RecruitmentHub, RecruitmentShop, Shortlist, SignIn, SignUp, ProfileSettings, etc.
- Pattern: Each page is a top-level route consumer; imports services and state hooks

**Components Layer:**
- Location: `src/components/`
- Structure:
  - `ui/` — Radix UI wrappers (button, dialog, select, slider, avatar, etc.)
  - `utility-components/` — App-specific UI components (player cards, filters, comparators)
  - `AccessibleNav.tsx` — Main navigation bar
- Pattern: Reusable, presentational; pass data and callbacks as props

**Services Layer:**
- Location: `src/services/`
- Modules:
  - `axiosInstance.ts` — Configured Axios client with auth interceptor (adds bearer token from `getToken()`)
  - `players/players.ts` — Player API calls (searchPlayers, getAllPlayers, getPlayerById, findPlayers, filterPlayers, getRoles, getSeasons, getLeagues)
  - `players/playstyles.ts` — Playstyle/role APIs
  - `shortlist.ts` — Shortlist creation/update/delete
  - `auth/signin.ts`, `auth/signup.ts`, `auth/transfers.ts` — Auth and transfer endpoints
  - `util.ts` — Utility functions (getToken, type definitions)
- Pattern: Each service file exports async functions that call `api.*()` with endpoints; uses TypeScript interfaces for type safety

**State Layer:**
- Location: `src/state/`
- Structure:
  - `reducer/` — Redux reducers
  - `types/` — State type definitions
- Pattern: Redux slices for global state (player filters, shortlist, user preferences)

**Hooks Layer:**
- Location: `src/hooks/`
- Custom React hooks for state and side effects

**Type Definitions:**
- Location: `src/types/apiTypes.ts`
- Exports: TypeScript interfaces matching API response schemas (Player, FilteredPlayersResponse, etc.)

**Styling:**
- Location: `src/styles/`
- Tailwind CSS configuration
- PostCSS for processing

**Data Flow - Player Filtering:**
1. User interacts with filter UI (age, position, compatibility, etc.) in page component
2. Page dispatches Redux action to update filter state
3. Page calls `filterPlayers(filters)` service function
4. Service formats params and makes GET `/players/filter?...` via `axiosInstance`
5. Interceptor adds `Authorization: Bearer {token}` header
6. Response parsed, TanStack Query caches result
7. Page renders filtered player list via component

---

### 3. pixel-perfect-clone-60729 (Modern React/TanStack Start + Supabase)

**Overall Pattern:** Full-stack TypeScript with file-based routing, PostgreSQL, server-side rendering (SSR), and real-time auth

**Key Characteristics:**
- TanStack Start (React 19 + TanStack Router + Vite)
- File-based routing via `src/routes/`
- Supabase for PostgreSQL + authentication
- TanStack Query for client-side server state
- Radix UI + Tailwind CSS
- Server-side rendering with Cloudflare Workers
- Zod for schema validation

**Layers:**

**Entry Points:**
- `src/start.ts` — Client entry point; initializes router and renders to DOM
- `src/server.ts` — Server entry point; uses Nitro for server-side handlers; error normalization for catastrophic SSR failures
- `src/router.tsx` — Creates TanStack Router with route tree and QueryClient context

**Routing Layer:**
- Location: `src/routes/`
- Files:
  - `__root.tsx` — Root layout; Auth context provider; navigation shell
  - `_authenticated.tsx` — Protected layout (requires auth); wraps all authenticated routes
  - `login.tsx`, `signup.tsx` — Public auth pages
  - `_authenticated/dashboard.tsx` — AI search & trending players
  - `_authenticated/shortlist.tsx` — Search and manage player shortlists
  - `_authenticated/clubs.tsx`, `_authenticated/clubs.$clubId.tsx` — Club analysis pages
  - `_authenticated/squad-planner.tsx` — Squad composition UI
  - `_authenticated/players.$playerId.tsx` — Player detail view
  - `_authenticated/find-clubs.tsx` — Find clubs for player
  - `_authenticated/deals.index.tsx`, `_authenticated/deals.$dealId.tsx` — Transfer deal tracking
  - `_authenticated/watchlist.tsx` — User watchlist
- Pattern: TanStack Router file-based routes; each route file exports Route object with component, loader, head metadata

**Components Layer:**
- Location: `src/components/`
- Radix UI wrapper components
- App-specific components: `club-context-cards.tsx`

**Hooks Layer:**
- Location: `src/hooks/`
- `use-auth.tsx` — Custom hook to access authenticated user via Supabase
- `use-mobile.tsx` — Responsive design helper

**Integration/Database Layer:**
- Location: `src/integrations/supabase/`
- Files:
  - `client.ts` — Supabase JS client factory; proxy pattern for lazy initialization
  - `client.server.ts` — Server-side Supabase client (uses process.env for env vars)
  - `types.ts` — Auto-generated TypeScript types from Supabase schema
  - `auth-middleware.ts` — Middleware to attach user context to server requests
  - `auth-attacher.ts` — Attaches Supabase auth to request context
- Pattern: Supabase client is a Proxy that lazily initializes on first access; environment variables use Vite's import.meta.env for client, process.env for server

**Database Schema (PostgreSQL via Supabase):**

Located in `supabase/migrations/`:

**Tables:**

- `public.clubs` — Club records
  - Fields: id (uuid), name, short_name, league, country, playing_style, avg_age, avg_market_value, transfer_budget, wage_budget, accent_color, created_at
  - Indexes: None explicit (auto on id)
  - RLS: Public read access

- `public.players` — Player records
  - Fields: id, name, position, age, nationality, club_id (FK), market_value, contract_until, player_score, transfer_probability, height_cm, foot, gbe_points, attributes (JSONB), trending, undervalued, created_at
  - Indexes: position, club_id
  - RLS: Public read access

- `public.profiles` — User profile metadata
  - Fields: id (FK to auth.users), full_name, job_title, club_id (FK), created_at, updated_at
  - Triggers: `touch_updated_at()` updates `updated_at` on every UPDATE
  - RLS: Users read/update/insert own profile

- `public.user_roles` — Role-based access control
  - Fields: id, user_id (FK), role (enum: scout|analyst|director|admin), created_at
  - Constraints: UNIQUE(user_id, role)
  - RLS: Users read own roles; admins can manage

- `public.watchlist` — Player watch list
  - Fields: id, user_id, player_id (FK), notes, created_at
  - Constraints: UNIQUE(user_id, player_id)
  - RLS: Users can do ALL operations on own watchlist

- `public.squad_plans` — Squad composition plans
  - Fields: id, user_id, club_id (FK), name, payload (JSONB for lineup data), created_at
  - RLS: Users can do ALL operations on own squad plans

- `public.recent_activity` — Audit log of user actions
  - Fields: id, user_id, kind (event type), payload (JSONB), created_at
  - Indexes: (user_id, created_at DESC)
  - RLS: Users can do ALL operations on own activity

**Auth Enums/Functions:**

- `app_role` enum: scout, analyst, director, admin
- `has_role(_user_id uuid, _role app_role) → boolean` — Check if user has role (security definer function)
- Trigger `on_auth_user_created` — On user signup, create profile and assign default "scout" role

**Domain Types (TypeScript):**
- Location: `src/lib/domain.ts`
- Exports:
  - `AppRole` — scout | analyst | director | admin
  - `Attributes` — Player attribute scores: pace, shooting, passing, defending, physical, dribbling (0-100 scale)
  - `Club` — Club data type (matches Supabase clubs table)
  - `Player` — Player data type (matches Supabase players table + attributes JSONB)
  - `POSITIONS` — Array of valid positions: GK, CB, LB, RB, CDM, CM, CAM, LW, RW, ST, CF
  - `POSITION_COMPONENTS` — Map of position → { key, label, weights } for impact scoring
    - Each component maps base attributes (pace, shooting, etc.) to position-specific skills via weighted sums
    - Example: `CB.defensive_actions = 0.65 * defending + 0.25 * physical + 0.1 * pace`
  - `positionComponents(player) → { key, label, value }[]` — Calculate component scores for player

**Server Logic:**
- Location: `src/server.ts`
- Handles fetch requests from Cloudflare Workers
- Normalizes catastrophic SSR errors into branded error page
- Logs unhandled errors to console

**Library/Utility Layer:**
- Location: `src/lib/`
- Files:
  - `utils.ts` — Shared utilities
  - `error-capture.ts` — Global error capture mechanism
  - `error-page.ts` — Branded error page HTML
  - `domain.ts` — Domain type definitions (see above)
  - `deal-analysis.ts` — Deal/transfer analysis logic
  - `club-recruitment.ts` — Club recruitment profile generation

**Data Flow - Player Shortlist Search:**
1. User navigates to `/shortlist` route (protected by `_authenticated` layout)
2. `_authenticated/shortlist.tsx` mounts; checks auth context
3. Component calls `supabase.from("players").select(...).eq("trending", true).limit(6)`
4. TanStack Query caches result, re-runs on refocus
5. Component renders player cards with comparison/add-to-watchlist actions
6. User click triggers `supabase.from("watchlist").insert({ user_id, player_id })`
7. Recent activity logged via `supabase.from("recent_activity").insert()`

**Data Flow - Club Analysis:**
1. User navigates to `/clubs/{clubId}` route
2. Route loader queries `supabase.from("clubs").select(...).eq("id", clubId)`
3. Also queries `supabase.from("players").select(...).eq("club_id", clubId)`
4. Component renders club stats, position-group distribution, transfer budget, team style
5. Dashboard links to `deal-analysis.ts` functions for transfer fit scoring

---

## Impact Scoring Engine (impact_model_v4.1.py)

**Overall Purpose:** Calculate player impact scores per position, role fit scores, team compatibility, financial fit, and generate shortlist recommendations

**Structure:** ~15,700-line Python module with 100+ functions organized by domain

**Key Functions:**

**Export/Formatting:**
- `export_team_shortlist_xlsx()` — Generate Excel report with full shortlist analysis
- `get_export_columns_for_position()` — Filter columns for position-specific export
- `round_money()`, `format_financial()`, `format_financial_num()` — Currency formatting

**Data Preparation:**
- `_rename_columns_safe()` — Normalize column names from CSVs
- `prepare_optional_transfer_fields()` — Add missing fields with defaults
- `normalize_league_name()`, `normalize_country_name()`, `normalize_text()` — Text normalization
- `_ensure_minutes()`, `_minutes_factor()`, `_reliability_flag()` — Handle minutes-played thresholds

**Impact Calculation per Position** (Core scoring logic):
- `_calc_gk_impact_raw(row, row_idx, std_lookup)` — GK: shot_stopping, command, distribution, buildup_support
- `_calc_cb_impact_raw()` — CB: defensive_actions, duel_dominance, aerial, reading, buildup
- `_calc_fb_impact_raw()` — FB (LB/RB): defending, progression, chance_creation, control, duel_work
- `_calc_cmf_impact_raw()` — CM: ball_progression, control, creation, ball_winning, carrying
- `_calc_dmf_impact_raw()` — DM: ball_winning, control, progression, distribution, creation
- `_calc_amf_impact_raw()` — AM: creation, final_third_progression, scoring_threat, carrying, connection
- `_calc_winger_impact_raw()` — Winger (LW/RW): dribbling, creation, threat, progression, duel_value
- `_calc_cf_impact_raw()` — CF: finishing, box_threat, chance_creation, progression, duel_value

Pattern for each:
1. Compute 4-5 position-specific components via weighted sums of standardized metrics
2. Aggregate into positive (favorable) and negative (unfavorable) sub-scores
3. Apply minutes-played weighting factor
4. Return: `(raw_impact, positive, negative, components_dict)` if return_components=True

**Standardization & Metrics:**
- `_build_std_lookup()` — Pre-compute z-scores (standardized values) for all metrics per position
- `_std(row_idx, position, metric_name, std_lookup)` — Retrieve z-score from lookup table
- `_position_percentile()` — Rank player within position cohort

**Team-Level Analysis:**
- `build_team_position_reference()` — Aggregate stats by team and position
- `compare_players_to_target_team()` — Compare candidate player impact vs team averages
- `compare_shortlist_to_target_team()` — Batch compare multiple candidates
- `club_transfer_profile()` — Analyze club transfer patterns over N years

**Role/Playing Style:**
- `normalize_role_vector_from_row()` — Extract per-position role distribution from player stats
- `build_team_style_vector()` — Extract team's role demand profile
- `compute_team_role_demand()` — Compute weighted role distribution for team
- `calculate_subjective_role_fit_for_player_to_team()` — Cosine similarity between player and team roles
- `get_role_vector_from_row()` — Extract role vector from player attributes
- `_cosine_similarity_from_series()` — Compute cosine similarity
- `calculate_player_to_team_player_similarity()` — Compare candidate to existing team player

**Shortlist Generation & Recommendations:**
- `external_target_shortlist_absolute_vectorized()` — Generate ranked shortlist from dataset
- `build_shortlist_input_recommendations()` — Generate recommendations summary
- `get_biggest_upgrade_area_for_row()` — Identify weakest component area
- `add_player_impact()` — Compute impact scores for all players in dataframe

**Classification/Formatting:**
- `classify_fit()` — Categorize values as "great", "moderate", "poor" vs average
- `classify_age_fit()` — Age suitability scoring
- `extract_playing_style_from_dataset()` — Extract role/style from player stats
- `get_top_roles_string()`, `get_top_roles_relative_to_best()` — Format role recommendations

**Data Flow - Generate Shortlist Report:**
1. Load players CSV, position CSVs, compatibility scores
2. Normalize column names, prepare optional fields
3. Build standardization lookup (z-scores per metric per position)
4. For each candidate player:
   - Call position-specific impact calculator
   - Compute components, positive, negative, raw impact
   - Compare to target team averages
   - Calculate role fit via cosine similarity
   - Classify financial fit, age fit
5. Sort by player_score
6. Export to Excel with 50+ columns

---

## Cross-Project Data Integration

### Current Data Flow (Legacy):
1. **RT-Tool-Frontend** ← Axios → **API-Updated-** ← MongoDB (seeded from CSVs in `dataset/`)
2. **API-Updated-** reads from MongoDB populated by `dataset/` CSVs
3. Scoring happens offline via `impact_model_v4.1.py` (not integrated into API-Updated)

### Future Data Flow (Post-Django):
1. **pixel-perfect-clone-60729** ← TanStack Query → **Django Backend** ← PostgreSQL
2. **Django Backend** ingests data from **API-Updated-** MongoDB + `dataset/` CSVs
3. **Django Backend** implements scoring engine (ported from Python)
4. Django exposes REST endpoints:
   - `/api/players/` — Player CRUD, filtering, search
   - `/api/clubs/` — Club CRUD, squad analysis
   - `/api/scoring/calculate-impact/` — Per-player impact calculation
   - `/api/scoring/generate-shortlist/` — Shortlist generation with role fit
   - `/api/scoring/team-analysis/` — Team squad composition analysis
   - `/api/transfers/` — Transfer data + probabilities
5. **pixel-perfect-clone-60729** connects to Django instead of Supabase

---

## Abstraction Boundaries

**Database Abstraction:**
- Supabase client (`supabase/client.ts`) abstracts PostgreSQL details
- Proxy pattern lazy-initializes on first access
- SSR and client use different auth approaches (env vars vs localStorage)

**Impact Scoring Abstraction:**
- Per-position calculators (`_calc_*_impact_raw()`) encapsulate position-specific logic
- Standardization lookup pre-computed to avoid repeated calculations
- Components dictionary allows flexible export/aggregation

**Authentication Abstraction:**
- Supabase Auth manages user sessions and JWT
- `use-auth()` hook provides unified auth context across app
- Row-level security (RLS) enforces data isolation at database level

**API Abstraction:**
- Axios instance in RT-Tool-Frontend wraps HTTP calls
- Service layer functions (players.ts, etc.) wrap API endpoints
- TanStack Query in modern frontend handles caching and refetching

---

## Error Handling & Observability

**API-Updated- (Express):**
- Centralized error middleware catches and formats all errors
- Request logging middleware logs method, URL, timestamp
- No error tracking system (TODO)

**RT-Tool-Frontend:**
- Error logging to console (no external service)
- Graceful degradation on API failures (errors logged, UI shows fallback)

**pixel-perfect-clone-60729:**
- Error capture module (`error-capture.ts`) catches global errors
- Branded error page (`error-page.ts`) rendered on catastrophic SSR failures
- Supabase auth errors handled in route guards and hooks

**Django Backend (TBD):**
- Should implement structured logging with timestamps, request IDs, stack traces
- Should integrate with error tracking (Sentry, DataDog, etc.)
- Should provide health check endpoint for load balancers

---

## Key Abstractions to Preserve in Django Port

1. **Position-Specific Scoring:** Each position (GK, CB, etc.) has distinct component logic. Django should use position-specific calculators or strategy pattern.

2. **Standardization Pipeline:** Z-score normalization must happen once and be memoized. Consider caching standardization lookup in Redis.

3. **Role/Playing Style Vectors:** Team and player role distributions computed via weighted role sums. Essential for cosine similarity matching.

4. **Shortlist Generation Algorithm:** High-level export function orchestrates multiple scoring passes. Should remain high-level in Django, with internal services doing heavy lifting.

5. **Data Versioning:** CSVs represent a snapshot of player data at a point in time. Django should track dataset versions (season, league, update date) to ensure reproducibility.

6. **Multi-Resource Queries:** Many endpoints join players × clubs × transfer data × compatibility scores. Use Django ORM relations or analytical database views for efficiency.

---

*Architecture analysis: 2026-07-20*
