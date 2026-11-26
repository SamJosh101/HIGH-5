"""
Bookings module – OWNER: Raheem.

Implements booking and passenger functionality against
docs/DATABASE.md and docs/ARCHITECTURE.md.
"""

from datetime import timedelta

from django.apps import apps
from django.contrib import messages
from django.core.cache import cache
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import passenger_required

from .emails import send_ticket_email
from .models import Booking
from .search_services import (
    LOOKAHEAD_DAYS,
    all_upcoming_trips,
    alternative_trips,
    city_choices,
    search_available_trips,
)
from .tickets import ticket_facts
from .serializers import BookingCreateSerializer, BookingSerializer
from .services import (
    BookingError,
    cancel_booking,
    get_booking_details,
    get_passenger_bookings,
)
from .trip_adapter import schedule_to_trip


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


@passenger_required
def trip_search(request):
    """Search available trips and display the selected trip."""

    origin = request.GET.get("origin", "").strip()
    destination = request.GET.get("destination", "").strip()

    travel_date = _travel_date(request.GET.get("date"))

    passenger_count = _passenger_count(
        request.GET.get("passengers")
    )

    # "All trips" tab: every trip that can still be booked, with optional filters.
    if request.GET.get("view") == "all":
        origins, destinations = city_choices()
        return render(request, "bookings/search.html", {
            "all_view": True,
            "all_trips": all_upcoming_trips(origin, destination, min(passenger_count, 10)),
            "origin": origin,
            "destination": destination,
            "passenger_count": min(passenger_count, 10),
            "origins": origins,
            "destinations": destinations,
            "lookahead_days": LOOKAHEAD_DAYS,
            "today": timezone.localdate(),
            "tomorrow": timezone.localdate() + timedelta(days=1),
        })

    context = {
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "passenger_count": passenger_count,
        "trips": [],
        "trip": None,
        "lookahead_days": LOOKAHEAD_DAYS,
    }

    if (
        origin
        and destination
        and origin.lower() != destination.lower()
    ):

        # Retrieve matching schedules.
        context["trips"] = search_available_trips(
            origin=origin,
            destination=destination,
            travel_date=travel_date,
            passengers=passenger_count,
        )

        # Check whether the passenger selected a particular schedule.
        selected_schedule_id = request.GET.get("schedule_id")

        if selected_schedule_id:

            Schedule = apps.get_model(
                "transport",
                "Schedule"
            )

            try:
                schedule = Schedule.objects.select_related(
                    "route",
                    "bus"
                ).get(
                    pk=selected_schedule_id,
                    route__origin__iexact=origin,
                    route__destination__iexact=destination,
                    route__is_active=True,
                    bus__is_active=True,
                    departure_date=travel_date,
                    status="SCHEDULED",
                )

                from .services import get_available_seats

                available_seats = get_available_seats(schedule)

                # a trip that has already left cannot be opened for booking
                if available_seats >= passenger_count and schedule.departure_datetime > timezone.now():

                    context["trip"] = schedule_to_trip(
                        schedule=schedule,
                        passengers=passenger_count
                    )

            except (Schedule.DoesNotExist, ValueError, TypeError):
                context["trip"] = None

        # Nothing on that route that day: suggest what they can book instead.
        if not context["trips"]:
            context["alternatives"] = alternative_trips(origin, destination, travel_date, passenger_count)

    return render(
        request,
        "bookings/search.html",
        context
    )


@passenger_required
def passenger_dashboard(request):
    """Display the passenger's upcoming trips and booking history."""

    bookings = get_passenger_bookings(request.user)
    now = timezone.now()

    upcoming_bookings = []
    booking_history = []

    for booking in bookings:
        departure = booking.schedule.departure_datetime

        if booking.status == Booking.Status.CONFIRMED and departure > now:
            upcoming_bookings.append(booking)
        else:
            booking_history.append(booking)

    # Soonest trip first; history stays newest booking first.
    upcoming_bookings.sort(key=lambda b: b.schedule.departure_datetime)

    context = {
        "upcoming_bookings": upcoming_bookings,
        "booking_history": booking_history,
        "today": timezone.localdate(),
    }

    return render(
        request,
        "bookings/dashboard.html",
        context,
    )


