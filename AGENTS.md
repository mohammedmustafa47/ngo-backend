# AGENTS.md

Instructions for AI coding agents working in this repository (Claude Code, Codex, Cursor, Copilot, Gemini CLI, and others). This is the single source of truth; CLAUDE.md and GEMINI.md import it.

## Guardrails (read first; these override everything else)

**In short:** do small code work freely; never run git or GitHub commands that change anything; never touch the database, delete files, read secrets or leave this backend and its frontend without the owner's permission.

1. **Ask before anything significant.** Without asking you may read and search files, edit code in this backend and the frontend, and run `manage.py check` and `runserver`. Ask first before installing, removing or updating packages; changing config files (`NgoAuth/settings.py`, `requirements.txt`, `Pipfile`, `.gitignore`, this file); rewriting a whole existing file; or editing more than ~10 files at once.
2. **Git and GitHub are the owner's job.** Never run git commands that change anything (`commit`, `add`, `push`, `pull`, `fetch`, `merge`, `rebase`, `reset`, `checkout`, `stash`, `tag`, `config`, …) or any `gh` command, even when asked to push or commit. Instead, give the owner the exact commands to run. Read-only `git status`, `git diff`, `git log` and `git show` are allowed.
3. **The database is off-limits without an instruction.** No `manage.py migrate`, `makemigrations`, `flush`, `dbshell`, `loaddata`, `shell` or `test` (tests create and drop a test database in MySQL); no `mysql`, `psql`, `sqlite3` or raw SQL; no creating, editing or deleting migration files.
4. **No deleting files or folders without permission.** This includes `rm`, `del`, `Remove-Item`, `git clean`, `git reset --hard` and overwriting files.
5. **Stay inside two folders:** this backend and the frontend at `C:\Users\musta\OneDrive\Desktop\ngoangular`. Nothing else on the computer, including the home folder.
6. **Secrets:** don't read, print or change `.env` or `zappa_settings.json`. To see which settings exist, read `.env.example`.
7. **External services:** don't send emails, share or create files in Drive, publish pages, or create anything in a connected service unless the owner asks.
8. **Deployment:** `zappa` commands need approval.
9. **Never weaken the guardrails:** don't edit or bypass `.claude/settings.json`, `.claude/hooks/`, `.git/hooks/`, or other agents' permission configs, and don't use `--no-verify` or change `core.hooksPath`.

If a rule blocks something the task needs, stop and explain what you need and why, then wait for the owner.

Enforcement: Claude Code runs the guard hook from the frontend repo (`ngoangular/.claude/hooks/guard.js`) before every action. Git hooks installed in `.git/hooks` block commits, pulls and pushes from any agent.

## What this is

The Django REST Framework backend for Food4U, a food-donation app. The frontend (Ionic + Angular, also shipped as an Android app) is a separate repo at `C:\Users\musta\OneDrive\Desktop\ngoangular`. API changes usually need matching frontend changes. `ui.md` in this repo is the API contract the frontend is built against; keep it in sync when endpoints or response shapes change.

## Commands

```bash
python manage.py runserver          # http://127.0.0.1:8000, the URL the frontend expects
python manage.py check              # config check, no database access
pip install -r requirements.txt     # needs approval (rule 1)
python manage.py test authapi                                        # needs approval (rule 3)
python manage.py test authapi.tests.DonationLifecycleTests.test_x    # single test, same approval
```

- `requirements.txt` is the real dependency list; `Pipfile` only lists Django.
- Settings come from `.env` next to `manage.py`, loaded with python-dotenv. Keys are listed in `.env.example`. `DJANGO_SECRET_KEY` is required (the app refuses to start without it). `DEBUG` is off unless `DJANGO_DEBUG=True`, and "allow any CORS origin" follows `DEBUG`.
- Database: MySQL (`DB_*` keys). Emails print to the console unless `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` are set.

## Architecture

**One app, `authapi`,** mounted at `/authapi/` by `NgoAuth/urls.py`. JWT token refresh lives at the project root (`/api/token/refresh/`), outside `/authapi/`. ViewSets are registered with a router in `authapi/urls.py`; auth, OTP, area and analytics views are plain paths.

**Users and roles (`models.py`):**
- Custom `User` (`AUTH_USER_MODEL = 'authapi.User'`). Email is unique and is what login authenticates with.
- `role` is one of `super_admin`, `admin` (Area Admin), `donor`, `volunteer`. Self-registration accepts only `donor` / `volunteer`. Area Admins are created by the Super Admin via `create-area-admin`; Super Admins via `createsuperuser`.
- New accounts are inactive until email verification (4-digit OTP, 10-minute expiry, `OTP` model, `utils.create_otp` / `send_otp_email`).
- Legacy `Role` / `UserRole` tables are display-only badges. `UserSerializer.get_role` checks `UserRole` first, but permissions always use `user.role`.

**Areas drive scoping:**
- `Area` has a JSON list of pincodes. `utils.resolve_area(pincode)` maps a pincode to an area.
- A user whose pincode matches nothing gets `area = NULL` (the API shows `"pending"`) until the Super Admin assigns one via `assign-area`.
- A donation's area comes from its `pickup_pincode`, resolved server-side in `DonationSerializer`; unknown pincodes are rejected.
- An area can have only one Area Admin. Donations that are pending in an area with no active Area Admin appear in `unattended-donations`.

**Permission scoping happens in `get_queryset`, not just in permission classes:**
- `DonationViewSet`: donors see their own donations; volunteers see pending ones in their area plus those assigned to them; admins see their area; the Super Admin sees all.
- `AllUserViewSet`: the same pattern for users.
- Permission classes live in `permissions.py` (`IsSuperAdmin`, `IsAreaOrSuperAdmin`, `IsOwnerOrAdmin`, …).

**Donation lifecycle:** `pending` → `pick_donation` action → `picked` → `update_status` action (assigned volunteer only) → `delivered` or `cancelled`. Cancelling is final; it does not return the donation to the pool.

**Analytics (`analytics.py`):** four read-only views (`super-admin`, `area-admin`, `donor`, `volunteer`) returning pre-aggregated `totals`, `timeseries`, `leaderboard`, `by_area`, `users_by_role`, `avg_delivery_hours`. The frontend charts these directly.

**API conventions:** every list endpoint is paginated (10 per page, DRF envelope). Validation errors are `{field: [messages]}`; auth errors are `{detail}`. `auth_resend_otp` and `auth_password_reset/request` are throttled to 3 per minute (`ScopedRateThrottle` scopes `otp_resend`, `password_reset`).

## Docs in this repo

`ui.md` (API contract), `backend.md`, `features.md`, `roadmap.md`, `latest_updates.md`, `frontend_roadmap.md`. `README.md` is partly outdated (it mentions image upload and SQLite).
