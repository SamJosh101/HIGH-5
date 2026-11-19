"""Project-level views that don't belong to a single app."""

from django.conf import settings
from django.views.generic import TemplateView

# PLACEHOLDER routes for the homepage "Popular routes" cards:
# (origin, destination, duration, departures per day, bus type, starting fare).
# Replace with a query on Daniel's transport.Route / Schedule models once they
# exist, e.g. the most-booked active routes with their lowest upcoming fare.
SAMPLE_ROUTES = [
    ("Eastgate", "Riverside", "6 h 15 m", 8, "Executive", "24.00"),
    ("Millbrook", "Harbour City", "3 h 40 m", 6, "Standard", "15.00"),
    ("Stonebridge", "Lakeview", "5 h 05 m", 4, "Executive", "21.00"),
    ("Oakfield", "Eastgate", "2 h 30 m", 10, "Standard", "11.00"),
]


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sample_routes"] = SAMPLE_ROUTES
        context["cancel_cutoff_hours"] = settings.BOOKING_CANCELLATION_CUTOFF_HOURS
        return context
