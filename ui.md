# Frontend Integration Guide

Everything the existing/updated frontend needs to talk to this API: every endpoint, request/response shapes, auth rules, and how the pieces map to screens. Companion to [features.md](features.md) (what exists) and [roadmap.md](roadmap.md) (what's next).

---

## 0. Conventions

- **Base path**: everything below is mounted under `/authapi/` except token refresh, which is at the project root. Full example: `http://localhost:8000/authapi/auth_login`.
- **Auth header**: `Authorization: Bearer <access_token>` on every endpoint marked "Auth required" below. The token comes from `/auth_login`.
- **Content type**: `application/json` for all request bodies.
- **Pagination**: every list endpoint (`donations`, `users`, `areas`, `pending-area-users`, `add-role`, `user-role`) returns DRF's standard page envelope, 10 items/page:
  ```json
  { "count": 42, "next": "http://.../?page=2", "previous": null, "results": [ ... ] }
  ```
  Page through with `?page=2`. **Always read `results`, not the raw array**, from these endpoints.
- **Errors**: validation errors come back as `{"field_name": ["message"]}` with status 400. Auth/permission errors come back as `{"detail": "message"}` with status 401 (not logged in) or 403 (logged in, wrong role) or 404 (not visible to you / doesn't exist).
- **Rate limiting**: `auth_resend_otp` and `auth_password_reset/request` are capped at 3 requests/minute — a 4th quick call returns 429.

---

## 1. Roles & Areas (read this before building any screen)

The app has **four roles**, and three of them are tied to an **Area** (a town/zone — pilot area is Murudeshwar):

| Role (`user.role` value) | Tied to an Area? | Scope |
|---|---|---|
| `super_admin` | No | Everything, everywhere |
| `admin` (displayed as "Area Admin") | Yes, exactly one area | Their own area's users + donations |
| `donor` | Yes | Their own donations, regardless of area |
| `volunteer` | Yes | Pending donations in their own area, plus donations assigned to them |

A signup whose pincode doesn't match any existing area still succeeds, but `area` comes back as `"pending"` (or `null` for Super Admin) until a Super Admin assigns one — **build a "pending area" state into the UI**, don't assume every user has an area immediately after registering.

**What this means for the frontend**: after login, branch your UI/navigation on `user.role` from the login/profile response. A `donor` and `volunteer` share almost nothing UI-wise; `admin` and `super_admin` share a lot, but `super_admin` has extra area-management screens `admin` doesn't.

---

## 2. Onboarding & Auth

| Step | Method & Path | Auth | Body | Success response |
|---|---|---|---|---|
| Register | `POST /auth_register` | none | `{username, email, password, pincode, role?}` | `201` `{"detail": "Registration successful. A verification code has been sent to your email."}` |
| Verify email | `POST /auth_verify_email` | none | `{email, otp}` | `200` `{"detail": "Email verified successfully."}` |
| Resend code | `POST /auth_resend_otp` | none | `{email}` | `200` `{"detail": "A new verification code has been sent to your email."}` |
| Login | `POST /auth_login` | none | `{email, password}` | `200` — see below |
| Refresh token | `POST /api/token/refresh/` (⚠ no `/authapi` prefix) | none | `{refresh}` | `200` `{"access": "..."}` |
| Get own profile | `GET /auth_profile` | ✅ | — | `200` — see below |
| Dashboard | `GET /auth_dashboard` | ✅ | — | `200` `{"message": "welcome to dashboard", "user": {...}}` |

**Register notes**:
- `email` **must** match `example@gmail.com` — any other domain is rejected with 400.
- `pincode` is **required** — used to auto-match an `Area`. No match = pending, not an error.
- `role` is optional (defaults to `donor`). Valid self-service values: `donor`, `volunteer` only. `admin` and `super_admin` are both rejected outright (400) — neither is self-service. See §4a for how Area Admin accounts get created.
- Account is created **inactive** — login is blocked (403) until `auth_verify_email` succeeds. **UI flow: registration form → OTP entry screen → success → redirect to login.**

**Login response** (`200`):
```json
{
  "refresh": "<jwt>",
  "access": "<jwt>",
  "user": { "id": 5, "username": "donora", "email": "donora@gmail.com", "role": "donor", "area": "Murudeshwar" },
  "result": true
}
```
Login failure modes: `403` `{"detail": "Email not verified..."}` if not verified yet, `401` `{"detail": "invalid credentials"}` otherwise.

**Profile response** (`200`) — the richer, one-call source for a "My Profile" screen:
```json
{
  "id": 5, "username": "donora", "email": "donora@gmail.com",
  "first_name": "", "last_name": "",
  "role": "donor", "area": "Murudeshwar", "pincode": "581342",
  "is_email_verified": true,
  "date_joined": "2026-09-05T04:45:17Z", "last_login": "2026-09-05T05:00:00Z"
}
```
`area` here can be `"pending"` (unmatched pincode, waiting on Super Admin) or `null` (only for `super_admin`).

---

## 3. Forgot Password (3-screen flow)

| Screen | Method & Path | Body | Response |
|---|---|---|---|
| 1. Enter email | `POST /auth_password_reset/request` | `{email}` | `200` `{"detail": "A password reset code has been sent to your email."}` |
| 2. Enter OTP | `POST /auth_password_reset/verify-otp` | `{email, otp}` | `200` `{"detail": "OTP verified. You can now set a new password."}` |
| 3. New password + confirm | `POST /auth_password_reset/confirm` | `{email, otp, new_password, confirm_password}` | `200` `{"detail": "Password has been reset successfully."}` |

Step 3 requires step 2 to have already succeeded for that `(email, otp)` pair, and enforces `new_password == confirm_password` plus Django's password-strength rules — surface field-level 400 errors from the response directly.

---

## 4. Area Management (Super Admin screens)

| Action | Method & Path | Auth | Body |
|---|---|---|---|
| List areas | `GET /areas/` | any authenticated user | — |
| View one area | `GET /areas/{id}/` | any authenticated user | — |
| **Open a new town** | `POST /areas/` | Super Admin only | `{name, pincodes: ["581342", "581343"], is_active?}` |
| Update an area | `PATCH /areas/{id}/` | Super Admin only | any subset of the above |
| Delete an area | `DELETE /areas/{id}/` | Super Admin only | — |

Area object shape: `{id, name, pincodes: [...], is_active, created_at}`. Any logged-in user can read the list (e.g. so an Area Admin can display their own area's name/pincodes), but only Super Admin can write.

## 4a. Create an Area Admin (Super Admin only)

| Action | Method & Path | Auth | Body |
|---|---|---|---|
| **Create Area Admin** | `POST /create-area-admin` | Super Admin only | `{username, email, password, area_id}` |

Creates the Area Admin account directly — **active and email-verified immediately**, no OTP step (unlike `/auth_register`). Fails `400` if `area_id` doesn't exist or that area already has an Area Admin. There's no invite-link flow yet, so the UI should show the Super Admin the credentials they just set so they can hand them to the new admin out-of-band. Response is the created user object (`{id, username, email, role: "admin", area}`).

## 5. Pending Signups & Assignment (Super Admin only)

| Action | Method & Path | Body |
|---|---|---|
| List pending signups | `GET /pending-area-users` | — |
| Assign a user to an area | `POST /assign-area` | `{user_id, area_id}` |

The pending list returns paginated `UserSerializer` objects (`{id, username, email, role, area: null}`). Build this as a queue/table with an "Assign to Area" action per row that calls `assign-area`. Fails with 400 if you try to assign a second Area Admin to an area that already has one.

---

## 6. User Management

| Action | Method & Path | Auth | Notes |
|---|---|---|---|
| List users | `GET /users/` | Area Admin or Super Admin | Area Admin sees only their own area's users; Super Admin sees everyone |
| View one user | `GET /users/{id}/` | Area Admin or Super Admin | 404 if outside your area (Area Admin) |
| Update a user | `PATCH /users/{id}/` | Area Admin or Super Admin | ⚠ Only `username`/`email` are actually writable through this endpoint — `role` and `area` are read-only computed fields here and will be **silently ignored** if included in the body. To change a user's area, use `/assign-area` (§5) instead. |
| Delete a user | `DELETE /users/{id}/` | Area Admin or Super Admin | |

User object shape (used here, in login, and in pending-users): `{id, username, email, role, area}` (`area` is the area **name** or `null`, not an id).

---

## 7. Custom Roles (`add-role` / `user-role`) — secondary system, use with care

These predate the Area Admin/Super Admin model and manage a separate `Role` table (free-text role names, e.g. for badges/tags), **not** the `role` field that drives permissions everywhere else in this app.

| Action | Method & Path | Auth | Body |
|---|---|---|---|
| List/create custom roles | `GET/POST /add-role/` | Area Admin or Super Admin | `{name}` |
| Link a user to a custom role | `GET/POST /user-role/` | Area Admin or Super Admin | `{user: "<username>", role: "<role name>"}` |

⚠ **Gotcha for the frontend**: creating a `UserRole` link here does **not** change what that user can actually do (permissions check `user.role` directly, set at registration or via `/assign-area`'s sibling flows) — it only affects what `UserSerializer`/`ProfileSerializer` *display* as the role (they check `UserRole` first, then fall back to the `role` field). Don't build a "change user's permissions" UI on top of this — there isn't a dedicated endpoint for that today; it's set at registration time.

---

## 8. Donations

| Action | Method & Path | Auth | Who / Notes |
|---|---|---|---|
| List donations | `GET /donations/` | ✅ | Scoped automatically by role (see §1 table). Supports `?status=pending` filter. |
| View one donation | `GET /donations/{id}/` | ✅ | 404 if not visible to your role/area |
| Create a donation | `POST /donations/` | ✅ | Donor screen — see body below |
| Edit a donation | `PATCH /donations/{id}/` | ✅ + owner/Area Admin/Super Admin | Only the donor who created it, their Area Admin, or Super Admin |
| Delete a donation | `DELETE /donations/{id}/` | ✅ + owner/Area Admin/Super Admin | Same restriction as edit |
| **Pick a donation** | `POST /donations/{id}/pick_donation/` | ✅ (volunteer) | No body. Fails 400 if already picked, 404 if not visible to you |
| **Update delivery status** | `POST /donations/{id}/update_status/` | ✅ (assigned volunteer) | `{status: "delivered" | "cancelled"}`. Fails 403 if you're not the assigned volunteer |

**Create donation** body:
```json
{ "item_name": "Rice", "quantity": 5, "description": "optional", "pickup_address": "123 St", "contact_number": "9876543210" }
```
Don't send `donor`, `status`, `volunteer`, `area`, `created_at`, `updated_at` — they're server-set and read-only (donation inherits the donor's area automatically, starts at `status: "pending"`).

**Donation object shape** (what every list/detail/create response returns):
```json
{
  "id": 12, "donor": 5, "donor_name": "donora",
  "item_name": "Rice", "quantity": 5, "description": "",
  "pickup_address": "123 St", "contact_number": "9876543210",
  "status": "pending", "volunteer": null, "volunteer_name": null,
  "area": 1, "created_at": "2026-09-05T04:45:17Z", "updated_at": "2026-09-05T04:45:17Z"
}
```
Note `area` here is an **id**, not a name (unlike the `User` serializer) — join against `/areas/` if you need to display the name in an admin-facing table.

**Donation lifecycle for the UI**:
```
pending → (volunteer taps "Pick Up") → picked → (volunteer taps "Delivered"/"Cancel") → delivered / cancelled
```

---

## 9. Analytics / Dashboards

All read-only, all `GET`, no body. These return pre-aggregated numbers meant to be handed straight to a chart component — don't recompute totals client-side from the raw `/donations/` list.

| Endpoint | Auth | Query params | Response fields |
|---|---|---|---|
| `GET /analytics/super-admin` | Super Admin only | — | `totals`, `timeseries`, `leaderboard`, `by_area`, `users_by_role`, `avg_delivery_hours` |
| `GET /analytics/area-admin` | Area Admin (own area) or Super Admin | `?area_id=<id>` **required** for Super Admin, ignored for Area Admin | `area`, `totals`, `timeseries`, `leaderboard`, `users_by_role`, `avg_delivery_hours` |
| `GET /analytics/donor` | any authenticated user | — | `totals`, `timeseries`, `total_items_donated` |
| `GET /analytics/volunteer` | any authenticated user | — | `totals`, `timeseries` (delivered only), `avg_delivery_hours` |

Field shapes, consistent across all four:
```json
{
  "totals": { "pending": 12, "picked": 4, "delivered": 58, "cancelled": 3 },
  "timeseries": [ { "date": "2026-09-01", "count": 5 }, { "date": "2026-09-02", "count": 3 } ],
  "leaderboard": [ { "username": "vol_amit", "delivered": 21 } ],
  "by_area": [ { "area": "Murudeshwar", "pending": 3, "picked": 1, "delivered": 58, "cancelled": 2, "total": 64 } ],
  "users_by_role": { "donor": 40, "volunteer": 12, "admin": 1 },
  "avg_delivery_hours": 6.4
}
```
- `by_area` only appears in the Super Admin response.
- `avg_delivery_hours` can be `null` if there are no delivered donations yet — handle that in the chart/tile, don't assume a number.
- Calling `/analytics/area-admin` as Super Admin **without** `?area_id=` returns `400` — use `/areas/` (§4) to populate an area picker first.

**Suggested charts per role** (data's ready, pick your library):
- **Super Admin**: bar chart of `by_area` (one bar per area), donut of `users_by_role`, drill-down button per area → `/analytics/area-admin?area_id=`.
- **Area Admin**: line chart of `timeseries`, stacked bar of `totals`, leaderboard table.
- **Donor**: donut of `totals`, KPI tile for `total_items_donated`.
- **Volunteer**: KPI tile for `totals.delivered`, line chart of `timeseries`.

---

## 10. Screens by Role — quick build checklist

**Everyone**: Register → Verify OTP → Login → (Forgot Password: email → OTP → new password) → Profile page → Logout.

**Donor**: Dashboard (analytics/donor tiles) → My Donations list (`/donations/` auto-scoped) → New Donation form (`POST /donations/`) → Donation detail/edit.

**Volunteer**: Dashboard (analytics/volunteer tiles) → Available Donations list (pending, own area) → "Pick Up" button → My Pickups list (assigned to them) → "Mark Delivered/Cancelled" button.

**Area Admin**: Dashboard (analytics/area-admin) → Users in my area (`/users/`) → All donations in my area (`/donations/`) → (read-only) My Area info (`/areas/{id}/`).

**Super Admin**: Dashboard (analytics/super-admin, area comparison) → Areas management (create/edit `/areas/`) → Create Area Admin form (`POST /create-area-admin`, §4a) → Pending Signups queue (`/pending-area-users` + `/assign-area`) → All Users (`/users/`) → drill into any Area Admin's dashboard.

---

## 11. Full Endpoint Reference

| Method | Path | Auth |
|---|---|---|
| POST | `/authapi/auth_register` | none |
| POST | `/authapi/auth_verify_email` | none |
| POST | `/authapi/auth_resend_otp` | none |
| POST | `/authapi/auth_login` | none |
| POST | `/api/token/refresh/` | none |
| GET | `/authapi/auth_profile` | ✅ |
| GET | `/authapi/auth_dashboard` | ✅ |
| POST | `/authapi/auth_password_reset/request` | none |
| POST | `/authapi/auth_password_reset/verify-otp` | none |
| POST | `/authapi/auth_password_reset/confirm` | none |
| GET/POST | `/authapi/areas/` | ✅ (write: Super Admin) |
| GET/PATCH/DELETE | `/authapi/areas/{id}/` | ✅ (write: Super Admin) |
| GET | `/authapi/pending-area-users` | Super Admin |
| POST | `/authapi/assign-area` | Super Admin |
| POST | `/authapi/create-area-admin` | Super Admin |
| GET/PATCH/DELETE | `/authapi/users/{id}/` | Area/Super Admin |
| GET | `/authapi/users/` | Area/Super Admin |
| GET/POST | `/authapi/add-role/` | Area/Super Admin |
| GET/POST | `/authapi/user-role/` | Area/Super Admin |
| GET/POST | `/authapi/donations/` | ✅ |
| GET/PATCH/DELETE | `/authapi/donations/{id}/` | ✅ (write: owner/Area/Super Admin) |
| POST | `/authapi/donations/{id}/pick_donation/` | ✅ (volunteer) |
| POST | `/authapi/donations/{id}/update_status/` | ✅ (assigned volunteer) |
| GET | `/authapi/analytics/super-admin` | Super Admin |
| GET | `/authapi/analytics/area-admin` | Area/Super Admin |
| GET | `/authapi/analytics/donor` | ✅ |
| GET | `/authapi/analytics/volunteer` | ✅ |
