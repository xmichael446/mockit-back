from django.conf import settings
from django.db import models
from rest_framework.exceptions import ValidationError

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


class SessionRequest(TimestampedModel):
    """
    Represents a candidate's request to book a session with an examiner.

    State machine:
        PENDING -> ACCEPTED | REJECTED | CANCELLED
        ACCEPTED -> CANCELLED
    """

    class Status(models.IntegerChoices):
        PENDING = 1, "Pending"
        ACCEPTED = 2, "Accepted"
        REJECTED = 3, "Rejected"
        CANCELLED = 4, "Cancelled"

    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_requests_as_candidate",
    )
    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="session_requests_as_examiner",
    )
    availability_slot = models.ForeignKey(
        "AvailabilitySlot",
        on_delete=models.CASCADE,
        related_name="session_requests",
    )
    requested_date = models.DateField()
    session = models.OneToOneField(
        "session.IELTSMockSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="session_request",
    )
    comment = models.TextField(blank=True)
    rejection_comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.candidate} -> {self.examiner} | {self.get_status_display()}"

    # ── State machine guards ──

    def can_accept(self) -> bool:
        return self.status == self.Status.PENDING

    def can_reject(self) -> bool:
        return self.status == self.Status.PENDING

    def can_cancel(self) -> bool:
        return self.status in (self.Status.PENDING, self.Status.ACCEPTED)

    # ── State machine transitions ──

    def accept(self):
        if not self.can_accept():
            raise ValidationError(
                f"Cannot accept a session request with status: {self.get_status_display()}"
            )
        self.status = self.Status.ACCEPTED

    def reject(self, rejection_comment: str):
        if not self.can_reject():
            raise ValidationError(
                f"Cannot reject a session request with status: {self.get_status_display()}"
            )
        self.rejection_comment = rejection_comment
        self.status = self.Status.REJECTED

    def cancel(self):
        if not self.can_cancel():
            raise ValidationError(
                f"Cannot cancel a session request with status: {self.get_status_display()}"
            )
        self.status = self.Status.CANCELLED
