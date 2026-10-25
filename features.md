# Features

A snapshot of everything the NGO food-donation backend supports today, organized by who can do what. Companion to [roadmap.md](roadmap.md), which documents what's planned next.

---

## 1. Authentication & Account Lifecycle (all users)

| Feature | Endpoint | Notes |
|---|---|---|
| Register | `POST /authapi/auth_register` | username, email, password, pincode, optional role. Email must strictly match `example@gmail.com` (Gmail addresses only). Account is created **inactive** until email is verified. The pincode is resolved to an `Area` automatically (see §2) — no match just means "pending area," registration still succeeds. Registering as `super_admin` is rejected; registering as `admin` (Area Admin) requires the pincode to match an existing area, and only one Area Admin is allowed per area. |
| Verify email | `POST /authapi/auth_verify_email` | `{email, otp}`. 4-digit code, expires in 10 minutes. Activates the account on success. |
| Resend verification code | `POST /authapi/auth_resend_otp` | `{email}`. Invalidates the previous unused code and issues a new one. Blocked once the email is already verified. Rate-limited to 3 requests/minute. |
| Login | `POST /authapi/auth_login` | `{email, password}`. Logs in by email, not username — usernames aren't guaranteed unique, emails are (enforced at the database level). Returns JWT `access` + `refresh` tokens. Blocked with a 403 until the email is verified. |
| View own profile | `GET /authapi/auth_profile` | Requires `Authorization: Bearer <access_token>`. Returns id, username, email, first/last name, role, area name (or `"pending"`), pincode, `is_email_verified`, `date_joined`, `last_login` — one call for a UI profile page. |
| Dashboard | `GET /authapi/auth_dashboard` | Requires login. Returns a welcome message + basic user info (id, username, email, role, area). |
| Forgot password — request code | `POST /authapi/auth_password_reset/request` | `{email}`. Sends a 4-digit reset code. Rate-limited to 3 requests/minute. |
| Forgot password — verify code | `POST /authapi/auth_password_reset/verify-otp` | `{email, otp}`. Marks the code as verified so the next step can proceed. |
| Forgot password — set new password | `POST /authapi/auth_password_reset/confirm` | `{email, otp, new_password, confirm_password}`. Requires the code to have been verified in the previous step; enforces Django's password strength rules and that the two password fields match. |
| Token refresh | `POST /api/token/refresh/` | Standard SimpleJWT refresh — exchange the refresh token for a new access token when it expires. |

OTP codes are emailed via Gmail SMTP (falls back to printing to the console in local dev if no email credentials are configured).

---

## 2. Roles & Areas

The platform is organized around **Areas** (towns/zones — the pilot area is Murudeshwar) rather than one flat admin over everything:

- **Super Admin** — platform-wide, not tied to any area. Opens new `Area`s, sees/manages everything everywhere. Never created through public registration — bootstrapped manually.
- **Area Admin** (stored as role `admin`) — manages only their own `Area`'s donors, volunteers, and donations. Exactly one per area.
- **Donor** and **Volunteer** — matched to an `Area` automatically by the pincode given at signup. `donor` is the default role if none is chosen at registration.

If a signup's pincode doesn't match any existing `Area`, the account is still created but sits in a **pending area** state (`area=None`) until a Super Admin assigns it — see §3.

Role can be attached either via the simple `role` field on the user or via a separate `UserRole` relation (used for custom roles created through `/authapi/add-role/`).

---

## 3. Super Admin — what they can view and do

- **Manage areas** (`GET/POST/PATCH/DELETE /authapi/areas/`) — open a new town by creating an `Area` with a name and its list of pincodes. Anyone authenticated can read the area list/detail; only the Super Admin can create/update/delete.
- **Review pending signups** (`GET /authapi/pending-area-users`) — lists every user whose pincode didn't match an existing area yet.
- **Assign a user to an area** (`POST /authapi/assign-area` with `{user_id, area_id}`) — clears a pending signup or reassigns/promotes a user. Refuses to create a second Area Admin for an area that already has one.
- **See everything, everywhere** — `users` and `donations` querysets are unrestricted for a Super Admin (no area filter applied), unlike an Area Admin.
- Everything an Area Admin, Donor, and Volunteer can also do, since Super Admin is just another authenticated user underneath.

## 4. Area Admin — what they can view and do

- **User management scoped to their own area** (`/authapi/users/`) — list, view, update, or delete donor/volunteer/admin accounts, but only the ones in their own `Area`.
- **Manage roles** (`/authapi/add-role/`) — create/list the available `Role` records (e.g. Admin, Donor, Volunteer).
- **Assign roles to users** (`/authapi/user-role/`) — link a user to a role via `UserRole`.
- **View all donations in their own area**, regardless of status or owner — donations from other areas are invisible to them.
- Everything a Donor and Volunteer can also do (profile, dashboard, etc.).

