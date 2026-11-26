
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from transport.models import Bus, Schedule


class Command(BaseCommand):
    help = (
        "Automatically complete bookings after their scheduled trips arrive, "
        "and mark those trips (schedules) Completed."
    )

    def handle(self, *args, **options):
        now = timezone.now()

        eligible_schedules = Schedule.objects.filter(
            status__in=[
                Schedule.Status.SCHEDULED,
                Schedule.Status.COMPLETED,
            ],
            departure_date__lte=timezone.localdate(),
        ).select_related("route", "bus")

        completed_count = 0
        trips_closed = 0

        with transaction.atomic():
            # Arrival = departure + route duration, worked out in Python
            # (MySQL here has no time-zone tables for date maths in SQL).
            arrived = [s for s in eligible_schedules if s.arrival_datetime <= now]
            arrived_ids = [s.pk for s in arrived]

            bookings = Booking.objects.select_for_update().filter(
                schedule_id__in=arrived_ids,
                status=Booking.Status.CONFIRMED,
            )
            completed_count = bookings.update(status=Booking.Status.COMPLETED)

            for schedule in arrived:
                if schedule.status != Schedule.Status.SCHEDULED:
                    continue
                schedule.status = Schedule.Status.COMPLETED
                schedule.save(update_fields=["status"])
                trips_closed += 1
                bus = schedule.bus
                still_busy = bus.schedules.filter(status=Schedule.Status.SCHEDULED).exists()
                if not still_busy and bus.status == Bus.Status.ASSIGNED:
                    bus.status = Bus.Status.AVAILABLE
                    bus.save(update_fields=["status"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed {completed_count} booking(s) "
                f"and {trips_closed} trip(s)."
            )
        )
