# Codebase Structure

**Analysis Date:** 2026-07-20

---

## Directory Layout

```
getScouted/                                  # Monorepo root (main git repo)
├── .git/                                   # Git repository
├── .planning/
│   └── codebase/                           # This documentation
├── GetScouted PRD.docx                     # Product requirements document
│
├── API-Updated-/                           # Legacy Node.js/Express REST API (sub-project)
│   ├── index.js                            # Entry point; Express app setup
│   ├── package.json                        # Dependencies; scripts: start, test
│   ├── middleware/
│   │   └── apikey.js                       # API key validation (disabled)
│   │   └── auth.js                         # JWT verification (TODO)
│   ├── routes/
│   │   ├── playerRoutes.js                 # GET/POST /players endpoints
│   │   ├── compatibilityRoutes.js          # /compatibility endpoints
│   │   ├── transferRoutes.js               # /transfers endpoints
│   │   ├── positionRoutes.js               # /positions/{position} endpoints
│   │   ├── playstyleRoutes.js              # /playstyles endpoints
│   │   ├── shortlistRoutes.js              # /shortlists endpoints
│   │   └── userRoutes.js                   # /users auth & profile endpoints
│   ├── models/
│   │   ├── player.js                       # Player schema (100+ stat fields)
│   │   ├── AM.js, CB.js, CM.js, DM.js      # Position-specific schemas
│   │   ├── FWD.js, LB.js, LW.js, RB.js, RW.js
│   │   ├── compatibilityScores.js          # Player compatibility matrix
│   │   ├── transferData.js                 # Transfer records schema
│   │   ├── playstyles.js                   # Role/style classification
│   │   ├── shortlist.js                    # User shortlist schema
│   │   ├── users.js                        # User account schema
│   │   └── TeamPassword.js                 # Club/team password schema
│   ├── utils/
│   │   └── fieldMapper.js                  # CSV-to-schema field name mapping
│   ├── dataset/                            # CSV data files (source-of-truth)
│   │   ├── Players.csv                     # ~25MB; all players + stats
│   │   ├── Playstyles.csv                  # Player role/style classification
│   │   ├── transferdata final.csv          # ~6.7MB; historical transfers
│   │   ├── Positions/                      # Per-position stat breakdowns
│   │   │   ├── AM with league.csv
│   │   │   ├── CB with league.csv
│   │   │   ├── CM with league.csv
│   │   │   ├── DM with league.csv
│   │   │   ├── FWD with league Updated.csv
│   │   │   ├── LB with league.csv
│   │   │   ├── LW with league2.csv
│   │   │   ├── RB with league.csv
│   │   │   └── RW with league.csv
│   │   └── Compatability Scores/           # Compatibility matrices
│   │       └── [position pairs] (various CSVs)
│   └── .env                                # Database URL, API key, JWT secret (NOT committed)
│
├── RT-Tool-Frontend/                       # Legacy React/Vite frontend (sub-project)
│   ├── package.json                        # React 18, axios, Redux, TanStack Query
│   ├── vite.config.ts                      # Vite bundler configuration
│   ├── tsconfig.json                       # TypeScript config
│   ├── tailwind.config.js                  # Tailwind CSS customization
│   ├── .eslintrc.js                        # ESLint rules
│   ├── index.html                          # HTML entry point
│   ├── public/                             # Static assets (icons, images)
│   ├── src/
│   │   ├── main.tsx                        # React app entry point; mounts to #app
│   │   ├── App.tsx                         # Root component; router setup
│   │   ├── routes/
│   │   │   ├── AuthenticationRoutes.tsx    # Auth layout wrapper; renders Outlet
│   │   │   └── Layout.tsx                  # Main layout shell
│   │   ├── pages/                          # Route-level page components
│   │   │   ├── Dashboard.tsx               # Homepage
│   │   │   ├── PlayerRecommendation.tsx
│   │   │   ├── DetailedPlayerProfiles.tsx
│   │   │   ├── PlayerComparison.tsx
│   │   │   ├── ClubSpecificCriteriaInput.tsx
│   │   │   ├── ClubSpecificList.tsx
│   │   │   ├── RecruitmentHub.tsx
│   │   │   ├── RecruitmentShop.tsx
│   │   │   ├── SignIn.tsx                  # Login form
│   │   │   ├── SignUp.tsx                  # Registration form
│   │   │   ├── ProfileSettings.tsx
│   │   │   ├── PlayerSpecific.tsx
│   │   │   ├── testing.tsx
│   │   │   └── Shortlist/
│   │   │       ├── Shortlist.tsx           # Main shortlist page
│   │   │       └── ShortlistPages.tsx
│   │   ├── components/                     # Reusable UI components
│   │   │   ├── ui/                         # Radix UI wrappers
│   │   │   │   ├── button.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── select.tsx
│   │   │   │   ├── slider.tsx
│   │   │   │   ├── avatar.tsx
│   │   │   │   ├── tabs.tsx
│   │   │   │   ├── checkbox.tsx
│   │   │   │   └── [other Radix components]
│   │   │   ├── utility-components/         # App-specific UI
│   │   │   │   ├── PlayerCard.tsx
│   │   │   │   ├── FilterPanel.tsx
│   │   │   │   ├── ComparisonChart.tsx
│   │   │   │   └── [other app components]
│   │   │   └── AccessibleNav.tsx           # Navigation bar
│   │   ├── services/                       # HTTP client & API calls
│   │   │   ├── axiosInstance.ts            # Configured Axios with auth interceptor
│   │   │   ├── util.ts                     # getToken(), shared utils
│   │   │   ├── players/
│   │   │   │   ├── players.ts              # searchPlayers, getAllPlayers, getPlayerById, etc.
│   │   │   │   └── playstyles.ts           # getPlaystyles, etc.
│   │   │   ├── auth/
│   │   │   │   ├── signin.ts               # POST /users/login
│   │   │   │   ├── signup.ts               # POST /users/register
│   │   │   │   └── transfers.ts            # GET /transfers endpoints
│   │   │   └── shortlist.ts                # POST/DELETE /shortlists endpoints
│   │   ├── state/                          # Redux state management
│   │   │   ├── reducer/                    # Redux reducers
│   │   │   │   ├── playerFiltersReducer.ts
│   │   │   │   ├── shortlistReducer.ts
│   │   │   │   └── userReducer.ts
│   │   │   └── types/                      # State type definitions
│   │   │       └── appState.ts
│   │   ├── hooks/                          # Custom React hooks
│   │   │   ├── usePlayerFilter.ts
│   │   │   ├── useShortlist.ts
│   │   │   └── useAuth.ts
│   │   ├── types/                          # TypeScript interfaces
│   │   │   ├── apiTypes.ts                 # API response schemas
│   │   │   └── domainTypes.ts              # Business domain types
│   │   ├── lib/                            # Utility functions
│   │   │   ├── api.ts                      # API helper functions
│   │   │   ├── formatting.ts               # Number/currency formatting
│   │   │   └── validation.ts               # Form validation
│   │   ├── assets/                         # Images, fonts, icons
│   │   │   └── icons/
│   │   ├── styles/                         # Global Tailwind CSS
│   │   │   └── globals.css
│   │   └── vite-env.d.ts                   # Vite type definitions
│   └── dist/                               # Built output (generated)
│
├── pixel-perfect-clone-60729/              # Modern React/TanStack Start + Supabase (sub-project)
│   ├── package.json                        # React 19, TanStack Router/Query/Start
│   ├── tsconfig.json                       # TypeScript config
│   ├── vite.config.ts                      # TanStack Start Vite config
│   ├── tailwind.config.js                  # Tailwind CSS
│   ├── .eslintrc.cjs                       # ESLint config
│   ├── prettier.config.cjs                 # Code formatter config
│   ├── index.html                          # Entry point
│   ├── src/
│   │   ├── start.ts                        # Client entry point; creates router, mounts to DOM
│   │   ├── server.ts                       # Server entry point; handles fetch requests (Cloudflare Workers)
│   │   ├── router.tsx                      # TanStack Router setup; creates QueryClient
│   │   ├── routeTree.gen.ts                # Auto-generated route tree (do not edit)
│   │   ├── routes/                         # File-based routing
│   │   │   ├── __root.tsx                  # Root layout; Auth context, main nav
│   │   │   ├── index.tsx                   # / route (home)
│   │   │   ├── login.tsx                   # /login
│   │   │   ├── signup.tsx                  # /signup
│   │   │   ├── _authenticated.tsx          # Protected layout; wraps all auth-required routes
│   │   │   └── _authenticated/
│   │   │       ├── dashboard.tsx           # /dashboard — AI search, trending players
│   │   │       ├── shortlist.tsx           # /shortlist — Search & manage player shortlist
│   │   │       ├── clubs.tsx               # /clubs — Club list page
│   │   │       ├── clubs.index.tsx         # /clubs/ — Club index view
│   │   │       ├── clubs.$clubId.tsx       # /clubs/:clubId — Club detail
│   │   │       ├── players.$playerId.tsx   # /players/:playerId — Player detail
│   │   │       ├── squad-planner.tsx       # /squad-planner — Squad composition UI
│   │   │       ├── find-clubs.tsx          # /find-clubs — Find clubs for player
│   │   │       ├── watchlist.tsx           # /watchlist — User's watched players
│   │   │       ├── deals.index.tsx         # /deals — Deal/transfer tracking list
│   │   │       └── deals.$dealId.tsx       # /deals/:dealId — Deal detail
│   │   ├── components/                     # Reusable UI components
│   │   │   ├── ui/                         # Radix UI wrapper components
│   │   │   │   ├── button.tsx
│   │   │   │   ├── card.tsx
│   │   │   │   ├── dialog.tsx
│   │   │   │   ├── select.tsx
│   │   │   │   ├── accordion.tsx
│   │   │   │   └── [other Radix UI]
│   │   │   └── club-context-cards.tsx      # App-specific club display component
│   │   ├── hooks/                          # Custom React hooks
│   │   │   ├── use-auth.tsx                # useAuth() — Access authenticated user
│   │   │   └── use-mobile.tsx              # useMobile() — Responsive design helper
│   │   ├── lib/                            # Domain logic & utilities
│   │   │   ├── domain.ts                   # Domain types (Player, Club, POSITION_COMPONENTS, etc.)
│   │   │   ├── utils.ts                    # Shared utilities
│   │   │   ├── deal-analysis.ts            # Transfer/deal analysis functions
│   │   │   ├── club-recruitment.ts         # Club recruitment profile generation
│   │   │   ├── error-capture.ts            # Global error capture
│   │   │   └── error-page.ts               # Branded error page HTML
│   │   ├── integrations/
│   │   │   ├── supabase/                   # Supabase integration
│   │   │   │   ├── client.ts               # Supabase client (Proxy pattern)
│   │   │   │   ├── client.server.ts        # Server-side Supabase client
│   │   │   │   ├── types.ts                # Auto-generated types from Supabase schema
│   │   │   │   ├── auth-middleware.ts      # Request middleware to attach user
│   │   │   │   └── auth-attacher.ts        # Auth context attachment
│   │   │   └── lovable/                    # Lovable platform integration
│   │   │       └── index.ts                # Lovable auth module
│   │   └── style.css                       # Global styles
│   ├── supabase/
│   │   └── migrations/                     # SQL migration files (versioned)
│   │       ├── 20260518040844_*.sql        # Initial schema (roles, clubs, players, profiles)
│   │       ├── 20260518040858_*.sql        # Watchlist table
│   │       ├── 20260518104346_*.sql        # Squad plans table
│   │       ├── 20260518105927_*.sql        # Recent activity table
│   │       ├── 20260518110034_*.sql        # [Other migrations]
│   │       └── [more migration files]
│   ├── docs/
│   │   └── impact_model_v4.1.py            # Scoring engine (15,700 lines)
│   │                                       # Contains ~100 functions for:
│   │                                       # - Position-specific impact calculation
│   │                                       # - Standardization/z-score logic
│   │                                       # - Role fit via cosine similarity
│   │                                       # - Team analysis & shortlist generation
│   ├── .lovable/                           # Lovable platform metadata
│   └── dist/                               # Build output (generated)
```

