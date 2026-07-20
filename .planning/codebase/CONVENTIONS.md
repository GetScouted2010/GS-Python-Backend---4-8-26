# Coding Conventions

**Analysis Date:** 2026-07-20

## Project Overview

This codebase contains three sub-projects with different language and framework conventions:
1. **API-Updated-**: Node.js/Express REST API with MongoDB (Mongoose)
2. **RT-Tool-Frontend**: React + Vite + TypeScript frontend
3. **pixel-perfect-clone-60729**: React + TanStack Start + TypeScript prototype
4. **docs/impact_model_v4.1.py**: Large Python pandas-based scoring engine (~15,700 lines)

---

## 1. API-Updated- (Node.js/Express/MongoDB)

### Naming Patterns

**Files:**
- kebab-case for filenames: `playerRoutes.js`, `userRoutes.js`, `fieldMapper.js`
- Mongoose models: PascalCase (e.g., `player.js`, `users.js`)
- Middleware files: camelCase (e.g., `auth.js`, `apikey.js`)

**Functions:**
- camelCase for all function names
- Examples from `utils/fieldMapper.js`:
  - `getOriginalFieldName(sanitizedFieldName)`
  - `getSanitizedFieldName(originalFieldName)`
- Examples from `routes/playerRoutes.js`:
  - `findTeamLeague(teamName)`
  - `calculateFinancialFit(teamField, position, playerData, customMarketValue)`

**Variables:**
- camelCase for local variables and parameters
- Example: `financialFit`, `externalData`, `customMarketValue`

**Database Field Naming (Mongoose Schemas):**
- **PascalCase with underscores** for player/performance data fields
- Used in `models/player.js`: `Total_Score`, `Market_value`, `Contract_expires`, `Matches_played`, `Minutes_played`, `Successful_defensive_actions_per_90`, `Aerial_duels_won_percentage`, `xG_against`
- **camelCase** for user-related fields
- Used in `models/users.js`: `username`, `firstname`, `lastname`, `email`, `team`, `role`
- **Key pattern**: Field names use underscores to separate words for readability in long technical metric names (sport stats)

**Constants:**
- UPPER_SNAKE_CASE for configuration mappings
- Example from `routes/playerRoutes.js`:
  ```javascript
  const positionMapping = { "AMF": "AM", "CB": "CB", ... }
  const leagueMapping = { "Allsvenskan (Sweden)": [...], ... }
  const MIN_MINUTES_FOR_AVG = 0
  ```

### Code Style

**Formatting:**
- No explicit formatter configured (no Prettier or ESLint in package.json)
- Indentation appears to be 2 spaces
- Semicolons used at end of statements

**Linting:**
- No ESLint configured
- No explicit style rules enforced

**Import Organization:**
Order observed in `routes/playerRoutes.js` and `index.js`:
1. Built-in Node modules (`require('express')`)
2. Third-party packages (`bcryptjs`, `cors`, `dotenv`, `mongoose`, `jsonwebtoken`)
3. Local modules (relative paths like `./middleware/auth`, `../models/player`)

### Error Handling

**Pattern:**
- Simple try/catch blocks in route handlers
- Error responses use JSON format: `res.status(statusCode).json({ error: 'Message' })`
- Example from `middleware/auth.js`:
  ```javascript
  if (!token) {
    return res.status(403).json({ error: 'No token provided' });
  }
  jwt.verify(token.split(' ')[1], process.env.JWT_SECRET, (err, decoded) => {
    if (err) {
      return res.status(403).json({ error: 'Invalid token' });
    }
  });
  ```
- Global error handler middleware in `index.js`:
  ```javascript
  app.use((err, req, res, next) => {
    const status = err.status || 500;
    const message = err.message || 'Internal Server Error';
    res.status(status).json({ error: message });
  });
  ```

### Logging

**Framework:** Native `console` object
- `console.log()` for info messages
- `console.error()` for errors
- Example: `console.log(req.method, req.url, new Date())` in logging middleware

