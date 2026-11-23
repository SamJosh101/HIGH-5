from urllib.parse import urlencode

from django.contrib.auth import REDIRECT_FIELD_NAME
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .email_verification import make_email_verification_token


def send_email_verification(request, user, next_url=""):
    """Email the user a signed link that verifies their address.

    `next_url` must already be checked as safe (accounts.views._safe_next). It is
    added to the link so that, after verifying and logging in, the user returns to
    the page they started from.
    """
    token = make_email_verification_token(user)
    verification_path = reverse("accounts:verify_email", kwargs={"token": token})
    if next_url:
        verification_path += "?" + urlencode({REDIRECT_FIELD_NAME: next_url})
    context = {"user": user, "verification_url": request.build_absolute_uri(verification_path)}
    subject = render_to_string("accounts/emails/email_verification_subject.txt").strip()
    text_body = render_to_string("accounts/emails/email_verification_email.txt", context)
    html_body = render_to_string("accounts/emails/email_verification_email.html", context)
    message = EmailMultiAlternatives(subject, text_body, None, [user.email])
    message.attach_alternative(html_body, "text/html")
    message.send()
