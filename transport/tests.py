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
