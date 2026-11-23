
from django.conf import settings

from .services import get_available_seats


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

        "duration": str(duration),

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

        # Real seat allocation has not been implemented yet.
        "seat_rows": [],
        "seat_map_available": False,

        "cancel_cutoff_hours": (
            settings.BOOKING_CANCELLATION_CUTOFF_HOURS
        ),
    }
