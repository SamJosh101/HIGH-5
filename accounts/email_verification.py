"""Email verification with a one-time 6-digit code (OTP).

A new passenger is emailed a code and types it on the "Verify your email"
page. Rules:
* the code is random (`secrets`), 6 digits, and only its hash is stored;
* it expires after CODE_VALID_MINUTES;
* after MAX_ATTEMPTS wrong tries it stops working and a new code is needed
  (new codes are limited to one a minute in accounts.views.resend_verification),
  so guessing 1 in 1,000,000 by trial is not practical;
* a new code replaces the old one, and a used code is deleted.
"""

import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone

from .models import EmailVerificationCode

CODE_LENGTH = 6
CODE_VALID_MINUTES = 10
MAX_ATTEMPTS = 5


def issue_code(user):
    """Create (or replace) the user's code and return it as text, e.g. "042917"."""
    code = f"{secrets.randbelow(10 ** CODE_LENGTH):0{CODE_LENGTH}d}"
    EmailVerificationCode.objects.update_or_create(
        user=user,
        defaults={
            "code_hash": make_password(code),
            "expires_at": timezone.now() + timedelta(minutes=CODE_VALID_MINUTES),
            "attempts": 0,
        },
    )
    return code


def has_live_code(user):
    """True if the user has a code that can still be used (not expired, tries left)."""
    return EmailVerificationCode.objects.filter(
        user=user, expires_at__gt=timezone.now(), attempts__lt=MAX_ATTEMPTS).exists()


def check_code(user, code):
    """True if `code` is the user's live code. A correct code is used up; a wrong
    one counts as an attempt. Expired or used-up codes never match."""
    record = EmailVerificationCode.objects.filter(user=user).first()
    if record is None or record.expires_at <= timezone.now() or record.attempts >= MAX_ATTEMPTS:
        return False
    if check_password(code, record.code_hash):
        record.delete()
        return True
    record.attempts += 1
    record.save(update_fields=["attempts"])
    return False
