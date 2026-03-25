from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from main.models import User
from main.serializers import UserMinimalSerializer
from questions.models import IELTSSpeakingPart, Topic
from questions.serializers import QuestionDetailSerializer
from .models import (
    CriterionScore,
    IELTSMockSession,
    MockPreset,
    Note,
    SessionFollowUp,
    SessionPart,
    SessionQuestion,
    SessionRecording,
    SessionResult,
    SessionStatus,
    SpeakingCriterion,
)


# ─── Preset ───────────────────────────────────────────────────────────────────

class PresetTopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ("id", "topic_number", "name", "part", "slug")


class MockPresetSerializer(serializers.ModelSerializer):
    part_1 = PresetTopicSerializer(many=True, read_only=True)
    part_2 = PresetTopicSerializer(many=True, read_only=True)
    part_3 = PresetTopicSerializer(many=True, read_only=True)

    class Meta:
        model = MockPreset
        fields = ("id", "owner", "name", "part_1", "part_2", "part_3", "created_at")


class MockPresetCreateSerializer(serializers.ModelSerializer):
    part_1 = serializers.PrimaryKeyRelatedField(many=True, queryset=Topic.objects.all())
    part_2 = serializers.PrimaryKeyRelatedField(many=True, queryset=Topic.objects.all())
    part_3 = serializers.PrimaryKeyRelatedField(many=True, queryset=Topic.objects.all())

    class Meta:
        model = MockPreset
        fields = ("name", "part_1", "part_2", "part_3")
        # owner is injected by the view via serializer.save(owner=request.user)

    def _validate_part(self, topics, expected_part: int, label: str):
        wrong = [t.name for t in topics if t.part != expected_part]
        if wrong:
            raise serializers.ValidationError(
                f"{label} can only contain {IELTSSpeakingPart(expected_part).label} topics. "
                f"Invalid: {', '.join(wrong)}"
            )
        return topics

    def validate_part_1(self, topics):
        return self._validate_part(topics, IELTSSpeakingPart.PART_1, "part_1")

    def validate_part_2(self, topics):
        return self._validate_part(topics, IELTSSpeakingPart.PART_2, "part_2")

    def validate_part_3(self, topics):
        return self._validate_part(topics, IELTSSpeakingPart.PART_3, "part_3")

    def create(self, validated_data):
        part_1 = validated_data.pop("part_1")
        part_2 = validated_data.pop("part_2")
        part_3 = validated_data.pop("part_3")
        preset = MockPreset.objects.create(**validated_data)  # owner passed via save(owner=...)
        preset.part_1.set(part_1)
        preset.part_2.set(part_2)
        preset.part_3.set(part_3)
        return preset

    def to_representation(self, instance):
        from django.db.models import prefetch_related_objects
        prefetch_related_objects([instance], "part_1", "part_2", "part_3")
        return MockPresetSerializer(instance).data


# ─── Session ──────────────────────────────────────────────────────────────────