---

## Directory Purposes

### `/API-Updated-` (Node.js REST API)

**Purpose:** Legacy REST API serving player data, compatibility scores, transfers, and shortlists. Reads from MongoDB seeded by CSV files.

**Core Files:**
- `index.js` — HTTP server entry point; mounts all route handlers
- `package.json` — Express 4, Mongoose 8, bcryptjs, jsonwebtoken, nodemon (dev)
- `middleware/apikey.js` — (Disabled) validates x-api-key header
- `middleware/auth.js` — (TODO) JWT verification

**Route Files** (each mounts to express router):
- `playerRoutes.js` — Player search, filtering, role/league/season lists
- `compatibilityRoutes.js` — Compatibility scores between player pairs
- `transferRoutes.js` — Transfer history and market averages
- `positionRoutes.js` — Per-position player lists and statistics
- `playstyleRoutes.js` — Player role/style data
- `shortlistRoutes.js` — User shortlist CRUD
- `userRoutes.js` — User authentication and profiles

**Models** (Mongoose schemas):
- One model per position (AM, CB, CM, DM, FWD, LB, LW, RB, RW)
- Central Player model with 100+ stat fields
- CompatibilityScores, TransferData, Playstyles, Shortlist, Users models

**Dataset** (source-of-truth CSVs):
- Loaded into MongoDB on app initialization or via scripts
- Per-position breakdowns in `Positions/` (9 files)
- Compatibility matrices in `Compatability Scores/` (multiple matrices)

