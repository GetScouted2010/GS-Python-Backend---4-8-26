# External Integrations

**Analysis Date:** 2026-07-20

---

## Overview

This codebase integrates with multiple external services across three sub-projects. The key architectural decision: legacy REST API (MongoDB) will be replaced by Django backend serving a modern SPA and TanStack Start app that currently uses Supabase.

---

## Project 1: API-Updated- (REST API)

### Data Storage

**Database:**
- **MongoDB Atlas (Cloud)**
  - Connection: Via `process.env.DB_URL` (MongoDB connection string)
  - Client: Mongoose 8.7.1 ODM
  - Collections:
    - `players` - Player statistics and profiles
    - `users` - User accounts with hashed passwords
    - `shortlists` - User-created player shortlists
    - `playstyles` - Team playstyle definitions
    - `transferData` - Historical transfer records
    - `compatibilityScores` - Position-specific compatibility metrics (AM, CB, CM, DM, FWD, LB, LW, RB, RW)

**CSV Data Sources:**
- Imported into MongoDB from flat files:
  - `dataset/Players.csv` (~25MB) - Base player statistics
  - `dataset/Playstyles.csv` - Team/league playstyle data
  - `dataset/transferdata final.csv` (~7MB) - Historical transfers
  - `dataset/Compatability Scores/` - Position-specific scoring matrices
- Field mapping config: `cs_field_mapping.json` (defines column aliases/transformations)

**File Storage:**
- Local filesystem only (CSV files committed to repo)
- No cloud file storage service

### Authentication & Authorization

**Method:** JWT-based token authentication

**Flow:**
1. User registers/logs in via `POST /users/register` or `POST /users/login`
2. Password hashing: bcryptjs 2.4.3
3. JWT token generated using `process.env.JWT_SECRET`
4. Client sends Bearer token in `Authorization: Bearer <token>` header
5. All protected routes require valid JWT (extracted and verified)

**Implementation:**
- Token generation/validation: jsonwebtoken 9.0.2
- Middleware in `middleware/apikey.js` (currently disabled/commented)
- User extraction from JWT claims

**API Key Middleware:**
- Location: `middleware/apikey.js`
- Status: Disabled (commented out as of 22.07.2025)
- Expected implementation: `x-api-key` header validation against `process.env.API_KEY`

### Environment Configuration

**Required Env Vars:**
- `DB_URL` - MongoDB Atlas connection string
- `JWT_SECRET` - Secret for signing JWT tokens
- `API_KEY` - API key for header validation (currently unused)

**Secrets Location:**
- `.env` file in project root (not committed, requires manual setup)
- File format specified in README.md

### API Endpoints

**User Routes:**
- `POST /users/register` - Create account (no auth required)
- `POST /users/login` - Get JWT token (no auth required)
- `GET /users/getTeamsList` - List teams for registration (no auth required)
- `GET /users/getUser` - Get current user profile (JWT required)
- `PUT /users/update` - Update user profile (JWT required)

**Player Routes:**
- `GET /players/getAll` - All players (JWT required)
- `GET /players/get/:id` - Single player by UniqueID (JWT required)
- `GET /players/find` - Query players by parameters (JWT required)
- `GET /players/search` - Search players and teams by name (JWT required)
- `GET /players/filter` - Advanced filtering with >=, <= operators (JWT required)
- `GET /players/csfilter` - Filtered search with pagination (JWT required)

**Shortlist Routes:**
- `GET /shortlists/getList` - User's shortlists (JWT required)
- `POST /shortlists/createList` - Create new shortlist (JWT required)
- `POST /shortlists/addToList` - Add player to shortlist (JWT required)
- `POST /shortlists/removeFromList` - Remove player from shortlist (JWT required)
- `GET /shortlists/getList/:id` - Get specific shortlist (JWT required)
- `POST /shortlists/deleteList` - Delete shortlist (JWT required)
- `GET /shortlists/searchList` - Search players in shortlist (JWT required)

**Compatibility Routes:**
- Detailed routes not shown in README, but compatibilityScores.js model exists

**Position Routes:**
- Position-specific endpoint (likely for role-based filtering)

**Playstyle Routes:**
- Playstyle definition endpoints

**Transfer Routes:**
- Transfer data queries

**Health Check:**
- `GET /healthcheck` - No auth required, returns `{ status: 'OK' }`

### Network & Deployment

**Development:**
- Runs on `http://localhost:3000`
- Auto-restart via nodemon on file changes
- Direct connections to MongoDB Atlas

**Production:**
- Nginx reverse proxy configured (indicated by `app.set('trust proxy', 1)`)
- Deployment strategy not specified (could be VPS, container, Platform-as-a-Service)
- Requires MongoDB Atlas accessible from production environment

### Error Handling

**Pattern:**
- Express error middleware catches errors
- Returns JSON: `{ error: message }`
- HTTP status codes included in response

---

## Project 2: RT-Tool-Frontend (React SPA)

### Backend Integration

