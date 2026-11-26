
from django.conf import settings

from math import ceil

from .seats import layout_label, letters_for, seat_grid
from .services import get_available_seats


def _duration_label(duration):
    """timedelta(hours=6, minutes=15) -> "6 h 15 min" (str() would give "6:15:00")."""
    hours, minutes = divmod(int(duration.total_seconds()) // 60, 60)
    return f"{hours} h {minutes:02d} min" if minutes else f"{hours} h"


def schedule_to_trip(schedule, passengers=1):
    """
    Convert a real Schedule object into the dictionary
    expected by the existing booking page.
    """

    total_seats = schedule.bus.total_seats
    seats_left = get_available_seats(schedule)

    duration = schedule.route.duration_estimate

    departure_datetime = schedule.departure_datetime
    arrival_datetime = departure_datetime + duration

    max_passengers = min(10, seats_left)

    return {
        "is_sample": False,

        "schedule_id": schedule.pk,

        "origin": schedule.route.origin,
        "destination": schedule.route.destination,

        "date": schedule.departure_date,
        "departure": schedule.departure_time,
        "arrival": arrival_datetime.time(),

        "arrives_next_day": (
            arrival_datetime.date() > schedule.departure_date
        ),

        "duration": _duration_label(duration),

        "bus_name": schedule.bus.name_or_plate,
        "bus_type": schedule.bus.get_bus_type_display(),

        "total_seats": total_seats,
        "seats_left": seats_left,

        "seats_left_percent": (
            round(seats_left * 100 / total_seats)
            if total_seats else 0
        ),

        "fare": schedule.fare,
        "currency": settings.CURRENCY_SYMBOL,

        "passengers": max(
            1,
            min(passengers, max_passengers)
        ),

        "max_passengers": max_passengers,

        # Seat map: one row per letter across the bus (bookings/seats.py).
        "seat_rows": seat_grid(schedule),
        "seat_numbers": list(range(1, ceil(total_seats / len(letters_for(schedule.bus))) + 1)),
        "seat_layout": layout_label(schedule.bus),
        "seat_berths": schedule.bus.bus_type == "SLEEPER",
        "seat_map_available": True,

        "cancel_cutoff_hours": (
            settings.BOOKING_CANCELLATION_CUTOFF_HOURS
        ),
    }
