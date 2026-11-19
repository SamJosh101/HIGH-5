"""Project-wide configuration and database tests."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse


class ConfigurationTests(TestCase):
    def test_custom_user_model_active(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "accounts.User")
        self.assertEqual(get_user_model()._meta.label, "accounts.User")

    def test_all_apps_installed(self):
        for app in ("accounts", "transport", "bookings", "dashboard"):
            with self.subTest(app=app):
                self.assertTrue(any(a.split(".")[0] == app for a in settings.INSTALLED_APPS))

    def test_security_middleware_enabled(self):
        for mw in (
            "django.middleware.security.SecurityMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
        ):
            with self.subTest(middleware=mw):
                self.assertIn(mw, settings.MIDDLEWARE)

    def test_secret_key_not_default_placeholder(self):
        self.assertNotIn(settings.SECRET_KEY, ("", "change-me"))

    def test_homepage_renders_base_template(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertContains(response, "HIGH 5")


class HomepageTests(TestCase):
    def test_search_form_submits_to_trip_search(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, f'action="{reverse("bookings:search")}"')
        for field in ('name="origin"', 'name="destination"', 'name="date"', 'name="passengers"'):
            self.assertContains(response, field)

    def test_homepage_assets_and_sections(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "css/home.css")
        self.assertContains(response, "js/home.js")
        for section_id in ('id="routes"', 'id="how"', 'id="support"'):
            self.assertContains(response, section_id)

    def test_cancellation_cutoff_comes_from_settings(self):
        with self.settings(BOOKING_CANCELLATION_CUTOFF_HOURS=12):
            response = self.client.get(reverse("home"))
        self.assertContains(response, "up to 12 hours before departure")


class AssetVersionTests(TestCase):
    def test_css_and_js_links_carry_a_version(self):
        with self.settings(ASSET_VERSION="r42"):
            response = self.client.get(reverse("home"))
        for asset in ("css/high5.css?v=r42", "css/home.css?v=r42", "js/high5.js?v=r42", "js/home.js?v=r42"):
            self.assertContains(response, asset)


class NavigationVisibilityTests(TestCase):
    """The nav shows different links to visitors, passengers and admins."""

    def make_user(self, role):
        return get_user_model().objects.create_user(
            email=f"{role.lower()}@example.com", password="Str0ng-pass-123", full_name=f"Pat {role.title()}", role=role
        )

    def test_visitor_sees_public_links_only(self):
        response = self.client.get(reverse("home"))
        for label in (">Book a Trip<", ">Routes<", ">Support<"):
            self.assertContains(response, label)
        for label in (">My Bookings<", ">History<", ">Dashboard<"):
            self.assertNotContains(response, label)
        self.assertContains(response, reverse("accounts:login"))
        self.assertContains(response, reverse("accounts:register"))

    def test_passenger_sees_my_bookings_and_history(self):
        self.client.force_login(self.make_user("PASSENGER"))
        response = self.client.get(reverse("home"))
        for label in (">Book a Trip<", ">My Bookings<", ">Routes<", ">History<", ">Support<"):
            self.assertContains(response, label)
        self.assertNotContains(response, ">Dashboard<")
        self.assertContains(response, reverse("accounts:logout"))
        self.assertNotContains(response, ">Sign up</a>")

    def test_admin_sees_dashboard_and_transport_not_passenger_links(self):
        self.client.force_login(self.make_user("ADMIN"))
        response = self.client.get(reverse("home"))
        self.assertContains(response, reverse("dashboard:home"))
        self.assertContains(response, reverse("transport:manage"))
        for label in (">My Bookings<", ">History<"):
            self.assertNotContains(response, label)

    def test_current_page_is_marked_active(self):
        response = self.client.get(reverse("bookings:search"))
        self.assertContains(response, 'class="is-active" aria-current="page">Book a Trip<')

    def test_same_nav_and_footer_on_inner_pages(self):
        for name in ("accounts:login", "accounts:register", "bookings:search"):
            response = self.client.get(reverse(name))
            self.assertTemplateUsed(response, "partials/navbar.html")
            self.assertContains(response, 'data-bs-theme="dark"')


class DatabaseTests(TestCase):
    def test_database_connection_works(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_database_engine_matches_configuration(self):
        expected = "mysql" if settings.DB_ENGINE == "mysql" else "sqlite"
        self.assertEqual(connection.vendor, expected)

    def test_mysql_version_is_8_or_newer(self):
        if connection.vendor != "mysql":
            self.skipTest("Running on temporary SQLite - MySQL version not checked.")
        self.assertGreaterEqual(connection.mysql_version[0], 8)