### Comments

**When to Comment:**
- Commented-out code blocks for disabled features (e.g., API key validation in `middleware/apikey.js`)
- Inline comments explaining complex logic
- Section headers with comment dividers

**Example from `routes/playerRoutes.js`:**
```javascript
// TO DO - Move mapping data to individual files for ease of updating and readability

// Configure Position Mapping
const positionMapping = { ... }
```

### Module Design

**Exports:**
- Named exports where useful, default exports for models
- Example: `module.exports = { getOriginalFieldName, getSanitizedFieldName }`
- Mongoose models: `module.exports = mongoose.model("Player", playerSchema)`

---

## 2. RT-Tool-Frontend (React/Vite/TypeScript)

### Naming Patterns

**Files:**
- PascalCase for React components: `PlayerCard.tsx`, `PlayerHeader.tsx`, `Navbar.tsx`
- camelCase for utility/service files: `players.ts`, `playerReducerTypes.ts`
- kebab-case for custom components within `components/ui/`: (if following shadcn pattern)

**Functions/Components:**
- PascalCase for React functional components: `PlayerSpecificSearchBox`, `PlayingstylesTable`, `PlayerCard`
- camelCase for utility functions: `searchPlayers()`, `handleInputChange()`, `handleSearch()`

**Variables:**
- camelCase for all variables: `searchTerm`, `setSearchTerm`, `isSearchLoading`, `setIsLoading`
- camelCase for state variables: `searchResults`, `setSearchResults`

**Types/Interfaces:**
- PascalCase for interface names: `Shortlist`, `CreateShortlistResponse`, `Player`, `SearchResponse`, `TransferData`
- Example from `types/apiTypes.ts`:
  ```typescript
  export interface Shortlist {
    _id: string;
    listName: string;
    players: string[];
  }
  
  export interface TransferStats {
    min: number | null;
    max: number | null;
    avg: number | null;
  }
  ```

**Constants:**
- camelCase or UPPER_CASE depending on context
- Used in type definitions and mock data

### Code Style

**Formatting:**
- No explicit Prettier configuration (none in `package.json`)
- TypeScript compiled to strict standards
- Indentation: 2 spaces (inferred from tsconfig and code)

**Linting:**
- ESLint configured in `eslint.config.js`
- Extends `@eslint/js` and `typescript-eslint` configs
- Includes React-specific plugins: `react-hooks`, `react-refresh`
- Rules enforced:
  - React Hooks conventions (dependency arrays, hook ordering)
  - React Refresh safe exports

**Import Organization:**
Order observed in `PlayerSpecificSearchBox.tsx`:
1. React and external UI library imports: `"use client"`, `import * as React`, `lucide-react`
2. Local utility imports: `@/lib/utils`, `@/components/ui/`
3. Service/API imports: `@/services/players/players`
4. Navigation imports: `react-router-dom`

### Error Handling

**Pattern:**
- Async/await with try/catch/finally
- Example from `PlayerSpecificSearchBox.tsx`:
  ```typescript
  try {
    const results = await searchPlayers(searchTerm);
    if (results.status === 200) {
      setSearchResults(results.data.Players);
    }
  } catch (err) {
    console.error("Search error:", err);
  } finally {
    setIsLoading(false);
  }
  ```
- Error objects logged to console
- User-facing errors handled through UI state updates (loading states, empty states)

### Logging

**Framework:** Native `console` object
- `console.log()` for debugging
- `console.error()` for error reporting
- Pattern: `console.error("Search error:", err)`

### Comments

**When to Comment:**
- JSDoc-style comments for complex hooks and utilities (not extensively used)
- Inline comments explaining UI behavior or debounce logic
- TODO comments for future work

### Function Design

**Size:** Most functions are compact (10-30 lines)
**Parameters:** Props passed as destructured object parameters
**Return Values:** Components return JSX, hooks return state/functions

