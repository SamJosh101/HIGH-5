
import secrets
import string

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import phone_validator


def generate_booking_reference():
    """Generate a random HIGH 5 booking reference."""
    characters = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(characters) for _ in range(9))
    return f"H5-{code}"


class Booking(models.Model):

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmed"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    class PaymentStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PAID = "PAID", "Paid"
        REFUNDED = "REFUNDED", "Refunded"

    booking_ref = models.CharField(
        max_length=12,
        unique=True,
        editable=False
    )

    passenger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="bookings"
    )

    schedule = models.ForeignKey(
        "transport.Schedule",
        on_delete=models.PROTECT,
        related_name="bookings"
    )

    seats_booked = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)]
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.CONFIRMED
    )

    payment_status = models.CharField(
        max_length=10,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING
    )

    booked_at = models.DateTimeField(auto_now_add=True)

    cancelled_at = models.DateTimeField(
        null=True,
        blank=True
    )

    # When the payment was confirmed. Revenue is counted on this date, not on
    # the booking date (a booking made in November can be paid in December).
    paid_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        ordering = ["-booked_at"]
        indexes = [
            models.Index(fields=["schedule", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.booking_ref:
            while True:
                reference = generate_booking_reference()

                if not Booking.objects.filter(
                    booking_ref=reference
                ).exists():
                    self.booking_ref = reference
                    break

        # Record the payment date the first time a booking becomes Paid,
        # whichever page or tool set it (dashboard button, Django admin, ...).
        if self.payment_status == self.PaymentStatus.PAID and self.paid_at is None:
            self.paid_at = timezone.now()
            update_fields = kwargs.get("update_fields")
            if update_fields is not None:
                kwargs["update_fields"] = set(update_fields) | {"paid_at"}

        super().save(*args, **kwargs)

    @property
    def seat_list(self):
        """The booked seats in reading order, e.g. "4A, 4B" ("" if none were assigned)."""
        from .seats import sort_key

        codes = [p.seat_number for p in self.passengers.all() if p.seat_number]
        return ", ".join(sorted(codes, key=sort_key))

    def __str__(self):
        return self.booking_ref


class PassengerDetail(models.Model):

    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="passengers"
    )

    full_name = models.CharField(max_length=150)

    phone = models.CharField(
        max_length=16,
        validators=[phone_validator]
    )

    email = models.EmailField(blank=True)

    seat_number = models.CharField(
        max_length=4,
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.full_name} - {self.booking.booking_ref}"
