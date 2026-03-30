from django.conf import settings
from django.db import models

from main.models import TimestampedModel


class AvailabilitySlot(TimestampedModel):
    """
    Represents a recurring weekly 1-hour availability window for an examiner.
    DayOfWeek uses MON=0 through SUN=6, matching Python's date.weekday() convention.
    end_time is NOT stored — it is always start_time + 1 hour (locked decision).
    """

    class DayOfWeek(models.IntegerChoices):
        MON = 0, "Monday"
        TUE = 1, "Tuesday"
        WED = 2, "Wednesday"
        THU = 3, "Thursday"
        FRI = 4, "Friday"
        SAT = 5, "Saturday"
        SUN = 6, "Sunday"

    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()

    class Meta:
        unique_together = [("examiner", "day_of_week", "start_time")]
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        day_name = self.DayOfWeek(self.day_of_week).label
        return f"{day_name} {self.start_time.strftime('%H:%M')}"


class BlockedDate(TimestampedModel):
    """
    Represents a specific date on which the examiner is NOT available,
    overriding any recurring AvailabilitySlot entries for that day.
    """

    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_dates",
    )
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("examiner", "date")]
        ordering = ["date"]

    def __str__(self):
        return f"{self.date} (Blocked)"
