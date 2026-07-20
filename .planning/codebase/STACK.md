# Technology Stack

**Analysis Date:** 2026-07-20

## Overview

This codebase contains three sub-projects with distinct technology stacks:
1. **API-Updated-** - Legacy Node.js/Express REST API with MongoDB
2. **RT-Tool-Frontend** - Legacy React/Vite frontend (SPA)
3. **pixel-perfect-clone-60729** - Modern full-stack React framework with Supabase and Cloudflare Workers

---

## Project 1: API-Updated- (REST API)

### Languages

**Primary:**
- JavaScript (Node.js) - Backend API implementation
  - Entry point: `index.js` (port 3000)
  - Model definitions: `models/*.js` (position-specific models using Mongoose)
  - Routes: `routes/*.js` (players, compatibility, transfers, positions, playstyles, shortlists, users)

### Runtime

**Environment:**
- Node.js (version not pinned in package.json)

**Package Manager:**
- npm
- Lockfile: `package-lock.json` present

### Frameworks

**Core:**
- Express.js 4.21.1 - HTTP server framework
  - CORS enabled globally
  - API key middleware: `middleware/apikey.js` (currently disabled)
  - Bearer token authentication via JWT
  - Health check endpoint: `GET /healthcheck`

**Database:**
- Mongoose 8.7.1 - MongoDB ODM
  - Connection: MongoDB Atlas via `process.env.DB_URL`
  - Models for: Player, User, Shortlist, Playstyle, TransferData, Position-specific (AM, CB, CM, DM, FWD, LB, LW, RB, RW)
  - Key collections: players, users, shortlists, playstyles, transferData, compatibilityScores

### Key Dependencies

**Critical:**
- bcryptjs 2.4.3 - Password hashing
- jsonwebtoken 9.0.2 - JWT encoding/decoding for auth
- dotenv 16.4.5 - Environment variable loading

**Development:**
- nodemon 3.1.7 - Auto-restart on file changes

### Configuration

**Environment:**
- `.env` file (not included, requires setup)
- Required vars: `DB_URL`, `JWT_SECRET`, `API_KEY`

**Server:**
- Listens on `localhost:3000` in development
- Trusts nginx proxy via `app.set('trust proxy', 1)` for production
- Request logging middleware logs method, URL, and timestamp

### Data

**Dataset Files:**
- `dataset/Players.csv` (~25MB) - Player statistics
- `dataset/Playstyles.csv` - Playstyle definitions
- `dataset/transferdata final.csv` (~7MB) - Transfer history
- `dataset/Compatability Scores/` - Position-specific compatibility data
- `cs_field_mapping.json` - Field mapping configuration

---

## Project 2: RT-Tool-Frontend (React SPA)

### Languages

**Primary:**
- TypeScript 5.5.3 - Type-safe React development
  - Entry point: `src/main.tsx`
  - Source directory: `src/`

**Secondary:**
- JSX/TSX - React component syntax

### Runtime

**Environment:**
- Browser/Node.js for build

**Package Manager:**
- npm
- Type: `"module"` (ES modules)

### Frameworks

**Core:**
- React 18.3.1 - UI framework
- Vite 5.4.8 - Build tool and dev server
  - Config: `vite.config.ts` (simple Vite + React plugin setup)
  - Alias: `@/*` → `./src/*`

**State & Data Fetching:**
- TanStack React Query 5.83.0 - Server state management
  - Query synchronization storage persister
  - Persist client for offline support
- React Hook Form 7.53.1 - Form state management
  - @hookform/resolvers 3.9.1 - Integration with validation schemas

**Validation:**
- yup 1.4.0 - Schema validation

**UI Components:**
- Radix UI components (multiple):
  - react-avatar, react-checkbox, react-dialog, react-label, react-popover
  - react-select, react-slider, react-slot, react-switch, react-tabs
- Lucide React 0.447.0 - Icon library
- tailwind-merge 2.5.3 - Utility class merging
- class-variance-authority 0.7.0 - Component variant system
- clsx 2.1.1 - Conditional className utility

**Data Visualization:**
- Chart.js 4.4.6 - Charting library
- react-chartjs-2 5.2.0 - React wrapper for Chart.js
- Recharts 2.12.7 - React charting library
- multi-range-slider-react 2.0.7 - Range slider component

**HTTP Client:**
- axios 1.7.7 - HTTP requests (configured in `src/services/axiosInstance.ts`)
  - Base URL: `http://localhost:3000`
  - Headers: x-api-key (from VITE_API_KEY), Authorization (Bearer token)
  - Interceptors: Auto-attach Bearer token from auth service

