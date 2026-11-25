import re
import smtplib
from datetime import timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import EmailVerificationCode

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

    def test_register_creates_unverified_passenger_and_sends_code(self):
        response = self.client.post(self.url, self.form_data())
        self.assertRedirects(response, reverse("accounts:verify_email"))
        user = User.objects.get(email="rider@example.com")
        self.assertEqual(user.role, User.Role.PASSENGER)
        self.assertFalse(user.email_verified)
        self.assertNotIn("_auth_user_id", self.client.session)  # not logged in until verified
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["rider@example.com"])
        self.assertRegex(mail.outbox[0].body, r"\b\d{6}\b")

    # The next two tests come from Cross's feature/email-validation-verification branch.
    def test_invalid_email_syntax_is_rejected(self):
        for email in ("not-an-email", "missing-domain@", "@example.com"):
            with self.subTest(email=email):
                response = self.client.post(self.url, self.form_data(email=email))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(User.objects.exists())

    def test_email_is_trimmed_and_case_normalized(self):
        self.client.post(self.url, self.form_data(email="  Rider@Example.COM  "))
        self.assertTrue(User.objects.filter(email="rider@example.com").exists())
        self.assertEqual(User.objects.create_user(email="  Bo@Example.com ", password=PASSWORD,
                                                  full_name="Bo").email, "bo@example.com")

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


def emailed_code(message):
    """The 6-digit code from a verification email."""
    return re.search(r"\b(\d{6})\b", message.body).group(1)


class EmailVerificationTests(TestCase):
    def setUp(self):
        cache.clear()  # the resend throttle uses the cache

    def register(self, **extra):
        data = {"full_name": "New Rider", "email": "rider@example.com", "phone": "+2348000000000",
                "password1": PASSWORD, "password2": PASSWORD, **extra}
        self.client.post(reverse("accounts:register"), data)
        return User.objects.get(email="rider@example.com")

    def enter_code(self, code, email="rider@example.com"):
        return self.client.post(reverse("accounts:verify_email"), {"email": email, "code": code})

    def wrong(self, code):
        """A 6-digit code that is not `code`."""
        return f"{(int(code) + 1) % 1_000_000:06d}"

    def test_unverified_user_cannot_log_in(self):
        self.register()
        response = self.client.post(reverse("accounts:login"), {"username": "rider@example.com", "password": PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verify your email address")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_code_page_is_prefilled_after_sign_up(self):
        self.register()
        response = self.client.get(reverse("accounts:verify_email"))
        self.assertContains(response, 'value="rider@example.com"')
        self.assertContains(response, 'autocomplete="one-time-code"')

    def test_correct_code_verifies_and_allows_login(self):
        user = self.register()
        response = self.enter_code(emailed_code(mail.outbox[0]))
        self.assertRedirects(response, reverse("accounts:login"))
        user.refresh_from_db()
        self.assertTrue(user.email_verified)
        self.assertFalse(EmailVerificationCode.objects.exists())  # a used code is deleted
        self.client.post(reverse("accounts:login"), {"username": "rider@example.com", "password": PASSWORD})
        self.assertIn("_auth_user_id", self.client.session)

    def test_code_is_stored_only_as_a_hash(self):
        user = self.register()
        code = emailed_code(mail.outbox[0])
        self.assertNotIn(code, user.verification_code.code_hash)

    def test_wrong_code_is_rejected(self):
        user = self.register()
        response = self.enter_code(self.wrong(emailed_code(mail.outbox[0])))
        self.assertContains(response, "wrong or has expired")
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_code_stops_working_after_five_wrong_tries(self):
        user = self.register()
        code = emailed_code(mail.outbox[0])
        for _ in range(5):
            self.enter_code(self.wrong(code))
        self.assertContains(self.enter_code(code), "wrong or has expired")
        user.refresh_from_db()
        self.assertFalse(user.email_verified)

    def test_expired_code_is_rejected(self):
        user = self.register()
        user.verification_code.expires_at = timezone.now() - timedelta(seconds=1)
        user.verification_code.save()
        self.assertContains(self.enter_code(emailed_code(mail.outbox[0])), "wrong or has expired")

    def test_code_only_works_for_its_own_account(self):
        self.register()
        User.objects.create_user(email="other@example.com", password=PASSWORD, full_name="Other")
        response = self.enter_code(emailed_code(mail.outbox[0]), email="other@example.com")
        self.assertContains(response, "wrong or has expired")

    def test_code_must_be_six_digits(self):
        self.register()
        self.assertContains(self.enter_code("12ab56"), "Enter the 6 digits")

    def test_new_code_replaces_the_old_one(self):
        user = self.register()
        old = emailed_code(mail.outbox[0])
        self.client.post(reverse("accounts:resend_verification"), {"email": "rider@example.com"})
        new = emailed_code(mail.outbox[-1])
        if new != old:  # 1 in a million they match
            self.assertContains(self.enter_code(old), "wrong or has expired")
        self.assertRedirects(self.enter_code(new), reverse("accounts:login"))
        user.refresh_from_db()
        self.assertTrue(user.email_verified)

    def test_resend_gives_the_same_answer_for_unknown_emails(self):
        self.register()
        mail.outbox.clear()
        for email in ("rider@example.com", "nobody@example.com"):
            with self.subTest(email=email):
                response = self.client.post(reverse("accounts:resend_verification"), {"email": email})
                self.assertRedirects(response, reverse("accounts:verify_email"))
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

    def test_sign_up_survives_a_mail_server_failure(self):
        # e.g. wrong Gmail app password or no internet: no 500 page, account kept.
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=smtplib.SMTPException("down")), \
                self.assertLogs("accounts.services", level="ERROR"):
            response = self.client.post(reverse("accounts:register"), {
                "full_name": "New Rider", "email": "rider@example.com", "phone": "+2348000000000",
                "password1": PASSWORD, "password2": PASSWORD,
            }, follow=True)
        self.assertRedirects(response, reverse("accounts:verify_email"))
        self.assertContains(response, "could not send the code email")
        self.assertFalse(User.objects.get(email="rider@example.com").email_verified)

    def test_resend_survives_a_mail_server_failure(self):
        self.register()
        cache.clear()
        with mock.patch("django.core.mail.EmailMultiAlternatives.send", side_effect=OSError("no network")), \
                self.assertLogs("accounts.services", level="ERROR"):
            response = self.client.post(reverse("accounts:resend_verification"), {"email": "rider@example.com"})
        self.assertRedirects(response, reverse("accounts:verify_email"))


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
