from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError

from .models import User


class BootstrapFormMixin:
    """Apply Bootstrap classes to fields and highlight validation errors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple)):
                css = "form-check-input"
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()
        for name, field in self.fields.items():
            if name in ("password1", "new_password1"):
                field.help_text = "At least 8 characters."
            elif "password" in name:
                field.help_text = ""
            if name in ("password2", "new_password2"):
                field.label = "Confirm password"
            if name == "email":
                field.label = "Email"

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class PassengerRegistrationForm(BootstrapFormMixin, UserCreationForm):
    """Public sign-up can create passenger accounts only."""

    class Meta:
        model = User
        fields = ("full_name", "email", "phone")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PASSENGER
        user.is_staff = False
        user.is_superuser = False
        user.email_verified = False
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.email_verified:
            raise ValidationError(
                "Verify your email address before signing in. Check your inbox or request a new verification email.",
                code="email_not_verified",
            )


class EmailVerificationResendForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(label="Email", max_length=254)


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "phone")


class StyledPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass
