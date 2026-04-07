import secrets
import string
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from rest_framework.exceptions import ValidationError

from django.utils import timezone

from main.models import TimestampedModel
from questions.models import FollowUpQuestion, IELTSSpeakingPart, Question, Topic


def _generate_invite_token():
    """Generate a Google Meet-style token: 3 letters + dash + 4 letters."""
    letters = string.ascii_lowercase
    part1 = "".join(secrets.choice(letters) for _ in range(3))
    part2 = "".join(secrets.choice(letters) for _ in range(4))
    return f"{part1}-{part2}"


# ─── Choices ──────────────────────────────────────────────────────────────────

class SessionStatus(models.IntegerChoices):
    SCHEDULED = 1, "Scheduled"
    IN_PROGRESS = 2, "In Progress"
    COMPLETED = 3, "Completed"
    CANCELLED = 4, "Cancelled"


class SpeakingCriterion(models.IntegerChoices):
    FC = 1, "Fluency and Coherence"
    GRA = 2, "Grammatical Range & Accuracy"
    LR = 3, "Lexical Resource"
    PR = 4, "Pronunciation"


class ScoreSource(models.IntegerChoices):
    EXAMINER = 1, "Examiner"
    AI = 2, "AI"


class MockPreset(TimestampedModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="presets", null=True)
    name = models.CharField(max_length=255)
    part_1 = models.ManyToManyField(Topic, related_name="part_1_presets")
    part_2 = models.ManyToManyField(Topic, related_name="part_2_presets")
    part_3 = models.ManyToManyField(Topic, related_name="part_3_presets")

    def clean(self):
        for topic in self.part_1.all():
            if topic.part != IELTSSpeakingPart.PART_1:
                raise ValidationError("part_1 can only contain Part 1 topics")

        for topic in self.part_2.all():
            if topic.part != IELTSSpeakingPart.PART_2:
                raise ValidationError("part_2 can only contain Part 2 topics")

        for topic in self.part_3.all():
            if topic.part != IELTSSpeakingPart.PART_3:
                raise ValidationError("part_3 can only contain Part 3 topics")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if self.pk and self.sessions.exists():
            raise ValidationError(
                "Cannot modify a preset that has sessions created from it."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.sessions.exists():
            raise ValidationError(
                "Cannot delete a preset that has sessions created from it."
            )
        super().delete(*args, **kwargs)


class IELTSMockSession(TimestampedModel):
    examiner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="examiner_sessions",)
    candidate = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="candidate_sessions", null=True, blank=True,)

    preset = models.ForeignKey(MockPreset, on_delete=models.SET_NULL, null=True, blank=True, related_name="sessions",)

    status = models.PositiveSmallIntegerField(choices=SessionStatus.choices, default=SessionStatus.SCHEDULED, db_index=True,)

    invite_token = models.CharField(max_length=9, default=_generate_invite_token, editable=False, unique=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    invite_accepted_at = models.DateTimeField(null=True, blank=True)

    video_room_id = models.CharField(max_length=1000, blank=True)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    @property
    def duration(self):
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return None

    def __str__(self):
        candidate = self.candidate or "No candidate"
        return f"{self.examiner} | {candidate} | {self.get_status_display()}"

    # ── State machine guards ──

    def can_start(self):
        return (
            self.status == SessionStatus.SCHEDULED
            and self.candidate is not None
            and (self.scheduled_at is None or timezone.now() >= self.scheduled_at)
        )

    def can_end(self):
        return self.status == SessionStatus.IN_PROGRESS

    def can_join(self):
        return self.status == SessionStatus.IN_PROGRESS

    def can_ask_question(self):
        return self.status == SessionStatus.IN_PROGRESS

    def can_start_part(self):
        return self.status == SessionStatus.IN_PROGRESS

    def can_end_part(self):
        return self.status == SessionStatus.IN_PROGRESS

    def can_accept_invite(self):
        return self.status == SessionStatus.SCHEDULED and self.candidate is None

    # ── State machine transitions ──

    def start(self):
        if not self.can_start():
            if self.candidate is None:
                raise ValidationError(
                    "Cannot start session: no candidate has accepted the invite yet."
                )
            if self.scheduled_at and timezone.now() < self.scheduled_at:
                raise ValidationError(
                    "Cannot start session before the scheduled time."
                )
            raise ValidationError(
                f"Session cannot be started. Current status: {self.get_status_display()}."
            )
        self.status = SessionStatus.IN_PROGRESS
        self.started_at = timezone.now()

    def end(self):
        if not self.can_end():
            raise ValidationError(
                f"Session is not in progress. Current status: {self.get_status_display()}."
            )
        self.status = SessionStatus.COMPLETED
        self.ended_at = timezone.now()

    def assert_in_progress(self):
        if self.status != SessionStatus.IN_PROGRESS:
            raise ValidationError(
                f"Session is not in progress. Current status: {self.get_status_display()}."
            )

    def can_cancel(self):
        return self.status == SessionStatus.SCHEDULED and self.candidate is None

    def cancel(self):
        if not self.can_cancel():
            raise ValidationError(
                "Only scheduled sessions with no candidate can be cancelled."
            )
        self.status = SessionStatus.CANCELLED
        self.invite_expires_at = timezone.now()  # expire invite immediately


class SessionPart(TimestampedModel):
    session = models.ForeignKey(IELTSMockSession, on_delete=models.CASCADE, related_name="parts")
    part = models.PositiveSmallIntegerField(choices=IELTSSpeakingPart.choices)

    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    @property
    def duration(self):
        if self.started_at and self.ended_at:
            return self.ended_at - self.started_at
        return None

    class Meta:
        unique_together = [("session", "part")]
        ordering = ["part"]

    def __str__(self):
        return f"{self.session} | {self.get_part_display()}"


class SessionQuestion(TimestampedModel):
    session_part = models.ForeignKey(SessionPart, on_delete=models.CASCADE, related_name="session_questions")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="session_questions")
    order = models.PositiveSmallIntegerField()

    asked_at = models.DateTimeField(null=True, blank=True)
    answer_started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    @property
    def prep_duration(self):
        if self.asked_at and self.answer_started_at:
            return self.answer_started_at - self.asked_at
        return None

    @property
    def speaking_duration(self):
        start = self.answer_started_at or self.asked_at
        if start and self.ended_at:
            return self.ended_at - start
        return None

    @property
    def total_duration(self):
        if self.asked_at and self.ended_at:
            return self.ended_at - self.asked_at
        return None

    class Meta:
        unique_together = [("session_part", "order")]
        ordering = ["order"]

    def __str__(self):
        return f"{self.session_part} | Q{self.order}: {self.question}"