**REST API Client:**
- Location: `src/services/axiosInstance.ts`
- Library: axios 1.7.7
- Base URL: `http://localhost:3000` (hardcoded - **issue for production**)
- Timeout: 50 seconds

**Request Headers:**
- `Content-Type: application/json`
- `x-api-key` - From `import.meta.env.VITE_API_KEY` (build-time variable)
- `Authorization` - Bearer token auto-attached via request interceptor

**Interceptors:**
- Request: Auto-injects Bearer token from auth service (`getToken()` from util.ts)
- Response: Commented-out token refresh logic (not implemented)

**Authentication:**
- Token source: Auth service (`src/services/auth/util.ts`)
- Method: `getToken()` retrieves stored JWT
- Flow: User logs in → token stored → auto-attached to all requests
- Token refresh: Not implemented (commented code shows intended pattern)

### Service Layer

**API Services:**
- `src/services/auth/signin.ts` - Login request
- `src/services/auth/signup.ts` - Registration request
- `src/services/players/players.ts` - Player queries (search, filter, get)
- `src/services/players/playstyles.ts` - Playstyle queries
- `src/services/auth/transfers.ts` - Transfer data requests
- `src/services/shortlist.ts` - Shortlist management (get, create, add, remove)
- `src/services/util.ts` - Token management, utility functions

### Type Definitions

**File:** `src/types/apiTypes.ts`

**Interfaces:**
- `Player` - Player object with dynamic fields
- `SearchResponse` - Combines players and teams
- `FilteredPlayersResponse` - Paginated player results
- `TransferData` - Transfer record schema
- `Shortlist` - User-created shortlist
- `CreateShortlistResponse`, `UpdateShortlistResponse`, `GetShortlistsResponse` - API responses

### Environment Configuration

**Client Build-time Variables:**
- `VITE_API_KEY` - API key for backend `/players/*` endpoints
- Injected at build time via Vite
- Accessed via `import.meta.env.VITE_API_KEY`

**Secrets Location:**
- `.env*` files (local development)
- Build system handles injection into compiled bundle

### File Export Capabilities

**Supported:**
- Excel export (.xlsx) via xlsx 0.18.5 and file-saver 2.0.5
- CSV-like exports for reporting

**Not Shown:**
- Backend-side export endpoints (likely provided by API-Updated-)

### Monitoring & Error Handling

**Toast Notifications:**
- react-toastify 10.0.6 for user feedback
- Error messages can be displayed to user

**Logging:**
- Browser console logging (default React dev behavior)
- No centralized error tracking service detected

---

## Project 3: pixel-perfect-clone-60729 (Full-Stack TanStack Start)

### Database & Backend

**Supabase (PostgreSQL):**
- Service: Hosted PostgreSQL + Auth + Realtime
- Connection:
  - **Client-side:** `src/integrations/supabase/client.ts`
    - Uses `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY`
    - Persists session to localStorage
    - Auto-refresh tokens enabled
  - **Server-side:** `src/integrations/supabase/client.server.ts`
    - Uses `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` (admin access)
    - No session persistence, no auto-refresh
    - Used only in SSR/server functions (bypasses RLS)

**Database Schema:**
- Type definitions auto-generated: `src/integrations/supabase/types.ts`
- Tables/relationships not detailed in codebase (generated from Supabase)
- RLS (Row-Level Security) enforced for user-authenticated queries

**Caching:**
- None detected (Supabase real-time or TanStack Query client-side caching)

### Authentication & Authorization

**Method:** Supabase Auth (OAuth/password-based)

**Client-side Flow:**
- Provider: `src/hooks/use-auth.tsx` (AuthProvider + useAuth hook)
- Session management: Supabase automatically handles via SDK
- Auth state listener: `supabase.auth.onAuthStateChange()`
- Session retrieval: `supabase.auth.getSession()`
- Storage: localStorage (browser-only, cleared on logout)

**Server-side Flow:**
- Middleware: `src/integrations/supabase/auth-middleware.ts`
- Implementation: `requireSupabaseAuth` middleware
- Token extraction: `Authorization: Bearer <token>` header
- Token validation: `supabase.auth.getClaims(token)` verifies JWT
- User context attached: `userId` and `claims` passed to server functions

**Route Protection:**
- Authenticated routes: `src/routes/_authenticated.tsx`
- Conditional rendering based on `useAuth().isAuthenticated`

**User Routes:**
- `src/routes/login.tsx` - Login form with Supabase auth
- `src/routes/signup.tsx` - Registration form with Supabase auth

### Server-Side Integration

**Server Framework:**
- Nitro (via TanStack Start)
- Environment: Cloudflare Workers
- File: `src/server.ts` (entry point for SSR)

**Error Handling:**
- Catastrophic SSR error detection and branded error page
- Error capture utility: `src/lib/error-capture.ts`
- Custom error page: `src/lib/error-page.ts`

### Environment Configuration

**Client (Vite Build-time):**
- `VITE_SUPABASE_URL` - Supabase project URL
- `VITE_SUPABASE_PUBLISHABLE_KEY` - Public/anon key (client-safe)