---

## 3. pixel-perfect-clone-60729 (React/TanStack Start/TypeScript)

### Naming Patterns

**Files:**
- kebab-case for route files: `club-context-cards.tsx`, `use-mobile.tsx`, `use-auth.tsx`
- camelCase for lib/utility files: `utils.ts`, `domain.ts`, `error-capture.ts`
- File structure follows TanStack Router convention: `routes/`, `components/`, `lib/`, `hooks/`

**Functions/Components:**
- PascalCase for React components: `ClubContextCards`, `NotFoundComponent`, `ErrorComponent`
- camelCase for utility and hook functions: `formatMoney()`, `topStyles()`, `cn()`

**Variables:**
- camelCase for all variables and parameters
- Example from `club-context-cards.tsx`:
  ```typescript
  export type ClubContextStats = {
    avgAge: number | null;
    avgMV: number | null;
    medianFee: number | null;
    countries: string[];
    style: TeamStyle | null;
  };
  ```

**Types/Interfaces:**
- PascalCase for type definitions: `ClubContextStats`, `TeamStyle`
- Suffixes used: `Stats`, `Response`, `Props`

### Code Style

**Formatting:**
- **Prettier** configured in `.prettierrc`:
  ```json
  {
    "printWidth": 100,
    "semi": true,
    "singleQuote": false,
    "trailingComma": "all"
  }
  ```
- Double quotes for strings, trailing commas in multiline structures
- Line width limit: 100 characters

**Linting:**
- ESLint configured in `eslint.config.js`
- Integrates Prettier: `eslintPluginPrettier`
- Extends `@eslint/js` and `typescript-eslint`
- React-specific rules for hooks and refresh
- Rule: `"@typescript-eslint/no-unused-vars": "off"` (disabled, likely via Prettier)

**Import Organization:**
Order observed in `club-context-cards.tsx`:
1. Aliased imports from `@/` (absolute paths): `@/lib/domain`, `@/components/ui/`
2. Icon library imports: `lucide-react`
3. Component-scoped imports

### Error Handling

**Pattern:**
- Try/catch with error logging
- Error component pattern for route-level errors:
  ```typescript
  function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
    console.error(error);
    // ... error UI
  }
  ```

### Logging

**Framework:** Native `console` object
- `console.error()` for error capture and reporting
- Minimal logging in production code

### Comments

**When to Comment:**
- Section headers for grouped functionality
- JSDoc-style comments for exported types
- Not extensively used

### Module Design

**Exports:**
- Named exports for components and utilities
- Type exports (e.g., `export type ClubContextStats = { ... }`)
- Single default export per component file

---

## 4. impact_model_v4.1.py (Python Pandas/Scoring Engine)

**CRITICAL FOR DJANGO BACKEND:** This Python file contains the core business logic for player scoring, compatibility, and scouting recommendations. When porting to Django:

### Naming Patterns

**Functions:**
- **snake_case** for all function names (Django ORM default)
- Examples:
  - `get_position_component_cols(position)`
  - `get_position_target_avg_cols(position)`
  - `get_position_delta_cols(position)`
  - `get_export_columns_for_position(shortlist_df, position)`
  - `export_team_shortlist_xlsx(...)`
  - `classify_squad_role(ratio)`
  - `classify_contract_status(contract_value)`
  - `club_transfer_profile(transfers_df, club_name, last_n_years=5)`
  - `normalize_league_name(raw, known_targets=None, use_fuzzy=False)`
  - `normalize_league_weights(raw_weights)`
  - `get_role_scores_from_dataset(row, position)`
  - `get_player_profile(shortlist, player_name)`

**Variables:**
- snake_case for all variables and parameters
- Examples: `df`, `target_team`, `age_min`, `mv_min`, `perf_threshold`, `top_n`
- DataFrame columns use naming schemes:
  - PascalCase for raw data: `"Player"`, `"Team"`, `"League"`, `"Season"`, `"Position"`, `"Age"`
  - PascalCase with underscores for technical metrics: `"Market_Value"`, `"Fee_Cleaned"`, `"Total_Score"`
  - Space-separated for display names: `"Player URL"`, `"Agent name"`, `"Agent link"`

