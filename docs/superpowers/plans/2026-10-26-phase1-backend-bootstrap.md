# Phase 1: Backend Modular Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `NgoAuth/settings.py` into single-purpose modules joined by a thin `base.py`, with fail-fast environment validation, a production safety check, log redaction and `GET /api/health`, each covered by tests.

**Architecture:** `NgoAuth/settings/` becomes a package. `env.py` is the only module that reads the environment; it returns a frozen `EnvConfig` (or raises one `ImproperlyConfigured` listing every problem). Concern modules read from `ENV`; `base.py` star-imports them in a fixed order and then calls the production check. A new `core` Django app holds the redaction filter and the health view.

**Tech Stack:** Python 3.12, Django 5.2, DRF, python-dotenv, MySQL, Django's test runner.

**Spec:** `docs/superpowers/specs/2026-10-26-modular-bootstrap-design.md` (§2, §4, §5.1–5.5, §5.7). Phase 2 (feature apps, model moves) is a separate plan.

## Global Constraints

- **Guardrails (`AGENTS.md`):**
  - The owner runs every git command. "Owner commits" steps give the owner the exact commands.
  - `manage.py test` that touches the database, `migrate` and any file deletion need the owner's approval.
- **No behaviour change.** Every existing URL, response and setting value stays the same. `diffsettings` output must match the baseline except for the additions listed in each task.
- **Package name stays `NgoAuth`.** Settings module stays `NgoAuth.settings`.
- **File size:** every file stays under ~200 lines.
- **Startup errors:** all validation errors are reported together in one `ImproperlyConfigured`, one problem per line.
- **Defaults:**
  - `DJANGO_ENV=development`
  - `DJANGO_DEBUG=false`
  - `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`
  - `DB_HOST=localhost`, `DB_PORT=3306`, `DB_NAME=ngoauth`, `DB_USER=root`
  - `CORS_ALLOWED_ORIGINS=http://localhost:8100,http://127.0.0.1:8100`
- **Database-free tests:** env, production-check and redaction tests use `SimpleTestCase`, so they create no database and run without approval. Only the health test uses the database.

## Review Focus

1. **`.env` with Windows line endings or spaces around values** (`DJANGO_DEBUG= True `). Expect the value to be trimmed and accepted. Test in Task 2: `test_values_are_trimmed`.
2. **`DJANGO_DEBUG` written as `True` / `FALSE`.** Expect case-insensitive parsing. Test in Task 2: `test_debug_is_case_insensitive`.
3. **`DB_PASSWORD` present but empty in development** (passwordless local MySQL root). Expect this to be accepted, because the key is set. Test in Task 2: `test_empty_db_password_allowed_when_key_present`.
4. **Secrets nested inside a request body dict that gets logged** (e.g. `{"user": {"password": "x"}}`). Expect it masked at any depth. Test in Task 4: `test_nested_secret_masked`.
5. **Health check when MySQL is down.** Expect 503 with no error text in the body. Test in Task 5: `test_database_down_returns_503_without_details`.

---

### Task 1: Split settings into a package (no behaviour change)

**Files:**
- Create: `NgoAuth/settings/__init__.py`, `base.py`, `env.py`, `core.py`, `security.py`, `database.py`, `cache.py`, `auth.py`, `middleware.py`, `static.py`, `email.py`
- Delete (owner approval): `NgoAuth/settings.py`
- Modify: `.env.example` (add `DJANGO_ENV=development`, `CORS_ALLOWED_ORIGINS=http://localhost:8100,http://127.0.0.1:8100`)

**Interfaces:**
- Produces:
  - `NgoAuth/settings/env.py` exports `BASE_DIR: Path` (repo root, i.e. `Path(__file__).resolve().parent.parent.parent`).
  - In this task, `env.py` also exports the raw values `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` and `DB_*` with today's exact parsing, so `security.py` and `database.py` can import them unchanged. Task 2 replaces those raw values.

Mapping of current `settings.py` lines:

