# Roadmap

Forward-looking plan for the NGO food-donation platform: what to build next, and new ideas worth exploring. Companion to [features.md](features.md), which documents what already exists.

---

## TL;DR — What We're Building

1. **Fix what exists first** — close a few open permission gaps and add tests, before layering on new features.
2. **Split "Admin" into two tiers** — a **Super Admin** who sees the whole platform, and one **Area Admin** per town (starting with Murudeshwar). Donors and volunteers sign up with an address, get auto-matched to their town's `Area`, and only ever see/manage things inside that area.
3. **Give every tier a dashboard** — Donors and Volunteers see their own stats; each Area Admin sees their town's stats; the Super Admin sees every town side by side and can drill into any one of them.
4. **Layer on feature ideas** — donation history/export, live tracking, ratings, moderation, reports — once the foundation above is solid.
5. **Scale the infrastructure** — background jobs, logging, CI, API docs — as real usage grows.

### The Big Picture

```
                     ┌───────────────┐
                     │  Super Admin  │   sees ALL areas, opens new towns
                     └───────┬───────┘
             ┌───────────────┼───────────────┐
             ▼                               ▼
     ┌───────────────┐               ┌───────────────┐
     │ Area: Murudeshwar│             │ Area: Next Town │   ← added later, no redeploy
     │  (Area Admin)   │             │  (Area Admin)   │
     └───────┬─────────┘             └───────┬─────────┘
     ┌───────┴───────┐               ┌───────┴───────┐
     ▼               ▼               ▼               ▼
  Donors        Volunteers        Donors        Volunteers
 (matched by address to their own Area at signup)
```

Today the app only has one flat "admin" role and no concept of area — everything below describes how we get from here to the picture above, in order.

### Build Phases

