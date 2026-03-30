import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
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
    max_sessions = models.PositiveIntegerField(default=50)
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


uzbek_phone_validator = RegexValidator(
    regex=r"^\+998\d{9}$",
    message="Phone number must be in format: +998XXXXXXXXX",
)


class ExaminerProfile(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="examiner_profile",
    )
    bio = models.TextField(blank=True)
    full_legal_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=13, blank=True, validators=[uzbek_phone_validator])
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)
    is_verified = models.BooleanField(
        default=False,
        help_text="IELTS examiner verification badge (admin-managed). Not to be confused with User.is_verified which is email verification.",
    )
    completed_session_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"ExaminerProfile({self.user.username})"


class ExaminerCredential(TimestampedModel):
    examiner_profile = models.OneToOneField(
        ExaminerProfile,
        on_delete=models.CASCADE,
        related_name="credential",
    )
    listening_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    reading_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    writing_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    speaking_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    certificate_url = models.URLField(max_length=500, blank=True)

    def __str__(self):
        return f"ExaminerCredential({self.examiner_profile.user.username})"


class CandidateProfile(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)
    target_speaking_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    current_speaking_score = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)

    def __str__(self):
        return f"CandidateProfile({self.user.username})"


class ScoreHistory(TimestampedModel):
    candidate_profile = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="score_history",
    )
    session = models.ForeignKey(
        "session.IELTSMockSession",
        on_delete=models.CASCADE,
        related_name="score_history_entries",
    )
    overall_band = models.DecimalField(max_digits=3, decimal_places=1)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("candidate_profile", "session")]

    def __str__(self):
        return f"ScoreHistory({self.candidate_profile.user.username}, band={self.overall_band})"


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
