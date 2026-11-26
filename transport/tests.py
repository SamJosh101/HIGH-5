from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from .models import Bus, Route, Schedule


class TransportModelTests(TestCase):
    def setUp(self):
        self.route = Route.objects.create(
            origin="Lagos",
            destination="Ibadan",
            distance_km=130,
            duration_estimate=timedelta(hours=2),
        )
        self.bus = Bus.objects.create(
            name_or_plate="LSD-123",
            bus_type=Bus.BusType.STANDARD,
            total_seats=40,
        )

    def test_route_rejects_same_origin_and_destination(self):
        route = Route(origin="Lagos", destination="lagos", distance_km=1, duration_estimate=timedelta(hours=1))
        with self.assertRaises(ValidationError):
            route.full_clean()

    def test_duplicate_registration_number_is_rejected(self):
        duplicate = Bus(name_or_plate="lsd-123", bus_type=Bus.BusType.LUXURY, total_seats=20)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_overlapping_schedule_is_rejected(self):
        departure = timezone.localdate() + timedelta(days=2)
        first = Schedule(
            route=self.route,
            bus=self.bus,
            departure_date=departure,
            departure_time=datetime.strptime("09:00", "%H:%M").time(),
            fare="5000.00",
        )
        first.save()
        second = Schedule(
            route=self.route,
            bus=self.bus,
            departure_date=departure,
            departure_time=datetime.strptime("10:00", "%H:%M").time(),  # first runs 09:00-11:00
            fare="5000.00",
        )
        with self.assertRaises(ValidationError):
            second.full_clean()

    def test_arrival_is_departure_plus_route_duration(self):
        schedule = Schedule(
            route=self.route,
            bus=self.bus,
            departure_date=timezone.localdate() + timedelta(days=2),
            departure_time=datetime.strptime("22:30", "%H:%M").time(),
            fare="5000.00",
        )
        self.assertEqual(schedule.arrival_datetime - schedule.departure_datetime, timedelta(hours=2))
        self.assertEqual(schedule.arrival_time.strftime("%H:%M"), "00:30")  # next day

    def test_bus_types_follow_the_srs(self):
        self.assertEqual(Bus.BusType.values, ["STANDARD", "LUXURY", "SLEEPER"])


class TransportPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="daniel@example.com",
            password="Strongpass123",
            full_name="Daniel",
            role=User.Role.ADMIN,
        )
        self.passenger = User.objects.create_user(
            email="passenger@example.com",
            password="Strongpass123",
            full_name="Passenger",
        )

    def test_passenger_cannot_manage_routes(self):
        self.client.force_login(self.passenger)
        response = self.client.get(reverse("transport:route_list"))
        self.assertEqual(response.status_code, 403)

    def test_admin_can_manage_routes(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("transport:route_list"))
        self.assertEqual(response.status_code, 200)

    def test_bus_with_past_schedules_is_kept_not_crashed(self):
        route = Route.objects.create(origin="Lagos", destination="Abuja", distance_km=760,
                                     duration_estimate=timedelta(hours=10))
        bus = Bus.objects.create(name_or_plate="ABC-999", bus_type=Bus.BusType.LUXURY, total_seats=44)
        Schedule.objects.create(route=route, bus=bus, departure_date=timezone.localdate() + timedelta(days=1),
                                departure_time=datetime.strptime("07:30", "%H:%M").time(), fare="24000.00",
                                status=Schedule.Status.CANCELLED)
        self.client.force_login(self.admin)
        response = self.client.post(reverse("transport:bus_delete", args=[bus.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "cannot be deleted")
        self.assertTrue(Bus.objects.filter(pk=bus.pk).exists())


class PastScheduleEditTests(TestCase):
    """A trip that has already left can still be edited, but not moved into the past."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="ops@example.com", password="Strongpass123", full_name="Ops", role=User.Role.ADMIN,
        )
        route = Route.objects.create(origin="Lagos", destination="Ibadan", distance_km=130,
                                     duration_estimate=timedelta(hours=2))
        bus = Bus.objects.create(name_or_plate="PST-001", bus_type=Bus.BusType.STANDARD, total_seats=40)
        # Created directly (no clean), as if it was booked before the day passed.
        self.schedule = Schedule.objects.create(
            route=route, bus=bus, departure_date=timezone.localdate() - timedelta(days=1),
            departure_time=datetime.strptime("07:00", "%H:%M").time(), fare="10000.00",
        )
        self.client.force_login(self.admin)

    def post_edit(self, **changes):
        s = self.schedule
        data = {"route": s.route_id, "bus": s.bus_id, "departure_date": s.departure_date.isoformat(),
                "departure_time": "07:00", "fare": "10000.00", "status": s.status, **changes}
        return self.client.post(reverse("transport:schedule_edit", args=[s.pk]), data)

    def test_past_trip_can_be_marked_completed(self):
        response = self.post_edit(status=Schedule.Status.COMPLETED)
        self.assertRedirects(response, reverse("transport:schedule_list"))
        self.schedule.refresh_from_db()
        self.assertEqual(self.schedule.status, Schedule.Status.COMPLETED)

    def test_past_trip_fare_can_be_corrected_even_if_bus_retired(self):
        self.schedule.bus.is_active = False
        self.schedule.bus.save()
        self.post_edit(fare="12000.00")
        self.schedule.refresh_from_db()
        self.assertEqual(str(self.schedule.fare), "12000.00")

    def test_moving_a_trip_to_another_past_time_is_rejected(self):
        response = self.post_edit(departure_time="08:00")
        self.assertContains(response, "Departure cannot be in the past.")

    def test_departed_tab_lists_past_trips_not_yet_completed(self):
        response = self.client.get(reverse("transport:schedule_list"), {"period": "departed"})
        self.assertContains(response, "PST-001")
        response = self.client.get(reverse("transport:schedule_list"))
        self.assertNotContains(response, "PST-001")


class TripCancellationTests(TestCase):
    """When the company cancels a trip, its bookings are cancelled and paid ones refunded."""

    def setUp(self):
        from bookings.models import Booking
        self.Booking = Booking
        self.admin = User.objects.create_user(email="ops2@example.com", password="Strongpass123",
                                              full_name="Ops", role=User.Role.ADMIN)
        rider = User.objects.create_user(email="rider2@example.com", password="Strongpass123", full_name="Rider")
        route = Route.objects.create(origin="Lagos", destination="Benin", distance_km=320,
                                     duration_estimate=timedelta(hours=5))
        bus = Bus.objects.create(name_or_plate="CXL-001", bus_type=Bus.BusType.STANDARD, total_seats=40)
        self.schedule = Schedule.objects.create(route=route, bus=bus, fare="8000.00",
                                                departure_date=timezone.localdate() + timedelta(days=3),
                                                departure_time=datetime.strptime("06:00", "%H:%M").time())
        make = lambda payment: Booking.objects.create(passenger=rider, schedule=self.schedule, seats_booked=1,
                                                      total_amount="8000.00", payment_status=payment)
        self.paid = make(Booking.PaymentStatus.PAID)
        self.unpaid = make(Booking.PaymentStatus.PENDING)
        self.client.force_login(self.admin)

    def check_cascade(self, response):
        self.paid.refresh_from_db()
        self.unpaid.refresh_from_db()
        self.assertEqual((self.paid.status, self.paid.payment_status),
                         (self.Booking.Status.CANCELLED, self.Booking.PaymentStatus.REFUNDED))
        self.assertEqual((self.unpaid.status, self.unpaid.payment_status),
                         (self.Booking.Status.CANCELLED, self.Booking.PaymentStatus.PENDING))
        self.assertIsNotNone(self.paid.cancelled_at)
        self.assertContains(response, "2 bookings cancelled, 1 marked refunded")

    def test_cancel_trip_button_cancels_and_refunds_bookings(self):
        response = self.client.post(reverse("transport:schedule_cancel", args=[self.schedule.pk]), follow=True)
        self.check_cascade(response)

    def test_setting_status_to_cancelled_in_the_edit_form_does_the_same(self):
        s = self.schedule
        response = self.client.post(reverse("transport:schedule_edit", args=[s.pk]), {
            "route": s.route_id, "bus": s.bus_id, "departure_date": s.departure_date.isoformat(),
            "departure_time": "06:00", "fare": "8000.00", "status": Schedule.Status.CANCELLED}, follow=True)
        self.check_cascade(response)
