# Tests for the bookings app. Every feature must ship with tests.
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from transport.models import Bus, Route, Schedule

from .models import Booking
from .services import get_available_seats

User = get_user_model()
PASSWORD = "Str0ng-Test-Pass!"


def traveller(name="Ada Traveller"):
    return {"full_name": name, "phone": "+2348000000000"}


class BookingApiTests(TestCase):
    """End-to-end checks of the booking API: totals, seat limits, ownership, cancellation."""

    def setUp(self):
        route = Route.objects.create(origin="Lagos", destination="Abuja", distance_km=760,
                                     duration_estimate=timedelta(hours=6, minutes=15))
        bus = Bus.objects.create(name_or_plate="H5-007", bus_type=Bus.BusType.LUXURY, total_seats=3)
        self.schedule = Schedule.objects.create(
            route=route, bus=bus, departure_date=timezone.localdate() + timedelta(days=5),
            departure_time=time(7, 30), fare="24000.00",
        )
        self.pat = User.objects.create_user(email="pat@example.com", password=PASSWORD,
                                            full_name="Pat Passenger", email_verified=True)
        self.sam = User.objects.create_user(email="sam@example.com", password=PASSWORD,
                                            full_name="Sam Passenger", email_verified=True)

    def book(self, user, travellers):
        self.client.force_login(user)
        return self.client.post(reverse("bookings:booking-create"),
                                {"schedule_id": self.schedule.pk, "passengers": travellers},
                                content_type="application/json")

    def test_booking_total_is_calculated_on_the_server(self):
        response = self.book(self.pat, [traveller(), traveller("Bo Traveller")])
        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get()
        self.assertEqual((booking.seats_booked, str(booking.total_amount)), (2, "48000.00"))
        self.assertEqual(booking.passengers.count(), 2)
        self.assertEqual(get_available_seats(self.schedule), 1)

    def test_cannot_book_more_seats_than_are_left(self):
        self.book(self.pat, [traveller(), traveller()])
        response = self.book(self.sam, [traveller(), traveller()])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Booking.objects.count(), 1)

    def test_passengers_cannot_see_or_cancel_each_others_bookings(self):
        self.book(self.pat, [traveller()])
        ref = Booking.objects.get().booking_ref
        self.client.force_login(self.sam)
        self.assertEqual(self.client.get(reverse("bookings:booking-detail", args=[ref])).status_code, 404)
        self.client.post(reverse("bookings:booking-cancel", args=[ref]))
        self.assertEqual(Booking.objects.get().status, Booking.Status.CONFIRMED)

    def test_cancelling_frees_the_seats(self):
        self.book(self.pat, [traveller(), traveller()])
        ref = Booking.objects.get().booking_ref
        response = self.client.post(reverse("bookings:booking-cancel", args=[ref]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Booking.objects.get().status, Booking.Status.CANCELLED)
        self.assertEqual(get_available_seats(self.schedule), 3)

    def test_admins_and_visitors_cannot_book(self):
        admin = User.objects.create_user(email="ada@example.com", password=PASSWORD, full_name="Ada Admin",
                                         role=User.Role.ADMIN, email_verified=True)
        self.assertEqual(self.book(admin, [traveller()]).status_code, 403)
        self.client.logout()
        response = self.client.post(reverse("bookings:booking-create"),
                                    {"schedule_id": self.schedule.pk, "passengers": [traveller()]},
                                    content_type="application/json")
        self.assertIn(response.status_code, (401, 403))
        self.assertFalse(Booking.objects.exists())
