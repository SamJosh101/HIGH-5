from django.contrib.auth import get_user_model
from django.core import mail
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

User = get_user_model()
PASSWORD = "Str0ng-Test-Pass!"


def make_passenger(email="pat@example.com", **kw):
    return User.objects.create_user(email=email, password=PASSWORD, full_name="Pat Passenger", **kw)


def make_admin(email="ada@example.com"):
    return User.objects.create_user(email=email, password=PASSWORD, full_name="Ada Admin", role=User.Role.ADMIN)


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

    def test_register_creates_passenger_and_logs_in(self):
        response = self.client.post(self.url, self.form_data())
        self.assertRedirects(response, reverse("accounts:after_login"), fetch_redirect_response=False)
        user = User.objects.get(email="rider@example.com")
        self.assertEqual(user.role, User.Role.PASSENGER)
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

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
        for name in ["home", "bookings:search", "accounts:login", "accounts:register"]:
            with self.subTest(url=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
