# Frontend Roadmap (Ionic Angular)

Phase-by-phase checklist for updating the existing frontend to match the current backend. Each phase is independently shippable — build and test one before starting the next. Endpoint details, request/response shapes, and gotchas are all in [ui.md](ui.md); this file is just the build order and checkboxes.

---

## Phase 1 — Auth Foundation (blocking everything else)

- [ ] Register form: role picker limited to `donor` / `volunteer` only — `admin` is no longer a valid self-service value (400s now, see [backend.md §4a](backend.md#4a-how-super-admin-and-area-admin-accounts-actually-get-created))
- [ ] OTP verification screen — mandatory step between register and login, not skippable
- [ ] Login screen — store `access` + `refresh` in persistent storage (not just in-memory), or users get logged out on every app reload
- [ ] **JWT auto-refresh interceptor** — access token is only 5 minutes. Add an HTTP interceptor: catch `401` → `POST /api/token/refresh/` with stored `refresh` → retry original request once. Build this before any authenticated screen; skipping it means constant surprise logouts.
- [ ] Forgot-password 3-screen flow: email → OTP → new password (`ui.md §3`)
- [ ] Role-based route guard reading `user.role` from the login response → redirect into one of 4 dashboards

## Phase 2 — Profile & Role-Based Shell

- [ ] Profile screen (`GET /auth_profile`)
- [ ] App shell per role — Donor/Volunteer share almost no UI; Admin/Super Admin share most of a shell but Super Admin has extra area-management screens
- [ ] Handle `area: "pending"` / `area: null` gracefully — expected state for fresh donor/volunteer signups and for Super Admin, not an error
- [ ] Logout (clear stored tokens)

## Phase 3 — Donor Portal

- [ ] My Donations list (`GET /donations/`, auto-scoped to the donor)
- [ ] New Donation form (`POST /donations/` — `item_name`, `quantity`, `description`, `pickup_address`, `contact_number`)
- [ ] Donation detail/edit (only editable while `status: pending`)
- [ ] Donor dashboard (`GET /analytics/donor` — donut of `totals`, KPI tile for `total_items_donated`)

## Phase 4 — Volunteer Portal

- [ ] Available Donations list (pending donations in their own area — same `/donations/` endpoint, pre-filtered server-side)
- [ ] "Pick Up" action (`POST /donations/{id}/pick_donation/`)
- [ ] My Pickups list (donations assigned to them)
- [ ] "Mark Delivered / Cancelled" action (`POST /donations/{id}/update_status/`)
- [ ] Volunteer dashboard (`GET /analytics/volunteer` — KPI tile for delivered count, line chart of `timeseries`)

## Phase 5 — Area Admin Portal

- [ ] Dashboard (`GET /analytics/area-admin`, auto-scoped to their area)
- [ ] Users in my area (`GET /users/`)
- [ ] All donations in my area (`GET /donations/`)
- [ ] Read-only "My Area" info card (`GET /areas/{id}/`)

## Phase 6 — Super Admin Portal

Build last — reuses components from Phase 5's Admin shell.

- [ ] Dashboard (`GET /analytics/super-admin` — bar chart of `by_area`, donut of `users_by_role`)
- [ ] Areas management: list/create/edit (`/areas/`) — "open a new town"
- [ ] **Create Area Admin form** (`POST /create-area-admin` — `username`, `email`, `password`, `area_id`). No invite-link flow yet — show the Super Admin the password they just set so they can hand it off out-of-band. ⚠ Backend endpoint has no automated test coverage yet (see [roadmap.md](roadmap.md)) — sanity-check the happy path and the "area already has an admin" 400 manually before relying on it.
- [ ] Pending Signups queue + "Assign to Area" action (`GET /pending-area-users`, `POST /assign-area`)
- [ ] All Users table, unscoped (`GET /users/`)
- [ ] Drill-down into any Area Admin's dashboard (`GET /analytics/area-admin?area_id=`)

## Phase 7 — Polish

- [ ] Error-state handling per `ui.md §0` — distinguish 400 (field errors), 401 (not logged in), 403 (wrong role), 404 (right role, object not in your scope)
- [ ] Rate-limit UX for OTP resend / password reset request — 429 means "wait and retry," show a cooldown message, not a generic error
- [ ] Loading/empty states for paginated lists — always read `results`, page via `next`/`previous`

---

## Notes

- Everything through Phase 6 maps to an existing, tested backend endpoint except the `create-area-admin` form (done, but flagged as untested in [roadmap.md](roadmap.md)) — no new backend work is required to complete this roadmap.
- Companion docs: [ui.md](ui.md) (full endpoint contracts + request/response shapes), [backend.md](backend.md) (why things work the way they do), [roadmap.md](roadmap.md) (backend-side what's-next).
