# HIGH 5 – Shared Database Contract

> **Status (23 Nov 2026):** all models below are **implemented** on the
> `integration` branch (accounts 0001–0004, transport 0001–0002, bookings 0001).
> Fields added during implementation are marked *(added)*. The open questions
> have been checked against the **SRS v1.0 (17 Nov 2026)** – see §5; FR/NFR
> numbers below refer to that document. Changes to this file go through a Pull
> Request reviewed by Sam (database architect).

Golden rules:

1. **One model per concept, in one app.** Nobody re-defines `Route`, `Bus`, `Schedule`, `Booking`, etc. in another app. Import them instead.
2. Refer to the user model with `settings.AUTH_USER_MODEL` in ForeignKeys and `get_user_model()` in code – never `from django.contrib.auth.models import User`.
3. Money is **always** `DecimalField(max_digits=10, decimal_places=2)`. Never `FloatField`.
4. All database access through the Django ORM. No raw SQL.
5. Only the model's owner creates migrations for that app (see CONTRIBUTING.md).

## Entity relationship overview

```
 accounts.User (PASSENGER / ADMIN)
        │ 1
        │
        │ *            *  1                 1
 bookings.Booking ───────────► transport.Schedule ◄──────── transport.Route
        │ 1                         │ *     (origin → destination)
        │                           │
        │ *                         ▼ 1
 bookings.PassengerDetail     transport.Bus (total_seats)
 (one per seat booked)
```

* A **Route** has many Schedules. A **Bus** has many Schedules.
* A **Schedule** is one bus running one route on one date and time, at one fare.
* A **Booking** belongs to one passenger account and one Schedule, and holds 1+ seats.
* A **PassengerDetail** row stores the traveller's name/phone/email for each seat (the person travelling may differ from the account holder).

## 1. `accounts.User` (implemented – owner: Sam)

| Field | Type | Notes |
|---|---|---|
| id | BigAutoField | PK |
| email | EmailField | **unique**, stored lowercase, used to log in |
| full_name | CharField(150) | required |
| phone | CharField(16) | optional, validated `+` and 7–15 digits |
| password | (inherited) | hashed with PBKDF2 by Django |
| role | CharField(10) | `ADMIN` / `PASSENGER`, default `PASSENGER`, indexed |
| email_verified | BooleanField | *(added)* default False, indexed. Must be True to log in (docs/EMAIL_VERIFICATION.md). Superusers and accounts that existed before migration 0003 are verified |
| is_active | (inherited) | inactive users cannot log in |
| date_joined | (inherited) | |
| is_staff / is_superuser | (inherited) | only control access to `/django-admin/` |

Helpers: `user.is_admin_role`, `user.is_passenger_role`.

### `accounts.EmailVerificationCode` *(added, migration 0004)*
The 6-digit sign-up code (one live code per user; see docs/EMAIL_VERIFICATION.md).

| Field | Type | Notes |
|---|---|---|
| user | OneToOne → User | `on_delete=CASCADE`, `related_name="verification_code"` |
| code_hash | CharField(128) | hash of the code (never the code itself) |
| expires_at | DateTimeField | 10 minutes after it was sent |
| attempts | PositiveSmallIntegerField | wrong tries so far; the code stops working at 5 |
| created_at | DateTimeField | `auto_now_add=True` |
Permission helpers: `accounts.permissions` → `admin_required`, `passenger_required`, `AdminRequiredMixin`, `PassengerRequiredMixin`.

## 2. `transport` models (implemented – owner: Daniel)

### Route
| Field | Type | Constraints |
|---|---|---|
| origin | CharField(100) | indexed |
| destination | CharField(100) | indexed; must differ from origin (CheckConstraint) |
| distance_km | PositiveIntegerField | *(added)* at least 1 |
| duration_estimate | DurationField | e.g. `timedelta(hours=5)` |
| description | TextField | blank allowed |
| is_active | BooleanField | default True |
| created_at | DateTimeField | `auto_now_add=True` |