---

### `/RT-Tool-Frontend` (Legacy React/Vite)

**Purpose:** User-facing scouting platform consuming API-Updated- via Axios. Provides player search, filtering, comparison, and shortlist management.

**Build/Config:**
- `package.json` — React 18, Vite, Tailwind, Redux, TanStack Query, Radix UI, axios
- `vite.config.ts` — Vite dev server and production build config
- `tsconfig.json` — TypeScript strict mode
- `tailwind.config.js` — Custom colors, spacing, utilities

**Entry Point:**
- `src/main.tsx` — React entry point; renders App into #app div
- `src/App.tsx` — Root component; initializes Redux store, React Router

**Routing:**
- `src/routes/AuthenticationRoutes.tsx` — Layout wrapper with AccessibleNav
- `src/routes/Layout.tsx` — Main layout shell (sidebar, header, etc.)
- Uses React Router v6 for navigation (not file-based)

**Pages** (Route-level components):
- `Dashboard.tsx` — Homepage with filters and player list
- `PlayerRecommendation.tsx`, `DetailedPlayerProfiles.tsx` — Player detail views
- `PlayerComparison.tsx` — Side-by-side player comparison
- `ClubSpecificCriteriaInput.tsx`, `RecruitmentHub.tsx` — Club-scoped searches
- `Shortlist/Shortlist.tsx` — User's shortlist management
- `SignIn.tsx`, `SignUp.tsx` — Authentication pages