**Utilities:**
- file-saver 2.0.5 - File download utility
- xlsx 0.18.5 - Excel file handling
- react-toastify 10.0.6 - Toast notifications
- react-joyride 2.9.3 - User onboarding tours
- react-loading 2.0.3 - Loading spinners
- cmdk 1.0.0 - Command palette component

### Build & Dev

**Build:**
- TypeScript 5.5.3 - Compilation (`tsc -b`)
- Vite build target: browser

**Styling:**
- TailwindCSS 3.4.13 - Utility-first CSS
  - Config: `tailwind.config.js`
- PostCSS 8.4.47 - CSS processing
  - Config: `postcss.config.js`
- autoprefixer 10.4.20 - Browser vendor prefixes
- tailwindcss-animate 1.0.7 - Animation utilities

**Linting & Formatting:**
- ESLint 9.11.1
  - Config: `eslint.config.js`
  - Plugins: react-hooks, react-refresh
- TypeScript ESLint 8.7.0

### Configuration

**Environment:**
- `.env*` files for build-time variables
- Prefix: `VITE_*` (available at runtime via import.meta.env)
- Key var: `VITE_API_KEY` (API key for backend)

**tsconfig:**
- `tsconfig.json` references separate `tsconfig.app.json` and `tsconfig.node.json`
- Target: ES2022
- Module: ESNext
- Path alias: `@/*` → `./src/*`

### Architecture

**Service Layer:**
- `src/services/axiosInstance.ts` - Axios configuration and interceptors
- `src/services/auth/` - Authentication services (signin, signup, transfers)
- `src/services/players/` - Player data services
- `src/services/util.ts` - Token retrieval and utility functions

**Type Definitions:**
- `src/types/apiTypes.ts` - API response interfaces (Player, Shortlist, TransferData, etc.)

---

## Project 3: pixel-perfect-clone-60729 (Full-Stack TanStack Start)

### Languages

**Primary:**
- TypeScript 5.8.3 - Type-safe full-stack development
  - Target: ES2022
  - Entry points: `src/start.ts` (client), `src/server.ts` (SSR handler)

**Secondary:**
- JSX/TSX - React component syntax
- Python 3.x - Data science layer
  - `docs/impact_model_v4.1.py` - Pandas/NumPy scoring engine (~552KB)

### Runtime

**Client:**
- Browser / Vite dev server

**Server:**
- Cloudflare Workers (via Nitro/TanStack Start)
- Node.js compatibility layer enabled

**Package Manager:**
- npm
- Type: `"module"` (ES modules)
- Lockfile: `package-lock.json` present

### Frameworks

**Core:**
- React 19.2.0 - UI framework
- TanStack Start 1.167.50 - Full-stack meta-framework
  - Server function integration for SSR
  - Server routes and middleware support
  - Automatic code splitting and streaming

**Build & Dev:**
- Vite 7.3.1 - Build tool
  - Config: `vite.config.ts` (uses @lovable.dev/vite-tanstack-config)
  - Special plugins auto-included: tanstackStart, viteReact, tailwindcss, tsConfigPaths, cloudflare (build-only), componentTagger, error-logger
- Nitro 3.0.260603-beta - Server runtime
  - Handles SSR and server functions

**Deployment:**
- Cloudflare Workers (via @cloudflare/vite-plugin 1.25.5)
  - Config: `wrangler.jsonc`
  - Compatibility date: 2025-09-24
  - Compatibility flags: nodejs_compat (enables Node.js polyfills)
  - Entry point: `src/server.ts`

**Routing:**
- TanStack React Router 1.168.25 - File-based routing
  - Route plugin: @tanstack/router-plugin 1.167.28
  - File structure: `src/routes/*.tsx` (nested routes)
  - Authenticated routes: `src/routes/_authenticated.tsx` with route guard

**State & Data Fetching:**
- TanStack React Query 5.83.0 - Server state management
  - Used on client for caching and sync

**Validation:**
- zod 3.24.2 - Schema validation library

**UI Components:**
- Radix UI (comprehensive set):
  - Accordion, alert-dialog, aspect-ratio, avatar, checkbox, collapsible
  - Context-menu, dialog, dropdown-menu, hover-card, label, menubar
  - Navigation-menu, popover, progress, radio-group, scroll-area, select
  - Separator, slider, slot, switch, tabs, toggle, toggle-group, tooltip
- Lucide React 0.575.0 - Icon library
- Embla Carousel React 8.6.0 - Carousel component
- Input OTP 1.4.2 - OTP input component
- Vaul 1.1.2 - Drawer component
- Sonner 2.0.7 - Toast notifications
- React Day Picker 9.14.0 - Date picker
- React Resizable Panels 4.6.5 - Resizable split panels

**Data Visualization:**
- Recharts 2.15.4 - React charting library