`UniqueConstraint(fields=["origin", "destination"])` (FR-10).

A route has **no intermediate stops** in the SRS (FR-08, §5.1). Pages show departure → estimated arrival, where arrival = departure + `duration_estimate`. Adding stops would be a new feature and needs the supervisor's approval first.

### Bus
| Field | Type | Constraints |
|---|---|---|
| name_or_plate | CharField(50) | **unique** |
| bus_type | CharField(20) + choices | `STANDARD` / `LUXURY` / `SLEEPER` (the SRS examples, FR-12) |
| total_seats | PositiveSmallIntegerField | `MinValueValidator(1)`, CheckConstraint `> 0` |
| status | CharField(20) + choices | *(added)* `AVAILABLE` / `ASSIGNED` / `MAINTENANCE` / `UNAVAILABLE`, default `AVAILABLE`. Set by the schedule admin pages; buses in maintenance cannot be scheduled |
| is_active | BooleanField | default True |

### Schedule
| Field | Type | Constraints |
|---|---|---|
| route | FK → Route | `on_delete=PROTECT`, `related_name="schedules"` |
| bus | FK → Bus | `on_delete=PROTECT`, `related_name="schedules"` |
| departure_date | DateField | indexed |
| departure_time | TimeField | |
| fare | DecimalField(10,2) | `MinValueValidator(0)`. One base fare per schedule (FR-15) – there are **no fare classes** to choose between on the same trip |
| status | CharField + choices | `SCHEDULED` / `CANCELLED` / `COMPLETED` (default `SCHEDULED`) |

* `UniqueConstraint(fields=["bus", "departure_date", "departure_time"])` – a bus cannot be scheduled twice at the same moment.
* `Index(fields=["departure_date", "status"])` for search.
* Property `departure_datetime` → timezone-aware datetime (used for the cancellation cut-off).
* Properties `arrival_datetime` / `arrival_time` = departure + `route.duration_estimate`. There is deliberately **no stored arrival field**, so a schedule can never disagree with its route.
* `clean()` also refuses past departures, inactive routes or buses, and a bus that is already on an overlapping trip.

**Why PROTECT?** Deleting a route or bus must never silently delete schedules and the bookings (financial records) attached to them. Admins *deactivate* (`is_active=False`) instead of deleting.

## 3. `bookings` models (implemented – owner: Raheem)

### Booking
| Field | Type | Constraints |
|---|---|---|
| booking_ref | CharField(12) | **unique**, generated server-side (e.g. `H5-7KQ2M9XA`) using `secrets` – never sequential |
| passenger | FK → `settings.AUTH_USER_MODEL` | `on_delete=PROTECT`, `related_name="bookings"` |
| schedule | FK → `transport.Schedule` | `on_delete=PROTECT`, `related_name="bookings"` |
| seats_booked | PositiveSmallIntegerField | ≥ 1 |
| total_amount | DecimalField(10,2) | = fare × seats, **calculated on the server** |
| status | CharField + choices | `CONFIRMED` / `CANCELLED` / `COMPLETED` (FR-29) |
| payment_status | CharField + choices | `PENDING` / `PAID` (FR-32) – simulated; an admin marks it paid. A paid booking that the passenger cancels (only allowed before the cutoff) becomes `REFUNDED` and stops counting as revenue |
| paid_at | DateTimeField | null; set automatically the first time `payment_status` becomes `PAID`. Revenue (dashboard, Reports, CSV) is counted on this date. Migration 0002 filled it with `booked_at` for bookings that were already paid |
| booked_at | DateTimeField | `auto_now_add=True` |
| cancelled_at | DateTimeField | null |

`Index(fields=["schedule", "status"])` – used to count seats taken.

