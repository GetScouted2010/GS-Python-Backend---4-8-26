# Testing Patterns

**Analysis Date:** 2026-07-20

## Executive Summary

**CRITICAL FINDING: No test framework or test files exist in any of the three sub-projects.** This is a significant gap that should be addressed when building the new Django backend.

---

## Test Framework Status by Project

### 1. API-Updated- (Node.js/Express/MongoDB)

**Testing Status:** ❌ NOT IMPLEMENTED

**Current Configuration:**
- `package.json` contains: `"test": "echo \"Error: no test specified\" && exit 1"`
- No test dependencies installed
- No test files found in repository

**Missing Frameworks:**
- No unit test runner (Jest, Mocha, Vitest not installed)
- No assertion library (Chai, Assert not available)
- No mocking library (Sinon, Jest mocks)

**What Should Be Tested:**
- Route handlers (all endpoints in `/routes/`)
  - Player search and filtering
  - Compatibility scoring calculations
  - Transfer data retrieval and averaging
  - User authentication (login, JWT verification)
  - Shortlist CRUD operations
- Middleware functions
  - `verifyToken()` in `middleware/auth.js`
  - API key validation (currently disabled)
- Database models and schema validation
  - Player schema (`models/player.js`)
  - User schema (`models/users.js`)
  - Position-specific models (AM, CB, CM, DM, FWD, LB, LW, RB, RW)
- Utility functions
  - `getOriginalFieldName()` in `utils/fieldMapper.js`
  - `getSanitizedFieldName()` in `utils/fieldMapper.js`
- Error handling in middleware (`index.js`)

**Why Testing is Critical:**
- API exposes 7 main routes (players, compatibility, transfers, positions, playstyles, shortlists, users)
- Complex scoring calculations (`calculateFinancialFit()` in `playerRoutes.js`) have no validation
- Field mapping logic (`fieldMapper.js`) is critical for data transformation

---

### 2. RT-Tool-Frontend (React/Vite/TypeScript)

**Testing Status:** ❌ NOT IMPLEMENTED

**Current Configuration:**
- `package.json` has no test script
- No test dependencies installed
- No test files found in repository

**Missing Frameworks:**
- No React test library (React Testing Library, Enzyme)
- No test runner (Jest, Vitest)
- No component testing setup

**What Should Be Tested:**
- Search components
  - `PlayerSpecificSearchBox.tsx` - debounced search, results rendering
  - Search API call integration
- Data display components
  - `PlayerHeader.tsx` - player data rendering
  - `PlayerCard.tsx` - player information display
  - `PlayingstylesTable.tsx` - tabular data rendering
  - `PlayingStyleChart.tsx` - chart rendering
- Form components
  - `dualSlider.tsx` - range slider input
- Shortlist management
  - `ShortListTabkeComponent.tsx` - shortlist creation/deletion
- State management
  - `UserContext.tsx` - context provider and hooks
- Service layer integration
  - `services/players/players.ts` - API integration

**Why Testing is Critical:**
- Complex async search with debouncing
- Form state management with validation (Yup used via react-hook-form)
- Multiple data visualization components (Charts.js, Recharts)
- User authentication and session management through context

**Observed Issues Without Tests:**
- No coverage for error states in search (only basic console.error)
- Loading state management (`isSearchLoading`) untested
- No validation of API response handling (`if (results.status === 200)`)

---

### 3. pixel-perfect-clone-60729 (React/TanStack Start/TypeScript)

**Testing Status:** ❌ NOT IMPLEMENTED

**Current Configuration:**
- `package.json` has no test script
- No test dependencies installed
- No test files found in repository

**Missing Frameworks:**
- No React test library
- No test runner
- No E2E testing framework (Playwright, Cypress)

**What Should Be Tested:**
- Route handlers and layout components
  - `routes/__root.tsx` - error handling, 404 page
  - `routes/_authenticated.tsx` - authentication guard
  - `routes/index.tsx`, `/login.tsx`, `/signup.tsx` - page rendering
  - `routes/_authenticated/clubs.tsx`, `/dashboard.tsx` - protected routes
- Authentication flow
  - `hooks/use-auth.tsx` - auth state and functions
  - Login/signup process
  - Token management