**Components** (Reusable UI):
- `ui/` — Radix UI component wrappers (Button, Dialog, Select, Slider, Avatar, Tabs, etc.)
- `utility-components/` — App-specific components (PlayerCard, FilterPanel, ComparisonChart)
- `AccessibleNav.tsx` — Main navigation bar

**Services** (HTTP layer):
- `axiosInstance.ts` — Configured Axios with `Authorization: Bearer {token}` interceptor
- `players/players.ts` — Player API functions (searchPlayers, getPlayerById, filterPlayers, etc.)
- `players/playstyles.ts` — Playstyle/role API
- `auth/signin.ts`, `auth/signup.ts` — User authentication
- `auth/transfers.ts` — Transfer data API
- `util.ts` — Helper functions (getToken from localStorage)

**State** (Redux):
- `state/reducer/` — Redux reducers (playerFiltersReducer, shortlistReducer, userReducer)
- `state/types/` — State shape definitions

**Hooks:**
- `usePlayerFilter()`, `useShortlist()`, `useAuth()` — Custom hooks wrapping Redux + service calls

**Types:**
- `types/apiTypes.ts` — TypeScript interfaces for API responses
- `types/domainTypes.ts` — Business domain types

**Utilities:**
- `lib/api.ts` — API helper functions
- `lib/formatting.ts` — Number/currency formatting
- `lib/validation.ts` — Form validation

