from django.test import TestCase
from django.urls import reverse

from accounts.models import User


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