class SessionFollowUp(TimestampedModel):
    session_question = models.ForeignKey(SessionQuestion, on_delete=models.CASCADE, related_name="session_follow_ups",)
    follow_up = models.ForeignKey(FollowUpQuestion, on_delete=models.CASCADE, related_name="session_follow_ups",)

    asked_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    @property
    def duration(self):
        if self.asked_at and self.ended_at:
            return self.ended_at - self.asked_at
        return None

    def __str__(self):
        return f"{self.session_question} | Follow-up: {self.follow_up}"


class Note(TimestampedModel):
    session_question = models.ForeignKey(SessionQuestion, on_delete=models.CASCADE, related_name="notes")
    content = models.CharField(max_length=1000)

    def __str__(self):
        return f"Note: {self.content[:30]}..."


class SessionResult(TimestampedModel):
    session = models.OneToOneField(IELTSMockSession, on_delete=models.CASCADE, related_name="result")
    overall_band = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    overall_feedback = models.TextField(null=True, blank=True)
    is_released = models.BooleanField(default=False)
    released_at = models.DateTimeField(null=True, blank=True)

    def compute_overall_band(self):
        bands = list(
            self.scores.filter(source=ScoreSource.EXAMINER).values_list("band", flat=True)
        )
        if len(bands) < 4:
            return None
        return (sum(bands) // 2) / 2

    def __str__(self):
        return f"Result: {self.session} | Band {self.overall_band}"


class CriterionScore(TimestampedModel):
    session_result = models.ForeignKey(SessionResult, on_delete=models.CASCADE, related_name="scores")
    criterion = models.PositiveSmallIntegerField(choices=SpeakingCriterion.choices)
    source = models.PositiveSmallIntegerField(
        choices=ScoreSource.choices,
        default=ScoreSource.EXAMINER,
    )
    band = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(9)])
    feedback = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = [("session_result", "criterion", "source")]

    def __str__(self):
        return f"{self.get_criterion_display()}: {self.band}"


class SessionRecording(TimestampedModel):
    session = models.OneToOneField(IELTSMockSession, on_delete=models.CASCADE, related_name="recording")
    audio_file = models.FileField(upload_to="recordings/")
    # When the client started recording — used as the anchor for all timecode offsets.
    # Falls back to session.started_at if not provided (assumes recording started with the session).
    recording_started_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.session.examiner} | {self.session.candidate}"


class SessionShare(models.Model):
    """Shareable public link for a completed, released session."""
    session = models.OneToOneField(IELTSMockSession, on_delete=models.CASCADE, related_name="share")
    share_token = models.CharField(max_length=9, default=_generate_invite_token, unique=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Share({self.share_token}) for session {self.session_id}"


class AIFeedbackJob(TimestampedModel):
    class Status(models.IntegerChoices):
        PENDING = 1, "Pending"
        PROCESSING = 2, "Processing"
        DONE = 3, "Done"
        FAILED = 4, "Failed"

    session = models.ForeignKey(
        IELTSMockSession,
        on_delete=models.CASCADE,
        related_name="ai_feedback_jobs",
    )
    status = models.PositiveSmallIntegerField(
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"AIFeedbackJob({self.pk}) session={self.session_id} status={self.get_status_display()}"