- Club context and analytics
  - `components/club-context-cards.tsx` - stats display
  - `lib/club-recruitment.ts` - club analysis logic
  - `lib/deal-analysis.ts` - deal scoring logic
- Data transformations
  - `lib/domain.ts` - business logic functions
  - `lib/utils.ts` - utility functions

**Why Testing is Critical:**
- Full-stack prototype with Supabase integration
- Authentication logic must be verified
- Complex analytics calculations in club-recruitment and deal-analysis libraries
- TanStack Router configuration untested

---

### 4. impact_model_v4.1.py (Python Scoring Engine)

**Testing Status:** ❌ NOT IMPLEMENTED

**Current Configuration:**
- No pytest configuration file
- No test directory
- No test files
- ~15,700 lines of complex pandas/numpy logic with zero test coverage

**What Should Be Tested (CRITICAL):**
- **Data Normalization Functions:**
  - `normalize_text(s: str) -> str` - text standardization
  - `normalize_league_name(raw, known_targets=None, use_fuzzy=False)` - league name normalization
  - `normalize_league_weights(raw_weights)` - weight normalization
  - `normalize_country_name(raw)` - country standardization
  - `normalise_position(pos)` - position normalization

- **Classification Functions:**
  - `classify_squad_role(ratio)` - outputs: "Important Player", "Regular Starter", "Squad Player", "Fringe Player", "Out-of-Favour"
  - `classify_contract_status(contract_value)` - outputs: "Unknown", "Expired", "Expiring <=12m", "Expiring 12-24m", "Long Deal"
  - `classify_age_fit(player_age, avg_age)` - age compatibility scoring
  - `classify_fit(value, avg, tol_great, tol_moderate)` - generic fit classification

- **Impact Calculation Functions (by position):**
  - `_calc_gk_impact_raw(row, row_idx, std_lookup, return_components=False)` - goalkeeper impact
  - `_calc_cb_impact_raw(row, row_idx, std_lookup, return_components=False)` - center back impact
  - `_calc_fb_impact_raw(row, row_idx, std_lookup, return_components=False)` - fullback impact
  - `_calc_cmf_impact_raw(row, row_idx, std_lookup, return_components=False)` - central midfielder impact
  - `_calc_dmf_impact_raw(row, row_idx, std_lookup, return_components=False)` - defensive midfielder impact
  - `_calc_amf_impact_raw(row, row_idx, std_lookup, return_components=False)` - attacking midfielder impact
  - `_calc_fwd_impact_raw(row, row_idx, std_lookup, return_components=False)` - forward impact

- **Data Processing Helpers:**
  - `_parse_mv(series)` - market value parsing
  - `_safe_num(v, default=0.0)` - safe numeric conversion
  - `_pct_to_dec(v)` - percentage to decimal conversion
  - `_get(row, col, default=0.0)` - safe row access
  - `_minutes_factor(minutes)` - minutes weighting factor
  - `_reliability_flag(minutes)` - data reliability assessment
  - `_build_std_lookup(df, metrics, position_col="Main_Position")` - standard deviation calculation

- **Export and Report Functions:**
  - `export_team_shortlist_xlsx(df, target_team, season, ...)` - Excel export
  - `get_export_columns_for_position(shortlist_df, position)` - column selection
  - `get_club_transfer_summary_table(clubs, transfers_df, players_df=None, season=None)` - transfer summary
  - `club_transfer_profile(transfers_df, club_name, last_n_years=5)` - club transfer analysis

- **DataFrame Transformations:**
  - `prepare_optional_transfer_fields(df)` - missing field handling
  - `_rename_columns_safe(df)` - column renaming
  - `_ensure_minutes(df)` - minutes field validation
  - `_position_percentile(series)` - percentile ranking

**Why Testing is CRITICAL:**
- Core business logic for player scouting and scoring
- All frontend analytics depends on these calculations
- No validation that inputs produce expected outputs
- Complex nested conditionals for position-specific scoring
- Risk of silent data corruption (NaN propagation, type mismatches)
- Scoring thresholds (e.g., ratio >= 0.8 for "Important Player") have no regression tests

