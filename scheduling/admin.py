from django.contrib import admin

from .models import AvailabilitySlot, BlockedDate


@admin.register(AvailabilitySlot)
class AvailabilitySlotAdmin(admin.ModelAdmin):
    list_display = ("examiner", "day_of_week", "start_time")
    list_filter = ("day_of_week",)


@admin.register(BlockedDate)
class BlockedDateAdmin(admin.ModelAdmin):
    list_display = ("examiner", "date", "reason")