**Forms:**
- React Hook Form 7.71.2 - Form state management
  - @hookform/resolvers 5.2.2 - Validation schema integration
  - Integrates with zod for validation

**Styling:**
- TailwindCSS 4.2.1 - Utility-first CSS
  - @tailwindcss/vite 4.2.1 - Vite plugin for v4
  - Config: auto-included in vite-tanstack-config
- tailwind-merge 3.5.0 - Utility class merging
- class-variance-authority 0.7.1 - Component variant system
- clsx 2.1.1 - Conditional className utility
- tw-animate-css 1.3.4 - Animation utilities

**Other Utilities:**
- date-fns 4.1.0 - Date manipulation
- vite-tsconfig-paths 6.0.2 - TypeScript paths resolution

### Database & Backend Integration

**Supabase (PostgreSQL):**
- @supabase/supabase-js 2.105.4 - Supabase JavaScript client
  - Client initialization: `src/integrations/supabase/client.ts`
  - Server admin client: `src/integrations/supabase/client.server.ts` (uses service role key)
  - Auth middleware: `src/integrations/supabase/auth-middleware.ts`
  - Auth attacher: `src/integrations/supabase/auth-attacher.ts`
  - Type definitions: `src/integrations/supabase/types.ts` (auto-generated)

**Authentication:**
- Supabase Auth (session-based)
  - Client-side: localStorage persistence, auto token refresh
  - Server-side: Bearer token validation via middleware
  - Auth context provider: `src/hooks/use-auth.tsx`
  - Login/signup routes: `src/routes/login.tsx`, `src/routes/signup.tsx`

**Cloud/External:**
- @lovable.dev/cloud-auth-js 1.1.2 - Lovable Cloud authentication
- @lovable.dev/vite-tanstack-config 2.3.2 - Vite configuration preset

### Configuration

**Environment (Client):**
- `VITE_SUPABASE_URL` - Supabase project URL
- `VITE_SUPABASE_PUBLISHABLE_KEY` - Supabase public/anon key

**Environment (Server):**
- `SUPABASE_URL` - Supabase project URL
- `SUPABASE_PUBLISHABLE_KEY` - Supabase public key (server-side)
- `SUPABASE_SERVICE_ROLE_KEY` - Supabase admin key (SSR/server functions)

**TypeScript:**
- `tsconfig.json`
- Target: ES2022
- Module: ESNext
- Path alias: `@/*` → `./src/*`
- Strict mode enabled

### Linting & Formatting

**ESLint:**
- Version 9.32.0
- Config: `eslint.config.js`
- Plugins: react-hooks, react-refresh, prettier
- Extends: @eslint/js, typescript-eslint

**Prettier:**
- Version 3.7.3
- Config: auto-included in vite-tanstack-config
- Integrated with ESLint via eslint-plugin-prettier

### Error Handling & Monitoring

**Error Capture:**
- `src/lib/error-capture.ts` - SSR error collection
- `src/lib/error-page.ts` - Branded error page rendering
- Server.ts handles catastrophic SSR errors, returns branded 500 page

### Data Science Layer

**Python Scoring Engine:**
- Location: `docs/impact_model_v4.1.py`
- Size: ~552KB
- Dependencies:
  - pandas - DataFrames and data manipulation
  - numpy - Numerical operations
  - scikit-learn - Machine learning (RandomForestRegressor, preprocessing, pipelines)
  - difflib - String matching for player names
  - re, unicodedata - String processing
  - openpyxl - Excel export
  - IPython.display - Jupyter integration

**Key Functions:**
- Position-specific component analysis
- Impact scoring and deltas vs team/league/best player
- Export to Excel with position-aware columns
- Similarity matching between players
- Contract fit scoring
- Transfer probability calculation

---

## Platform Requirements

### Development

**API-Updated-:**
- Node.js (version unspecified, assume 14+)
- MongoDB Atlas account (cloud database)

**RT-Tool-Frontend:**
- Node.js 18+
- npm 9+

**pixel-perfect-clone-60729:**
- Node.js 18+
- npm 9+
- Wrangler CLI (for local Cloudflare Workers testing)
- Python 3.8+ (for scoring engine, if running locally)

### Production

**API-Updated-:**
- Node.js server deployment
- Nginx reverse proxy (configured in index.js trust proxy setting)
- MongoDB Atlas connection

**RT-Tool-Frontend:**
- Static hosting (SPA) or Node.js server for serving
- API endpoint: `http://localhost:3000` (hardcoded, would need env var in production)

**pixel-perfect-clone-60729:**
- Cloudflare Workers (via wrangler deploy)
- Supabase project (database + auth)
- Service role key required for server operations

---

*Stack analysis: 2026-07-20*