**Server (Runtime):**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_PUBLISHABLE_KEY` - Public key (server access)
- `SUPABASE_SERVICE_ROLE_KEY` - Secret admin key (server-only)

**Secrets Location:**
- `.env` file (local development)
- Environment variables set in Cloudflare Workers dashboard
- Lovable Cloud integration handles env var setup

### Deployment & Infrastructure

**Hosting:**
- Cloudflare Workers (serverless)
- Deployment tool: Wrangler CLI
- Config file: `wrangler.jsonc`
  - Name: `tanstack-start-app`
  - Compatibility date: 2025-09-24
  - Flags: `nodejs_compat` (enables Node.js polyfills for Cloudflare environment)
  - Main entry: `src/server.ts`

**Build Target:**
- Vite builds for Cloudflare Workers runtime
- @cloudflare/vite-plugin handles integration
- Output: Workers-compatible bundle

### Integration with Lovable Platform

**Purpose:**
- Lovable Cloud provides IDE/hosting/deployment orchestration
- Auto-generates Supabase type definitions and middleware
- Handles environment variable injection

**Components:**
- @lovable.dev/vite-tanstack-config - Preset Vite config with required plugins
- @lovable.dev/cloud-auth-js - Authentication integration
- Auto-generated files (marked "Do not edit directly"):
  - `src/integrations/supabase/client.ts`
  - `src/integrations/supabase/client.server.ts`
  - `src/integrations/supabase/auth-middleware.ts`
  - `src/integrations/supabase/types.ts`

### Data Operations

**Scoring Engine:**
- Location: `docs/impact_model_v4.1.py` (Python)
- Purpose: Pandas-based player impact scoring and compatibility analysis
- Execution: Likely triggered by TanStack Start server functions
- Output: Excel exports with position-specific metrics

**Export Capabilities:**
- Can generate Excel files with player impact data
- Position-aware columns (Offensive, Defensive, Passing, etc.)
- Compatibility scores, deltas vs team/league averages
- Similarity matching between players

### Monitoring & Error Handling

**Error Tracking:**
- Custom error capture: `src/lib/error-capture.ts`
- Branded error page for SSR failures
- Console logging (development)
- No third-party error tracking service configured

**Observability:**
- Browser console (client)
- Cloudflare Workers logs (server)

---

## Cross-Project Integration Points

### Data Migration Strategy

**Current State:**
- API-Updated-: MongoDB with CSV-sourced data
- pixel-perfect-clone-60729: Supabase PostgreSQL (newer, empty/mock data)
- RT-Tool-Frontend: Consumes API-Updated- REST API

**Future State (New Django Backend):**
- Django backend will replace MongoDB REST API
- Must migrate datasets from CSV and MongoDB
- Must migrate user data (accounts, shortlists)
- Must maintain compatibility scores and compatibility logic
- Scoring engine (`impact_model_v4.1.py`) must be integrated with Django

**Migration Path:**
1. Export data from MongoDB and CSV
2. Transform to Django models
3. Load into PostgreSQL (via Django ORM)
4. Maintain Supabase compatibility for pixel-perfect-clone auth

### Frontend Communication

**RT-Tool-Frontend:**
- Currently: REST API at `http://localhost:3000` (hardcoded)
- After Django: Will consume new Django API endpoints
- Must update `src/services/axiosInstance.ts` base URL
- JWT-based auth compatible with Django

**pixel-perfect-clone-60729:**
- Currently: Supabase for data + auth
- After migration: Could consume Django API via SSR server functions
- Supabase auth can remain (or switch to Django-based)
- TanStack Start server functions can bridge Supabase → Django

### Authentication Harmonization

**Current Misalignment:**
- API-Updated-: JWT with `JWT_SECRET`
- pixel-perfect-clone-60729: Supabase Auth (OAuth/JWTs)
- RT-Tool-Frontend: Consumes both (via axios interceptor)

**Options for Django Backend:**
1. Keep JWT-based (similar to API-Updated-)
2. Integrate with Supabase Auth (via Supabase PostgreSQL + admin API)
3. Hybrid: Support both token types

### Scoring Engine Integration

**Current:**
- `docs/impact_model_v4.1.py` - Python/pandas/sklearn
- Likely executed via Jupyter or imported as module
- Output: Excel files with player metrics

**Integration with Django:**
- Can be called as subprocess/celery task
- Can be embedded in Django app (via Django views)
- Can remain separate, triggered by scheduler or API
- Output: JSON API responses or Excel downloads

---

## Third-Party Services Summary

| Service | Project | Purpose | Auth Method | Status |
|---------|---------|---------|-------------|--------|
| MongoDB Atlas | API-Updated- | Player/user data | Connection string | Active |
| Supabase | pixel-perfect-clone-60729 | PostgreSQL + Auth | API keys | Active |
| Cloudflare Workers | pixel-perfect-clone-60729 | Serverless hosting | Wrangler token | Active |
| Lovable Cloud | pixel-perfect-clone-60729 | IDE/deployment | Lovable account | Active |

---

*Integration audit: 2026-07-20*
