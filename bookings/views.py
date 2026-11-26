"""
Bookings module – OWNER: Raheem.

Implements booking and passenger functionality against
docs/DATABASE.md and docs/ARCHITECTURE.md.
"""

from datetime import timedelta

from django.apps import apps
from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import passenger_required

from .models import Booking
from .search_services import search_available_trips
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

    context = {
        "origin": origin,
        "destination": destination,
        "travel_date": travel_date,
        "passenger_count": passenger_count,
        "trips": [],
        "trip": None,
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

                if available_seats >= passenger_count:

                    context["trip"] = schedule_to_trip(
                        schedule=schedule,
                        passengers=passenger_count
                    )

            except (Schedule.DoesNotExist, ValueError, TypeError):
                context["trip"] = None

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

    context = {
        "upcoming_bookings": upcoming_bookings,
        "booking_history": booking_history,
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

    cutoff_hours = getattr(
        settings,
        "BOOKING_CANCELLATION_CUTOFF_HOURS",
        24,
    )

    cancellation_cutoff = (
        booking.schedule.departure_datetime
        - timedelta(hours=cutoff_hours)
    )

    can_cancel = (
        booking.status == Booking.Status.CONFIRMED
        and timezone.now() < cancellation_cutoff
    )

    context = {
        "booking": booking,
        "can_cancel": can_cancel,
        "cutoff_hours": cutoff_hours,
    }

    return render(
        request,
        "bookings/ticket_detail.html",
        context,
    )


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

        # Return the actual saved booking, not the input data.
        response_serializer = BookingSerializer(
            booking,
            context=self.get_serializer_context()
        )

        return Response(
            response_serializer.data,
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