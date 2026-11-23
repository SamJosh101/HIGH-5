from django.core import signing
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from .email_verification import make_email_verification_token


def send_email_verification(request, user):
    token = make_email_verification_token(user)
    verification_path = reverse("accounts:verify_email", kwargs={"token": token})
    context = {
        "user": user,
        "verification_url": request.build_absolute_uri(verification_path),
    }
    subject = render_to_string("accounts/emails/email_verification_subject.txt").strip()
    text_body = render_to_string("accounts/emails/email_verification_email.txt", context)
    html_body = render_to_string("accounts/emails/email_verification_email.html", context)

    message = EmailMultiAlternatives(subject, text_body, None, [user.email])
    message.attach_alternative(html_body, "text/html")
    message.send()
