# HIGH 5 – Shared Database Contract

> **Status:** `accounts.User` is implemented and migrated.
> `transport` and `bookings` models below are a **PROPOSED CONTRACT** – the
> team must agree on it (and confirm the open questions against the SRS)
> before anyone writes these models. Changes to this file go through a Pull
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
| is_active | (inherited) | inactive users cannot log in |
| date_joined | (inherited) | |
| is_staff / is_superuser | (inherited) | only control access to `/django-admin/` |

Helpers: `user.is_admin_role`, `user.is_passenger_role`.
Permission helpers: `accounts.permissions` → `admin_required`, `passenger_required`, `AdminRequiredMixin`, `PassengerRequiredMixin`.

## 2. `transport` models (proposed – owner: Daniel)

### Route
| Field | Type | Constraints |
|---|---|---|
| origin | CharField(100) | indexed |
| destination | CharField(100) | indexed; must differ from origin (CheckConstraint) |
| duration_estimate | DurationField | e.g. `timedelta(hours=5)` |
| description | TextField | blank allowed |
| is_active | BooleanField | default True |
| created_at | DateTimeField | `auto_now_add=True` |

`UniqueConstraint(fields=["origin", "destination"])`.

### Bus
| Field | Type | Constraints |
|---|---|---|
| name_or_plate | CharField(50) | **unique** |
| bus_type | CharField(20) + choices | e.g. STANDARD / EXECUTIVE / VIP (**confirm list with SRS**) |
| total_seats | PositiveSmallIntegerField | `MinValueValidator(1)`, CheckConstraint `> 0` |
| is_active | BooleanField | default True |

### Schedule
| Field | Type | Constraints |
|---|---|---|
| route | FK → Route | `on_delete=PROTECT`, `related_name="schedules"` |
| bus | FK → Bus | `on_delete=PROTECT`, `related_name="schedules"` |
| departure_date | DateField | indexed |
| departure_time | TimeField | |
| fare | DecimalField(10,2) | `MinValueValidator(0)` |
| status | CharField + choices | `SCHEDULED` / `CANCELLED` / `COMPLETED` (default `SCHEDULED`) |

* `UniqueConstraint(fields=["bus", "departure_date", "departure_time"])` – a bus cannot be scheduled twice at the same moment.
* `Index(fields=["departure_date", "status"])` for search.
* Property `departure_datetime` → timezone-aware datetime (used for the cancellation cut-off).

**Why PROTECT?** Deleting a route or bus must never silently delete schedules and the bookings (financial records) attached to them. Admins *deactivate* (`is_active=False`) instead of deleting.

## 3. `bookings` models (proposed – owner: Raheem)

### Booking
| Field | Type | Constraints |
|---|---|---|
| booking_ref | CharField(12) | **unique**, generated server-side (e.g. `H5-7KQ2M9XA`) using `secrets` – never sequential |
| passenger | FK → `settings.AUTH_USER_MODEL` | `on_delete=PROTECT`, `related_name="bookings"` |
| schedule | FK → `transport.Schedule` | `on_delete=PROTECT`, `related_name="bookings"` |
| seats_booked | PositiveSmallIntegerField | ≥ 1 |
| total_amount | DecimalField(10,2) | = fare × seats, **calculated on the server** |
| status | CharField + choices | `CONFIRMED` / `CANCELLED` (see open question Q3) |
| payment_status | CharField + choices | `PENDING` / `PAID` / `REFUNDED` – simulated / admin-confirmed |
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
| seat_number | PositiveSmallIntegerField | **only if Q1 = specific seats** |

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

## 5. Open questions (must be confirmed against the SRS)

| # | Question | Default assumed until confirmed |
|---|---|---|
| Q1 | Do passengers choose **specific seat numbers** (seat map), or just a **number of seats**? The objective says "view available seats / seat selection" but the SRS BOOKING table only has `seats_booked`. | Specific seat numbers stored on `PassengerDetail.seat_number` |
| Q2 | What is the **cancellation cut-off**? | 24 hours before departure (`BOOKING_CANCELLATION_CUTOFF_HOURS`) |
| Q3 | Which **booking statuses** does the SRS list (e.g. PENDING, CONFIRMED, CANCELLED, COMPLETED)? | CONFIRMED / CANCELLED |
| Q4 | Which **payment statuses** and is a booking confirmed before payment? | PENDING / PAID / REFUNDED; seats held on booking |
| Q5 | Which **bus types** does the SRS list? | STANDARD / EXECUTIVE / VIP |
| Q6 | One `PassengerDetail` per **booking** or per **seat**? | Per seat |
| Q7 | Which **currency** and **time zone**? | Configurable in `.env` (`CURRENCY_SYMBOL`, `TIME_ZONE`) |
| Q8 | Can admins be created only by another admin / superuser? | Yes – public registration creates passengers only |
