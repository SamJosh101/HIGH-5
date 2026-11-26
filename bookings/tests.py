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


class TicketEmailAndPageTests(TestCase):
    """The ticket email after booking, "Email it again", the ticket page and My Bookings."""

    def setUp(self):
        route = Route.objects.create(origin="Lagos", destination="Abuja", distance_km=760,
                                     duration_estimate=timedelta(hours=10))
        bus = Bus.objects.create(name_or_plate="H5-LAG-01", bus_type=Bus.BusType.LUXURY, total_seats=30)
        self.schedule = Schedule.objects.create(
            route=route, bus=bus, departure_date=timezone.localdate() + timedelta(days=5),
            departure_time=time(6, 0), fare="25000.00",
        )
        self.ada = User.objects.create_user(email="ada@example.com", password=PASSWORD,
                                            full_name="Ada Okafor", email_verified=True)
        self.client.force_login(self.ada)

    def book(self, passengers):
        return self.client.post(reverse("bookings:booking-create"),
                                {"schedule_id": self.schedule.pk, "passengers": passengers},
                                content_type="application/json")

    def test_ticket_is_emailed_to_the_booker_and_travellers_with_an_email(self):
        from django.core import mail
        response = self.book([
            {"full_name": "Ada Okafor", "phone": "+2348012345678", "seat": "3A"},
            {"full_name": "Tunde Bello", "phone": "+2348098765432", "email": "tunde@example.com", "seat": "3B"},
            {"full_name": "No Email", "phone": "+2348000000001", "seat": "4A"},
        ])
        self.assertEqual(response.status_code, 201)
        ref = Booking.objects.get().booking_ref
        self.assertEqual(response.json()["emailed_to"], ["ada@example.com", "tunde@example.com"])
        self.assertEqual(response.json()["ticket_url"], reverse("bookings:ticket-detail", args=[ref]))
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ["ada@example.com", "tunde@example.com"])
        to_ada = next(m for m in mail.outbox if m.to == ["ada@example.com"])
        self.assertIn(ref, to_ada.subject)
        html = to_ada.alternatives[0][0]
        for text in ("Tunde Bello", "3A", "3B", "4A", "H5-LAG-01", "75,000", "Pending", "View your ticket"):
            self.assertIn(text, html)
        self.assertIn("75,000", to_ada.body)
        # a traveller's copy has no "View your ticket" (only the booker can open it)
        to_tunde = next(m for m in mail.outbox if m.to == ["tunde@example.com"])
        self.assertNotIn("View your ticket", to_tunde.alternatives[0][0])
        self.assertIn("Ada Okafor booked this trip for you", to_tunde.alternatives[0][0])

    def test_same_address_twice_gets_one_email(self):
        from django.core import mail
        self.book([{"full_name": "Ada Okafor", "phone": "+2348012345678", "email": "ADA@example.com"}])
        self.assertEqual(len(mail.outbox), 1)

    def test_booking_is_kept_when_the_email_fails(self):
        import smtplib
        from unittest import mock
        with mock.patch("django.core.mail.backends.locmem.EmailBackend.send_messages",
                        side_effect=smtplib.SMTPException("down")), self.assertLogs("bookings.emails", "ERROR"):
            response = self.book([traveller()])
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["emailed_to"], [])
        page = self.client.get(response.json()["ticket_url"] + "?booked=1")
        self.assertContains(page, "couldn't email the ticket")

    def test_booked_page_shows_the_ticket_and_where_it_was_emailed(self):
        response = self.book([{"full_name": "Ada Okafor", "phone": "+2348012345678", "seat": "3A"}])
        page = self.client.get(response.json()["ticket_url"] + "?booked=1")
        self.assertContains(page, "booked, Ada")
        self.assertContains(page, "We emailed this ticket to <b>ada@example.com</b>")
        self.assertContains(page, 'class="h5-ticket')
        self.assertContains(page, "3A")
        # the note is shown once; a reload is the normal ticket page
        again = self.client.get(response.json()["ticket_url"])
        self.assertContains(again, "Your ticket")
        self.assertNotContains(again, "We emailed this ticket")

    def test_email_it_again_is_limited_to_once_a_minute(self):
        from django.core import mail
        from django.core.cache import cache
        self.book([traveller()])
        booking = Booking.objects.get()
        cache.delete(f"h5-ticket-email-{booking.pk}")
        mail.outbox.clear()
        url = reverse("bookings:ticket-email", args=[booking.booking_ref])
        self.assertContains(self.client.post(url, follow=True), "Ticket sent to ada@example.com")
        self.assertContains(self.client.post(url, follow=True), "wait a minute")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.get(url).status_code, 405)
        cache.delete(f"h5-ticket-email-{booking.pk}")

    def test_others_cannot_open_or_email_my_ticket(self):
        self.book([traveller()])
        ref = Booking.objects.get().booking_ref
        other = User.objects.create_user(email="other@example.com", password=PASSWORD,
                                         full_name="Other", email_verified=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("bookings:ticket-detail", args=[ref])).status_code, 404)
        self.assertEqual(self.client.post(reverse("bookings:ticket-email", args=[ref])).status_code, 404)

    def test_my_bookings_lists_upcoming_and_past_rows(self):
        self.book([traveller()])
        cancelled = Booking.objects.get()
        cancelled.status = Booking.Status.CANCELLED
        cancelled.save()
        self.book([traveller()])
        page = self.client.get(reverse("bookings:dashboard"))
        self.assertContains(page, "Upcoming · 1")
        self.assertContains(page, "Past &amp; cancelled · 1")
        self.assertContains(page, "Payment pending")
        self.assertContains(page, "h5-trip-row is-past")


