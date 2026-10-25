# Latest Backend Updates

Pincode-based donation routing and the unattended-donations queue. Companion docs: [backend.md](backend.md), [ui.md](ui.md).

## 1. Donations are routed by pickup pincode

**Problem:** a donor could type any location when donating, and the donation always went to the donor's registered area. A donor donating from another place reached the wrong Area Admin.

**Now:**
- `Donation` has a new field `pickup_pincode` (required on create). `pickup_address` stays as the free-text address (flat, street, landmark).
- The serializer checks the pincode with `resolve_area()` against active Areas. If none matches, the API returns `400`:
  ```json
  { "pickup_pincode": ["We don't operate in this pincode yet."] }
  ```
- The server sets `donation.area` from the pincode. `area` is read-only, so a client can't send it. The donor's registered area is no longer used.
- Editing a donation's `pickup_pincode` re-routes it to the new area.
- Migration: `0010_donation_pickup_pincode.py`. Existing donations get an empty pincode and are unaffected until edited.

**Request example**
```json
POST /authapi/donations/
{
  "item_name": "Rice",
  "quantity": 5,
  "pickup_address": "Flat 12, Sunrise Apt, near Metro station",
  "pickup_pincode": "581342",
  "contact_number": "1234567890"
}
```

**Files:** `authapi/models.py`, `authapi/serializers.py` (`DonationSerializer`), `authapi/views.py` (`DonationViewSet.perform_create` no longer passes `area`).

## 2. Unattended donations queue (Super Admin)

`GET /authapi/unattended-donations` lists `pending` donations whose area has no active Area Admin. That covers areas where the admin was deactivated and areas that never had one.

- Super Admin only (`IsSuperAdmin`); other roles get `403`.
- Paginated like other list endpoints (`results`, `next`, `previous`).
- Volunteers in the area can still pick these donations up as before.

**Files:** `authapi/views.py` (`UnattendedDonationsView`), `authapi/urls.py` (`unattended-donations`).

## 3. Tests

Suite: 42 tests, all passing.
- Existing donation tests now send `pickup_pincode`, and the lifecycle test users belong to an area.
- New tests:
  - An unserved pincode is rejected.
  - A missing pincode is rejected.
  - A donation is routed by pickup pincode, not the donor's area (a fake `area` in the payload is ignored).
  - The unattended queue is empty while the admin is active, and lists the donation once the admin is deactivated.
  - The unattended queue returns `403` for an Area Admin.

## 4. Running

```
python manage.py migrate
python manage.py test authapi --noinput
```

Don't use `--parallel` here: it needs `mysqldump`, which isn't installed. The suite takes about 5 minutes.

## 5. Not done yet

- Existing donations have no pincode until a donor edits them.
- The donation list pages in the frontend still only show `pickup_address`.
