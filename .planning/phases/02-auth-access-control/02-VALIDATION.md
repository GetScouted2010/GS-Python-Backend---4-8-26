---
phase: 2
slug: auth-access-control
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-07-21
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.1.1 + pytest-django 4.12.0 (already installed in `get-scouted-be/.venv`) |
| **Config file** | `get-scouted-be/pyproject.toml` (`[tool.pytest.ini_options]`, `DJANGO_SETTINGS_MODULE = "config.settings.local"`) |
| **Quick run command** | `cd get-scouted-be && ./.venv/bin/pytest accounts -x -q` |
| **Full suite command** | `cd get-scouted-be && ./.venv/bin/pytest` |
| **Estimated runtime** | ~5 seconds (accounts app only, unit-level) |

Note: `pyproject.toml`'s `testpaths` currently lists `["clubs", "players", "transfers", "core"]` — Wave 0 must add `"accounts"` to that list, or the full-suite command will silently skip the new app's tests.

---

## Sampling Rate

- **After every task commit:** Run `cd get-scouted-be && ./.venv/bin/pytest accounts -x -q`
- **After every plan wave:** Run `cd get-scouted-be && ./.venv/bin/pytest`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-0X-XX | TBD | 0 | (infra) | setup | dev DB reset + `accounts` app scaffold | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-01 | unit | `pytest accounts/tests/test_registration.py -x -q` | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-01 | unit | `pytest accounts/tests/test_auth_flow.py::test_login_flow -x -q` | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-01 | unit | `pytest accounts/tests/test_auth_flow.py::test_refresh_rotation -x -q` | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-02 | unit | `pytest accounts/tests/test_permissions.py::test_write_requires_auth -x -q` | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-02 | unit | `pytest accounts/tests/test_permissions.py::test_role_gated_403 -x -q` | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-02 | integration | `pytest accounts/tests/test_permissions.py::test_role_change_takes_effect_immediately -x -q` | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-03 | unit | `pytest accounts/tests/test_auth_flow.py::test_logout_blacklist -x -q` | ❌ W0 | ⬜ pending |
| 02-0X-XX | TBD | TBD | AUTH-03 | unit (settings assertion) | `pytest accounts/tests/test_auth_flow.py::test_single_auth_backend -x -q` | ❌ W0 | ⬜ pending |

*Task IDs/plan/wave columns are placeholders — gsd-planner fills these in once plans are broken into concrete tasks.*

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Dev database reset (drop/recreate) + re-run Phase 1's `import_all` — required before `accounts` migrations can safely set `AUTH_USER_MODEL` (the stock `auth_user` table already exists from Phase 1's Django setup with 0 rows; swapping the user model after `django.contrib.auth`'s own migrations have run requires a clean re-migrate, not an in-place ALTER)
- [ ] `accounts/` app scaffold (`models.py`, `serializers.py`, `views.py`, `permissions.py`, `urls.py`, `admin.py`)
- [ ] `accounts/tests/conftest.py` — `UserFactory` (factory_boy) + `authenticated_client(role)` fixture pattern (`RefreshToken.for_user(user)` + `APIClient().credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")`)
- [ ] `pip install djangorestframework-simplejwt>=5.5.1,<5.6` (pinned floor for CVE-2024-22513) + add to `requirements/base.txt`
- [ ] `INSTALLED_APPS`: add `rest_framework`, `rest_framework_simplejwt.token_blacklist`, `accounts`
- [ ] `REST_FRAMEWORK` + `SIMPLE_JWT` + `AUTH_USER_MODEL` + `EMAIL_BACKEND` settings blocks in `config/settings/base.py`
- [ ] Add `"accounts"` to `pyproject.toml`'s `testpaths`

---

## Manual-Only Verifications

*None — all Phase 2 behaviors (registration, login, token refresh/rotation, logout blacklist, role-gated permissions, immediate role/deactivation effect, single-auth-backend enforcement) have automated pytest coverage per the map above.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
