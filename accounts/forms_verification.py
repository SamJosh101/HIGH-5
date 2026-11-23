from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError


class EmailAuthenticationForm(AuthenticationForm):
    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not getattr(user, "email_verified", False) and not user.is_superuser:
            raise ValidationError(
                "Verify your email address before signing in. "
                "Check your inbox or request a new verification email.",
                code="email_not_verified",
            )
