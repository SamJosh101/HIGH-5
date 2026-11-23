import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "Str0ng-Test-Pass!"


def make_passenger(email="pat@example.com", **kw):
    kw.setdefault("email_verified", True)  # most tests need a user who can log in
    return User.objects.create_user(email=email, password=PASSWORD, full_name="Pat Passenger", **kw)


def make_admin(email="ada@example.com"):
    return User.objects.create_user(
        email=email, password=PASSWORD, full_name="Ada Admin", role=User.Role.ADMIN, email_verified=True
    )


class UserModelTests(TestCase):
    def test_password_is_hashed(self):
        user = make_passenger()
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith(("pbkdf2_sha256$", "argon2", "bcrypt", "scrypt")))
        self.assertTrue(user.check_password(PASSWORD))

    def test_default_role_is_passenger(self):
        user = make_passenger()
        self.assertEqual(user.role, User.Role.PASSENGER)
        self.assertTrue(user.is_passenger_role)
        self.assertFalse(user.is_admin_role)
        self.assertFalse(user.is_staff)

    def test_email_is_unique_and_lowercased(self):
        make_passenger(email="Pat@Example.com")
        self.assertTrue(User.objects.filter(email="pat@example.com").exists())
        with self.assertRaises(IntegrityError):
            make_passenger(email="PAT@example.com")

    def test_create_superuser_is_admin(self):
        su = User.objects.create_superuser(email="root@example.com", password=PASSWORD, full_name="Root")
        self.assertEqual(su.role, User.Role.ADMIN)
        self.assertTrue(su.is_staff and su.is_superuser and su.is_admin_role)

    def test_inactive_user_has_no_role_access(self):
        user = make_admin()
        user.is_active = False
        self.assertFalse(user.is_admin_role)


