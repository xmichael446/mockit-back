from datetime import date, time

from rest_framework import serializers

from .models import AvailabilitySlot, BlockedDate, SessionRequest


class AvailabilitySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilitySlot
        fields = ["id", "day_of_week", "start_time", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_start_time(self, value):
        if value.minute != 0 or value.second != 0:
            raise serializers.ValidationError(
                "start_time must be on the hour (e.g., 08:00, 14:00)."
            )
        if not (time(8, 0) <= value <= time(21, 0)):
            raise serializers.ValidationError(
                "start_time must be between 08:00 and 21:00 inclusive."
            )
        return value


class BlockedDateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlockedDate
        fields = ["id", "date", "reason", "created_at"]
        read_only_fields = ["id", "created_at"]


class SessionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionRequest
        fields = [
            "id",
            "candidate",
            "examiner",
            "availability_slot",
            "requested_date",
            "session",
            "comment",
            "rejection_comment",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "candidate",
            "examiner",
            "session",
            "rejection_comment",
            "status",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        availability_slot = data.get("availability_slot")
        requested_date = data.get("requested_date")

        if availability_slot and requested_date:
            if requested_date.weekday() != availability_slot.day_of_week:
                raise serializers.ValidationError(
                    "Requested date does not match the slot's day of week."
                )
            if requested_date < date.today():
                raise serializers.ValidationError(
                    "Requested date cannot be in the past."
                )

        return data


class SessionRequestRejectSerializer(serializers.Serializer):
    rejection_comment = serializers.CharField(required=True, allow_blank=False)
