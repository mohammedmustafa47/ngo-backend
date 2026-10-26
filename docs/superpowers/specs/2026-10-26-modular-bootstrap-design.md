# Modular bootstrap and feature-based structure (frontend + backend)

Date: 2026-10-26 · Status: draft for owner approval · Repos: `ngoangular` (frontend), `djangoauth` (backend)

## 1. Intent

The owner wants both projects to follow one clear, conventional structure so that anyone opening them for the first time knows where things live and doesn't make mistakes ("not be in blunder"). Two ideas carry this:

- **Feature-based structure:** code is grouped by what it does (accounts, areas, donations, analytics; donor, volunteer, admin screens), not by file type. Each feature is self-contained; shared pieces live in clearly marked places.
- **Modular bootstrap:** application startup is split into small, single-purpose steps joined by one thin "manager" file. Startup checks its configuration and fails loudly and clearly instead of half-working.

## 2. Requirements (owner's rules)

1. One file, one concern. Each startup concern gets its own small file.
2. Thin entry files. One manager file (`settings/base.py`, `bootstrap/bootstrap.ts`) only joins the modules in a fixed order, with no logic.
3. Fail fast. Every required environment variable is read and checked at startup. Missing or invalid values stop startup with a clear message.
4. Production safety check. In production, refuse to start if DEBUG is on, the secret key is weak, hosts include `*`, or cookies are not secure.
5. Health check. `GET /api/health` confirms the app is up and the database answers.
6. Frontend: `main.ts` only calls `bootstrap()` and renders. `bootstrap.ts` runs its steps in order. A bad setting shows a clear error screen, never a white screen. Each step can be swapped in tests.
7. The logger redacts secrets: passwords, tokens, OTP codes, session ids.
8. Files stay under about 200 lines.
9. Tests for each startup step: missing variable, unsafe production setting, health check.

Adaptations agreed with the owner (the original rules were written for a React + cookie-session stack):
- `main.tsx` becomes `main.ts` (Angular).
- The "query client" step is dropped; Angular's `HttpClient` covers it.
- The "csrf" step becomes an **auth** step. The app authenticates with JWT bearer tokens in a header, so there's no CSRF token to fetch.
- "PINs" means the 4-digit OTP codes. Pincodes (postal codes) are not secret and are not redacted.

## 3. Goals, non-goals, anti-goals

**Goals**
- The folder structures in §5 and §6.
- Startup validation, the production check, `/api/health`, log redaction, and tests for them.
- Every phase leaves both apps working end to end.

