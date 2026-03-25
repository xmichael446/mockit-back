import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


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
    is_verified = models.BooleanField(default=False)

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


class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="verification_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.pk and not self.expires_at:
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"VerificationToken({self.user.username}, used={self.is_used})"
