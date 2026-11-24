"""Project-level views that don't belong to a single app."""

from collections import Counter, defaultdict
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from django.views.generic import TemplateView

from bookings.models import Booking
from transport.models import Schedule

POPULAR_ROUTE_COUNT = 4
UPCOMING_DAYS = 7  # "departures this week" on each card


def _duration_label(duration):
    """timedelta(hours=6, minutes=15) -> "6 h 15 m" (the short form used on the cards)."""
    hours, minutes = divmod(int(duration.total_seconds()) // 60, 60)
    return f"{hours} h {minutes:02d} m" if minutes else f"{hours} h"


def popular_routes(limit=POPULAR_ROUTE_COUNT):
    """The homepage "Popular routes" cards, built from real transport data.

    Only routes a passenger can book right now are shown: active route, active
    bus, and at least one SCHEDULED departure in the next UPCOMING_DAYS days.
    They are ordered by confirmed bookings (most booked first), then by how many
    departures they have this week.
    """
    today = timezone.localdate()
    upcoming = (
        Schedule.objects.filter(
            status=Schedule.Status.SCHEDULED,
            departure_date__gte=today,
            departure_date__lt=today + timedelta(days=UPCOMING_DAYS),
            route__is_active=True,
            bus__is_active=True,
        )
        .exclude(departure_date=today, departure_time__lte=timezone.localtime().time())  # already left today
        .select_related("route", "bus")
    )

    by_route = defaultdict(list)
    for schedule in upcoming:
        by_route[schedule.route].append(schedule)
    if not by_route:
        return []

    bookings = dict(
        Booking.objects.filter(status=Booking.Status.CONFIRMED, schedule__route__in=list(by_route))
        .values_list("schedule__route")
        .annotate(n=Count("id"))
    )

    cards = []
    for route, schedules in by_route.items():
        bus_types = Counter(s.bus.get_bus_type_display() for s in schedules)
        cards.append({
            "origin": route.origin,
            "destination": route.destination,
            "duration": _duration_label(route.duration_estimate),
            "departures": len(schedules),
            "bus_type": bus_types.most_common(1)[0][0],
            "fare_from": min(s.fare for s in schedules),
            "bookings": bookings.get(route.pk, 0),
        })
    cards.sort(key=lambda c: (-c["bookings"], -c["departures"], c["origin"], c["destination"]))
    return cards[:limit]


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["popular_routes"] = popular_routes()
        context["currency"] = settings.CURRENCY_SYMBOL
        context["cancel_cutoff_hours"] = settings.BOOKING_CANCELLATION_CUTOFF_HOURS
        return context
