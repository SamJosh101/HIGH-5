"""PLACEHOLDER data (owner: Sam) until Daniel's transport models and Raheem's
booking models exist. Everything here is sample data for designing the pages;
nothing is saved and nothing here is used to make a real booking.

Replace:
  * SAMPLE_ROUTES  -> the most-booked active transport.Route objects.
  * sample_trip()  -> a real transport.Schedule. The dict it returns is the shape
                      the Book a Trip page templates expect (templates/partials/booking/).
"""

import datetime as dt
import re
from decimal import Decimal

from django.conf import settings

# Homepage "Popular routes" cards:
# (origin, destination, duration, departures per day, bus type, starting fare).
# Bus types follow the SRS examples (FR-12): Standard / Luxury / Sleeper.
SAMPLE_ROUTES = [
    ("Eastgate", "Riverside", "6 h 15 m", 8, "Luxury", "24.00"),
    ("Millbrook", "Harbour City", "3 h 40 m", 6, "Standard", "15.00"),
    ("Stonebridge", "Lakeview", "5 h 05 m", 4, "Luxury", "21.00"),
    ("Oakfield", "Eastgate", "2 h 30 m", 10, "Standard", "11.00"),
]

# Seat layout of the sample 44-seat coach: rows A and B on one side of the
# aisle, C and D on the other; seats numbered 1-11 from the front.
SEAT_ROWS = ("A", "B", "C", "D")
SEAT_COLUMNS = 11
AISLE_AFTER_ROW = "B"
_TAKEN = {"A": (1, 2, 3, 5, 9, 11), "B": (1, 2, 3, 5, 9, 11), "C": (1, 2, 4, 6, 8, 10), "D": (1, 2, 3, 4, 6, 8, 10, 11)}
SAMPLE_TAKEN_SEATS = frozenset(f"{n}{row}" for row, numbers in _TAKEN.items() for n in numbers)

MAX_PASSENGERS = 10
_DEFAULT_ROUTE = ("6 h 15 m", "Luxury", "24.00")


def _minutes(duration_text):
    hours, minutes = re.match(r"(\d+)\s*h\s*(\d+)", duration_text).groups()
    return int(hours) * 60 + int(minutes)


def _duration_label(minutes):
    hours, mins = divmod(minutes, 60)
    return f"{hours} h {mins:02d} min" if mins else f"{hours} h"


def seat_grid(taken):
    """Rows of seats for the seat map: [{"letter", "aisle_after", "seats": [{"code", "number", "taken"}]}]."""
    return [
        {
            "letter": row,
            "aisle_after": row == AISLE_AFTER_ROW,
            "seats": [
                {"code": f"{n}{row}", "number": n, "taken": f"{n}{row}" in taken}
                for n in range(1, SEAT_COLUMNS + 1)
            ],
        }
        for row in SEAT_ROWS
    ]


def sample_trip(origin, destination, travel_date, passengers=1):
    """A sample trip for the given search, shaped like the real page context."""
    match = next(
        (r for r in SAMPLE_ROUTES if r[0].lower() == origin.lower() and r[1].lower() == destination.lower()),
        None,
    )
    duration_text, bus_type, fare = (match[2], match[4], match[5]) if match else _DEFAULT_ROUTE
    minutes = _minutes(duration_text)
    departure = dt.datetime.combine(travel_date, dt.time(7, 30))
    arrival = departure + dt.timedelta(minutes=minutes)

    total_seats = len(SEAT_ROWS) * SEAT_COLUMNS
    seats_left = total_seats - len(SAMPLE_TAKEN_SEATS)
    max_passengers = min(MAX_PASSENGERS, seats_left)
    return {
        "is_sample": True,
        "origin": origin,
        "destination": destination,
        "date": travel_date,
        "departure": departure.time(),
        "arrival": arrival.time(),
        "arrives_next_day": arrival.date() > travel_date,
        "duration": _duration_label(minutes),
        "bus_name": "H5 Coach 07",
        "bus_type": bus_type,
        "total_seats": total_seats,
        "seats_left": seats_left,
        "seats_left_percent": round(seats_left * 100 / total_seats),
        "fare": Decimal(fare),
        "currency": settings.CURRENCY_SYMBOL,
        "passengers": max(1, min(passengers, max_passengers)),
        "max_passengers": max_passengers,
        "seat_rows": seat_grid(SAMPLE_TAKEN_SEATS),
        "seat_numbers": list(range(1, SEAT_COLUMNS + 1)),
        "cancel_cutoff_hours": settings.BOOKING_CANCELLATION_CUTOFF_HOURS,
    }
