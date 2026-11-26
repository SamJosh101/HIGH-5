from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError

from .email_verification import CODE_LENGTH
from .models import User


class BootstrapFormMixin:
    """Adds Bootstrap 5 CSS classes to every widget, so templates can render
    any form with templates/partials/form_fields.html. Teammates: use this
    on your forms too:  class RouteForm(BootstrapFormMixin, forms.ModelForm)"""

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
        # Keep pages short: replace Django's long password rules list with one line.
        # The validators still run and explain any problem after submitting.
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
        # Highlight invalid fields in red (Bootstrap's .is-invalid).
        for name in self.errors:
            if name in self.fields:
                widget = self.fields[name].widget
                widget.attrs["class"] = f"{widget.attrs.get('class', '')} is-invalid".strip()


class PassengerRegistrationForm(BootstrapFormMixin, UserCreationForm):
    """Public sign-up form. It can ONLY create PASSENGER accounts: the role
    field is not exposed, so nobody can register themselves as ADMIN."""

    class Meta:
        model = User
        fields = ("full_name", "email", "phone")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PASSENGER
        user.is_staff = False
        user.is_superuser = False
        user.email_verified = False  # becomes True when the emailed code is entered
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    # Django's login form calls this field "username"; for us it holds the email.
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))

    def confirm_login_allowed(self, user):
        """Runs after the password is checked: inactive and unverified accounts may not log in."""
        super().confirm_login_allowed(user)
        if not user.email_verified:
            raise ValidationError(
                "Verify your email address before signing in: "
                "enter the 6-digit code we emailed you, or request a new code.",
                code="email_not_verified",
            )


class VerifyEmailCodeForm(BootstrapFormMixin, forms.Form):
    """Only the 6-digit code. The email address comes from the session
    (set at sign-up, or at log in with the right password), never from the user."""

    code = forms.CharField(
        label="Verification code", max_length=CODE_LENGTH,
        widget=forms.TextInput(attrs={
            "inputmode": "numeric", "autocomplete": "one-time-code", "placeholder": "000000",
            "maxlength": CODE_LENGTH, "pattern": f"[0-9]{{{CODE_LENGTH}}}", "autofocus": True,
            "class": "h5-code-input",
        }),
        error_messages={"max_length": f"The code has exactly {CODE_LENGTH} digits."},
    )

    def clean_code(self):
        code = self.cleaned_data["code"].strip()
        if not (code.isdigit() and len(code) == CODE_LENGTH):
            raise ValidationError(f"Enter the {CODE_LENGTH} digits from the email.")
        return code


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "phone")


# Django's password forms with the same styling, used by the password views.
class StyledPasswordResetForm(BootstrapFormMixin, PasswordResetForm):
    pass


class StyledSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    pass


class StyledPasswordChangeForm(BootstrapFormMixin, PasswordChangeForm):
    pass
