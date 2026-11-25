from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth import REDIRECT_FIELD_NAME, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .email_verification import check_code
from .forms import (
    EmailAuthenticationForm,
    EmailVerificationResendForm,
    PassengerRegistrationForm,
    ProfileForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
    VerifyEmailCodeForm,
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


VERIFY_EMAIL_KEY = "verify_email"  # session: the address waiting for its code
VERIFY_NEXT_KEY = "verify_next"    # session: the safe page to return to afterwards


def _remember_for_verification(request, email, next_url=None):
    """Prefill the code page with this address (kept in the session, never in the URL)."""
    request.session[VERIFY_EMAIL_KEY] = email
    if next_url is not None:
        request.session[VERIFY_NEXT_KEY] = next_url


@require_http_methods(["GET", "POST"])
def register(request):
    next_url = _safe_next(request)
    if request.user.is_authenticated:
        return redirect(next_url or "accounts:after_login")
    form = PassengerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        # Not logged in yet: the user must first prove they own the email address
        # by typing the code we send. `next` is kept in the session, so after
        # verifying and logging in they land on the page they started from.
        sent = send_email_verification(user)
        _remember_for_verification(request, user.email, next_url)
        if sent:
            messages.success(request, f"Account created. We sent a 6-digit code to {user.email}.")
        else:
            messages.warning(request, "Account created, but we could not send the code email right now. "
                                      "Please use \"Send a new code\" in a minute.")
        return redirect("accounts:verify_email")
    return render(request, "accounts/register.html", {"form": form, "next": next_url})


@require_http_methods(["GET", "POST"])
def verify_email(request):
    """Enter the 6-digit code from the verification email."""
    form = VerifyEmailCodeForm(request.POST or None, initial={"email": request.session.get(VERIFY_EMAIL_KEY, "")})
    if request.method == "POST" and form.is_valid():
        user = User.objects.filter(email=form.cleaned_data["email"], email_verified=False, is_active=True).first()
        if user and check_code(user, form.cleaned_data["code"]):
            user.email_verified = True
            user.save(update_fields=["email_verified"])
            request.session.pop(VERIFY_EMAIL_KEY, None)
            next_url = request.session.pop(VERIFY_NEXT_KEY, "")
            messages.success(request, "Your email is verified. You can now log in.")
            return redirect(_login_url(next_url))
        # One message for every failure (wrong, expired, used up, unknown or already
        # verified address), so the page never reveals which accounts exist.
        form.add_error("code", "That code is wrong or has expired. Check the latest email or send a new code.")
    return render(request, "accounts/verify_email.html", {"form": form})


@require_http_methods(["GET", "POST"])
def resend_verification(request):
    form = EmailVerificationResendForm(request.POST or None, initial={"email": request.session.get(VERIFY_EMAIL_KEY, "")})
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]  # trimmed and lowercased by the form
        # Same answer whether or not the account exists (like password reset), and
        # at most one code per address and IP address per minute.
        throttle_key = f"email-verification:{request.META.get('REMOTE_ADDR', '')}:{email}"
        if cache.add(throttle_key, True, timeout=60):
            user = User.objects.filter(email__iexact=email, email_verified=False, is_active=True).first()
            if user:
                send_email_verification(user)
        _remember_for_verification(request, email)
        messages.info(request, "If that address has an account waiting for verification, a new code is on its way. "
                               "You can ask for another one after a minute.")
        return redirect("accounts:verify_email")
    return render(request, "accounts/resend_verification.html", {"form": form})


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