**Assets:**
- `assets/icons/` — Icon SVGs/images
- `styles/globals.css` — Global Tailwind CSS

---

### `/pixel-perfect-clone-60729` (React/TanStack Start + Supabase)

**Purpose:** Modern prototype scouting platform using file-based routing, Supabase PostgreSQL backend, and real-time auth. Will eventually replace RT-Tool-Frontend and be backed by Django.

**Build/Config:**
- `package.json` — React 19, TanStack Start, TanStack Query, TanStack Router, Supabase JS, Radix UI
- `vite.config.ts` — TanStack Start with Cloudflare Workers deployment
- `tsconfig.json` — TypeScript strict mode
- `tailwind.config.js`, `prettier.config.cjs`, `.eslintrc.cjs` — Code quality

**Entry Points:**
- `src/start.ts` — Client-side entry; initializes router, mounts to DOM
- `src/server.ts` — Server-side entry; Cloudflare Workers handler, error normalization
- `src/router.tsx` — TanStack Router setup with QueryClient context

**Routing** (File-based via TanStack Router):
- `__root.tsx` — Root layout; provides Auth context, main shell
- `index.tsx` — / (home/landing)
- `login.tsx`, `signup.tsx` — Public auth pages
- `_authenticated.tsx` — Protected layout (requires auth) wrapping all user routes
  - `dashboard.tsx` — AI search, trending players
  - `shortlist.tsx` — Search and manage player shortlist
  - `clubs.tsx`, `clubs.index.tsx`, `clubs.$clubId.tsx` — Club browsing and detail
  - `players.$playerId.tsx` — Player detail with stats
  - `squad-planner.tsx` — Squad composition UI
  - `find-clubs.tsx` — Find clubs for specific player
  - `watchlist.tsx` — User's watched players
  - `deals.index.tsx`, `deals.$dealId.tsx` — Transfer deal tracking

**Components:**
- `ui/` — Radix UI wrapper components (Button, Card, Dialog, Select, Accordion, etc.)
- `club-context-cards.tsx` — App-specific club context display

**Hooks:**
- `use-auth.tsx` — useAuth() hook; accesses Supabase user context
- `use-mobile.tsx` — useMobile() hook; responsive design helper

**Integration/Database** (`src/integrations/supabase/`):
- `client.ts` — Supabase JS client factory with Proxy lazy initialization
- `client.server.ts` — Server-side Supabase client using process.env
- `types.ts` — Auto-generated TypeScript types from Supabase schema
- `auth-middleware.ts` — Middleware to attach user to server request context
- `auth-attacher.ts` — Auth context attachment helper

**Domain Logic** (`src/lib/`):
- `domain.ts` — TypeScript type definitions (Player, Club, AppRole, POSITION_COMPONENTS, etc.)
  - POSITION_COMPONENTS maps each position to 4-5 components with attribute weights
  - Example: `CB.defensive_actions = { weights: { defending: 0.65, physical: 0.25, pace: 0.1 } }`