class TripCancelledEmailTests(TestCase):
    """When an admin cancels a trip, everyone on its bookings is emailed."""

    def setUp(self):
        route = Route.objects.create(origin="Lagos", destination="Benin", distance_km=320,
                                     duration_estimate=timedelta(hours=5))
        bus = Bus.objects.create(name_or_plate="CXL-002", bus_type=Bus.BusType.STANDARD, total_seats=40)
        self.schedule = Schedule.objects.create(route=route, bus=bus, fare="8000.00",
                                                departure_date=timezone.localdate() + timedelta(days=3),
                                                departure_time=time(6, 0))
        self.admin = User.objects.create_user(email="ops3@example.com", password=PASSWORD,
                                              full_name="Ops", role=User.Role.ADMIN)
        rider = User.objects.create_user(email="rider3@example.com", password=PASSWORD, full_name="Rider Three")
        self.paid = Booking.objects.create(passenger=rider, schedule=self.schedule, seats_booked=1,
                                           total_amount="8000.00", payment_status=Booking.PaymentStatus.PAID)
        self.paid.passengers.create(full_name="Kemi Ade", phone="+2348011111111", email="kemi@example.com",
                                    seat_number="2C")
        self.unpaid = Booking.objects.create(passenger=rider, schedule=self.schedule, seats_booked=1,
                                             total_amount="8000.00")
        self.unpaid.passengers.create(full_name="Rider Three", phone="+2348022222222", seat_number="2D")

    def test_cancelling_a_trip_emails_the_booker_and_travellers(self):
        from django.core import mail
        self.client.force_login(self.admin)
        response = self.client.post(reverse("transport:schedule_cancel", args=[self.schedule.pk]), follow=True)
        self.assertContains(response, "3 emails sent to the travellers")
        self.assertEqual(sorted(m.to[0] for m in mail.outbox),
                         ["kemi@example.com", "rider3@example.com", "rider3@example.com"])
        paid_body = next(m.body for m in mail.outbox if self.paid.booking_ref in m.subject)
        unpaid_body = next(m.body for m in mail.outbox if self.unpaid.booking_ref in m.subject)
        self.assertIn("full refund", paid_body)
        self.assertIn("Nothing to pay", unpaid_body)
        self.assertTrue(all(m.subject.startswith("Trip cancelled: Lagos → Benin") for m in mail.outbox))


class PassengerListTests(TestCase):
    """Admins see who is travelling on a trip; passengers cannot."""

    def setUp(self):
        route = Route.objects.create(origin="Lagos", destination="Abuja", distance_km=760,
                                     duration_estimate=timedelta(hours=10))
        bus = Bus.objects.create(name_or_plate="PL-001", bus_type=Bus.BusType.LUXURY, total_seats=30)
        self.schedule = Schedule.objects.create(route=route, bus=bus, fare="25000.00",
                                                departure_date=timezone.localdate() + timedelta(days=2),
                                                departure_time=time(6, 0))
        self.rider = User.objects.create_user(email="rider4@example.com", password=PASSWORD,
                                              full_name="Booker Four")
        paid = Booking.objects.create(passenger=self.rider, schedule=self.schedule, seats_booked=2,
                                      total_amount="50000.00", payment_status=Booking.PaymentStatus.PAID)
        paid.passengers.create(full_name="Zed Last", phone="+2348000000010", seat_number="10A")
        paid.passengers.create(full_name="Amy First", phone="+2348000000011", seat_number="2B")
        gone = Booking.objects.create(passenger=self.rider, schedule=self.schedule, seats_booked=1,
                                      total_amount="25000.00", status=Booking.Status.CANCELLED)
        gone.passengers.create(full_name="Cancelled Person", phone="+2348000000012", seat_number="1A")
        self.url = reverse("transport:schedule_passengers", args=[self.schedule.pk])

    def test_admin_sees_travellers_sorted_by_seat_without_cancelled(self):
        admin = User.objects.create_user(email="ops4@example.com", password=PASSWORD, full_name="Ops",
                                         role=User.Role.ADMIN)
        self.client.force_login(admin)
        page = self.client.get(self.url)
        self.assertContains(page, "2 / 30")
        self.assertNotContains(page, "Cancelled Person")
        self.assertContains(page, "1 cancelled booking not listed")
        html = page.content.decode()
        self.assertLess(html.index("Amy First"), html.index("Zed Last"))  # 2B before 10A
        self.assertContains(self.client.get(reverse("transport:schedule_list")), self.url)

    def test_passengers_cannot_open_the_list(self):
        self.client.force_login(self.rider)
        self.assertEqual(self.client.get(self.url).status_code, 403)
