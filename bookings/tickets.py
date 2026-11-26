"""Everything shown on a ticket, worked out once for the ticket page, the
"You're booked" page and the ticket email, so the three always agree."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from .models import Booking
from .trip_adapter import _duration_label


def ticket_facts(booking):
    """A dict for templates. Expects the booking with schedule, route, bus,
    passenger (the account) and passengers loaded (see get_booking_details)."""
    schedule = booking.schedule
    cutoff_hours = settings.BOOKING_CANCELLATION_CUTOFF_HOURS
    departure = timezone.localtime(schedule.departure_datetime)
    arrival = timezone.localtime(schedule.arrival_datetime)
    cancel_until = departure - timedelta(hours=cutoff_hours)
    travellers = sorted(booking.passengers.all(), key=lambda p: p.pk)

    return {
        "booking": booking,
        "schedule": schedule,
        "route": schedule.route,
        "bus": schedule.bus,
        "departure": departure,
        "arrival": arrival,
        "arrives_next_day": arrival.date() > departure.date(),
        "duration": _duration_label(schedule.route.duration_estimate),
        "travellers": travellers,
        "fare": schedule.fare,
        "currency": settings.CURRENCY_SYMBOL,
        "cutoff_hours": cutoff_hours,
        "cancel_until": cancel_until,
        "can_cancel": (
            booking.status == Booking.Status.CONFIRMED
            and timezone.now() < cancel_until
        ),
        "is_paid": booking.payment_status == Booking.PaymentStatus.PAID,
        "is_refunded": booking.payment_status == Booking.PaymentStatus.REFUNDED,
        "is_confirmed": booking.status == Booking.Status.CONFIRMED,
        "is_cancelled": booking.status == Booking.Status.CANCELLED,
        "trip_cancelled": schedule.status == "CANCELLED",
    }
