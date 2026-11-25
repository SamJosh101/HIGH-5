
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from bookings.models import Booking
from transport.models import Schedule


class Command(BaseCommand):
    help = "Automatically complete bookings after their scheduled trips arrive."

    def handle(self, *args, **options):
        now = timezone.now()

        eligible_schedule_ids = Schedule.objects.filter(
            status__in=[
                Schedule.Status.SCHEDULED,
                Schedule.Status.COMPLETED,
            ],
            departure_date__lte=timezone.localdate(),
        ).values_list("id", flat=True)

        completed_count = 0

        with transaction.atomic():
            bookings = (
                Booking.objects.select_for_update()
                .filter(
                    schedule_id__in=eligible_schedule_ids,
                    status=Booking.Status.CONFIRMED,
                )
                .select_related("schedule", "schedule__route")
            )

            for booking in bookings:
                if booking.schedule.arrival_datetime <= now:
                    booking.status = Booking.Status.COMPLETED
                    booking.save(update_fields=["status"])
                    completed_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully completed {completed_count} booking(s)."
            )
        )
