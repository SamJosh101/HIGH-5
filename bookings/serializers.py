
from django.apps import apps
from django.utils import timezone

from rest_framework import serializers

from accounts.models import phone_validator
from .models import Booking, PassengerDetail
from .services import create_booking


class PassengerDetailInputSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)

    phone = serializers.CharField(
        max_length=16,
        validators=[phone_validator]
    )

    email = serializers.EmailField(
        required=False,
        allow_blank=True
    )

    # Seat code from the seat map, e.g. "4A". Optional: without seats the
    # server gives out the first free ones (bookings.services._choose_seats).
    seat = serializers.CharField(
        max_length=4,
        required=False,
        allow_blank=True
    )


class BookingCreateSerializer(serializers.Serializer):

    schedule_id = serializers.IntegerField(min_value=1)

    passengers = PassengerDetailInputSerializer(
        many=True,
        allow_empty=False
    )

    def validate_schedule_id(self, value):
        Schedule = apps.get_model("transport", "Schedule")

        try:
            schedule = Schedule.objects.select_related(
                "route",
                "bus"
            ).get(pk=value)

        except Schedule.DoesNotExist:
            raise serializers.ValidationError(
                "The selected trip does not exist."
            )

        if schedule.status != "SCHEDULED":
            raise serializers.ValidationError(
                "This trip is not available for booking."
            )

        if not schedule.route.is_active:
            raise serializers.ValidationError(
                "This route is currently unavailable."
            )

        if not schedule.bus.is_active:
            raise serializers.ValidationError(
                "This bus is currently unavailable."
            )

        if schedule.departure_datetime <= timezone.now():
            raise serializers.ValidationError(
                "This trip has already departed."
            )

        return value

    def validate(self, attrs):
        passengers = attrs["passengers"]

        if len(passengers) > 10:
            raise serializers.ValidationError({
                "passengers": (
                    "You can book a maximum of 10 seats at once."
                )
            })

        return attrs

    def create(self, validated_data):
        Schedule = apps.get_model("transport", "Schedule")

        schedule = Schedule.objects.get(
            pk=validated_data["schedule_id"]
        )

        passenger = self.context["request"].user

        return create_booking(
            passenger=passenger,
            schedule=schedule,
            passengers=validated_data["passengers"]
        )


class PassengerDetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = PassengerDetail
        fields = [
            "id",
            "full_name",
            "phone",
            "email",
            "seat_number"
        ]


class BookingSerializer(serializers.ModelSerializer):

    passengers = PassengerDetailSerializer(
        many=True,
        read_only=True
    )

    passenger_count = serializers.IntegerField(
        source="seats_booked",
        read_only=True
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "booking_ref",
            "schedule",
            "seats_booked",
            "passenger_count",
            "total_amount",
            "status",
            "payment_status",
            "booked_at",
            "cancelled_at",
            "passengers"
        ]

        read_only_fields = fields
