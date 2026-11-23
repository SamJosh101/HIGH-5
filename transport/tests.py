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
        duplicate = Bus(name_or_plate="lsd-123", bus_type=Bus.BusType.VIP, total_seats=20)
        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_overlapping_schedule_is_rejected(self):
        departure = timezone.localdate() + timedelta(days=2)
        first = Schedule(
            route=self.route,
            bus=self.bus,
            departure_date=departure,
            departure_time=datetime.strptime("09:00", "%H:%M").time(),
            arrival_time=datetime.strptime("12:00", "%H:%M").time(),
            fare="5000.00",
        )
        first.save()
        second = Schedule(
            route=self.route,
            bus=self.bus,
            departure_date=departure,
            departure_time=datetime.strptime("11:00", "%H:%M").time(),
            arrival_time=datetime.strptime("14:00", "%H:%M").time(),
            fare="5000.00",
        )
        with self.assertRaises(ValidationError):
            second.full_clean()


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
