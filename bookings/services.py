from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Booking, PassengerDetail
from .seats import seat_codes, sort_key, taken_seats


class BookingError(Exception):
    """Raised when a booking operation cannot be completed."""

    def __init__(self, message, taken_seats=()):
        super().__init__(message)
        # Seats someone else booked first, so the page can grey them out.
        self.taken_seats = list(taken_seats)


def get_available_seats(schedule):
    """
    Return the number of seats available for a schedule.
    Cancelled bookings are excluded.
    """

    booked_seats = Booking.objects.filter(
        schedule=schedule,
        status=Booking.Status.CONFIRMED
    ).aggregate(
        total=Sum("seats_booked")
    )["total"] or 0

    total_seats = schedule.bus.total_seats

    return total_seats - booked_seats


@transaction.atomic
def create_booking(passenger, schedule, passengers):
    """
    Create a booking safely while preventing overbooking.

    passengers should be a list of dictionaries containing:
    full_name, phone and optionally email.
    """

    # Lock the schedule so simultaneous bookings cannot
    # both claim the same remaining seats.
    schedule = schedule.__class__.objects.select_for_update().get(
        pk=schedule.pk
    )

    # Check that the passenger account is allowed to book.
    if not passenger.is_authenticated:
        raise BookingError("You must log in before booking.")

    if passenger.role != "PASSENGER":
        raise BookingError("Only passengers can create bookings.")

    # Check that the trip is still available.
    if schedule.status != "SCHEDULED":
        raise BookingError("This trip is not available for booking.")

    if not schedule.bus.is_active or not schedule.route.is_active:
        raise BookingError("This bus or route is no longer active.")

    # Prevent booking trips that have already departed.
    if schedule.departure_datetime <= timezone.now():
        raise BookingError("This trip has already departed.")

    seats_requested = len(passengers)

    if seats_requested < 1:
        raise BookingError("You must provide at least one passenger.")

    if seats_requested > 10:
        raise BookingError("You can book a maximum of 10 seats at once.")

    # Calculate available seats while holding the schedule lock.
    available_seats = get_available_seats(schedule)

    if seats_requested > available_seats:
        raise BookingError(
            f"Only {available_seats} seat(s) are available."
        )

    seats = _choose_seats(schedule, passengers)

    # Calculate the total fare on the server.
    total_amount = schedule.fare * seats_requested

    # Create the booking.
    booking = Booking.objects.create(
        passenger=passenger,
        schedule=schedule,
        seats_booked=seats_requested,
        total_amount=total_amount
    )

    # Save each passenger's details.
    for passenger_data, seat in zip(passengers, seats):
        detail = PassengerDetail(
            booking=booking,
            full_name=passenger_data["full_name"],
            phone=passenger_data["phone"],
            email=passenger_data.get("email", ""),
            seat_number=seat
        )

        detail.full_clean()
        detail.save()

    return booking


def _choose_seats(schedule, passengers):
    """One seat code per passenger, checked while the trip row is locked.

    If the passengers chose seats (the seat map), every one must have a seat,
    each seat must exist on this bus and be free. If nobody chose a seat (an
    API client), the first free seats from the front are given out."""
    all_seats = seat_codes(schedule.bus)
    taken = taken_seats(schedule)
    chosen = [str(p.get("seat") or "").strip().upper() for p in passengers]

    if not any(chosen):
        free = [code for code in all_seats if code not in taken]
        if len(free) < len(passengers):
            raise BookingError("There are not enough free seats on this trip.")
        return free[: len(passengers)]

    if not all(chosen):
        raise BookingError("Choose a seat for every passenger.")
    if len(set(chosen)) != len(chosen):
        raise BookingError("Each passenger needs a different seat.")
    unknown = [code for code in chosen if code not in all_seats]
    if unknown:
        raise BookingError(f"Seat {', '.join(unknown)} does not exist on this bus.")
    clash = sorted((code for code in chosen if code in taken), key=sort_key)
    if clash:
        were = "was" if len(clash) == 1 else "were"
        raise BookingError(
            f"Seat {', '.join(clash)} {were} just booked by someone else. "
            "Your other choices are kept; please pick another seat.",
            taken_seats=clash,
        )
    return chosen


@transaction.atomic
def cancel_booking(passenger, booking_id):
    """
    Cancel a passenger's booking before the cancellation cutoff.
    """

    # Find the booking first so we know which schedule to lock.
    try:
        existing_booking = Booking.objects.get(
            pk=booking_id,
            passenger=passenger
        )
    except Booking.DoesNotExist:
        raise BookingError("Booking not found.")

    # Lock the schedule to coordinate booking and cancellation.
    schedule = existing_booking.schedule.__class__.objects.select_for_update().get(
        pk=existing_booking.schedule_id
    )

    # Lock and retrieve the booking again.
    booking = Booking.objects.select_for_update().get(
        pk=booking_id,
        passenger=passenger
    )

    if booking.status != Booking.Status.CONFIRMED:
        raise BookingError("This booking cannot be cancelled.")

    # Get the cancellation cutoff from project settings.
    cutoff_hours = getattr(
        settings,
        "BOOKING_CANCELLATION_CUTOFF_HOURS",
        24
    )

    cutoff_time = schedule.departure_datetime - timedelta(
        hours=cutoff_hours
    )

    if timezone.now() >= cutoff_time:
        raise BookingError(
            f"Bookings must be cancelled at least {cutoff_hours} "
            "hours before departure."
        )

    # Update booking status.
    booking.status = Booking.Status.CANCELLED
    booking.cancelled_at = timezone.now()

    # Cancelling is only allowed before the cutoff, so a paid booking is
    # refunded in full; it then no longer counts as revenue anywhere.
    if booking.payment_status == Booking.PaymentStatus.PAID:
        booking.payment_status = Booking.PaymentStatus.REFUNDED

    booking.save(
        update_fields=["status", "cancelled_at", "payment_status"]
    )

    return booking


@transaction.atomic
def cancel_trip_bookings(schedule):
    """The company cancelled this trip: cancel every live booking on it and
    refund the paid ones (no cutoff applies; it is not the passenger's choice).
    Returns (bookings cancelled, of which refunded)."""
    now = timezone.now()
    live = Booking.objects.select_for_update().filter(schedule=schedule, status=Booking.Status.CONFIRMED)
    refunded = live.filter(payment_status=Booking.PaymentStatus.PAID).update(
        status=Booking.Status.CANCELLED, cancelled_at=now, payment_status=Booking.PaymentStatus.REFUNDED)
    unpaid = live.update(status=Booking.Status.CANCELLED, cancelled_at=now)
    return refunded + unpaid, refunded


def get_passenger_bookings(passenger):
    """
    Retrieve all bookings belonging to a passenger.
    """

    return Booking.objects.filter(
        passenger=passenger
    ).select_related(
        "schedule",
        "schedule__route",
        "schedule__bus"
    ).prefetch_related(
        "passengers"
    ).order_by(
        "-booked_at"
    )


def get_booking_details(passenger, booking_ref):
    """
    Retrieve one booking using its unique reference.
    Only the passenger who owns the booking can access it.
    """

    try:
        return Booking.objects.select_related(
            "schedule",
            "schedule__route",
            "schedule__bus",
            "passenger"
        ).prefetch_related(
            "passengers"
        ).get(
            booking_ref=booking_ref,
            passenger=passenger
        )

    except Booking.DoesNotExist:
        raise BookingError("Booking not found.")