"""Project-level views that don't belong to a single app."""

from django.conf import settings
from django.views.generic import TemplateView

# PLACEHOLDER routes (see config/sample_data.py). Replace with a query on
# Daniel's transport.Route / Schedule models once they exist, e.g. the
# most-booked active routes with their lowest upcoming fare.
from .sample_data import SAMPLE_ROUTES


class HomeView(TemplateView):
    template_name = "home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["sample_routes"] = SAMPLE_ROUTES
        context["currency"] = settings.CURRENCY_SYMBOL
        context["cancel_cutoff_hours"] = settings.BOOKING_CANCELLATION_CUTOFF_HOURS
        return context
