from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

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
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PASSENGER
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(BootstrapFormMixin, AuthenticationForm):
    # Django's login form calls this field "username"; for us it holds the email.
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))


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
