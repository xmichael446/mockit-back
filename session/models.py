import random
import string
import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from rest_framework.exceptions import ValidationError

from main.models import TimestampedModel
from questions.models import FollowUpQuestion, IELTSSpeakingPart, Question, Topic


def _generate_invite_token():
    """Generate a Google Meet-style token like 'abcd-efgh'."""
    chars = string.ascii_lowercase + string.digits
    return (
        "".join(random.choices(chars, k=4))
        + "-"
        + "".join(random.choices(chars, k=4))
    )


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


class MockPreset(TimestampedModel):
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
        bands = list(self.scores.values_list("band", flat=True))
        if len(bands) < 4:
            return None
        return (sum(bands) // 2) / 2

    def __str__(self):
        return f"Result: {self.session} | Band {self.overall_band}"


class CriterionScore(TimestampedModel):
    session_result = models.ForeignKey(SessionResult, on_delete=models.CASCADE, related_name="scores")
    criterion = models.PositiveSmallIntegerField(choices=SpeakingCriterion.choices)
    band = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(9)])
    feedback = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = [("session_result", "criterion")]

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