### PassengerDetail
| Field | Type | Constraints |
|---|---|---|
| booking | FK → Booking | `on_delete=CASCADE`, `related_name="passengers"` |
| full_name | CharField(150) | |
| phone | CharField(16) | same validator as User.phone |
| email | EmailField | blank allowed |
| seat_number | CharField(4), null | e.g. `7A`. Filled only when the passenger uses the seat map – a bonus feature (FR-21, SRS §6.3). Booking by **number of seats** must work without it |

If seat numbers are used: a seat may be held by only one *active* booking per schedule. Enforce in the atomic booking service (below) and, if we denormalise `schedule` onto this table, with `UniqueConstraint(fields=["schedule", "seat_number"], condition=Q(is_active=True))`.

**Avoiding duplication:** the account holder's name/email live only on `User`. `PassengerDetail` is for the people travelling on each seat; it is not a copy of the user.

## 4. Seat availability and overbooking (rules 1, 7, 9, 10)

Seats available = `bus.total_seats − SUM(seats_booked of CONFIRMED bookings on that schedule)`.
Cancelled bookings are excluded, so cancelling automatically releases seats.

All booking creation and cancellation must go through one service function in `bookings/services.py`:

```python
from django.db import transaction
from django.db.models import Sum

@transaction.atomic
def create_booking(*, user, schedule_id, passengers):
    # Lock the schedule row: a second booking for the same trip waits here
    # until this transaction commits, so two people cannot take the last seat.
    schedule = (Schedule.objects.select_for_update()
                .select_related("bus", "route")
                .get(pk=schedule_id, status=Schedule.Status.SCHEDULED,
                     route__is_active=True, bus__is_active=True))
    taken = (schedule.bookings.filter(status=Booking.Status.CONFIRMED)
             .aggregate(n=Sum("seats_booked"))["n"] or 0)
    if taken + len(passengers) > schedule.bus.total_seats:
        raise NotEnoughSeats(...)
    ...
```

MySQL's InnoDB engine supports `SELECT ... FOR UPDATE` row locks, which is what `select_for_update()` produces.

## 5. Questions checked against the SRS (v1.0, 17 Nov 2026)

| # | Question | Answer | SRS reference |
|---|---|---|---|
| Q1 | Specific seat numbers or just a number of seats? | **Number of seats is required.** Specific seat numbers are allowed when a seat layout is implemented; the interactive seat map is a recommended **bonus** feature | FR-21, §6.3 |
| Q2 | Cancellation cut-off? | "A configurable number of hours before departure" – no value given; the team chose 5 h (was 24 h until Nov 2026), set in `BOOKING_CANCELLATION_CUTOFF_HOURS` | FR-28 |
| Q3 | Booking statuses? | **Confirmed / Cancelled / Completed** | FR-29, §5.1 |
| Q4 | Payment statuses? | Simulated payment; an admin marks bookings **Paid / Pending**. The booking is confirmed (seats held) when it is made | FR-32, §2.5 |
| Q5 | Bus types? | Examples given: **Standard, Luxury, Sleeper** | FR-12 |
| Q6 | `PassengerDetail` per booking or per seat? | Details are recorded against each booking, "optional per seat" – useful for multiple travellers. We keep **one row per seat** | FR-25, §5.1 |
| Q7 | Currency and time zone? | **Answered (team decision, 20 Nov 2026):** Nigerian Naira (`CURRENCY_SYMBOL=₦`), time zone `Africa/Lagos`. One currency only; multi-currency stays out of scope. Both are set in `.env` | §1.3 |
| Q8 | Who creates admins? | Public registration creates passengers only (FR-01). Admins are created with `createsuperuser` / by another admin. The README must list **default admin credentials for testing** | FR-01, §6.1 |

Other SRS points that affect the models and pages:

* Trip search is for **authenticated passengers** (FR-19) – already enforced by `bookings:search`.
* Search results show departure time, bus name/type, available seats and fare (FR-20). Only active routes and active buses appear (§5.3).
* Before confirming, show a booking summary: route, date, time, seats, total amount (FR-23).
* Routes have no intermediate stops and schedules have one base fare (see §2).
