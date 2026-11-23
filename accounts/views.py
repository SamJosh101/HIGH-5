from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .email_verification import verify_email_verification_token
from .forms import (
    EmailAuthenticationForm,
    EmailVerificationResendForm,
    PassengerRegistrationForm,
    ProfileForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)
from .services import send_email_verification

User = get_user_model()


def _safe_next(request):
    """The ?next= page to return to, only if it is on this site (no open redirects)."""
    target = request.POST.get(REDIRECT_FIELD_NAME) or request.GET.get(REDIRECT_FIELD_NAME, "")
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return target
    return ""


def _login_url(next_url=""):
    """The login page, keeping a safe ?next= so the user returns where they started."""
    url = reverse("accounts:login")
    return f"{url}?{urlencode({REDIRECT_FIELD_NAME: next_url})}" if next_url else url


@require_http_methods(["GET", "POST"])
def register(request):
    next_url = _safe_next(request)
    if request.user.is_authenticated:
        return redirect(next_url or "accounts:after_login")
    form = PassengerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # Not logged in yet: the user must first prove they own the email address.
        # The link carries `next`, so after verifying and logging in they land on
        # the page they started from (for example a Popular Route search).
        send_email_verification(request, user, next_url)
        messages.success(request, "Account created. Check your inbox for a link to verify your email address.")
        return redirect("accounts:verification_sent")
    return render(request, "accounts/register.html", {"form": form, "next": next_url})


@require_http_methods(["GET", "POST"])
def verify_email(request, token):
    """GET shows a confirm button; only the POST verifies. (Email scanners and link
    previews open links automatically; they must not verify accounts by accident.)"""
    try:
        payload = verify_email_verification_token(token)
        user = User.objects.get(pk=payload["user_id"], email=payload["email"])
    except (signing.BadSignature, KeyError, TypeError, ValueError, User.DoesNotExist):
        # SignatureExpired is a kind of BadSignature, so expired links land here too.
        return render(request, "accounts/email_verification_invalid.html", status=400)

    next_url = _safe_next(request)
    if request.method == "POST":
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        messages.success(request, "Your email is verified. You can now log in.")
        return redirect(_login_url(next_url))
    if user.email_verified:
        return redirect(_login_url(next_url))
    return render(request, "accounts/email_verification_confirm.html")


@require_http_methods(["GET", "POST"])
def resend_verification(request):
    form = EmailVerificationResendForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        # Same answer whether or not the account exists (like password reset), and
        # at most one email per address and IP address per minute.
        throttle_key = f"email-verification:{request.META.get('REMOTE_ADDR', '')}:{email}"
        if cache.add(throttle_key, True, timeout=60):
            user = User.objects.filter(email__iexact=email, email_verified=False, is_active=True).first()
            if user:
                send_email_verification(request, user)
        return redirect("accounts:verification_sent")
    return render(request, "accounts/resend_verification.html", {"form": form})


def verification_sent(request):
    return render(request, "accounts/email_verification_sent.html")


class HighFiveLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


@login_required
def after_login(request):
    """Send each role to its own landing page."""
    if request.user.is_admin_role:
        return redirect("dashboard:home")
    return redirect("bookings:dashboard")


@login_required
@require_http_methods(["GET", "POST"])
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


# Password reset/change use Django's secure built-in views
# (signed, single-use, expiring tokens).
password_reset = auth_views.PasswordResetView.as_view(
    template_name="accounts/password_reset_form.html",
    form_class=StyledPasswordResetForm,
    email_template_name="accounts/emails/password_reset_email.txt",
    subject_template_name="accounts/emails/password_reset_subject.txt",
    success_url=reverse_lazy("accounts:password_reset_done"),
)
password_reset_done = auth_views.PasswordResetDoneView.as_view(
    template_name="accounts/password_reset_done.html",
)
password_reset_confirm = auth_views.PasswordResetConfirmView.as_view(
    template_name="accounts/password_reset_confirm.html",
    form_class=StyledSetPasswordForm,
    success_url=reverse_lazy("accounts:password_reset_complete"),
)
password_reset_complete = auth_views.PasswordResetCompleteView.as_view(
    template_name="accounts/password_reset_complete.html",
)
password_change = auth_views.PasswordChangeView.as_view(
    template_name="accounts/password_change.html",
    form_class=StyledPasswordChangeForm,
    success_url=reverse_lazy("accounts:profile"),
)
