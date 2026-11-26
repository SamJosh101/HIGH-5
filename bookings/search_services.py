"""Finding trips a passenger can still book (Book a Trip page)."""

from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from .trip_adapter import _duration_label, schedule_to_trip

# How far ahead "All trips" and the empty-search suggestions look.
LOOKAHEAD_DAYS = 14


def _bookable_schedules():
    """Scheduled trips on active routes and buses from today on, with the
    number of seats already taken (confirmed bookings) in `seats_taken`."""
    Schedule = apps.get_model("transport", "Schedule")
    return (
        Schedule.objects.filter(
            route__is_active=True,
            bus__is_active=True,
            status="SCHEDULED",
            departure_date__gte=timezone.localdate(),
        )
        .select_related("route", "bus")
        .annotate(seats_taken=Coalesce(Sum("bookings__seats_booked", filter=Q(bookings__status="CONFIRMED")), 0))
        .order_by("departure_date", "departure_time")
    )


def _not_departed(schedules):
    """Drop trips from earlier today that have already left."""
    now = timezone.now()
    return [s for s in schedules if s.departure_datetime > now]


def _trip_row(schedule, passengers):
    """The few facts a trip list shows (lighter than schedule_to_trip, no seat map)."""
    arrival = schedule.arrival_datetime
    seats_left = max(0, schedule.bus.total_seats - schedule.seats_taken)
    return {
        "schedule_id": schedule.pk,
        "origin": schedule.route.origin,
        "destination": schedule.route.destination,
        "date": schedule.departure_date,
        "departure": schedule.departure_time,
        "arrival": timezone.localtime(arrival).time(),
        "arrives_next_day": timezone.localtime(arrival).date() > schedule.departure_date,
        "duration": _duration_label(schedule.route.duration_estimate),
        "bus_name": schedule.bus.name_or_plate,
        "bus_type": schedule.bus.get_bus_type_display(),
        "seats_left": seats_left,
        "few_left": 0 < seats_left <= 5,
        "full": seats_left < passengers,
        "fare": schedule.fare,
        "currency": settings.CURRENCY_SYMBOL,
    }


def search_available_trips(origin, destination, travel_date, passengers=1):
    """Trips on one route and day with enough free seats, soonest first."""
    schedules = _bookable_schedules().filter(
        route__origin__iexact=origin,
        route__destination__iexact=destination,
        departure_date=travel_date,
    )
    return [
        schedule_to_trip(schedule=s, passengers=passengers)
        for s in _not_departed(schedules)
        if s.bus.total_seats - s.seats_taken >= passengers
    ]


def all_upcoming_trips(origin="", destination="", passengers=1):
    """Every trip in the next LOOKAHEAD_DAYS days, full ones included (marked `full`)."""
    schedules = _bookable_schedules().filter(
        departure_date__lte=timezone.localdate() + timedelta(days=LOOKAHEAD_DAYS))
    if origin:
        schedules = schedules.filter(route__origin__iexact=origin)
    if destination:
        schedules = schedules.filter(route__destination__iexact=destination)
    return [_trip_row(s, passengers) for s in _not_departed(schedules)]


def alternative_trips(origin, destination, travel_date, passengers=1, limit=4):
    """For a search with no results: the same route on other days, and other
    trips from the same city on the chosen day. Full trips are left out."""
    upcoming = _bookable_schedules().filter(
        departure_date__lte=timezone.localdate() + timedelta(days=LOOKAHEAD_DAYS))

    def rows(schedules):
        found = [_trip_row(s, passengers) for s in _not_departed(schedules)]
        return [row for row in found if not row["full"]][:limit]

    return {
        "same_route": rows(upcoming.filter(route__origin__iexact=origin, route__destination__iexact=destination)
                           .exclude(departure_date=travel_date)),
        "same_origin": rows(_bookable_schedules().filter(route__origin__iexact=origin, departure_date=travel_date)
                            .exclude(route__destination__iexact=destination)),
    }


def city_choices():
    """Departure and destination cities of active routes, for the All trips filters."""
    Route = apps.get_model("transport", "Route")
    routes = Route.objects.filter(is_active=True)
    origins = sorted(set(routes.values_list("origin", flat=True)), key=str.lower)
    destinations = sorted(set(routes.values_list("destination", flat=True)), key=str.lower)
    return origins, destinations