@ensure_csrf_cookie
@passenger_required
def ticket_detail(request, booking_ref):
    """Display the details of one passenger's booking."""

    try:
        booking = get_booking_details(
            passenger=request.user,
            booking_ref=booking_ref,
        )
    except BookingError:
        raise Http404("Booking not found.")

    context = ticket_facts(booking)
    # Right after booking, booking.js opens this page with ?booked=1. The
    # addresses the ticket was emailed to were kept in the session for it
    # (None = this page was not reached from a new booking).
    context["just_booked"] = request.GET.get("booked") == "1"
    context["emailed_to"] = request.session.pop(_emailed_key(booking), None)

    return render(
        request,
        "bookings/ticket_detail.html",
        context,
    )


def _emailed_key(booking):
    return f"h5_ticket_emailed_{booking.booking_ref}"


TICKET_EMAIL_EVERY_SECONDS = 60


@require_POST
@passenger_required
def ticket_email(request, booking_ref):
    """"Email it again": send the ticket to the account's own address
    (at most once a minute per booking, so the button cannot spam)."""
    try:
        booking = get_booking_details(passenger=request.user, booking_ref=booking_ref)
    except BookingError:
        raise Http404("Booking not found.")

    if booking.status == Booking.Status.CANCELLED:
        messages.error(request, "This booking is cancelled, so there is no ticket to send.")
    elif not cache.add(f"h5-ticket-email-{booking.pk}", True, TICKET_EMAIL_EVERY_SECONDS):
        messages.info(request, "The ticket was just sent. Please wait a minute before asking again.")
    elif send_ticket_email(booking, request.build_absolute_uri("/"), only_booker=True):
        messages.success(request, f"Ticket sent to {request.user.email}.")
    else:
        cache.delete(f"h5-ticket-email-{booking.pk}")
        messages.error(request, "The ticket could not be emailed just now. Please try again later.")
    return redirect("bookings:ticket-detail", booking_ref=booking.booking_ref)


class IsPassenger(BasePermission):
    """
    Allow access only to authenticated passenger accounts.
    """

    message = "Only passengers can access this endpoint."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == "PASSENGER"
        )


class BookingCreateAPIView(generics.CreateAPIView):
    serializer_class = BookingCreateSerializer
    permission_classes = [IsAuthenticated, IsPassenger]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            booking = serializer.save()

        except BookingError as error:
            detail = {"booking": str(error)}
            if error.taken_seats:
                detail["taken_seats"] = error.taken_seats
            raise ValidationError(detail)

        # Email the ticket to the booker and to travellers who gave an email.
        # The booking is already saved, so a mail failure only means the ticket
        # page says it could not be sent.
        booking = get_booking_details(passenger=request.user, booking_ref=booking.booking_ref)
        emailed_to = send_ticket_email(booking, request.build_absolute_uri("/"))
        request.session[_emailed_key(booking)] = emailed_to

        # Return the actual saved booking, not the input data.
        response_serializer = BookingSerializer(
            booking,
            context=self.get_serializer_context()
        )
        data = dict(response_serializer.data)
        data["emailed_to"] = emailed_to
        data["ticket_url"] = reverse("bookings:ticket-detail", args=[booking.booking_ref])

        return Response(
            data,
            status=status.HTTP_201_CREATED
        )


class BookingHistoryAPIView(generics.ListAPIView):
    serializer_class = BookingSerializer
    permission_classes = [IsAuthenticated, IsPassenger]

    def get_queryset(self):
        return get_passenger_bookings(self.request.user)


class BookingDetailAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPassenger]

    def get(self, request, booking_ref):
        try:
            booking = get_booking_details(
                passenger=request.user,
                booking_ref=booking_ref
            )

            serializer = BookingSerializer(booking)

            return Response(serializer.data)

        except BookingError as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_404_NOT_FOUND
            )


class BookingCancelAPIView(APIView):
    permission_classes = [IsAuthenticated, IsPassenger]

    def post(self, request, booking_ref):
        try:
            booking = Booking.objects.get(
                booking_ref=booking_ref,
                passenger=request.user
            )

            cancelled_booking = cancel_booking(
                passenger=request.user,
                booking_id=booking.pk
            )

            serializer = BookingSerializer(cancelled_booking)

            return Response({
                "message": "Booking cancelled successfully.",
                "booking": serializer.data
            })

        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        except BookingError as error:
            return Response(
                {"error": str(error)},
                status=status.HTTP_400_BAD_REQUEST
            )