- `utils.ts` — Shared utility functions
- `deal-analysis.ts` — Transfer/deal analysis logic
- `club-recruitment.ts` — Club recruitment profile generation
- `error-capture.ts` — Global error capture mechanism
- `error-page.ts` — Branded error page HTML renderer

**Database** (`supabase/migrations/`):
- Versioned SQL migration files
- Tables: clubs, players, profiles, user_roles, watchlist, squad_plans, recent_activity
- Row-level security (RLS) policies for multi-tenancy
- Auth triggers for on-signup profile creation

**Docs:**
- `docs/impact_model_v4.1.py` — Python scoring engine (15,700 lines)

---

## Key File Locations

### Entry Points

**API-Updated-:**
- `index.js` — Express app initialization, route mounting, error handling

**RT-Tool-Frontend:**
- `src/main.tsx` — React app entry; renders to DOM
- `src/App.tsx` — Root component initializing Redux and Router

**pixel-perfect-clone-60729:**
- `src/start.ts` — Client-side Vite entry
- `src/server.ts` — Server-side Cloudflare Workers entry
- `src/routes/__root.tsx` — Root layout (authentication, navigation)

### Configuration

**API-Updated-:**
- `.env` — DB_URL, API_KEY, JWT_SECRET (not committed)
- `package.json` — Dependencies and scripts

**RT-Tool-Frontend:**
- `.env.local` — VITE_API_KEY, VITE_API_URL (not committed)
- `vite.config.ts` — Build configuration
- `tsconfig.json` — TypeScript settings
- `tailwind.config.js` — Tailwind customization
- `.eslintrc.js` — Linting rules

**pixel-perfect-clone-60729:**
- `.env.local` — VITE_SUPABASE_URL, VITE_SUPABASE_PUBLISHABLE_KEY (not committed)
- `vite.config.ts` — TanStack Start configuration
- `tsconfig.json` — TypeScript settings
- `tailwind.config.js`, `prettier.config.cjs` — Code formatting

### Core Logic

**API-Updated-:**
- `models/player.js` — Main player schema definition
- `models/{AM,CB,CM,DM,FWD,LB,LW,RB,RW}.js` — Position-specific schemas
- `routes/playerRoutes.js` — Player CRUD and filtering logic
- `utils/fieldMapper.js` — CSV-to-schema mapping

**RT-Tool-Frontend:**
- `src/services/players/players.ts` — Player API service (search, filter, etc.)
- `src/services/axiosInstance.ts` — HTTP client with auth
- `src/state/reducer/` — Redux state management

**pixel-perfect-clone-60729:**
- `src/lib/domain.ts` — Player/Club types and POSITION_COMPONENTS
- `src/integrations/supabase/client.ts` — Database client
- `src/lib/deal-analysis.ts` — Transfer analysis logic

### Testing

**API-Updated-:**
- `package.json` has `"test": "echo \"Error: no test specified\""`
- No test files present

**RT-Tool-Frontend:**
- `package.json` has no test script
- No test files present

**pixel-perfect-clone-60729:**
- `package.json` has no test script
- No test files present

### Data/Datasets

**API-Updated-:**
- `dataset/Players.csv` — Player master data (~25MB)
- `dataset/Playstyles.csv` — Role classification
- `dataset/transferdata final.csv` — Transfer history (~6.7MB)
- `dataset/Positions/*.csv` — Per-position stat breakdowns (9 files)
- `dataset/Compatability Scores/*.csv` — Compatibility matrices

---

## Naming Conventions

### Files

**API-Updated-:**
- `.js` files for all code
- camelCase for file names (except middleware like auth.js)
- Examples: `playerRoutes.js`, `fieldMapper.js`

**RT-Tool-Frontend:**
- `.ts`, `.tsx` for code
- PascalCase for component files (e.g., `PlayerCard.tsx`, `Dashboard.tsx`)
- camelCase for utility files (e.g., `playerService.ts`, `axiosInstance.ts`)
- Examples: `src/pages/Dashboard.tsx`, `src/services/players/players.ts`

