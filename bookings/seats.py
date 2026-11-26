"""Seat numbers and the seat map for real trips.

Seats are numbered like an airline: the row number counts from the front of
the bus and the letter is the position across, e.g. "4A".

    Standard  2 + 2   A B | aisle | C D
    Luxury    2 + 1   A B | aisle | C      (wider seats)
    Sleeper   2 + 1   A B | aisle | C      (berths)

The number of rows comes from the bus's total_seats; a last, partly filled row
only has the first letters (a 42-seat standard bus ends with 11A and 11B).

A seat is taken while a live (not cancelled) booking on the same trip has a
passenger in it. The server checks every chosen seat again while it holds the
trip's row lock (bookings.services.create_booking), so two people can never
end up with the same seat even if they click at the same moment.
"""

from math import ceil

LETTERS_BY_BUS_TYPE = {
    "STANDARD": ("A", "B", "C", "D"),
    "LUXURY": ("A", "B", "C"),
    "SLEEPER": ("A", "B", "C"),
}
AISLE_AFTER = "B"  # the aisle runs between B and C on every bus type


def letters_for(bus):
    return LETTERS_BY_BUS_TYPE.get(bus.bus_type, LETTERS_BY_BUS_TYPE["STANDARD"])


def layout_label(bus):
    return "2 + 2" if len(letters_for(bus)) == 4 else "2 + 1"


def seat_codes(bus):
    """Every seat on the bus, front to back: ["1A", "1B", "1C", "1D", "2A", ...]."""
    letters = letters_for(bus)
    rows = ceil(bus.total_seats / len(letters))
    codes = [f"{row}{letter}" for row in range(1, rows + 1) for letter in letters]
    return codes[: bus.total_seats]


def sort_key(code):
    """Order seats the way people read them: 2A, 2B, 10A (not 10A, 2A)."""
    return int(code[:-1]), code[-1]


def taken_seats(schedule):
    """Seat codes held by live (not cancelled) bookings on this trip."""
    from .models import Booking, PassengerDetail

    return set(
        PassengerDetail.objects.filter(booking__schedule=schedule, seat_number__isnull=False)
        .exclude(booking__status=Booking.Status.CANCELLED)
        .exclude(seat_number="")
        .values_list("seat_number", flat=True)
    )


def seat_grid(schedule, taken=None):
    """Rows for the seat map template, one per letter across the bus:
    [{"letter": "A", "aisle_after": False, "seats": [{"code", "number", "taken"} or None]}]
    None marks a gap where a partly filled last row has no seat."""
    bus = schedule.bus
    taken = taken_seats(schedule) if taken is None else taken
    existing = set(seat_codes(bus))
    rows = ceil(bus.total_seats / len(letters_for(bus)))
    grid = []
    for letter in letters_for(bus):
        seats = []
        for number in range(1, rows + 1):
            code = f"{number}{letter}"
            seats.append({"code": code, "number": number, "taken": code in taken} if code in existing else None)
        grid.append({"letter": letter, "aisle_after": letter == AISLE_AFTER, "seats": seats})
    return grid
