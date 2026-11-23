
from django.apps import apps
from django.utils import timezone
from .trip_adapter import schedule_to_trip

def search_available_trips(origin, destination, travel_date, passengers=1):
    """
    Search for available trips using active routes and buses.
    """

    Schedule = apps.get_model("transport", "Schedule")

    schedules = Schedule.objects.filter(
        route__origin__iexact=origin,
        route__destination__iexact=destination,
        route__is_active=True,
        bus__is_active=True,
        departure_date=travel_date,
        status="SCHEDULED",
    ).select_related(
        "route",
        "bus"
    ).order_by(
        "departure_time"
    )

    available_trips = []

    from .services import get_available_seats

    for schedule in schedules:

        available_seats = get_available_seats(schedule)

        if available_seats >= passengers:
           available_trips.append(
    schedule_to_trip(
        schedule=schedule,
        passengers=passengers
    )
)

    return available_trips