**pixel-perfect-clone-60729:**
- `.ts`, `.tsx` for code
- PascalCase for component/route files (e.g., `Dashboard.tsx`, `players.$playerId.tsx`)
- kebab-case for route directories (e.g., `_authenticated/`, with kebab-case route names)
- camelCase for utility/service files (e.g., `use-auth.tsx`, `domain.ts`)
- Examples: `src/routes/_authenticated/dashboard.tsx`, `src/lib/domain.ts`

### Directories

**API-Updated-:**
- Lowercase plural names: `routes/`, `models/`, `middleware/`, `utils/`, `dataset/`

**RT-Tool-Frontend:**
- Lowercase plural names: `src/pages/`, `src/components/`, `src/services/`, `src/state/`, `src/hooks/`, `src/types/`, `src/lib/`, `src/assets/`, `src/styles/`
- Nested logic by domain: `src/components/ui/`, `src/services/players/`, `src/services/auth/`, `src/state/reducer/`, `src/state/types/`

**pixel-perfect-clone-60729:**
- Lowercase plural names: `src/routes/`, `src/components/`, `src/hooks/`, `src/lib/`, `src/integrations/`
- Underscore prefixes for layout/grouping routes: `_root.tsx`, `_authenticated/`
- Dollar prefixes for dynamic route params: `players.$playerId.tsx`
- Kebab-case for file names in routes: `squad-planner.tsx`, `find-clubs.tsx`

### TypeScript/Functions

**RT-Tool-Frontend:**
- PascalCase for React components: `function Dashboard() {}`, `export const PlayerCard = ()`
- camelCase for functions/utils: `getPlayerById()`, `filterPlayers()`, `formatCurrency()`
- UPPER_CASE for constants: `const POSITIONS = [...]`, `const MAX_PLAYERS = 100`

**pixel-perfect-clone-60729:**
- Same as RT-Tool-Frontend
- Add `use` prefix for custom hooks: `useAuth()`, `useMobile()`

### Interfaces/Types

- PascalCase with optional `Type` suffix: `Player`, `Club`, `AppRole`, `PlayerType`
- Prefix enum types with `type` keyword: `type AppRole = "scout" | "analyst" | "director" | "admin"`

---

## Where to Add New Code

### New Feature in API-Updated-

1. **Data Model Changes:**
   - Create new Mongoose schema in `models/{FeatureName}.js`
   - Export from model file
   - Import in relevant route file

2. **New API Endpoint:**
   - Create/update route file in `routes/{featureName}Routes.js`
   - Define route handlers as middleware functions
   - Export router
   - Mount in `index.js` at appropriate `/path`

3. **CSV Data:**
   - Add CSV to `dataset/` folder
   - Update data loading script (if exists) or `index.js` to seed from CSV
   - Document column names in route handlers

### New Feature in RT-Tool-Frontend

1. **New Page:**
   - Create new `.tsx` file in `src/pages/{FeatureName}.tsx`
   - Implement as functional component
   - Add route in `App.tsx` or route config

2. **New Component:**
   - Create in `src/components/` (or `src/components/ui/` for reusable UI)
   - PascalCase file name matching component name
   - Import in page or parent component

3. **New Service/API Call:**
   - Create in `src/services/` (organize by domain, e.g., `src/services/deals/dealsService.ts`)
   - Export async functions calling `api.get()`, `api.post()`, etc.
   - Import service in page/component

4. **New State Management:**
   - Create reducer in `src/state/reducer/{feature}Reducer.ts`
   - Define actions and action creators
   - Integrate into Redux store in `App.tsx`

5. **New Custom Hook:**
   - Create in `src/hooks/use{FeatureName}.ts`
   - Use useState, useEffect, Redux hooks, service calls
   - Export as function prefixed with `use`

### New Feature in pixel-perfect-clone-60729

