"""python manage.py seed_demo – test accounts and sample trips for development and marking.

Creates (or updates) two test accounts and a week of trips on real Nigerian routes,
so the site can be tried straight after `migrate`:

    admin@high5.test       ADMIN      password = DEMO_ADMIN_PASSWORD in .env
    passenger@high5.test   PASSENGER  password = DEMO_PASSENGER_PASSWORD in .env

The passwords are never written in the code (project rule): each person sets
their own in .env. Running the command again is safe – it only adds what is
missing and resets the two test passwords to the .env values.
"""

import os
from datetime import time, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from transport.models import Bus, Route, Schedule

ACCOUNTS = (
    # email, full name, role, .env variable holding the password
    ("admin@high5.test", "Test Admin", "ADMIN", "DEMO_ADMIN_PASSWORD"),
    ("passenger@high5.test", "Test Passenger", "PASSENGER", "DEMO_PASSENGER_PASSWORD"),
)

# origin, destination, distance (km), duration, fare (₦), bus, departure times
ROUTES = (
    ("Lagos", "Abuja", 760, timedelta(hours=10), "25000.00", "H5-LAG-01", (time(6, 0),)),
    ("Lagos", "Ibadan", 130, timedelta(hours=2), "6000.00", "H5-LAG-02", (time(7, 0), time(12, 0), time(17, 0))),
    ("Lagos", "Benin City", 320, timedelta(hours=5, minutes=30), "14000.00", "H5-LAG-03", (time(6, 30),)),
    ("Abuja", "Kaduna", 190, timedelta(hours=3), "9000.00", "H5-ABJ-01", (time(8, 0), time(15, 0))),
    ("Port Harcourt", "Enugu", 250, timedelta(hours=4, minutes=30), "12000.00", "H5-PHC-01", (time(7, 30), time(14, 0))),
)

# registration, type, seats
BUSES = (
    ("H5-LAG-01", Bus.BusType.LUXURY, 30),
    ("H5-LAG-02", Bus.BusType.STANDARD, 44),
    ("H5-LAG-03", Bus.BusType.STANDARD, 44),
    ("H5-ABJ-01", Bus.BusType.STANDARD, 44),
    ("H5-PHC-01", Bus.BusType.SLEEPER, 30),
)


class Command(BaseCommand):
    help = "Create test accounts (passwords from .env) and a week of sample trips. Development only."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="How many days of trips to create (default 7).")

    def handle(self, *args, days, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo is for development only (DJANGO_DEBUG=True). It will not run in production.")

        passwords = {}
        for email, _name, _role, variable in ACCOUNTS:
            value = os.environ.get(variable, "")
            if not value:
                raise CommandError(f"Set {variable} in .env first (see .env.example).")
            try:
                validate_password(value)
            except ValidationError as error:
                raise CommandError(f"{variable} is too weak: {' '.join(error.messages)}")
            passwords[email] = value

        with transaction.atomic():
            self._accounts(passwords)
            created = self._trips(days)

        self.stdout.write(self.style.SUCCESS(f"Test accounts ready; {created} new trip(s) created."))
        for email, _name, role, variable in ACCOUNTS:
            self.stdout.write(f"  {role:<9} {email}  (password: {variable} in .env)")

    def _accounts(self, passwords):
        User = get_user_model()
        for email, name, role, _variable in ACCOUNTS:
            user, _ = User.objects.get_or_create(email=email, defaults={"full_name": name, "role": role})
            user.full_name, user.role = name, role
            user.is_active = user.email_verified = True
            user.set_password(passwords[email])  # hashed, never stored as plain text
            user.save()

    def _trips(self, days):
        buses = {}
        for plate, bus_type, seats in BUSES:
            buses[plate], _ = Bus.objects.get_or_create(
                name_or_plate=plate, defaults={"bus_type": bus_type, "total_seats": seats}
            )

        today = timezone.localdate()
        created = 0
        for origin, destination, km, duration, fare, plate, times in ROUTES:
            route, _ = Route.objects.get_or_create(
                origin=origin, destination=destination,
                defaults={"distance_km": km, "duration_estimate": duration},
            )
            for offset in range(days):
                for departs in times:
                    _, new = Schedule.objects.get_or_create(
                        bus=buses[plate], departure_date=today + timedelta(days=offset), departure_time=departs,
                        defaults={"route": route, "fare": Decimal(fare)},
                    )
                    created += new
        return created