**Test Coverage Gaps:**
- Edge cases: null values, empty DataFrames, missing columns
- Boundary conditions: age 0, negative market values, invalid positions
- Integration: full pipeline from raw data to export
- Regression: scoring consistency across seasons

---

## Current Error Handling (Without Tests)

### API Error Handling (Untested)
- Basic try/catch in route handlers
- Example from `routes/userRoutes.js`:
  ```javascript
  try {
    // Check if user exists
    const existingUserEmail = await User.findOne({ email });
    if (existingUserEmail) {
      return res.status(400).json({ error: 'User with this email already exists' });
    }
  } catch (error) {
    return res.status(500).json({ error: 'Server error' });
  }
  ```
- No tests verify error cases (invalid input, database failures)

### Frontend Error Handling (Untested)
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
- No tests verify error UI rendering or recovery

### Python Error Handling (Untested)
- Defensive programming pattern without tests:
  ```python
  def _safe_num(v, default=0.0):
      # Safely convert to number, return default if fails
      if pd.isna(v):
          return default
      # ... conversion logic
  ```
- No tests validate fallback behavior

---

## Recommended Testing Strategy for Django Backend

### Phase 1: Unit Tests (High Priority)

**Models & Serializers:**
- Validate field types and constraints
- Test model methods and managers
- Test serializer validation rules

**Views/Endpoints:**
- Test each GET, POST, PUT, DELETE endpoint
- Test authentication/permission checks
- Test error responses (400, 403, 404, 500)

**Utils & Business Logic:**
- Port and test Python scoring functions
- Test data normalization functions
- Test classification functions

### Phase 2: Integration Tests

**API Workflows:**
- Full user registration → login → create shortlist flow
- Player search → filter → compatibility scoring flow
- Transfer data retrieval → averaging flow

**Database Interactions:**
- Ensure Mongoose-to-Django model mapping is correct
- Validate data migration from MongoDB

### Phase 3: E2E Tests

- Frontend → API → Database complete workflows
- Authentication token lifecycle
- Error recovery and retry logic

### Test Setup Recommendations

**Framework:**
- **pytest** for unit/integration tests
- **pytest-django** for Django integration
- **Factory Boy** for test data generation
- **unittest.mock** for mocking external services (Supabase, file exports)

**Structure:**
```
myproject/
├── tests/
│   ├── test_models.py
│   ├── test_serializers.py
│   ├── test_views.py
│   ├── test_utils.py
│   ├── conftest.py  # pytest fixtures
│   └── factories.py  # test data factories
├── manage.py
└── ...
```

**Run Commands:**
```bash
pytest                          # Run all tests
pytest -v                       # Verbose output
pytest tests/test_models.py    # Run specific test file
pytest -k "test_player"        # Run tests matching pattern
pytest --cov                    # Coverage report
```

**Coverage Target:** Minimum 80% for critical business logic (scoring functions)

---

## Known Testing Gaps Blocking Production

| Area | Project | Impact | Priority |
|------|---------|--------|----------|
| API endpoint validation | API-Updated- | Wrong data returned to frontend | HIGH |
| Scoring calculation | impact_model_v4.1.py | Player rankings incorrect | HIGH |
| Search functionality | RT-Tool-Frontend | Users can't find players | HIGH |
| Authentication flow | All | Unauthorized access risk | HIGH |
| Data migration correctness | Django backend | Data loss/corruption | HIGH |
| Form validation | RT-Tool-Frontend | Invalid data submitted | MEDIUM |
| Error recovery | All | Silent failures | MEDIUM |
| Export formatting | impact_model_v4.1.py | Malformed reports | MEDIUM |

---

## Migration Path: Tests to Write Before Django Launch

1. **Week 1:** Unit tests for Python scoring functions (~300 lines of test code)
2. **Week 2:** Unit tests for Django models and serializers (~400 lines)
3. **Week 3:** Integration tests for API workflows (~300 lines)
4. **Week 4:** E2E tests for frontend-to-backend (~200 lines)

*Estimated total: ~1,200 lines of test code for 20,000+ lines of production code*

---

*Testing audit: 2026-07-20 - Zero existing tests, comprehensive gap identified*
