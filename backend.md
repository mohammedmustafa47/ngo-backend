# Backend Architecture

End-to-end explanation of how this backend is built and why, so the frontend can be built *with* its grain instead of against it. Companion docs: [ui.md](ui.md) (endpoint contracts), [features.md](features.md) (what exists), [roadmap.md](roadmap.md) (what's next).

---

## 1. Stack & Project Layout

- **Django 5.0** + **Django REST Framework 3.15** — the whole API is DRF views/viewsets, no server-rendered pages.
- **MySQL** (`ngoauth` database) — configured in `NgoAuth/settings.py`, credentials currently hardcoded there (see §7).
- **JWT auth** via `djangorestframework-simplejwt` — stateless, no server-side sessions for the API.
- **`django-filter`** for query-param filtering (`?status=pending` on donations).
- **`django-cors-headers`** — CORS is currently wide open (`CORS_ALLOW_ALL_ORIGINS = True`), fine for development, **should be locked to real frontend origins before production**.
- **`python-dotenv`** — loads `.env` at startup for email credentials.

```
NgoAuth/            project config: settings.py, urls.py (root — mounts authapi under /authapi/, plus /api/token/*)
authapi/
  models.py         User, Area, OTP, Role, UserRole, Donation
  serializers.py     request/response shaping + validation
  views.py           auth, area, user, donation endpoints
  analytics.py        aggregation views (separate module, kept out of views.py)
  permissions.py       custom DRF permission classes
  utils.py             OTP generation + area-resolution helpers
  urls.py              all /authapi/* routes
  tests.py             37 tests covering all of the above
```

There is **one Django app** (`authapi`) — everything lives in it. No microservices, no separate analytics service.

---

## 2. Data Model

```
Area ──┬───< User (area FK, nullable)
       └───< Donation (area FK, nullable — inherited from donor at creation)

User ──┬───< Donation (donor FK)
       ├───< Donation (volunteer FK, nullable)
       └───< UserRole >─── Role   (legacy secondary role-tagging system, §4)

OTP  (standalone — keyed by email string, not a User FK)
```

- **`User`** (extends Django's `AbstractUser`): `role` (`super_admin` / `admin` / `donor` / `volunteer`, default `donor`), `email` (**unique**, this is the login credential), `is_email_verified`, `pincode`, `area` (FK, nullable). `username` still exists (required by `AbstractUser`) but is **not** unique-enforced for login purposes — email is.
- **`Area`**: `name` (unique), `pincodes` (JSON list of strings), `is_active`. This is the only "geography" concept in the system — deliberately just a flat pincode list, no GPS/polygons (see roadmap §8 for why).
- **`Donation`**: `donor`, `volunteer` (nullable until picked), `area` (nullable, copied from `donor.area` at creation time — **not** re-derived later, so if a donor's area changes after the donation exists, the donation keeps its original area), `status` (`pending`/`picked`/`delivered`/`cancelled`), `created_at`, `updated_at` (auto-updated every save — this is what analytics uses to compute delivery time).
- **`OTP`**: `email` (plain string, not a FK — works even mid-registration before the User row is finalized), `code` (4 digits), `purpose` (`verify_email`/`reset_password`), `is_verified`, `is_used`, `created_at` (10-minute expiry computed from this, not stored).
- **`Role`/`UserRole`**: a separate, mostly-vestigial tagging system — see §4's warning.

---

## 3. Auth & Token Lifecycle

**Login is by email, not username** (`LoginSerializer` / `LoginView`) — the view looks up `User` by `email__iexact`, then internally calls Django's `authenticate()` with that user's `username` (SimpleJWT/Django's `authenticate()` still keys off `USERNAME_FIELD` under the hood; this is invisible to the API caller).

**Token lifetimes are SimpleJWT's untouched defaults** — not overridden anywhere in `settings.py`:
- **Access token: 5 minutes**
- **Refresh token: 1 day**
- No rotation, no blacklisting on refresh.

⚠ **This is the single most important thing for the frontend to design around.** A 5-minute access token means any session longer than that will hit 401s constantly unless the frontend proactively refreshes. Recommended pattern:
- On every API call, catch `401` → call `POST /api/token/refresh/` with the stored `refresh` token → retry the original request once with the new `access` token.
- Alternatively, decode the JWT `exp` claim client-side and refresh a little before it expires (e.g. at 4 minutes).
- Store `refresh` somewhere that survives a page reload (not just in-memory) or users get logged out on every refresh.
- If `/api/token/refresh/` itself 401s, the refresh token has expired (>1 day since login) — force a full re-login.

**Registration → verification is a two-step, stateful process**, not just a form submit:
1. `POST /auth_register` creates the `User` row with `is_active=False`, generates a 4-digit `OTP` (purpose `verify_email`), emails it.
2. `POST /auth_verify_email` checks the code, flips `is_active=True` and `is_email_verified=True`.
3. Login is blocked with `403` until step 2 completes — build the OTP screen as a mandatory step between register and login, not a skippable one.

**`/auth_register` only ever produces a `donor` or `volunteer`.** `role: "admin"` and `role: "super_admin"` are both rejected at validation (`400`) — there is no self-signup path to either. See §4a for how those accounts actually get created.

**Password reset is a three-step, stateful process** (`request` → `verify-otp` → `confirm`) — step 3 will `400` if step 2 wasn't completed first for that email/code pair (the serializer checks `OTP.is_verified=True`), so the frontend can't skip straight from "enter email" to "set new password."

**OTP invalidation**: `create_otp()` marks all previous unused OTPs for that `(email, purpose)` as used before creating a new one — so "resend code" always fully invalidates the old code, there's no window where both work.

---

## 4. Authorization Architecture

Two layers, applied in order for every request:

1. **`permission_classes`** on the view — a yes/no gate on whether the request is allowed to reach the view at all (e.g. `IsSuperAdmin`, `IsAreaOrSuperAdmin`).
2. **`get_queryset()`** on the view — scopes *which rows* that user can see once past the gate (e.g. an Area Admin passes the `IsAreaOrSuperAdmin` gate but `get_queryset` still filters to `area=self.area`).

This two-layer pattern is used consistently across `AllUserViewSet` and `DonationViewSet` — **a 403 means the role is wrong; a 404 on a specific ID usually means the role is right but the object isn't in your scope** (wrong area, not your donation, etc.). Distinguish these in the frontend's error handling rather than showing a generic "error" for both.

**Custom permission classes** (`authapi/permissions.py`):
| Class | Allows |
|---|---|
| `IsSuperAdmin` | `role == 'super_admin'` only |
| `IsAreaOrSuperAdmin` | `role in ('admin', 'super_admin')` |
| `IsOwnerOrAdmin` | object-level: the donation's own donor, or `admin`/`super_admin` |
| `IsAdminRole` | legacy, `role == 'admin'` only (still used by nothing critical) |

⚠ **Two parallel role systems exist — know which one is authoritative.** The `User.role` CharField is what every permission class and every `get_queryset` actually checks — **this is the one that matters for access control**. The separate `Role`/`UserRole` tables (exposed via `/add-role/` and `/user-role/`) only affect what `UserSerializer`/`ProfileSerializer` *display* as a user's role (they check `UserRole` first, fall back to `.role`). Creating a `UserRole` link does **not** grant any actual permission. Don't build a "manage permissions" UI on top of `/user-role/` expecting it to change what a user can do.

---

## 4a. How Super Admin and Area Admin Accounts Actually Get Created

Neither role is self-service — both are provisioned top-down, on purpose (an Area Admin controls a whole region's donors/volunteers/donations, and a Super Admin controls everything, so neither should be creatable by just filling out a public form).

- **Super Admin**: no API endpoint at all. Created via `python manage.py createsuperuser` (or directly in Django admin) with `role='super_admin'` set manually. This is an infrastructure-level bootstrap step, not something the frontend ever calls.
- **Area Admin**: `POST /create-area-admin`, **Super-Admin-only** (`IsSuperAdmin`). Body: `username`, `email`, `password`, `area_id`. Rejects if `area_id` doesn't exist or if that area already has an Area Admin (`400`). Unlike `/auth_register`, the created account is **immediately active and email-verified** — no OTP step — since the Super Admin is vouching for it directly. The frontend should treat this as "Super Admin fills out a form and hands the new Area Admin their credentials," not an invite-link flow (there is no invite/magic-link mechanism today).
- `GET /pending-area-users` + `POST /assign-area` are a separate, older mechanism — they only handle donors/volunteers whose pincode didn't match any `Area` yet (`area=null`) by letting a Super Admin manually attach them to an area after the fact. They do **not** change a user's `role` and cannot be used to grant Area Admin access.

---

## 5. Multi-Area Design (how "which area am I in" actually resolves)

- A pincode is matched against `Area.pincodes` (a JSON list) via a **Python loop over all active areas** (`resolve_area()` in `utils.py`) — not a database query. Fine at the scale of a handful of pilot towns; if this grows to hundreds of areas, this should become an indexed lookup table (`pincode → area_id`) instead.
- No match → the user is created anyway with `area=None` ("pending"), not rejected. The frontend must treat `area: null` / `area: "pending"` as a valid, expected state for a freshly-registered donor/volunteer, not an error state.
- A `Donation`'s `area` is a **snapshot at creation time** from the donor's area — it does not update retroactively if the donor is later reassigned. Historical donations stay attributed to the area they were created in.
- Area Admin accounts bypass this pincode-matching flow entirely — they're created directly against a chosen `Area` via `POST /create-area-admin` (§4a), not derived from a pincode.

---

## 6. Request Lifecycle Example

Tracing `POST /authapi/donations/` end to end, useful for understanding where to debug a frontend issue:

1. **CORS middleware** checks `Origin` header (currently allows everything).
2. **`JWTAuthentication`** (DRF's `DEFAULT_AUTHENTICATION_CLASSES`) reads the `Authorization: Bearer <token>` header, decodes it, sets `request.user`. No token / bad token → `request.user` is `AnonymousUser`, not an exception yet.
3. **`DonationViewSet.get_permissions()`** runs — for `create`, that's `IsAuthenticated`. Anonymous user → `401` here, request stops.
4. **`DonationSerializer`** validates the body — `donor`, `status`, `volunteer`, `area`, `created_at`, `updated_at` are all `read_only_fields`, so anything sent for those is silently dropped, not an error. Missing `item_name`/`pickup_address`/`contact_number` → `400` with field errors.
5. **`perform_create()`** sets `donor=request.user` and `area=request.user.area` explicitly — this is the only place a donation's area is ever set.
6. Response is the full serialized `Donation`, `201`.

The same shape (permission → queryset/serializer scoping → response) applies to every endpoint in [ui.md](ui.md) — if something 401s, it's step 2; if it 403s, step 3; if it 400s, step 4; if a `GET` returns fewer rows than expected, it's `get_queryset` scoping (§4), not a bug.

---

## 7. Configuration & Environment

- **`.env`** (gitignored) holds `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` — a Gmail App Password. Loaded via `python-dotenv` at the top of `settings.py`. Without both set, `EMAIL_BACKEND` falls back to the console backend (emails print to the server log instead of sending) — **useful to know when testing against a local backend**: OTP codes will be in the terminal output, not an inbox.
- **Database credentials are currently hardcoded** in `settings.py` (MySQL `root`/`1234` on `localhost`) — fine for local dev, must move to environment variables before any shared/staging/production deployment.
- **`SECRET_KEY` is also hardcoded** and checked into the repo — same caveat.
- **`CORS_ALLOWED_ORIGINS`** lists `localhost:8100`/`127.0.0.1:8100` but `CORS_ALLOW_ALL_ORIGINS = True` currently overrides it, so effectively any origin is allowed. If the frontend runs on a different port during development, it'll still work today — but don't rely on this once CORS gets locked down.

---

## 8. Pagination, Filtering, Throttling (global config in `REST_FRAMEWORK` settings)

- **Pagination**: `PageNumberPagination`, 10 items/page, applied globally — every `ModelViewSet` list endpoint (`donations`, `users`, `areas`, `add-role`, `user-role`) and `ListAPIView` (`pending-area-users`) returns the `{count, next, previous, results}` envelope. **The analytics endpoints (§9) are plain `APIView`s and are NOT paginated** — they return one aggregated object, not a list.
- **Filtering**: only `donations` has a filter backend wired up (`?status=pending|picked|delivered|cancelled`). No other endpoint supports query-param filtering today — don't build a filter UI against `/users/` or `/areas/` expecting server-side support.
- **Throttling**: `ScopedRateThrottle` at 3/min, applied only to `auth_resend_otp` and `auth_password_reset/request`. Throttling is keyed by IP for anonymous requests (both these endpoints are `AllowAny`) — a shared office/NAT IP could hit this limit across different users' requests. A `429` from these two endpoints specifically means "wait and retry," not a real error — show a cooldown message, not a generic failure.

---

## 9. Analytics: How the Numbers Are Computed

`authapi/analytics.py` holds pure aggregation functions (`build_totals`, `build_timeseries`, `build_leaderboard`, `build_avg_delivery_hours`, `build_users_by_role`, `build_by_area`), each doing one `GROUP BY`-style DB query via Django's `annotate`/`aggregate` — **no caching layer**, every call re-queries live. At pilot scale (single town, low volume) this is fine; if a dashboard polls these endpoints frequently once there's real traffic, that's the first place to add a short TTL cache (roadmap flags this).

`avg_delivery_hours` is computed **in Python**, not SQL — it pulls `(created_at, updated_at)` pairs for delivered donations and averages `total_seconds()` in application code, specifically to stay portable across DB backends (MySQL doesn't do datetime subtraction the way Postgres does). It returns `null` when there are zero delivered donations — **the frontend must handle `null` here**, not assume a number.

---

## 10. Database Migrations (chronological, for context on why fields exist)

| Migration | What it added |
|---|---|
| `0001_initial` | Base `User`, `Role`, `UserRole` |
| `0002_donation` | `Donation` model |
| `0003_otp_user_is_email_verified` | `OTP` model, `User.is_email_verified` |
| `0004_alter_donation_options` | `Donation.Meta.ordering` (fixed a pagination warning) |
| `0005_area_...` | `Area` model, `User.pincode`/`area`, `Donation.area`, `super_admin` role choice |
| `0006_alter_user_options` | `User.Meta.ordering` (same pagination-warning fix, for users) |
| `0007_donation_updated_at` | `Donation.updated_at` (powers `avg_delivery_hours`) |
| `0008_alter_user_email` | `User.email` made `unique=True` (enables email-based login) |

No new migration was needed for the §4a Area Admin creation flow — it reuses the existing `User.role`/`User.area` fields, it's purely new serializer/view/permission code.

---

## 11. Known Architectural Debt (be aware, don't design around it as if permanent)

- Dual role system (§4) — confusing but not dangerous as long as the frontend only reads/writes `user.role`, never builds features on `/add-role/`+`/user-role/` for access control.
- Pincode-to-area matching is O(number of areas) per registration, in Python — fine now, will need indexing if areas scale into the hundreds.
- No response caching on analytics endpoints — fine for a pilot, a polling dashboard should self-throttle its own refresh interval (e.g. every 30–60s) rather than relying on the backend to do it.
- No CI pipeline — nothing stops a merged backend change from silently breaking a documented contract in [ui.md](ui.md); until that exists, treat this document and `ui.md` as needing manual re-sync after backend changes, not as permanently guaranteed contracts.
