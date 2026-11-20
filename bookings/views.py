"""
Bookings module – OWNER: Raheem.

Phase 1 contains placeholders only. Implement against the contract in
docs/DATABASE.md and the rules in docs/ARCHITECTURE.md (atomic booking,
select_for_update, ownership checks).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from accounts.permissions import passenger_required


@login_required
def trip_search(request):
    """Book a Trip page: trip search for logged-in users. TODO(Raheem).

    Login is enforced here on the server. A logged-out visitor (for example one
    who clicked a Popular Route on the homepage) is redirected to the login page
    with ?next=<this URL incl. origin/destination>, and comes back to this
    search, pre-filled, after logging in or signing up.
    """
    return render(request, "bookings/search.html")


@passenger_required
def passenger_dashboard(request):
    """Passenger landing page after login. TODO(Raheem)."""
    return render(request, "bookings/dashboard.html")