class SessionSerializer(serializers.ModelSerializer):
    examiner = UserMinimalSerializer(read_only=True)
    candidate = UserMinimalSerializer(read_only=True)
    preset = MockPresetSerializer(read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = IELTSMockSession
        fields = (
            "id",
            "examiner",
            "candidate",
            "preset",
            "status",
            "status_label",
            "invite_token",
            "invite_expires_at",
            "invite_accepted_at",
            "video_room_id",
            "scheduled_at",
            "started_at",
            "ended_at",
            "created_at",
        )


class SessionCreateSerializer(serializers.Serializer):
    """
    Write serializer for creating a new session.
    `examiner` is set from request.user in the view — not accepted from the body.
    """
    preset = serializers.PrimaryKeyRelatedField(
        queryset=MockPreset.objects.all(), required=False, allow_null=True
    )
    scheduled_at = serializers.DateTimeField()

    def validate_scheduled_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("scheduled_at must be in the future.")
        return value

    def create(self, validated_data):
        # invite_expires_at: whichever comes first — 7 days from now or scheduled_at
        expires = min(timezone.now() + timedelta(days=7), validated_data["scheduled_at"])
        return IELTSMockSession.objects.create(
            examiner=validated_data["examiner"],
            preset=validated_data.get("preset"),
            scheduled_at=validated_data["scheduled_at"],
            invite_expires_at=expires,
        )


class AcceptInviteSerializer(serializers.Serializer):
    """
    Write serializer for accepting an invite.
    `candidate` is taken from request.user in the view — not accepted from the body.
    """
    token = serializers.UUIDField()

    def validate(self, data):
        try:
            session = (
                IELTSMockSession.objects
                .select_related("examiner", "candidate", "preset")
                .get(invite_token=data["token"])
            )
        except IELTSMockSession.DoesNotExist:
            raise serializers.ValidationError({"token": "Invalid invite token."})

        if session.status != SessionStatus.SCHEDULED:
            raise serializers.ValidationError(
                {"token": f"Session is not accepting invitations (status: {session.get_status_display()})."}
            )

        if session.candidate is not None:
            raise serializers.ValidationError({"token": "This invite has already been accepted."})

        if session.invite_expires_at and timezone.now() > session.invite_expires_at:
            raise serializers.ValidationError({"token": "This invite has expired."})

        data["session"] = session
        return data


# ─── Session Parts ─────────────────────────────────────────────────────────────

class SessionPartSerializer(serializers.ModelSerializer):
    part_label = serializers.CharField(source="get_part_display", read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = SessionPart
        fields = ("id", "session", "part", "part_label", "started_at", "ended_at", "duration_seconds")
        read_only_fields = ("id", "session", "started_at", "ended_at", "duration_seconds")

    def get_duration_seconds(self, obj):
        d = obj.duration
        return d.total_seconds() if d else None


# ─── Session Questions ─────────────────────────────────────────────────────────

class SessionFollowUpSerializer(serializers.ModelSerializer):
    follow_up_text = serializers.CharField(source="follow_up.text", read_only=True)
    duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = SessionFollowUp
        fields = ("id", "follow_up", "follow_up_text", "asked_at", "ended_at", "duration_seconds")

    def get_duration_seconds(self, obj):
        d = obj.duration
        return d.total_seconds() if d else None


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = ("id", "content", "created_at")


class SessionQuestionSerializer(serializers.ModelSerializer):
    question = QuestionDetailSerializer(read_only=True)
    session_follow_ups = SessionFollowUpSerializer(many=True, read_only=True)
    notes = NoteSerializer(many=True, read_only=True)
    prep_duration_seconds = serializers.SerializerMethodField()
    speaking_duration_seconds = serializers.SerializerMethodField()
    total_duration_seconds = serializers.SerializerMethodField()

    class Meta:
        model = SessionQuestion
        fields = (
            "id",
            "session_part",
            "question",
            "order",
            "asked_at",
            "answer_started_at",
            "ended_at",
            "prep_duration_seconds",
            "speaking_duration_seconds",
            "total_duration_seconds",
            "session_follow_ups",
            "notes",
        )

    def get_prep_duration_seconds(self, obj):
        d = obj.prep_duration
        return d.total_seconds() if d else None

    def get_speaking_duration_seconds(self, obj):
        d = obj.speaking_duration
        return d.total_seconds() if d else None

    def get_total_duration_seconds(self, obj):
        d = obj.total_duration
        return d.total_seconds() if d else None


# ─── Results ──────────────────────────────────────────────────────────────────

class CriterionScoreSerializer(serializers.ModelSerializer):
    criterion_label = serializers.CharField(source="get_criterion_display", read_only=True)

    class Meta:
        model = CriterionScore
        fields = ("id", "criterion", "criterion_label", "band", "feedback")


class CriterionScoreWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CriterionScore
        fields = ("criterion", "band", "feedback")

    def validate_criterion(self, value):
        if value not in SpeakingCriterion.values:
            raise serializers.ValidationError("Invalid criterion value.")
        return value

    def validate_band(self, value):
        if not (1 <= value <= 9):
            raise serializers.ValidationError("Band must be between 1 and 9.")
        return value


class SessionResultSerializer(serializers.ModelSerializer):
    # Expose as "overall" — cleaner name for the frontend.
    overall = serializers.DecimalField(source="overall_band", max_digits=3, decimal_places=1, read_only=True)
    scores = CriterionScoreSerializer(many=True, read_only=True)

    class Meta:
        model = SessionResult
        fields = ("id", "overall", "overall_feedback", "is_released", "released_at", "scores")


class SessionResultWriteSerializer(serializers.Serializer):
    """Submit criterion scores and optional overall feedback at once."""
    scores = CriterionScoreWriteSerializer(many=True)
    overall_feedback = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_scores(self, value):
        criteria = [s["criterion"] for s in value]
        if len(criteria) != len(set(criteria)):
            raise serializers.ValidationError("Duplicate criterion entries.")
        return value


# ─── Recording ────────────────────────────────────────────────────────────────

def _offset(session_start, dt):
    """Return seconds between session_start and dt, or None if either is missing."""
    if session_start is None or dt is None:
        return None
    return (dt - session_start).total_seconds()


class SessionRecordingSerializer(serializers.ModelSerializer):
    audio_url = serializers.SerializerMethodField()
    parts = serializers.SerializerMethodField()

    class Meta:
        model = SessionRecording
        fields = ("id", "session", "audio_url", "recording_started_at", "created_at", "parts")

    def get_audio_url(self, obj):
        request = self.context.get("request")
        if request and obj.audio_file:
            return request.build_absolute_uri(obj.audio_file.url)
        return obj.audio_file.url if obj.audio_file else None

    def get_parts(self, obj):
        session = obj.session
        # Use recording_started_at as the anchor so offsets match the actual audio file.
        # Fall back to session.started_at only if the client didn't send a recording start time.
        anchor = obj.recording_started_at or session.started_at

        parts = (
            SessionPart.objects
            .filter(session=session)
            .prefetch_related(
                "session_questions__question",
                "session_questions__session_follow_ups__follow_up",
                "session_questions__notes",
            )
            .order_by("part")
        )

        result = []
        for part in parts:
            questions_timeline = []

            # Use the prefetch cache — don't call .order_by() here or it fires a new query.
            # SessionQuestion.Meta already defines ordering = ["order"].
            for sq in part.session_questions.all():
                questions_timeline.append({
                    "type": "question",
                    "id": sq.pk,
                    "order": sq.order,
                    "text": sq.question.text,
                    "asked_offset": _offset(anchor, sq.asked_at),
                    "answer_started_offset": _offset(anchor, sq.answer_started_at),
                    "ended_offset": _offset(anchor, sq.ended_at),
                    "notes": [
                        {"id": n.pk, "content": n.content, "created_at": n.created_at.isoformat()}
                        for n in sq.notes.all()
                    ],
                })

                # SessionFollowUp has no Meta ordering, so sort in Python to preserve prefetch.
                follow_ups = sorted(sq.session_follow_ups.all(), key=lambda sf: sf.asked_at or sq.asked_at)
                for sf in follow_ups:
                    questions_timeline.append({
                        "type": "followup",
                        "id": sf.pk,
                        "text": sf.follow_up.text,
                        "asked_offset": _offset(anchor, sf.asked_at),
                        "ended_offset": _offset(anchor, sf.ended_at),
                    })

            result.append({
                "part": part.part,
                "part_label": part.get_part_display(),
                "start_offset": _offset(anchor, part.started_at),
                "end_offset": _offset(anchor, part.ended_at),
                "questions": questions_timeline,
            })

        return result
