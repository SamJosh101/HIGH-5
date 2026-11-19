from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods

from .forms import (
    EmailAuthenticationForm,
    PassengerRegistrationForm,
    ProfileForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:after_login")
    form = PassengerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Welcome to HIGH 5! Your account has been created.")
        return redirect("accounts:after_login")
    return render(request, "accounts/register.html", {"form": form})


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
