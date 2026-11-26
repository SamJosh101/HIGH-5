# Tests for the bookings app. Every feature must ship with tests.
from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from transport.models import Bus, Route, Schedule

from .models import Booking
from io import StringIO
from decimal import Decimal
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

    def test_price_sent_by_the_browser_is_ignored(self):
        self.client.force_login(self.pat)
        self.client.post(reverse("bookings:booking-create"),
                         {"schedule_id": self.schedule.pk, "passengers": [traveller()], "total_amount": "1.00"},
                         content_type="application/json")
        self.assertEqual(str(Booking.objects.get().total_amount), "24000.00")

    def test_admin_fare_change_does_not_alter_existing_bookings(self):
        self.book(self.pat, [traveller()])
        self.schedule.fare = "30000.00"
        self.schedule.save()
        self.assertEqual(str(Booking.objects.get().total_amount), "24000.00")

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

    def test_cancelling_a_paid_booking_refunds_it(self):
        self.book(self.pat, [traveller()])
        booking = Booking.objects.get()
        booking.payment_status = Booking.PaymentStatus.PAID
        booking.save()
        self.client.post(reverse("bookings:booking-cancel", args=[booking.booking_ref]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertEqual(booking.payment_status, Booking.PaymentStatus.REFUNDED)

    def test_cancelling_an_unpaid_booking_stays_pending(self):
        self.book(self.pat, [traveller()])
        self.client.post(reverse("bookings:booking-cancel", args=[Booking.objects.get().booking_ref]))
        self.assertEqual(Booking.objects.get().payment_status, Booking.PaymentStatus.PENDING)

    def test_payment_date_is_recorded_once(self):
        self.book(self.pat, [traveller()])
        booking = Booking.objects.get()
        self.assertIsNone(booking.paid_at)
        booking.payment_status = Booking.PaymentStatus.PAID
        booking.save(update_fields=["payment_status"])
        booking.refresh_from_db()
        first = booking.paid_at
        self.assertIsNotNone(first)
        booking.save()
        booking.refresh_from_db()
        self.assertEqual(booking.paid_at, first)

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


class AutomaticBookingCompletionTests(TestCase):
    def setUp(self):
        route = Route.objects.create(
            origin="Lagos",
            destination="Ibadan",
            distance_km=130,
            duration_estimate=timedelta(hours=2),
        )

        bus = Bus.objects.create(
            name_or_plate="H5-AUTO-01",
            bus_type=Bus.BusType.STANDARD,
            total_seats=4,
        )

        self.schedule = Schedule.objects.create(
            route=route,
            bus=bus,
            departure_date=timezone.localdate() - timedelta(days=1),
            departure_time=time(7, 0),
            fare="10000.00",
        )

        self.passenger = User.objects.create_user(
            email="auto@example.com",
            password=PASSWORD,
            full_name="Auto Passenger",
            email_verified=True,
        )

    def create_booking(self, status, payment_status):
        return Booking.objects.create(
            passenger=self.passenger,
            schedule=self.schedule,
            seats_booked=1,
            total_amount=Decimal("10000.00"),
            status=status,
            payment_status=payment_status,
        )

    def run_completion_command(self):
        output = StringIO()
        call_command("complete_bookings", stdout=output)
        return output.getvalue()

    def test_past_trip_booking_is_completed(self):
        booking = self.create_booking(
            Booking.Status.CONFIRMED,
            Booking.PaymentStatus.PENDING,
        )

        self.run_completion_command()

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.COMPLETED)
        self.assertEqual(booking.payment_status, Booking.PaymentStatus.PENDING)

    def test_cancelled_booking_is_not_changed(self):
        booking = self.create_booking(
            Booking.Status.CANCELLED,
            Booking.PaymentStatus.REFUNDED,
        )

        self.run_completion_command()

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.assertEqual(booking.payment_status, Booking.PaymentStatus.REFUNDED)

    def test_future_trip_booking_is_not_completed(self):
        self.schedule.departure_date = timezone.localdate() + timedelta(days=2)
        self.schedule.save()

        booking = self.create_booking(
            Booking.Status.CONFIRMED,
            Booking.PaymentStatus.PAID,
        )

        self.run_completion_command()

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        self.assertEqual(booking.payment_status, Booking.PaymentStatus.PAID)

    def test_cancelled_schedule_booking_is_not_completed(self):
        self.schedule.status = Schedule.Status.CANCELLED
        self.schedule.save()

        booking = self.create_booking(
            Booking.Status.CONFIRMED,
            Booking.PaymentStatus.PAID,
        )

        self.run_completion_command()

        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)

    def test_arrived_trip_is_marked_completed_and_bus_freed(self):
        bus = self.schedule.bus
        bus.status = Bus.Status.ASSIGNED
        bus.save()

        output = self.run_completion_command()

        self.schedule.refresh_from_db()
        bus.refresh_from_db()
        self.assertEqual(self.schedule.status, Schedule.Status.COMPLETED)
        self.assertEqual(bus.status, Bus.Status.AVAILABLE)
        self.assertIn("1 trip(s)", output)

    def test_future_trip_stays_scheduled(self):
        self.schedule.departure_date = timezone.localdate() + timedelta(days=2)
        self.schedule.save()

        self.run_completion_command()

        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status, Schedule.Status.SCHEDULED)


