from django.core import signing


EMAIL_VERIFICATION_SALT = "accounts.email-verification"
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24


def make_email_verification_token(user):
    """Create a signed, expiring token bound to this user's current email."""
    return signing.dumps({"user_id": user.pk, "email": user.email}, salt=EMAIL_VERIFICATION_SALT)


def verify_email_verification_token(token):
    """Validate token signature and its 24-hour age limit."""
    return signing.loads(token, salt=EMAIL_VERIFICATION_SALT, max_age=EMAIL_VERIFICATION_MAX_AGE)
