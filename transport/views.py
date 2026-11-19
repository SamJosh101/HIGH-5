"""
Transport management module – OWNER: Daniel.

Every view here is ADMIN-only. Phase 1 contains a placeholder only.
Implement Route / Bus / Schedule models exactly as agreed in docs/DATABASE.md.
"""

from django.shortcuts import render

from accounts.permissions import admin_required


@admin_required
def manage_index(request):
    """Entry page for route/bus/schedule management. TODO(Daniel)."""
    return render(request, "transport/manage_index.html")
