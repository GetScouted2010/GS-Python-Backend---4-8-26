# Deferred Items — Phase 06 (scoring-performance-caching-layer)

Out-of-scope discoveries logged during plan execution (not fixed, per
SCOPE BOUNDARY — only issues directly caused by the current task's changes
are auto-fixed).

## Found during 06-02 execution

- **Untracked migration `get-scouted-be/players/migrations/0002_denormalized_scores.py`**
  Corresponds to plan 06-01's `feat(06-01): add 4 denormalized score
  FloatFields + indexes to Player model` commit (9fefee4), which committed
  the model change but not its generated migration. Pre-existing, unrelated
  to 06-02's population.py caching work — left untracked rather than folded
  into a 06-02 commit. Should be committed under 06-01 (or as a standalone
  chore commit) before the phase is considered complete, otherwise
  `manage.py migrate` will be out of sync with `players/models.py`.
  **RESOLVED** during 06-01's own Task 2/self-check: this was actually
  06-01's own Task 2 migration file, temporarily knocked untracked by a git
  race between the two parallel wave-1 executors (06-01 and 06-02 both
  staging/committing in the same working directory). Content and applied-DB
  state were unaffected throughout; committed cleanly as `5d71090
  feat(06-01): generate and apply migration for denormalized score columns`.

- **Unstaged `get-scouted-be/clubs/models.py` docstring reformat**
  Pre-existing modified file (single-line docstring reformatted to
  multi-line) present before 06-02 execution started. Not related to any
  06-02 task — left as-is.
