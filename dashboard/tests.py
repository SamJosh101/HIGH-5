from datetime import time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from bookings.models import Booking
from transport.models import Bus, Route, Schedule


class DashboardPermissionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="Strongpass123",
            full_name="Admin",
            role=User.Role.ADMIN,
        )
        self.passenger = User.objects.create_user(
            email="customer@example.com",
            password="Strongpass123",
            full_name="Customer",
        )

    def test_passenger_cannot_access_dashboard(self):
        self.client.force_login(self.passenger)
        self.assertEqual(self.client.get(reverse("dashboard:home")).status_code, 403)

    def test_admin_dashboard_uses_real_zero_statistics(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_buses"], 0)
        self.assertEqual(response.context["total_routes"], 0)


class DashboardDataTests(TestCase):
    """The admin pages show real numbers, and date grouping works on MySQL
    without its time-zone tables (no `__date` / TruncDate in the queries)."""

    def setUp(self):
        self.admin = User.objects.create_user(email="admin@example.com", password="Strongpass123",
                                              full_name="Ada Admin", role=User.Role.ADMIN)
        self.rider = User.objects.create_user(email="pat@example.com", password="Strongpass123", full_name="Pat")
        route = Route.objects.create(origin="Lagos", destination="Ibadan", distance_km=130,
                                     duration_estimate=timedelta(hours=2))
        bus = Bus.objects.create(name_or_plate="H5-TEST-1", bus_type=Bus.BusType.STANDARD, total_seats=4)
        self.schedule = Schedule.objects.create(route=route, bus=bus, fare="10000.00", departure_time=time(10, 0),
                                                departure_date=timezone.localdate() + timedelta(days=1))
        self.client.force_login(self.admin)

    def book(self, seats, payment=Booking.PaymentStatus.PENDING, status=Booking.Status.CONFIRMED):
        return Booking.objects.create(passenger=self.rider, schedule=self.schedule, seats_booked=seats,
                                      total_amount=Decimal("10000.00") * seats, status=status, payment_status=payment)

    def test_dashboard_numbers_and_seat_fill(self):
        self.book(3, payment=Booking.PaymentStatus.PAID)
        self.book(1, status=Booking.Status.CANCELLED)  # ignored everywhere, frees its seat
        context = self.client.get(reverse("dashboard:home")).context
        self.assertEqual(context["month_revenue"], Decimal("30000.00"))
        self.assertEqual(context["month_bookings"], 1)
        self.assertEqual(context["pending_bookings"], 0)
        trip = context["upcoming_departures"][0]
        self.assertEqual((trip.seats_taken, trip.fill, trip.almost_full), (3, 75, False))
        self.assertEqual(context["chart_data"]["daily"]["values"][-1], 30000.0)  # today, the last point

        self.book(1)  # an unpaid booking fills the bus
        context = self.client.get(reverse("dashboard:home")).context
        self.assertEqual(context["pending_bookings"], 1)
        self.assertTrue(context["upcoming_departures"][0].almost_full)

    def test_reports_group_paid_bookings_by_local_day(self):
        self.book(2, payment=Booking.PaymentStatus.PAID)
        self.book(1)  # pending: not in the report
        today = timezone.localdate()
        response = self.client.get(reverse("dashboard:reports"), {"start": today.isoformat()})
        self.assertEqual(response.context["daily"], [{"day": today, "revenue": Decimal("20000.00")}])
        self.assertEqual(response.context["total_bookings"], 1)
        later = self.client.get(reverse("dashboard:reports"), {"start": (today + timedelta(days=1)).isoformat()})
        self.assertEqual(later.context["total_bookings"], 0)

    def test_bookings_list_date_filter(self):
        booking = self.book(1)
        today = timezone.localdate()
        found = self.client.get(reverse("dashboard:bookings"), {"date": today.isoformat()})
        self.assertEqual([b.pk for b in found.context["bookings"]], [booking.pk])
        other_day = self.client.get(reverse("dashboard:bookings"), {"date": (today - timedelta(days=1)).isoformat()})
        self.assertEqual(list(other_day.context["bookings"]), [])

    def test_booking_detail_unknown_id_is_404(self):
        self.assertEqual(self.client.get(reverse("dashboard:booking_detail", args=[999999])).status_code, 404)

    def test_admin_pages_render_with_the_current_stop_lit(self):
        for name in ["dashboard:home", "dashboard:bookings", "dashboard:reports", "transport:manage",
                     "transport:route_list", "transport:bus_list", "transport:schedule_list",
                     "transport:route_create", "transport:bus_create", "transport:schedule_create"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'aria-current="page"')
        self.assertContains(self.client.get(reverse("transport:route_list")), "2 h")  # duration filter
