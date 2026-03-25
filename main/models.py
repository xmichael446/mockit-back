from django.contrib.auth.models import AbstractUser
from django.db import models


class TimestampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class User(AbstractUser):
    class Role(models.IntegerChoices):
        EXAMINER = 1, "Examiner"
        CANDIDATE = 2, "Candidate"

    role = models.PositiveSmallIntegerField(choices=Role.choices, default=Role.EXAMINER)
    max_sessions = models.PositiveIntegerField(default=10)

    # Guest account fields — set when a candidate joins via invite link without registration
    is_guest = models.BooleanField(default=False)
    guest_session = models.ForeignKey(
        "session.IELTSMockSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="guest_users",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_role_display()} | {self.get_full_name() or self.username}"
