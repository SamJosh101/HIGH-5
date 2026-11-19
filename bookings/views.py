"""
Bookings module – OWNER: Raheem.

Phase 1 contains placeholders only. Implement against the contract in
docs/DATABASE.md and the rules in docs/ARCHITECTURE.md (atomic booking,
select_for_update, ownership checks).
"""

from django.shortcuts import render

from accounts.permissions import passenger_required


def trip_search(request):
    """Public trip search (no login needed to search). TODO(Raheem)."""
    return render(request, "bookings/search.html")


@passenger_required
def passenger_dashboard(request):
    """Passenger landing page after login. TODO(Raheem)."""
    return render(request, "bookings/dashboard.html")
