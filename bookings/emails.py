"""Booking emails: the ticket after booking, and the notice when HIGH 5
cancels a trip.

Both go to the account that booked and to every traveller on the booking who
gave an email (each address once). Sending never breaks the page: a failure
(wrong SMTP settings, no internet, Gmail refusing the login) is logged and the
caller is told nothing was sent, so it can say so.
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.urls import reverse

from .models import Booking
from .tickets import ticket_facts

logger = logging.getLogger(__name__)


def _recipients(booking, travellers):
    """[(email, full name, is_booker)], the booker first, no address twice."""
    seen = {}
    account = booking.passenger
    if account.email:
        seen[account.email.lower()] = (account.email, account.full_name, True)
    for traveller in travellers:
        if traveller.email and traveller.email.lower() not in seen:
            seen[traveller.email.lower()] = (traveller.email, traveller.full_name, False)
    return list(seen.values())


def _first_name(full_name):
    parts = (full_name or "").split()
    return parts[0] if parts else "there"


def _send_all(messages, what):
    """Send the messages over one connection. Returns the addresses on success, [] on failure."""
    if not messages:
        return []
    try:
        get_connection().send_messages(messages)
    except Exception:  # smtplib errors, socket errors, timeouts
        # Log the booking reference only, never addresses or SMTP details.
        logger.exception("Failed to send the %s email", what)
        return []
    return [address for message in messages for address in message.to]


def _message(subject, template, context, address):
    text_body = render_to_string(f"bookings/emails/{template}.txt", context)
    html_body = render_to_string(f"bookings/emails/{template}.html", context)
    message = EmailMultiAlternatives(subject, text_body, None, [address])
    message.attach_alternative(html_body, "text/html")
    return message


def send_ticket_email(booking, base_url, only_booker=False):
    """Email the full ticket. `base_url` is the site address, e.g.
    request.build_absolute_uri("/"), for the "View your ticket" link.
    Returns the list of addresses it was sent to ([] if sending failed)."""
    facts = ticket_facts(booking)
    route = facts["route"]
    subject = (
        f"Your HIGH 5 ticket {booking.booking_ref} · {route.origin} → "
        f"{route.destination}, {facts['departure']:%a} {facts['departure'].day} {facts['departure']:%b}"
    )
    ticket_url = base_url.rstrip("/") + reverse("bookings:ticket-detail", args=[booking.booking_ref])

    messages = []
    for address, name, is_booker in _recipients(booking, facts["travellers"]):
        if only_booker and not is_booker:
            continue
        context = {
            **facts,
            "first_name": _first_name(name),
            "is_booker": is_booker,
            "booker_name": booking.passenger.full_name,
            "ticket_url": ticket_url,
        }
        messages.append(_message(subject, "ticket", context, address))
    return _send_all(messages, f"ticket ({booking.booking_ref})")


def send_trip_cancelled_emails(booking_ids, base_url):
    """Tell everyone on these (now cancelled) bookings that HIGH 5 cancelled
    the trip, with the refund line. Returns how many emails were sent."""
    bookings = (
        Booking.objects.filter(pk__in=list(booking_ids))
        .select_related("schedule", "schedule__route", "schedule__bus", "passenger")
        .prefetch_related("passengers")
    )
    search_url = base_url.rstrip("/") + reverse("bookings:search")
    messages = []
    for booking in bookings:
        facts = ticket_facts(booking)
        route = facts["route"]
        subject = (
            f"Trip cancelled: {route.origin} → {route.destination}, "
            f"{facts['departure']:%a} {facts['departure'].day} {facts['departure']:%b} ({booking.booking_ref})"
        )
        for address, name, is_booker in _recipients(booking, facts["travellers"]):
            context = {
                **facts,
                "first_name": _first_name(name),
                "is_booker": is_booker,
                "booker_name": booking.passenger.full_name,
                "search_url": search_url,
            }
            messages.append(_message(subject, "trip_cancelled", context, address))
    return len(_send_all(messages, "trip cancelled"))
