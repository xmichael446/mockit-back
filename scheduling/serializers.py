from datetime import time

from rest_framework import serializers

from .models import AvailabilitySlot, BlockedDate


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
