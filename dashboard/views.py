"""
Administrator dashboard – OWNER: Daniel.

ADMIN-only. Statistics, revenue summaries and reports read from the
transport and bookings models; this app should not define its own copies
of that data (dashboard/models.py stays empty unless the team agrees).
"""

from django.shortcuts import render

from accounts.permissions import admin_required


@admin_required
def admin_home(request):
    """Admin landing page after login. TODO(Daniel): statistics, revenue."""
    return render(request, "dashboard/home.html")