**Non-goals (explicitly later)**
- No UI redesign, no visual changes (that's `ui-prompts.md`, later).
- No bug fixes from `ui-brief.md` §9, except where a moved file must change to keep working.
- No change to API URLs, request or response shapes, or user-visible behaviour.
- No authentication-provider change (Clerk is still undecided).

**Anti-goals (failure even if it "works")**
- Any data loss, or any SQL that changes existing tables during the model move.
- The Android build or the Capacitor `www/` output breaking.
- A half-moved state where a feature's code lives in both old and new places.

## 4. Constraints

- The guardrails in `AGENTS.md` apply throughout:
  - The owner runs all git commands; there's a commit point after each phase.
  - Any migration, `manage.py test` or package install needs the owner's approval.
  - File deletions need approval. Moving files means create-new then delete-old, so each phase's deletions are batched into a single approval.
- Stack stays as is: Angular 20 + Ionic 8 + Capacitor 7 on `@angular/build:application`; Django 5.2 + DRF + simplejwt + MySQL.
- `NgoAuth` stays the backend project package name, because `wsgi.py`, `manage.py` and `zappa_settings.json` refer to `NgoAuth.settings`.
- The frontend build still outputs to `www/`.
- Android talks to the backend over HTTP during development, so the security rules only apply when `DJANGO_ENV=production`.

## 5. Backend design (`djangoauth`)

### 5.1 Structure

```
djangoauth/
├── manage.py
├── NgoAuth/
│   ├── settings/
│   │   ├── __init__.py          # from .base import *
│   │   ├── base.py              # manager: star-imports modules below in fixed order, then runs production_check
│   │   ├── env.py               # reads + validates env → module-level constants (ENV, SECRET_KEY, DEBUG, DB_*, …)
│   │   ├── core.py              # INSTALLED_APPS, ROOT_URLCONF, TEMPLATES, WSGI/ASGI, i18n, DEFAULT_AUTO_FIELD
│   │   ├── database.py
│   │   ├── cache.py             # LocMemCache (also backs DRF throttling)
│   │   ├── security.py          # ALLOWED_HOSTS, CORS, cookie + HTTPS flags derived from ENV
│   │   ├── auth.py              # AUTH_USER_MODEL, password validators, REST_FRAMEWORK, SIMPLE_JWT, throttle rates
│   │   ├── email.py
│   │   ├── logging.py           # LOGGING dict using core.logging_redact.RedactFilter
│   │   ├── middleware.py
│   │   ├── static.py
│   │   └── production_check.py  # check(settings_namespace) → raises ImproperlyConfigured listing every problem
│   ├── urls.py                  # admin, api/token/refresh/, api/health, authapi/ → features' urls (prefix unchanged)
│   ├── wsgi.py, asgi.py
├── core/                        # Django app "core": shared, no business features
│   ├── health.py, logging_redact.py, pagination.py, permissions.py (moved from authapi/permissions.py)
│   └── tests/
└── features/
    ├── accounts/   apps.py (label = "authapi") · models.py (User, OTP, Role, UserRole) · serializers/ · views/ · urls.py · services/ (otp, email) · tests/
    ├── areas/      models.py (Area) · resolve_area service · views (areas CRUD, assign-area, pending users, create-area-admin) · urls.py · tests/
    ├── donations/  models.py (Donation) · serializers · views (viewset, pick, update_status, unattended) · urls.py · tests/
    └── analytics/  views (4 endpoints, split per role if >200 lines) · urls.py · tests/
```

The URL prefix `/authapi/...` stays, and every path inside it stays the same. `NgoAuth/urls.py` includes each feature's `urls.py` under `authapi/`.

### 5.2 Environment variables (`env.py`)

| Variable | Required | Rule |
|---|---|---|
| `DJANGO_ENV` | no, default `development` | must be `development`, `test` or `production` |
| `DJANGO_SECRET_KEY` | yes | non-empty |
| `DJANGO_DEBUG` | no, default `false` | `true` / `false` only |
| `DJANGO_ALLOWED_HOSTS` | no, default `localhost,127.0.0.1` | comma list |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER` | no, current defaults | `DB_PORT` must be an integer |
| `DB_PASSWORD` | yes (may be empty only when `DJANGO_ENV=test`) | — |
| `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` | no | both set or both empty |
| `CORS_ALLOWED_ORIGINS` | no, default `http://localhost:8100,http://127.0.0.1:8100` | comma list of URLs |

- `env.py` collects **all** problems and raises one `ImproperlyConfigured` listing them all, so the owner fixes everything in one pass.
- `.env.example` is updated to match the table.

### 5.3 Production check (only when `DJANGO_ENV=production`)

The check fails if any of these is true:
- `DEBUG` is on.
- The secret key is shorter than 50 characters, has fewer than 5 unique characters, or starts with `django-insecure-`.
- `ALLOWED_HOSTS` is empty or contains `*`.
- `SESSION_COOKIE_SECURE` or `CSRF_COOKIE_SECURE` is false.
- `CORS_ALLOW_ALL_ORIGINS` is true.

All failures are reported together. In production, `security.py` sets the cookie-secure flags and `SECURE_PROXY_SSL_HEADER`.

### 5.4 Health check

`GET /api/health` needs no authentication and is not throttled. It runs `SELECT 1` on the default database:
- 200 `{"status": "ok", "database": "ok"}` on success
- 503 `{"status": "degraded", "database": "error"}` on failure

No error details are exposed in the response; the error is logged instead.

### 5.5 Logging redaction

`RedactFilter` masks values as `***` in these places:
- **Keys:** any key matching `password|passwd|secret|token|access|refresh|otp|code|session|authorization|cookie` (case-insensitive), in dicts, `extra` and record args.
- **Message text:** `Bearer <token>`, JWT-shaped strings, and `otp=1234`-style pairs.

The OTP email helper logs only to the console backend in development; it is changed so it never logs the code in production.

### 5.6 Moving models (option A, owner's choice)

- `features/accounts/apps.py` sets `label = "authapi"` and `name = "features.accounts"`. `User`, `OTP`, `Role` and `UserRole` stay owned by app label `authapi`. Their database tables and existing migration history (`authapi/migrations/0001`–`0010`) don't change; the migrations folder moves with the app.
- `Area` and `Donation` move to the `areas` and `donations` apps with `Meta.db_table` pinned to the current table names (`authapi_area`, `authapi_donation`). The move is done with state-only migrations (`SeparateDatabaseAndState`, no database operations):
  - `authapi`: remove the models from state.
  - `areas` / `donations`: create them in state.
  - Dependencies make sure foreign keys (`User.area`, `Donation.area`, `Donation.donor`, `Donation.volunteer`) resolve in order.
- Proof before running: `sqlmigrate` is run for each new migration (owner approves) and must print no table-changing SQL. The owner then approves `migrate`.

### 5.7 Backend tests

The existing 42 tests in `authapi/tests.py` are moved into each feature's `tests/` folder. The new tests:

| File | What it covers |
|---|---|
| `test_env.py` | each required variable missing; bad `DJANGO_DEBUG`; bad `DB_PORT`; all errors reported together |
| `test_production_check.py` | each unsafe setting refused; a clean production config passes |
| `test_health.py` | 200 when the database answers; 503 when the connection is mocked to fail |
| `test_redaction.py` | keys and message patterns masked; non-secret fields (pincode, username) kept |

`env.py` and `production_check.py` expose pure functions that take a mapping or namespace, so they can be tested without reloading settings. Running tests creates a MySQL test database, so the owner approves each run.

## 6. Frontend design (`ngoangular`)

### 6.1 Structure

```
src/
├── main.ts                  # bootstrap().then(start => start()).catch(showBootError)  (nothing else)
├── environments/            # environment.ts / environment.prod.ts (values unchanged)
└── app/
    ├── bootstrap/
    │   ├── bootstrap.ts     # manager: builds providers from steps in order, returns a start function
    │   ├── boot-step.ts     # BootStep type: { name, providers(config) }
    │   ├── steps/ config.step.ts · api.step.ts · auth.step.ts · router.step.ts · ionic.step.ts
    │   ├── boot-error.ts    # renders a plain-DOM error screen (no Angular needed)
    │   └── *.spec.ts
    ├── core/                # app-wide singletons
    │   ├── auth/            auth.service · token-storage · token.interceptor (functional) · role.guard (functional)
    │   ├── api/             api-client (base URL, fetchAllPages)
    │   ├── logging/         logger (redacts) + spec
    │   └── errors/          http-error (moved from shared/http-error)
    ├── entities/            # shared domain data: types + API calls
    │   ├── donation/ · user/ · area/ · analytics/
    ├── shared/ui/           # app-header (and later shared components), standalone
    ├── shared/styles/       # _auth.scss
    ├── features/
    │   ├── auth/            login · register · verify-otp · forgot-password · reset-password · auth.routes.ts
    │   ├── donor/           donor-shell (tabs) · dashboard · donate-form · history · donor.routes.ts
    │   ├── volunteer/       volunteer-shell · dashboard · pickups · history · volunteer.routes.ts
    │   ├── area-admin/      admin-shell · dashboard · donations · users · reports · area-admin.routes.ts
    │   ├── super-admin/     dashboard · areas · area-detail · pending-signups · unattended · create-admin · all-users · super-admin.routes.ts
    │   └── profile/         donor-profile · volunteer-profile · admin-profile · profile.routes.ts
    ├── app.routes.ts        # one lazy loadChildren line per feature
    └── app.component.ts     # standalone; ion-app, side menu, router outlet
```

### 6.2 Bootstrap flow

- `bootstrap()` runs `config → api → auth → router → ionic` in that order.
- Each step is a small object; the order is a single array in `bootstrap.ts`.
- **config:** reads `environment`, checks that `apiUrl` and `local_url` are absolute `http(s)` URLs and that `apiUrl` ends with `/`, and provides an `APP_CONFIG` injection token. On failure it throws a `BootError` with a message the owner can act on, e.g. "apiUrl is missing in src/environments/environment.ts".
- **api:** `provideHttpClient(withInterceptors([...]))`.
- **auth:** the token interceptor, rewritten as a function with the same behaviour as today (public endpoints skipped, one refresh with queued requests, logout on refresh failure).
- **router:** `provideRouter(appRoutes, withPreloading(PreloadAllModules))`.
- **ionic:** `provideIonicAngular()` and `IonicRouteStrategy`.
- `bootstrapApplication` failures and `BootError`s both go to `showBootError`. It replaces the page body with a simple screen showing a title, the message and a "Reload" button, so there's never a white page.
- **Testability:** `bootstrap(steps = defaultSteps)` takes the step list as a parameter, so tests can swap any step.

### 6.3 Pages and routing

- Every page becomes `standalone: true` (Angular 20's default) and imports `IonicModule`-equivalent standalone pieces or `IonicModule` directly. Every `*.module.ts` and `*-routing.module.ts` is removed.
- Routes keep their current URLs (`/login`, `/tab-donor/donateform`, `/super-admin-areas`, …), so links and the Android app behave the same.
- `RoleGuard` becomes a functional `roleGuard` with the same logic.
- `Auth`, the god-service, is split so no file goes over 200 lines:
  - `core/auth/auth.service.ts`: login, register, OTP, password reset, logout, tokens.
  - `core/api/api-client.ts`: the generic `getList` / `saveRecord` / `deleteRecord` / `postAction` helpers.
  - `entities/*`: the per-endpoint calls (analytics, areas, users).
  - Pages are updated to use these. Behaviour is unchanged.

### 6.4 Logger

`core/logging/logger.ts` wraps `console` with `debug`, `info`, `warn` and `error`. Before printing, it masks:
- **Object keys:** `password`, `new_password`, `confirm_password`, `token`, `access`, `refresh`, `otp`, `code`, `authorization`, `session`, in nested objects.
- **Strings:** `Bearer …`, JWT-shaped strings, and 4-digit values on keys named `otp`.

Every existing `console.log` / `console.error` call is replaced with the logger. In production builds, `debug` is silenced.

### 6.5 Test runner and tests

- Fix `ng test` after the builder migration (`@angular/build:karma`, `karma.conf.js`, `src/test.ts`). This adds no packages if the existing karma packages work; any package change needs the owner's approval.
- New specs:
  - `config.step.spec` (missing or invalid `apiUrl` → `BootError`)
  - `bootstrap.spec` (step order; a swapped step is used; a failing step reaches the error handler)
  - `boot-error.spec` (screen shows the message)
  - `logger.spec` (redaction)
- The existing page `*.spec.ts` files are updated to the standalone setup (they're mostly default "should create" tests).

## 7. Phases (each ends in a working app and an owner commit)

| # | Repo | Work | Owner approvals needed |
|---|---|---|---|
| 1 | backend | Settings split, `env.py`, production check, cache, logging redaction, `/api/health`, `core` app, their tests, `.env.example` | run tests |
| 2 | backend | Feature apps (`accounts`/`areas`/`donations`/`analytics`), move code and tests, state-only migrations, delete old `authapi` files | `sqlmigrate` check, `migrate`, run tests, file deletions |
| 3 | frontend | Bootstrap folder + steps, `main.ts`, error screen, standalone `AppComponent`, test runner fixed, bootstrap tests | config edits (`angular.json`, `tsconfig`), run tests |
| 4 | frontend | `core/`, `entities/`, `shared/` moves; `Auth` split; logger replaces `console` | file deletions |
| 5 | frontend | Features converted to standalone one role at a time (auth → donor → volunteer → area-admin → super-admin → profile); old modules deleted | file deletions |

After phases 2 and 5, update `AGENTS.md` in both repos (structure section), with the owner's approval.

Each phase is checked before handing over:
- `manage.py check`
- the tests (with approval)
- `ng build` and `ng lint` (frontend)
- a manual smoke test of login and one screen per role

## 8. Left to the builder

- Exact file splits inside a feature (e.g. `views/` package vs. `views.py`), as long as files stay under ~200 lines.
- Naming of internal helper functions and test names.
- Whether profile pages merge into one role-aware page: **no** for this restructure (behaviour unchanged); revisit during the redesign.

## 9. Decisions made by Claude (owner to check)

- No behaviour, UI or API changes in this work; bugs and redesign come after.
- The URL prefix `/authapi/` and all frontend route URLs stay the same.
- `DJANGO_ENV` is introduced to decide when production checks apply.
- Frontend env "variables" are the values in `src/environments/*.ts` (Angular has no runtime env), checked at boot.
- Ionic standalone imports: `@ionic/angular/standalone` per page if it builds cleanly, otherwise `IonicModule`. The builder picks whichever keeps `www/` and Android working.