## 5. Donor — what they can view and do

- Register/login/verify/reset password like any user; gets matched to an `Area` by pincode at signup.
- **Create a donation** (`POST /authapi/donations/`) — item name, quantity, description, pickup address, contact number. The donation is automatically linked to the logged-in donor, inherits the donor's `Area`, and starts in `pending` status.
- **View only their own donations** — the donation list/detail queryset for a donor is filtered to `donor=self`, regardless of area.
- Cannot pick or update the delivery status of donations (those actions require being the assigned volunteer).

## 6. Volunteer — what they can view and do

- Register/login/verify/reset password like any user; gets matched to an `Area` by pincode at signup.
- **View pending donations in their own area, plus donations already assigned to them** — queryset is `(status='pending' AND area=self.area) OR volunteer=self`. A volunteer never sees another area's pending donations.
- **Pick a donation** (`POST /authapi/donations/{id}/pick_donation/`) — claims a `pending` donation, assigns themselves as the volunteer, and moves it to `picked`. Fails if the donation is no longer pending or isn't visible to them (prevents two volunteers picking the same donation).
- **Update delivery status** (`POST /authapi/donations/{id}/update_status/`) — moves a donation they are assigned to from `picked` to `delivered` or `cancelled`. Fails if they aren't the assigned volunteer, or if the target status isn't `delivered`/`cancelled`.
- Cannot create donations (that's a Donor action) or view another volunteer's already-picked donations.

---

## 7. Donation Lifecycle

```
pending → (volunteer picks) → picked → (volunteer updates) → delivered
                                              └────────────→ cancelled
```

- `pending`: created by a donor, visible to volunteers/admins in the same `Area`, not yet claimed.
- `picked`: claimed by exactly one volunteer; other volunteers can no longer pick it.
- `delivered` / `cancelled`: terminal states set by the assigned volunteer.
- Direct edits/deletes (`PATCH`/`DELETE /authapi/donations/{id}/`) are restricted to the donation's own donor, its Area Admin, or the Super Admin (`IsOwnerOrAdmin` permission) — nobody else can modify a donation outside the pick/update-status actions above.

---

## 8. Analytics (data for dashboards)

Every list-based endpoint above returns raw records; these return pre-aggregated numbers instead, meant to be plotted directly by a frontend charting library — no client-side math needed.

| Endpoint | Who | Returns |
|---|---|---|
| `GET /authapi/analytics/super-admin` | Super Admin | Platform-wide totals by status, a daily time-series, a top-5 volunteer leaderboard, a **per-area breakdown** (`by_area`), users-by-role platform-wide, and average pending→delivered time in hours. |
| `GET /authapi/analytics/area-admin` | Area Admin (their own area) or Super Admin (`?area_id=<id>` to drill into any area) | Same shape as above, scoped to one `Area`. |
| `GET /authapi/analytics/donor` | Any authenticated user | Their own donation totals by status, a time-series, and total items donated (sum of quantity). |
| `GET /authapi/analytics/volunteer` | Any authenticated user | Their own pickup/delivery totals, a delivery time-series, and their average delivery time. |

These endpoints exist today; the charts/UI that consume them are not built yet (frontend work, see [roadmap.md §3](roadmap.md#3-analytics--visual-dashboards)).

---

## 9. Cross-Cutting Protections

- **Pagination**: every list endpoint (`donations`, `users`, `areas`, etc.) is paginated at 10 items/page.
- **Rate limiting**: `auth_resend_otp` and `auth_password_reset/request` are capped at 3 requests/minute to prevent OTP spam.
- **Permission lock-down**: `add-role`, `user-role`, `users`, `areas`, and the analytics endpoints all require authentication plus the appropriate admin tier where relevant — none of them are open to the public.
- **Automated tests**: `authapi/tests.py` covers the full auth flow, the donation lifecycle, the area hierarchy, and the analytics endpoints — 37 tests, all passing.

---

## 10. Tech Stack

- Django 5.x + Django REST Framework
- JWT auth via `djangorestframework-simplejwt`
- MySQL database
- Gmail SMTP for OTP emails (console backend in local dev), configured via `.env` + `python-dotenv`
- `django-filter` for donation status filtering
- `django-cors-headers` for cross-origin frontend access

---

## 11. Known Gaps / Not Yet Built

- Analytics endpoints have no response caching yet — fine at pilot scale, worth adding a short TTL cache once a real frontend polls them frequently.
- No escalation workflow yet for a donation/dispute stuck inside one area to reach the Super Admin.
- Address matching is pincode-only (no GPS/geofencing) — a deliberate near-term tradeoff, see [roadmap.md §8](roadmap.md#8-decisions-locked-in).
- Notifications are email-only; SMS/WhatsApp is deferred.
- No CI/CD pipeline yet — tests are run manually.
