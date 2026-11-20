"""Project-wide configuration and database tests."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.urls import reverse
from django.utils.http import urlencode

PASSWORD = "Str0ng-pass-123"


def make_user(role):
    return get_user_model().objects.create_user(
        email=f"{role.lower()}@example.com", password=PASSWORD, full_name=f"Pat {role.title()}", role=role
    )


def nav_html(response):
    """Only the site header (desktop pill + mobile menu), not the page body or footer."""
    html = response.content.decode()
    start = html.index('<header class="h5-hnav"')
    return html[start:html.index("</header>", start)]


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
    def test_homepage_has_no_trip_search_form(self):
        """Trip search lives on the Book a Trip page only, for every visitor type."""
        for role in (None, "PASSENGER"):
            with self.subTest(role=role):
                self.client.logout()
                if role:
                    self.client.force_login(make_user(role))
                response = self.client.get(reverse("home"))
                self.assertNotContains(response, 'id="h5Search"')
                for field in ('name="origin"', 'name="destination"', 'name="date"', 'name="passengers"'):
                    self.assertNotContains(response, field)

    def test_book_a_trip_page_still_has_the_search_form(self):
        self.client.force_login(make_user("PASSENGER"))
        response = self.client.get(reverse("bookings:search"))
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
    """The navbar follows Django's real login state (strict lists, see nav_links.html)."""

    LOGGED_OUT = (">Routes<", ">Support<", ">How It Works<")
    PASSENGER = (">Book a Trip<", ">My Bookings<", ">History<")

    def assert_nav(self, response, shown, hidden):
        nav = nav_html(response)
        for label in shown:
            self.assertIn(label, nav)
        for label in hidden:
            self.assertNotIn(label, nav)

    def test_logged_out_nav(self):
        response = self.client.get(reverse("home"))
        self.assert_nav(response, self.LOGGED_OUT, self.PASSENGER + (">Dashboard<", ">Transport<"))
        nav = nav_html(response)
        self.assertIn(reverse("accounts:login"), nav)
        self.assertIn(reverse("accounts:register"), nav)
        self.assertNotIn(reverse("accounts:logout"), nav)

    def test_logged_out_page_never_offers_booking_links(self):
        response = self.client.get(reverse("home"))
        for label in (">Book a Trip<", ">My Bookings<", ">History<", "Book a trip &rarr;"):
            self.assertNotContains(response, label)

    def test_passenger_nav(self):
        self.client.force_login(make_user("PASSENGER"))
        response = self.client.get(reverse("home"))
        self.assert_nav(response, self.PASSENGER, self.LOGGED_OUT + (">Dashboard<", ">Log in<", ">Sign up<"))
        self.assertIn(reverse("accounts:logout"), nav_html(response))

    def test_admin_nav(self):
        self.client.force_login(make_user("ADMIN"))
        response = self.client.get(reverse("home"))
        self.assert_nav(response, (">Dashboard<", ">Transport<"), self.LOGGED_OUT + self.PASSENGER)

    def test_nav_changes_immediately_on_login_and_logout(self):
        make_user("PASSENGER")
        self.client.post(reverse("accounts:login"), {"username": "passenger@example.com", "password": PASSWORD})
        self.assert_nav(self.client.get(reverse("home")), self.PASSENGER, self.LOGGED_OUT)
        self.client.post(reverse("accounts:logout"))
        self.assert_nav(self.client.get(reverse("home")), self.LOGGED_OUT, self.PASSENGER)

    def test_current_page_is_marked_active(self):
        self.client.force_login(make_user("PASSENGER"))
        response = self.client.get(reverse("bookings:search"))
        self.assertContains(response, 'class="is-active" aria-current="page">Book a Trip<')

    def test_same_nav_and_footer_on_inner_pages(self):
        for name in ("accounts:login", "accounts:register"):
            response = self.client.get(reverse(name))
            self.assertTemplateUsed(response, "partials/navbar.html")
            self.assertContains(response, 'data-bs-theme="dark"')


class PopularRouteAccessTests(TestCase):
    """Popular routes are visible to everyone, but opening one needs a login (server-enforced)."""

    def route_url(self, origin="Eastgate", destination="Riverside"):
        return f'{reverse("bookings:search")}?{urlencode({"origin": origin, "destination": destination})}'

    def test_routes_are_visible_and_link_to_the_trip_search_when_logged_out(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'id="routes"')
        self.assertContains(response, f'href="{reverse("bookings:search")}?origin=', count=4)

    def test_logged_out_route_click_redirects_to_login_with_the_route_kept(self):
        response = self.client.get(self.route_url())
        expected = f'{reverse("accounts:login")}?{urlencode({"next": self.route_url()})}'
        self.assertRedirects(response, expected)

    def test_after_login_the_user_lands_on_the_prefilled_search(self):
        make_user("PASSENGER")
        login_url = f'{reverse("accounts:login")}?{urlencode({"next": self.route_url()})}'
        page = self.client.get(login_url)
        self.assertContains(page, "?next=")  # the Sign up link keeps the route too
        response = self.client.post(login_url, {"username": "passenger@example.com", "password": PASSWORD}, follow=True)
        self.assertEqual(response.redirect_chain[-1][0], self.route_url())
        self.assertContains(response, 'value="Eastgate"')
        self.assertContains(response, 'value="Riverside"')

    def test_after_sign_up_the_user_lands_on_the_prefilled_search(self):
        data = {"full_name": "New Rider", "email": "rider@example.com", "phone": "+2348000000000",
                "password1": PASSWORD, "password2": PASSWORD, "next": self.route_url()}
        response = self.client.post(reverse("accounts:register"), data)
        self.assertRedirects(response, self.route_url())

    def test_sign_up_ignores_next_urls_on_other_sites(self):
        data = {"full_name": "New Rider", "email": "rider@example.com", "phone": "+2348000000000",
                "password1": PASSWORD, "password2": PASSWORD, "next": "https://evil.example.com/"}
        response = self.client.post(reverse("accounts:register"), data)
        self.assertRedirects(response, reverse("accounts:after_login"), fetch_redirect_response=False)

    def test_logged_in_route_click_opens_book_a_trip_prefilled(self):
        self.client.force_login(make_user("PASSENGER"))
        response = self.client.get(self.route_url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "bookings/search.html")
        self.assertContains(response, 'value="Eastgate"')
        self.assertContains(response, 'value="Riverside"')

    def test_protected_pages_redirect_to_login_when_logged_out(self):
        for name in ("bookings:search", "bookings:dashboard", "dashboard:home", "transport:manage",
                     "accounts:profile", "accounts:password_change"):
            with self.subTest(url=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response["Location"].startswith(reverse("accounts:login")))


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
