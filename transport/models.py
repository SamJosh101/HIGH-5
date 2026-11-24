# Transport models – owner: Daniel.
from datetime import datetime

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class Route(models.Model):
    origin = models.CharField(max_length=100, db_index=True)
    destination = models.CharField(max_length=100, db_index=True)
    distance_km = models.PositiveIntegerField(
        "distance (km)",
        validators=[MinValueValidator(1)],
    )
    duration_estimate = models.DurationField()
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["origin", "destination"]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(origin=models.F("destination")),
                name="transport_route_origin_destination_differ",
            ),
            models.UniqueConstraint(
                fields=["origin", "destination"],
                name="transport_unique_origin_destination",
            ),
        ]

    def clean(self):
        super().clean()
        if self.origin.strip().lower() == self.destination.strip().lower():
            raise ValidationError({"destination": "Destination must differ from departure."})

    def save(self, *args, **kwargs):
        self.origin = self.origin.strip()
        self.destination = self.destination.strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.origin} → {self.destination}"


class Bus(models.Model):
    class BusType(models.TextChoices):
        # The SRS examples (FR-12), as agreed in docs/DATABASE.md.
        STANDARD = "STANDARD", "Standard"
        LUXURY = "LUXURY", "Luxury"
        SLEEPER = "SLEEPER", "Sleeper"

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ASSIGNED = "ASSIGNED", "Assigned"
        MAINTENANCE = "MAINTENANCE", "Maintenance"
        UNAVAILABLE = "UNAVAILABLE", "Unavailable"

    name_or_plate = models.CharField("registration number", max_length=50, unique=True)
    bus_type = models.CharField(max_length=20, choices=BusType.choices)
    total_seats = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1)],
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.AVAILABLE)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name_or_plate"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_seats__gt=0),
                name="transport_bus_seats_positive",
            )
        ]

    def clean(self):
        super().clean()
        if self.name_or_plate:
            self.name_or_plate = self.name_or_plate.strip().upper()

    def save(self, *args, **kwargs):
        self.name_or_plate = self.name_or_plate.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name_or_plate} ({self.total_seats} seats)"


class Schedule(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        CANCELLED = "CANCELLED", "Cancelled"
        COMPLETED = "COMPLETED", "Completed"

    route = models.ForeignKey(Route, on_delete=models.PROTECT, related_name="schedules")
    bus = models.ForeignKey(Bus, on_delete=models.PROTECT, related_name="schedules")
    departure_date = models.DateField(db_index=True)
    departure_time = models.TimeField()
    # No arrival field: arrival = departure + route.duration_estimate (docs/DATABASE.md),
    # so a schedule can never disagree with its route about how long the trip takes.
    fare = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )

    class Meta:
        ordering = ["departure_date", "departure_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["bus", "departure_date", "departure_time"],
                name="transport_unique_bus_departure",
            ),
            models.CheckConstraint(
                condition=models.Q(fare__gte=0),
                name="transport_schedule_fare_nonnegative",
            ),
        ]
        indexes = [
            models.Index(fields=["departure_date", "status"], name="transport_schedule_date_status"),
        ]

    @property
    def departure_datetime(self):
        naive = datetime.combine(self.departure_date, self.departure_time)
        return timezone.make_aware(naive, timezone.get_current_timezone())

    @property
    def arrival_datetime(self):
        return self.departure_datetime + self.route.duration_estimate

    @property
    def arrival_time(self):
        """Estimated arrival time of day (shown in lists and the admin)."""
        return self.arrival_datetime.time()

    def clean(self):
        super().clean()
        if not self.route_id:
            raise ValidationError({"route": "Select a route."})
        if not self.bus_id:
            raise ValidationError({"bus": "Select a bus."})
        if not self.route.is_active:
            raise ValidationError({"route": "Route must be active."})
        if not self.bus.is_active:
            raise ValidationError({"bus": "Bus must be active."})
        if self.departure_datetime < timezone.now():
            raise ValidationError({"departure_date": "Departure cannot be in the past."})

        departure = self.departure_datetime
        arrival = self.arrival_datetime
        conflicts = Schedule.objects.filter(
            bus=self.bus,
            status=Schedule.Status.SCHEDULED,
        ).exclude(pk=self.pk)
        for schedule in conflicts:
            if schedule.departure_datetime < arrival and departure < schedule.arrival_datetime:
                raise ValidationError({"bus": "Bus has an overlapping schedule."})