| Module | Takes |
|---|---|
| `core.py` | `INSTALLED_APPS` (40–51), `ROOT_URLCONF` (87), `TEMPLATES` + `WSGI_APPLICATION` (89–104), i18n (147–153), `DEFAULT_AUTO_FIELD` (164) |
| `security.py` | `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` (27–33), `CORS_ALLOWED_ORIGINS` (64–68), `CORS_ALLOW_ALL_ORIGINS` (169) |
| `database.py` | `DATABASES` (110–119) |
| `cache.py` | `CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}` (same as Django's default; written out explicitly) |
| `auth.py` | `REST_FRAMEWORK` (70–85), `AUTH_PASSWORD_VALIDATORS` (128–141), `AUTH_USER_MODEL` (166) |
| `middleware.py` | `MIDDLEWARE` (53–62) |
| `static.py` | `STATIC_URL` (159) |
| `email.py` | lines 175–186 |
| `env.py` | `BASE_DIR`, `load_dotenv(BASE_DIR / ".env")`, the raw env reads |
| `base.py` | `from .env import *`, then `core`, `security`, `database`, `cache`, `auth`, `middleware`, `static`, `email`, each as `from .x import *`, in that order. Nothing else. |
| `__init__.py` | `from .base import *` |

- [ ] **Step 1: Record the baseline (secrets filtered out)**

Run, in `djangoauth`:

```bash
python manage.py diffsettings --all | grep -vE "SECRET_KEY|PASSWORD" > "$SCRATCH/settings-before.txt"
```

`$SCRATCH` is the session scratchpad folder.
Expected: the file exists and has more than 100 lines.

- [ ] **Step 2: Create the package files from the mapping above**

Each module gets a one-line docstring naming its concern. `security.py` and `database.py` import their values from `.env`.

- [ ] **Step 3: Owner approves deleting `NgoAuth/settings.py`**

Expected: `NgoAuth/settings.py` is gone; `NgoAuth/settings/` remains.

- [ ] **Step 4: Verify that nothing changed**

Run:

```bash
python manage.py check
python manage.py diffsettings --all | grep -vE "SECRET_KEY|PASSWORD" > "$SCRATCH/settings-after.txt"
diff "$SCRATCH/settings-before.txt" "$SCRATCH/settings-after.txt"
```

Expected:
- `check` prints `System check identified no issues (0 silenced).`
- `diff` prints nothing, or only a `CACHES` line identical in meaning to the default.

- [ ] **Step 5: Owner commits**

```bash
git add NgoAuth/settings .env.example
git rm --cached NgoAuth/settings.py
git commit -m "refactor: split settings into single-concern modules"
```

---

### Task 2: Fail-fast environment validation (`env.py`)

**Files:**
- Modify: `NgoAuth/settings/env.py`, `security.py`, `database.py`, `email.py`
- Create: `core/__init__.py`, `core/tests/__init__.py`, `core/tests/test_env.py`

**Interfaces:**
- Consumes: `BASE_DIR` from Task 1.
- Produces:
  - `load_env(environ: Mapping[str, str]) -> EnvConfig`. It raises `ImproperlyConfigured` whose message starts with `Invalid environment configuration:` followed by one `- <problem>` line per error.
  - `EnvConfig` is a frozen dataclass with fields `env: str`, `secret_key: str`, `debug: bool`, `allowed_hosts: list[str]`, `db_host: str`, `db_port: int`, `db_name: str`, `db_user: str`, `db_password: str`, `email_host_user: str`, `email_host_password: str`, `cors_allowed_origins: list[str]`.
  - The module-level `ENV: EnvConfig = load_env(os.environ)` runs after `load_dotenv`.
  - `security.py`, `database.py` and `email.py` read only from `ENV`; the raw values from Task 1 are removed.

Validation rules (spec §5.2):
- `DJANGO_ENV` must be one of `development`, `test`, `production`.
- `DJANGO_SECRET_KEY` must be non-empty.
- `DJANGO_DEBUG` must be `true` or `false` (case-insensitive).
- `DB_PORT` must be an integer.
- The `DB_PASSWORD` **key** must be present, unless the env is `test`.
- `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` must be both set or both empty.
- Each `CORS_ALLOWED_ORIGINS` item must start with `http://` or `https://`.
- All values are stripped of surrounding whitespace and `\r`.

- [ ] **Step 1: Write the failing tests** in `core/tests/test_env.py` (`SimpleTestCase`). `VALID` is a dict holding a minimal valid environment: `DJANGO_SECRET_KEY="k"`, `DB_PASSWORD=""`.
  - `test_valid_minimal_env_uses_defaults`: `load_env(VALID)` gives `env == "development"`, `debug is False`, `allowed_hosts == ["localhost", "127.0.0.1"]`, `db_port == 3306`, `cors_allowed_origins == ["http://localhost:8100", "http://127.0.0.1:8100"]`.
  - `test_missing_secret_key`: the message contains `DJANGO_SECRET_KEY`.
  - `test_invalid_django_env`: `DJANGO_ENV="prod"` → the message contains `DJANGO_ENV`.
  - `test_invalid_debug`: `DJANGO_DEBUG="yes"` → the message contains `DJANGO_DEBUG`.
  - `test_debug_is_case_insensitive`: `"True"` → `True`; `"FALSE"` → `False`.
  - `test_invalid_db_port`: `"33o6"` → the message contains `DB_PORT`.
  - `test_missing_db_password_key`: `VALID` without `DB_PASSWORD` → the message contains `DB_PASSWORD`. The same with `DJANGO_ENV="test"` → no error.
  - `test_empty_db_password_allowed_when_key_present`: `load_env(VALID).db_password == ""`.
  - `test_email_must_be_paired`: only `EMAIL_HOST_USER` set → the message contains `EMAIL_HOST_PASSWORD`.
  - `test_bad_cors_origin`: `"localhost:8100"` → the message contains `CORS_ALLOWED_ORIGINS`.
  - `test_values_are_trimmed`: `DJANGO_DEBUG=" True\r"` → `debug is True`.
  - `test_all_errors_reported_together`: missing secret + bad port + bad debug → all three names appear in one message.

- [ ] **Step 2: Run the tests and see them fail**

Run: `python manage.py test core.tests.test_env -v 2`
Expected: FAIL / ImportError on `load_env`. No database is created.

- [ ] **Step 3: Implement `load_env` and `EnvConfig`**, and switch `security.py`, `database.py` and `email.py` to `ENV`

Fields map directly. `DATABASES["default"]["PORT"]` becomes `str(ENV.db_port)`, so `diffsettings` stays identical.

- [ ] **Step 4: Run the tests and verify**

Run:

```bash
python manage.py test core.tests.test_env -v 2
python manage.py check
```

Expected: 12 tests OK; check reports no issues. Re-run the Task 1 `diff`; expected: no differences.

- [ ] **Step 5: Owner commits**

```bash
git add NgoAuth/settings core
git commit -m "feat: validate environment at startup and fail fast"
```

---

### Task 3: Production safety check

**Files:**
- Create: `NgoAuth/settings/production_check.py`, `core/tests/test_production_check.py`
- Modify: `NgoAuth/settings/security.py`, `NgoAuth/settings/base.py`

**Interfaces:**
- Consumes: `ENV.env`.
- Produces:
  - `find_problems(s: Mapping[str, Any]) -> list[str]`. It returns `[]` unless `s["ENV"].env == "production"`.
  - `check(s: Mapping[str, Any]) -> None` raises `ImproperlyConfigured("Refusing to start in production:\n- …")` when `find_problems` is non-empty.
  - The last line of `base.py` is `production_check.check(globals())`.
  - `security.py` sets `SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = ENV.env == "production"`, and `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` only in production.

Rules (spec §5.3):
- `DEBUG` is true.
- `SECRET_KEY` is weak: `len < 50`, fewer than 5 unique characters, or starts with `django-insecure-`.
- `ALLOWED_HOSTS` is empty or contains `"*"`.
- `SESSION_COOKIE_SECURE` or `CSRF_COOKIE_SECURE` is false.
- `CORS_ALLOW_ALL_ORIGINS` is true.

- [ ] **Step 1: Write the failing tests** (`SimpleTestCase`). `SAFE` is a dict for a clean production setup: `ENV` with `env="production"`, a 60-character random key, `DEBUG=False`, `ALLOWED_HOSTS=["api.food4u.in"]`, both cookie flags `True`, `CORS_ALLOW_ALL_ORIGINS=False`.
  - `test_safe_production_passes`: `find_problems(SAFE) == []`.
  - `test_non_production_is_never_checked`: `SAFE` with `env="development"` and `DEBUG=True` → `[]`.
  - `test_debug_on_refused`, `test_short_key_refused`, `test_low_variety_key_refused` (`"a" * 60`), `test_insecure_prefix_refused`, `test_wildcard_host_refused`, `test_empty_hosts_refused`, `test_insecure_session_cookie_refused`, `test_insecure_csrf_cookie_refused`, `test_cors_allow_all_refused`: each changes one key and expects exactly one problem naming that setting.
  - `test_check_raises_with_all_problems`: two unsafe keys → `ImproperlyConfigured` whose message names both.

- [ ] **Step 2: Run the tests and see them fail**

Run: `python manage.py test core.tests.test_production_check -v 2`
Expected: ImportError.

- [ ] **Step 3: Implement `find_problems` / `check`**, add the `security.py` flags, and add the call at the end of `base.py`

- [ ] **Step 4: Verify**

Run: `python manage.py test core.tests.test_production_check -v 2` and `python manage.py check`.
Expected: 12 tests OK; no issues. The `diff` from Task 1 shows only the new `SESSION_COOKIE_SECURE`/`CSRF_COOKIE_SECURE` lines, still `False` in development.

- [ ] **Step 5: Owner commits**

```bash
git add NgoAuth/settings core
git commit -m "feat: refuse to start in production with unsafe settings"
```

---

### Task 4: Log redaction

**Files:**
- Create: `core/apps.py` (`CoreConfig`, `name = "core"`), `core/logging_redact.py`, `NgoAuth/settings/logging.py`, `core/tests/test_redaction.py`
- Modify: `NgoAuth/settings/core.py` (append `"core"` to `INSTALLED_APPS`), `NgoAuth/settings/base.py` (import `logging` after `email`)

**Interfaces:**
- Produces:
  - `redact(value: Any) -> Any`: returns a copy with secrets masked as `"***"`. It recurses into dicts, lists and tuples; strings get pattern-masked.
  - `class RedactFilter(logging.Filter)`: `filter(record) -> True` after replacing `record.msg` and `record.args` with redacted versions.
  - `LOGGING` (in `settings/logging.py`): a dictConfig with filter `redact` (`"()": "core.logging_redact.RedactFilter"`), a `console` `StreamHandler` using it, and root logger level `INFO`.

Key pattern, case-insensitive, matched on dict keys:

```python
SECRET_KEY_RE = re.compile(r"password|passwd|secret|token|access|refresh|otp|code|session|authorization|cookie", re.I)
```

String patterns, each replaced with the safe prefix kept:
- `r"Bearer\s+\S+"` → `"Bearer ***"`
- `r"eyJ[\w-]+\.[\w-]+\.[\w-]+"` → `"***"` (JWT shape)
- `r"\b(otp|code)\s*[=:]\s*\d{4}\b"` → `"\1=***"`

- [ ] **Step 1: Write the failing tests** (`SimpleTestCase`)
  - `test_password_key_masked`: `redact({"password": "p", "username": "u"}) == {"password": "***", "username": "u"}`.
  - `test_nested_secret_masked`: `redact({"user": {"new_password": "x"}, "items": [{"refresh": "r"}]})` masks both and keeps the structure.
  - `test_pincode_not_masked`: `redact({"pincode": "581342"})` is unchanged.
  - `test_bearer_token_in_text`: `"Authorization: Bearer abc.def"` → contains `Bearer ***`, not `abc`.
  - `test_jwt_in_text`: a string containing `eyJhbGc.eyJzdWI.sig` loses it.
  - `test_otp_in_text`: `"otp=4721 sent"` → `"otp=*** sent"`.
  - `test_filter_masks_record_args`: a `LogRecord` with `msg="login %s"` and `args=({"password": "p"},)` → after `RedactFilter().filter(record)`, `record.getMessage()` has no `'p'` value.

- [ ] **Step 2: Run the tests and see them fail**

Run: `python manage.py test core.tests.test_redaction -v 2`
Expected: ImportError.

- [ ] **Step 3: Implement `redact`, `RedactFilter`, `LOGGING`**, and register the `core` app

- [ ] **Step 4: Verify**

Run: `python manage.py test core.tests.test_redaction -v 2` and `python manage.py check`.
Expected: 7 tests OK; no issues.

- [ ] **Step 5: Owner commits**

```bash
git add NgoAuth/settings core
git commit -m "feat: redact secrets in logs"
```

---

### Task 5: Health check endpoint

**Files:**
- Create: `core/health.py`, `core/tests/test_health.py`
- Modify: `NgoAuth/urls.py` (add `path("api/health", health, name="health")`; all existing paths unchanged)

**Interfaces:**
- Produces: `health(request: HttpRequest) -> JsonResponse`, GET only (`require_GET`).
  - It runs `SELECT 1` through `django.db.connection.cursor()`.
  - Success: 200 `{"status": "ok", "database": "ok"}`.
  - Any `DatabaseError`: logs it with `logger.exception` (logger name `core.health`) and returns 503 `{"status": "degraded", "database": "error"}`.
  - No authentication, no throttling. It's a plain Django view, so the DRF defaults don't apply.

- [ ] **Step 1: Write the failing tests** (`django.test.TestCase`)
  - `test_health_ok`: `self.client.get("/api/health")` → 200 with the exact JSON above.
  - `test_database_down_returns_503_without_details`: patch `core.health.connection.cursor` with `side_effect=OperationalError("boom")` → 503, exact JSON, and `"boom"` not in the body.
  - `test_post_not_allowed`: POST → 405.
  - `test_no_auth_needed`: the `Authorization: Bearer invalid` header still gives 200.

- [ ] **Step 2: Owner approves running the tests**, because they create the MySQL test database

Run: `python manage.py test core.tests.test_health -v 2`
Expected: FAIL with 404.

- [ ] **Step 3: Implement `health`** and add the URL

- [ ] **Step 4: Owner approves the full phase-1 test run**

Run: `python manage.py test core authapi -v 1`
Expected:
- all new `core` tests pass;
- the existing 42 `authapi` tests still pass;
- `python manage.py check` reports no issues;
- with `runserver` up, `GET http://127.0.0.1:8000/api/health` returns 200 `{"status": "ok", "database": "ok"}`.

- [ ] **Step 5: Owner commits**

```bash
git add core NgoAuth/urls.py
git commit -m "feat: add /api/health endpoint"
```

---

## Done when

- `NgoAuth/settings/` holds 13 small modules, `base.py` has imports only plus the final `production_check.check(globals())`, and `settings.py` is gone.
- Removing `DJANGO_SECRET_KEY` from `.env` stops `manage.py check` with a message naming it.
- `DJANGO_ENV=production` with `DEBUG=true` refuses to start and lists the problem.
- `/api/health` answers 200, or 503 when the database is down.
- The new tests (12 + 12 + 7 + 4 = 35) and the existing 42 pass. The frontend works unchanged against the backend: login, and one list screen per role.