| Phase | What | Detail |
|---|---|---|
| **1** ✅ | Harden the existing auth + donation endpoints | [§1](#1-near-term-hardening-before-adding-new-features) |
| **2** ✅ | Introduce `Area` model, Super Admin / Area Admin split, address-based matching | [§2](#2-multi-area-admin-hierarchy-super-admin--area-admins) |
| **3** ✅ | Build the three dashboard tiers (Super Admin / Area Admin / Donor & Volunteer) | [§3](#3-analytics--visual-dashboards) |
| **4** | Donor, Volunteer, and Admin feature ideas | [§4](#4-donor-facing-ideas)–[§6](#6-admin-facing-ideas) |
| **5** | Infra: background jobs, logging, CI, API docs | [§7](#7-platform--infra-roadmap) |

Phases are meant to be sequential — Phase 3's dashboards depend on Phase 2's `Area` model existing, and Phase 2's area-scoped permissions depend on Phase 1's permission cleanup being done first so we're not building new scoping rules on top of known holes.

---

## 1. Near-Term Hardening (before adding new features) — ✅ Done

- ✅ Locked down `add-role` and `user-role` endpoints to `IsAdminRole`.
- ✅ Donation update/delete now require `IsAuthenticated` + a new `IsOwnerOrAdmin` object-level check (only the donor who owns it, or an admin, can edit/delete it directly).
- ✅ Rate-limited `auth_resend_otp` and `auth_password_reset/request` to 3 requests/minute via DRF's `ScopedRateThrottle`.
- ✅ Added an automated test suite (`authapi/tests.py`, 13 tests) covering the full auth flow (register → verify → login → resend OTP → password reset) and the donation lifecycle (create → pick → update status, including permission/visibility edge cases). All passing.
- ✅ Added pagination (`PageNumberPagination`, page size 10) to all list endpoints (`donations`, `users`, etc.) plus a stable `-created_at` ordering on `Donation` to make pagination deterministic.

---

## 2. Multi-Area Admin Hierarchy (Super Admin + Area Admins) — ✅ Done

Launch in one town (Murudeshwar) first, but the model is built so adding the next town later is just a new row, not a new deploy. Two admin tiers instead of one flat "admin" role:

- **Super Admin** (platform-wide) — sees and manages every area. Not tied to any single `Area`.
- **Area Admin** (per town/zone) — manages only donors, volunteers, and donations inside their own `Area`. Today's single hard-capped "admin" account effectively becomes the first Area Admin for Murudeshwar.

### Data model changes — ✅ shipped

- ✅ New `Area` model: `name` (e.g. "Murudeshwar"), `pincodes` (JSON list), `is_active`.
- ✅ `User` got an `area` FK (nullable — null for Super Admin and for signups pending area assignment) and a `pincode` field recording what was submitted at signup.
- ✅ `User.role` gained a `super_admin` choice alongside `admin` (Area Admin), `donor`, `volunteer`.
- ✅ `Donation` got an `area` FK too, auto-set from the donor's area at creation — this is what makes volunteer/admin visibility actually area-scoped (see Permission changes below).
- ✅ Registration flow: signup captures a `pincode`; `resolve_area()` in `authapi/utils.py` matches it against active `Area.pincodes`. No match → the account is created anyway with `area=None` (**pending area**, not rejected), and shows up in the Super Admin's pending queue.
- ✅ **Superseded below:** self-signup as `role=admin` was briefly the mechanism (pincode had to match an existing `Area`, one Area Admin per area) — this has since been **removed** in favor of direct Super Admin provisioning. See "Area Admin creation, take two" below. Registering as `role=super_admin` remains rejected outright — Super Admins are bootstrapped manually (Django shell/admin), never through public signup.

### Area Admin creation, take two — ✅ Done

Self-signup for Area Admin turned out to be the wrong shape (a stranger picking the Area Admin role for themselves and racing to claim an area isn't how an NGO hierarchy should actually work) — replaced with direct top-down provisioning:

- ✅ `/auth_register` now rejects `role: "admin"` outright, same as `super_admin` — **no self-service path to Area Admin exists anymore**.
- ✅ New `POST /authapi/create-area-admin` (Super-Admin-only): takes `username`, `email`, `password`, `area_id` and creates the Area Admin directly, active and email-verified immediately (no OTP step — the Super Admin is vouching for the account). Still rejects if the target area already has an Area Admin.
- ⚠ **Known gap**: no automated tests yet for this endpoint (not covered by `AreaHierarchyTests`) — add coverage (happy path, duplicate-admin-per-area rejection, non-Super-Admin `403`) before relying on this in production.
- Not yet built: any invite-link / temp-password-reset flow for the new Area Admin — today the Super Admin has to hand over the raw password out-of-band.

### Address capture — pincode matching (decided, see [§8](#8-decisions-locked-in))

- Pincode text field at signup, matched against each `Area`'s registered pincodes. No maps dependency.
- GPS pin-drop + geofencing is deliberately deferred until there's real NGO traction.

### Permission changes — ✅ shipped

- New permission classes in `authapi/permissions.py`: `IsSuperAdmin` (super_admin only) and `IsAreaOrSuperAdmin` (admin or super_admin — used where an Area Admin should get scoped access and a Super Admin unscoped access to the same endpoint).
- `AllUserViewSet` (`/authapi/users/`) and `DonationViewSet` (`/authapi/donations/`) both scope their `get_queryset` by `area=self.area` for an Area Admin/volunteer, and return everything for a Super Admin — same pattern, applied consistently across users and donations.
- `IsOwnerOrAdmin` (donation update/delete) now also accepts `super_admin`, not just `admin`.
- `add-role`/`user-role` endpoints now use `IsAreaOrSuperAdmin` instead of admin-only.

### New endpoints — ✅ shipped

| Endpoint | Who | Purpose |
|---|---|---|
| `GET/POST /authapi/areas/` | Any authenticated user can read; only Super Admin can write | List/create/update `Area`s — this is the "open the next town" workflow. |
| `GET /authapi/pending-area-users` | Super Admin | Queue of signups whose pincode didn't match any `Area` yet. |
| `POST /authapi/assign-area` | Super Admin | Assigns a user (`user_id`) to an `Area` (`area_id`) — used to clear the pending queue. Does **not** change `role`, so it cannot be used to grant Area Admin access. |
| `POST /authapi/create-area-admin` | Super Admin | Directly creates an Area Admin (`username`, `email`, `password`, `area_id`) for a chosen area — active + verified immediately, no self-signup involved. |

### Escalation path (still a future idea)

- A donation or dispute stuck inside one area could be escalated to the Super Admin for visibility/intervention — not built yet, worth revisiting once towns scale past what one Area Admin can babysit.

### Tests

- `authapi/tests.py` → `AreaHierarchyTests` (16 new tests) covers: pincode-to-area resolution, pending-area signups, Area Admin/volunteer/Super Admin visibility scoping for both users and donations, the one-Area-Admin-per-area rule, the "no area, no Area Admin signup" rule, and the pending-queue/assign-area endpoints. 29 tests total, all passing.

---

## 3. Analytics & Visual Dashboards — ✅ Done

The API previously returned only raw records. A dashboard UI (charts, KPI tiles) shouldn't have to download every row and compute totals client-side — so the backend now exposes small, pre-aggregated endpoints (`authapi/analytics.py`) the frontend can plot directly with a charting library (Chart.js, Recharts, etc.). Three dashboard tiers, matching the area hierarchy above.

### Endpoints — ✅ shipped

| Endpoint | Who | Returns |
|---|---|---|
| `GET /authapi/analytics/super-admin` | Super Admin | Platform-wide `totals` by status, daily `timeseries`, top-5 `leaderboard` of volunteers by delivered count, `by_area` (per-area status breakdown — this is what turns a single dashboard into a multi-area rollup), `users_by_role` platform-wide, and `avg_delivery_hours` across all areas. |
| `GET /authapi/analytics/area-admin` | Area Admin (own area) or Super Admin (`?area_id=` to drill into any area) | Same shape, scoped to one `Area`: `totals`, `timeseries`, `leaderboard` (top volunteers in that area), `users_by_role` in that area, `avg_delivery_hours` in that area. |
| `GET /authapi/analytics/donor` | Any authenticated user | Their own donations: `totals` by status, `timeseries`, `total_items_donated` (sum of quantity). Scoped to `donor=request.user` regardless of caller's role. |
| `GET /authapi/analytics/volunteer` | Any authenticated user | Their own pickups: `totals` by status, `timeseries` of deliveries, `avg_delivery_hours` for their own deliveries. Scoped to `volunteer=request.user`. |

Actual response shape (verified live):
```json
{
  "totals": {"pending": 1, "picked": 0, "delivered": 1, "cancelled": 0},
  "timeseries": [{"date": "2026-09-05", "count": 2}],
  "leaderboard": [{"username": "smokevol", "delivered": 1}],
  "by_area": [{"area": "SmokeTownX", "pending": 1, "picked": 0, "delivered": 1, "cancelled": 0, "total": 2}],
  "users_by_role": {"admin": 1, "donor": 1, "volunteer": 1},
  "avg_delivery_hours": 0.0
}
```
That shape drops straight into a chart component with no client-side math — "easy to build in the UI" means the backend does the aggregation, not the frontend.

### Suggested chart types per role (still to be built on the frontend)

- **Super Admin**: bar chart comparing areas side by side (from `by_area`), drill-down into any area's own dashboard via `?area_id=`, donut (`users_by_role`, platform-wide).
- **Area Admin**: line chart (`timeseries`), stacked bar (`totals` breakdown), leaderboard table/bar (top volunteers), donut (`users_by_role`).
- **Donor**: donut (`totals`), line chart (`timeseries`), KPI tile (`total_items_donated`).
- **Volunteer**: KPI tiles (`totals.delivered`), bar chart (delivered vs cancelled from `totals`), line chart (`timeseries`).

### Implementation notes — what actually shipped

- `Donation` gained an `updated_at` field (`auto_now=True`) so `avg_delivery_hours` can be computed as the average `updated_at - created_at` for `delivered` donations — done in Python over `.values_list(...)` rather than a DB-side date-diff, to stay portable across backends.
- Super Admin's `by_area` is one `.values('area__name').annotate(...)` group-by across all donations — no separate per-area queries.
- No caching layer yet (see Known Gaps below) — each call re-aggregates live. Fine at pilot scale; revisit if dashboards get polled heavily.
- These are plain `APIView`s, not ViewSets — they're computed, not stored, resources.

### Tests

- `authapi/tests.py` → `AnalyticsTests` (8 tests): totals/by-area correctness for Super Admin, permission lock-down (non-Super-Admin blocked from `/analytics/super-admin`), Area Admin scoping to their own area, Super Admin drill-down via `?area_id=` (and the 400 when it's missing), donor/volunteer self-scoping, and the auth requirement. 37 tests total, all passing.

### Known gap

- No response caching yet — a short TTL cache (roadmap originally suggested ~60s) would help once dashboards are polled frequently in a real frontend.

---

## 4. Donor-Facing Ideas

- Donation history with filters (date range, status) and CSV export.
- Recurring/scheduled donations (e.g. "donate weekly").
- Optional photo upload per donation (`Donation` model already has fields for description; image field would need adding).
- Auto-generated thank-you email / donation receipt after delivery.
- Favorite/preferred pickup addresses saved to profile.

## 5. Volunteer-Facing Ideas

- Availability toggle (online/offline) so admins/donors know who's active.
- Live pickup tracking (lat/long updates while a donation is in `picked` state).
- Ratings/feedback from donors after delivery, feeding the "top volunteers" leaderboard.
- Notify volunteers by email when a new `pending` donation appears in their area (SMS/WhatsApp is a later-phase channel — see [§8](#8-decisions-locked-in)).

## 6. Admin-Facing Ideas

- Moderation queue for flagged/suspicious donations (Area Admin scope; escalate to Super Admin if unresolved).
- Manual reassignment of a stuck `picked` donation to another volunteer within the same area.
- Exportable reports (CSV/PDF) built on top of the analytics endpoints above.
- Audit log of role changes and admin actions, visible to Super Admin across all areas.
- ✅ Super Admin tooling to open a new `Area` (`POST /authapi/areas/`) and directly create its first Area Admin (`POST /authapi/create-area-admin`, [§2](#2-multi-area-admin-hierarchy-super-admin--area-admins)) — this is the "add the next town" workflow. Still a two-step manual process (Super Admin has to call both endpoints); a combined "create area + admin in one request" convenience endpoint is a nice-to-have, not built.
- Super Admin queue of **pending area** signups (users whose pincode didn't match any existing `Area`) to review and assign — see [§8](#8-decisions-locked-in).

---

## 7. Platform / Infra Roadmap

- Move OTP email sending to a background task queue (Celery + Redis, or `django-q`) so registration/login requests don't block on SMTP latency.
- Add structured logging + error tracking (Sentry) once this moves toward production traffic.
- Introduce environment-based settings split (`settings/dev.py`, `settings/prod.py`) instead of one `settings.py` with in-file conditionals.
- API documentation via `drf-spectacular` (OpenAPI/Swagger) so frontend devs don't have to read the source to know request/response shapes.
- CI/CD pipeline — deliberately deferred for now (see [§8](#8-decisions-locked-in)); revisit once we understand the deployment setup better.

---

## 8. Decisions Locked In

- **Area matching**: V1 pincode/city matching only for now. No maps/GPS integration until the platform has traction with NGOs — revisit if it takes off.
- **Unmatched signup address**: goes into a **pending area** state rather than being rejected. The Super Admin reviews pending signups and either assigns them to an existing `Area` or opens a new one. Nobody gets turned away at signup.
- **Notifications**: **email only** for now (already built). SMS/WhatsApp is a later channel to evaluate, not part of the current build.
- **CI/CD**: deferred. Manual testing/deploys for now — set up automated pipelines later once there's a clearer picture of the deployment setup.