1. **New Route/Page:**
   - Create file in `src/routes/` following TanStack Router naming
   - For protected route: place under `_authenticated/` subdirectory
   - Use `.tsx` extension
   - Export `Route` object with `createFileRoute()`:
   ```typescript
   export const Route = createFileRoute('/_authenticated/newfeature')({
     component: NewFeatureComponent,
   });
   ```

2. **New Component:**
   - Create in `src/components/`
   - PascalCase file name
   - Import and use in route or parent component

3. **Database Access:**
   - Use `import { supabase } from "@/integrations/supabase/client"`
   - Call `supabase.from("table").select(...).eq(...)`
   - Wrap in TanStack Query `useQuery()` hook
   - Example in any `_authenticated/` route

4. **New Domain Type:**
   - Add to `src/lib/domain.ts`
   - Export as TypeScript interface or type
   - Reference throughout app

5. **Custom Hook:**
   - Create in `src/hooks/use{FeatureName}.ts`
   - Prefix with `use`
   - Can use Supabase client, TanStack Query, auth context

### New Feature Involving Scoring (Impact Model)

For Django backend (future), scoring logic should:

1. **Create Django App:**
   ```
   scoring/
   ├── models.py          # PlayerImpact, TeamAnalysis models
   ├── serializers.py     # Impact score output serialization
   ├── views.py           # API endpoints
   ├── services/
   │   ├── __init__.py
   │   ├── base_scoring.py        # Shared scoring utilities
   │   ├── position_scorers.py    # Position-specific calculators
   │   ├── standardization.py     # Z-score lookup and caching
   │   └── shortlist_generator.py # Shortlist orchestration
   ├── tests.py
   └── urls.py             # Route definitions
   ```

2. **Scoring Service Structure:**
   - One service class per position (GKScorer, CBScorer, etc.)
   - Shared base class with common methods
   - Cached standardization lookup (Redis)
   - Inputs: player stats row, std_lookup; outputs: impact, components

3. **API Endpoints:**
   - `POST /api/scoring/calculate-impact/` — Single player impact
   - `POST /api/scoring/calculate-bulk-impact/` — Multiple players
   - `POST /api/scoring/generate-shortlist/` — Generate ranked shortlist
   - `POST /api/scoring/team-analysis/` — Analyze team vs candidate

---

## Special Directories

**API-Updated-:**
- `dataset/` — Generated from initial CSV load; NOT normally edited after seeding
  - Committed: Yes (source-of-truth)
  - Generated: No (manual upload or data science team updates)

**RT-Tool-Frontend:**
- `dist/` — Built output
  - Committed: No
  - Generated: Yes (run `npm run build`)

**pixel-perfect-clone-60729:**
- `dist/` — Built output
  - Committed: No
  - Generated: Yes (run `npm run build`)
- `supabase/migrations/` — Database migration files
  - Committed: Yes
  - Generated: Manually via Supabase CLI
- `.lovable/` — Lovable platform configuration
  - Committed: Yes
  - Generated: By Lovable platform

---

## Module Boundaries for Django Port

When porting to Django, use these file/directory guidelines:

**Django Apps:**
- `scoring/` — Impact scoring engine (ported from Python)
- `players/` — Player data, CSV import, per-position models
- `clubs/` — Club data and analysis
- `shortlists/` — User shortlist management
- `watchlist/` — User watchlist
- `transfers/` — Transfer history and analysis
- `auth/` — User authentication and roles
- `api/` — REST API endpoints (DRF)

**Shared Utilities:**
- `core/utils/` — Shared helpers (formatting, validation, etc.)
- `core/constants.py` — POSITIONS, LEAGUE_MAPPING, etc.
- `core/middleware/` — Custom middleware

**Frontend Integration (TanStack Start connecting to Django):**
- Update `src/integrations/supabase/client.ts` to call Django API instead
- Create `src/integrations/django/client.ts` with Django API client
- Update routes to use new client

---

*Structure analysis: 2026-07-20*