class RegistrationTests(TestCase):
    url = reverse("accounts:register")

    def form_data(self, **overrides):
        data = {
            "full_name": "New Rider",
            "email": "rider@example.com",
            "phone": "+2348000000000",
            "password1": PASSWORD,
            "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_register_page_loads(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_register_creates_unverified_passenger_and_sends_link(self):
        response = self.client.post(self.url, self.form_data())
        self.assertRedirects(response, reverse("accounts:verification_sent"))
        user = User.objects.get(email="rider@example.com")
        self.assertEqual(user.role, User.Role.PASSENGER)
        self.assertFalse(user.email_verified)
        self.assertNotIn("_auth_user_id", self.client.session)  # not logged in until verified
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["rider@example.com"])
        self.assertIn("/accounts/verify-email/", mail.outbox[0].body)

    def test_cannot_register_as_admin_by_tampering(self):
        self.client.post(self.url, self.form_data(role="ADMIN", is_staff="on", is_superuser="on"))
        user = User.objects.get(email="rider@example.com")
        self.assertEqual(user.role, User.Role.PASSENGER)
        self.assertFalse(user.is_staff or user.is_superuser)

    def test_duplicate_email_rejected_case_insensitive(self):
        make_passenger(email="rider@example.com")
        response = self.client.post(self.url, self.form_data(email="RIDER@example.com"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.count(), 1)

    def test_mismatched_passwords_rejected(self):
        response = self.client.post(self.url, self.form_data(password2="different-Pass-99"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_weak_password_rejected(self):
        response = self.client.post(self.url, self.form_data(password1="12345678", password2="12345678"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())

    def test_invalid_phone_rejected(self):
        response = self.client.post(self.url, self.form_data(phone="call-me"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.exists())


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.passenger = make_passenger()
        self.admin = make_admin()

    def test_login_with_email(self):
        response = self.client.post(reverse("accounts:login"), {"username": "pat@example.com", "password": PASSWORD})
        self.assertRedirects(response, reverse("accounts:after_login"), fetch_redirect_response=False)
        self.assertIn("_auth_user_id", self.client.session)

    def test_login_wrong_password_fails(self):
        response = self.client.post(reverse("accounts:login"), {"username": "pat@example.com", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_login(self):
        self.passenger.is_active = False
        self.passenger.save()
        self.client.post(reverse("accounts:login"), {"username": "pat@example.com", "password": PASSWORD})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_passenger_redirected_to_passenger_dashboard(self):
        self.client.force_login(self.passenger)
        self.assertRedirects(self.client.get(reverse("accounts:after_login")), reverse("bookings:dashboard"))

    def test_admin_redirected_to_admin_dashboard(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("accounts:after_login")), reverse("dashboard:home"))

    def test_logout_requires_post(self):
        self.client.force_login(self.passenger)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_view_enforces_csrf(self):
        from django.test import Client

        strict = Client(enforce_csrf_checks=True)
        response = strict.post(reverse("accounts:login"), {"username": "pat@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 403)


def verification_link(message):
    """The /accounts/verify-email/... address (with any ?next=) from a sent email."""
    return re.search(r"https?://[^/\s]+(/accounts/verify-email/\S+)", message.body).group(1)


class EmailVerificationTests(TestCase):
    def setUp(self):
        cache.clear()  # the resend throttle uses the cache

    def register(self, **extra):
        data = {"full_name": "New Rider", "email": "rider@example.com", "phone": "+2348000000000",
                "password1": PASSWORD, "password2": PASSWORD, **extra}
        self.client.post(reverse("accounts:register"), data)
        return User.objects.get(email="rider@example.com")

    def test_unverified_user_cannot_log_in(self):
        self.register()
        response = self.client.post(reverse("accounts:login"), {"username": "rider@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verify your email address")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_opening_the_link_does_not_verify_but_confirming_does(self):
        user = self.register()
        link = verification_link(mail.outbox[0])
        self.assertContains(self.client.get(link), "Verify email")
        user.refresh_from_db()
        self.assertFalse(user.email_verified)  # link scanners only GET
        response = self.client.post(link)
        self.assertRedirects(response, reverse("accounts:login"))
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        response = self.client.post(reverse("accounts:login"), {"username": "rider@example.com", "password": PASSWORD})
        self.assertIn("_auth_user_id", self.client.session)

    def test_tampered_or_unknown_token_is_rejected(self):
        response = self.client.get(reverse("accounts:verify_email", kwargs={"token": "not-a-real-token"}))
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "invalid or has expired", status_code=400)

    def test_verification_sent_page_is_not_mistaken_for_a_token(self):
        response = self.client.get(reverse("accounts:verification_sent"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Check your email")

    def test_resend_gives_the_same_answer_for_unknown_emails(self):
        self.register()
        mail.outbox.clear()
        for email in ("rider@example.com", "nobody@example.com"):
            with self.subTest(email=email):
                response = self.client.post(reverse("accounts:resend_verification"), {"email": email})
                self.assertRedirects(response, reverse("accounts:verification_sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["rider@example.com"])

    def test_resend_is_throttled(self):
        self.register()
        mail.outbox.clear()
        for _ in range(3):
            self.client.post(reverse("accounts:resend_verification"), {"email": "rider@example.com"})
        self.assertEqual(len(mail.outbox), 1)

    def test_superuser_is_verified_automatically(self):
        admin = User.objects.create_superuser(email="root@example.com", password=PASSWORD, full_name="Root")
        self.assertTrue(admin.email_verified)


class PasswordResetTests(TestCase):
    def test_reset_email_sent_for_existing_user(self):
        make_passenger()
        response = self.client.post(reverse("accounts:password_reset"), {"email": "pat@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)

    def test_reset_does_not_reveal_unknown_email(self):
        response = self.client.post(reverse("accounts:password_reset"), {"email": "nobody@example.com"})
        self.assertRedirects(response, reverse("accounts:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)


class RolePermissionTests(TestCase):
    admin_urls = ["dashboard:home", "transport:manage"]
    passenger_urls = ["bookings:dashboard"]
    login_urls = ["accounts:profile", "accounts:password_change"]

    def setUp(self):
        self.passenger = make_passenger()
        self.admin = make_admin()

    def test_anonymous_redirected_to_login(self):
        for name in self.admin_urls + self.passenger_urls + self.login_urls:
            with self.subTest(url=name):
                url = reverse(name)
                response = self.client.get(url)
                self.assertRedirects(response, f"{reverse('accounts:login')}?next={url}", fetch_redirect_response=False)

    def test_passenger_cannot_access_admin_pages(self):
        self.client.force_login(self.passenger)
        for name in self.admin_urls:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_passenger_cannot_access_django_admin(self):
        self.client.force_login(self.passenger)
        response = self.client.get("/django-admin/")
        self.assertEqual(response.status_code, 302)  # Django admin redirects non-staff to its login

    def test_admin_can_access_admin_pages(self):
        self.client.force_login(self.admin)
        for name in self.admin_urls:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_admin_cannot_use_passenger_pages(self):
        self.client.force_login(self.admin)
        for name in self.passenger_urls:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_passenger_can_access_passenger_pages(self):
        self.client.force_login(self.passenger)
        for name in self.passenger_urls + self.login_urls:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)

    def test_public_pages_open_to_everyone(self):
        # bookings:search (Book a Trip) needs a login - see config.tests.PopularRouteAccessTests
        for name in ["home", "accounts:login", "accounts:register"]:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
