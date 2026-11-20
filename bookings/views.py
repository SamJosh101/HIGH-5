"""
Bookings module – OWNER: Raheem.

Phase 1 contains placeholders only. Implement against the contract in
docs/DATABASE.md and the rules in docs/ARCHITECTURE.md (atomic booking,
select_for_update, ownership checks).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.permissions import passenger_required
from config.sample_data import sample_trip


def _travel_date(raw):
    """The searched date, or today if it is missing, invalid or in the past."""
    today = timezone.localdate()
    try:
        chosen = parse_date(raw or "")
    except ValueError:  # well-formed but impossible, e.g. 2026-02-30
        chosen = None
    return chosen if chosen and chosen >= today else today


def _passenger_count(raw):
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


@login_required
def trip_search(request):
    """Book a Trip page: trip search for logged-in users. TODO(Raheem).

    Login is enforced here on the server. A logged-out visitor (for example one
    who clicked a Popular Route on the homepage) is redirected to the login page
    with ?next=<this URL incl. origin/destination>, and comes back to this
    search, pre-filled, after logging in or signing up.
    """
    context = {}
    origin = request.GET.get("origin", "").strip()
    destination = request.GET.get("destination", "").strip()
    if origin and destination and origin.lower() != destination.lower():
        # PLACEHOLDER (Sam): one sample trip so the page design (trip band, seat
        # map, booking summary) can be reviewed. Raheem: replace with the real
        # matching schedules (FR-19, FR-20) and pass the chosen one as `trip`
        # in the same shape as config.sample_data.sample_trip().
        context["trip"] = sample_trip(
            origin,
            destination,
            _travel_date(request.GET.get("date")),
            _passenger_count(request.GET.get("passengers")),
        )
    return render(request, "bookings/search.html", context)


@passenger_required
def passenger_dashboard(request):
    """Passenger landing page after login. TODO(Raheem)."""
    return render(request, "bookings/dashboard.html")