**Constants:**
- UPPER_SNAKE_CASE for configuration mappings
- Example: `POSITION_COMPONENT_MAP`, `MIN_MINUTES_FOR_AVG=0`

### Code Style

**Formatting:**
- PEP 8 compliant (inferred from consistent snake_case usage)
- Numeric separators for readability: `200_000_000`, `80_000`, `500_000`

**Comments:**
- Section headers with comment dividers:
  ```python
  # =========================
  # EXPORT HELPERS
  # =========================
  ```
- Inline comments for complex logic
- Function docstrings recommended but not consistently present

### Error Handling

**Pattern:**
- Try/except blocks with specific exception handling
- Graceful defaults for missing data:
  ```python
  def _safe_num(v, default=0.0):
      # Returns default value if conversion fails
  ```
- Null/NaN checking pattern:
  ```python
  if pd.isna(contract_value):
      return "Unknown"
  if not df.empty:
      # Process dataframe
  ```

### Data Processing Conventions

**DataFrame Operations:**
- Nested helper functions for complex transformations
- Pattern of column existence checking:
  ```python
  if "Column_Name" in df.columns:
      df["New_Column"] = df["Column_Name"].apply(transform_func)
  ```
- Use of `apply()` for vectorized transformations

**Classification Functions:**
- Return string classifications based on thresholds
- Example: `classify_squad_role()` returns strings: `"Important Player"`, `"Regular Starter"`, `"Squad Player"`, `"Fringe Player"`, `"Out-of-Favour"`

---

## Cross-Project Patterns

### Consistent Patterns Across All Projects

1. **Error Response Format:**
   - API: `{ error: 'Message' }`
   - Frontend: Console logging + state updates
   - Python: Try/except + default values

2. **Async Operations:**
   - API: Callback-based (`jwt.verify()`) or callback-free (`async/await`)
   - Frontend: `async/await` with try/catch
   - Python: Synchronous (pandas processing)

3. **Component Organization:**
   - API routes organized by resource (playerRoutes, userRoutes, transferRoutes)
   - Frontend components organized by feature
   - Python functions organized by operation type (helpers, exports, analysis)

### Divergence Points (Important for Django Backend)

| Aspect | API | Frontend | Python |
|--------|-----|----------|--------|
| Primary Naming | camelCase (functions) | PascalCase (components), camelCase (functions) | snake_case (ALL) |
| Database Fields | PascalCase with underscores (player data) | N/A | PascalCase with underscores (output) |
| Error Handling | JSON responses | Console + UI state | Try/except + defaults |
| Logging | console.log | console.log | print/logging |
| Code Style | No formatter | No formatter | PEP 8 (inferred) |

---

## Recommendations for New Django Backend

**Naming Convention:**
- Follow **Python/PEP 8 standard**: snake_case for functions, variables, and methods
- Follow Django ORM default: snake_case for field names (e.g., `market_value`, `contract_expires`)
- This aligns naturally with the existing Python scoring engine in `impact_model_v4.1.py`
- Model fields should match the Mongoose schema field naming but converted to snake_case:
  - `Total_Score` → `total_score`
  - `Market_value` → `market_value`
  - `Contract_expires` → `contract_expires`
  - User fields: `username`, `firstname`, `lastname`, `email`, `team`, `role` (already camelCase in original)

**Error Handling:**
- Use Django REST Framework's exception handling
- Return JSON error responses consistent with current API: `{ "error": "message" }`
- Implement centralized error handling middleware

**Code Organization:**
- Follow Django project structure: `models/`, `views/`, `serializers/`, `urls.py`
- Mirror API route organization by resource

*Convention analysis complete: 2026-07-20*
