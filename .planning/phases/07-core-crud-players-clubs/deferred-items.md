# Deferred Items — Phase 07 (core-crud-players-clubs)

## Pre-existing failing test: `accounts/tests/test_permissions.py::test_director_read_only_visibility`

- **Found during:** 07-03 Task 3 full-suite verification (`pytest -q`).
- **Symptom:** `TypeError: string indices must be integers, not 'str'` at
  `emails = [row["email"] for row in response.data]` — the test assumes
  `GET /api/auth/admin/users/` returns a plain list, but the response is now
  a paginated dict (`{"results": [...], "count": ...}`).
- **Root cause:** 07-01 wired `DEFAULT_PAGINATION_CLASS` project-wide in
  `REST_FRAMEWORK` settings, which changed this pre-existing (Phase 2)
  endpoint's response shape from an unpaginated list to a paginated object.
  The test was never updated to match.
- **Scope determination:** Out of scope for 07-03 (and arguably 07-01/07-02
  too) — it is a Phase 2 (`accounts` app) test regressed by an unrelated
  Phase 7 settings change, not something caused by clubs/players CRUD code.
  Confirmed via `git checkout e970a28 -- get-scouted-be` (the commit
  immediately before 07-03 started, i.e. right after 07-02 completed) that
  the failure already existed there — 07-03's changes did not introduce or
  worsen it.
- **Action:** NOT fixed here (scope boundary — only issues directly caused
  by the current task's changes are auto-fixed). Needs a follow-up fix in
  either `accounts/tests/test_permissions.py` (update the assertion to read
  `response.data["results"]`) or a decision to exempt that admin endpoint
  from pagination.
- **Status:** Deferred, unresolved as of 07-03 completion.