class SeatSelectionTests(TestCase):
    """Passengers pick seats on the map; the server checks them again (bookings/seats.py)."""

    def setUp(self):
        route = Route.objects.create(origin="Lagos", destination="Ibadan", distance_km=130,
                                     duration_estimate=timedelta(hours=2))
        self.bus = Bus.objects.create(name_or_plate="SEAT-01", bus_type=Bus.BusType.STANDARD, total_seats=10)
        self.schedule = Schedule.objects.create(
            route=route, bus=self.bus, departure_date=timezone.localdate() + timedelta(days=3),
            departure_time=time(7, 30), fare="5000.00",
        )
        self.pat = User.objects.create_user(email="pat@example.com", password=PASSWORD,
                                            full_name="Pat", email_verified=True)
        self.sam = User.objects.create_user(email="sam@example.com", password=PASSWORD,
                                            full_name="Sam", email_verified=True)

    def book(self, user, *seats):
        self.client.force_login(user)
        passengers = [dict(traveller(f"Rider {seat or i}"), seat=seat) for i, seat in enumerate(seats)]
        return self.client.post(reverse("bookings:booking-create"),
                                {"schedule_id": self.schedule.pk, "passengers": passengers},
                                content_type="application/json")

    def test_layouts_follow_the_bus_type(self):
        from .seats import seat_codes
        self.assertEqual(seat_codes(self.bus), ["1A", "1B", "1C", "1D", "2A", "2B", "2C", "2D", "3A", "3B"])
        luxury = Bus(name_or_plate="L", bus_type=Bus.BusType.LUXURY, total_seats=4)
        self.assertEqual(seat_codes(luxury), ["1A", "1B", "1C", "2A"])

    def test_chosen_seats_are_saved_per_passenger(self):
        response = self.book(self.pat, "2B", "2A")
        self.assertEqual(response.status_code, 201)
        booking = Booking.objects.get()
        self.assertEqual(sorted(booking.passengers.values_list("seat_number", flat=True)), ["2A", "2B"])
        self.assertEqual(booking.seat_list, "2A, 2B")
        self.assertEqual({p["seat_number"] for p in response.json()["passengers"]}, {"2A", "2B"})

    def test_a_booked_seat_cannot_be_booked_again(self):
        self.book(self.pat, "1A")
        response = self.book(self.sam, "1B", "1A")
        self.assertEqual(response.status_code, 400)
        self.assertIn("1A was just booked by someone else", str(response.json()["booking"]))
        self.assertEqual(response.json()["taken_seats"], ["1A"])
        self.assertEqual(Booking.objects.count(), 1)  # nothing saved, not even 1B

    def test_cancelling_frees_the_seat(self):
        self.book(self.pat, "1A")
        ref = Booking.objects.get().booking_ref
        self.client.post(reverse("bookings:booking-cancel", args=[ref]))
        self.assertEqual(self.book(self.sam, "1A").status_code, 201)

    def test_bad_seat_choices_are_rejected(self):
        for seats, message in [(("9Z",), "does not exist"), (("4A",), "does not exist"),
                               (("1A", "1A"), "different seat"), (("1A", ""), "every passenger")]:
            with self.subTest(seats=seats):
                response = self.book(self.pat, *seats)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, str(response.json()))
        self.assertFalse(Booking.objects.exists())

    def test_without_choices_the_first_free_seats_are_given(self):
        self.book(self.pat, "1A")
        self.book(self.sam, "", "")
        self.assertEqual(Booking.objects.get(passenger=self.sam).seat_list, "1B, 1C")

    def test_booking_page_shows_the_seat_map_with_booked_seats(self):
        self.book(self.pat, "1A")
        self.client.force_login(self.sam)
        response = self.client.get(reverse("bookings:search"), {
            "origin": "Lagos", "destination": "Ibadan", "date": self.schedule.departure_date.isoformat(),
            "passengers": 1, "schedule_id": self.schedule.pk})
        self.assertContains(response, 'data-seat="1B"')
        self.assertNotContains(response, 'data-seat="1A"')
        self.assertContains(response, "Seat 1A, booked")
        self.assertNotContains(response, "Seat selection coming soon")
