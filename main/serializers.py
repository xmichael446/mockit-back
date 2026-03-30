import uuid

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers

from .models import CandidateProfile, EmailVerificationToken, ExaminerCredential, ExaminerProfile, ScoreHistory, User


class UserMinimalSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email", "role", "role_label", "is_guest", "max_sessions")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "password", "first_name", "email", "role")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(username=data["username"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid credentials.")
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled.")
        data["user"] = user
        return data


class VerifyEmailSerializer(serializers.Serializer):
    token = serializers.UUIDField()

    def validate_token(self, value):
        try:
            obj = EmailVerificationToken.objects.select_related("user").get(token=value)
        except EmailVerificationToken.DoesNotExist:
            raise serializers.ValidationError("Invalid verification token.")
        if obj.is_used:
            raise serializers.ValidationError("This token has already been used.")
        if obj.is_expired:
            raise serializers.ValidationError("This token has expired. Request a new one.")
        self._token_obj = obj
        return value

    def get_token_obj(self):
        return self._token_obj


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()


class GuestJoinSerializer(serializers.Serializer):
    """
    Validates an invite token and resolves the associated session.
    Used by POST /api/auth/guest-join/.
    """
    invite_token = serializers.CharField(max_length=9)
    first_name = serializers.CharField(required=False, max_length=150, allow_blank=True, default="")

    def validate_invite_token(self, value):
        from session.models import IELTSMockSession, SessionStatus
        try:
            session = IELTSMockSession.objects.select_related("candidate").get(
                invite_token=value
            )
        except IELTSMockSession.DoesNotExist:
            raise serializers.ValidationError("Invalid invite token.")

        if not session.can_accept_invite():
            if session.status != SessionStatus.SCHEDULED:
                raise serializers.ValidationError(
                    f"Session is not accepting guests (status: {session.get_status_display()})."
                )
            raise serializers.ValidationError("This invite has already been accepted.")

        if session.invite_expires_at and timezone.now() > session.invite_expires_at:
            raise serializers.ValidationError("This invite has expired.")

        self._session = session
        return value

    def get_session(self):
        return self._session


class UserNestedSerializer(serializers.ModelSerializer):
    """Read-only nested user fields for profile responses."""
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name")
        read_only_fields = ("id", "username", "email", "first_name", "last_name")


class ExaminerCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExaminerCredential
        fields = ("id", "listening_score", "reading_score", "writing_score", "speaking_score", "certificate_url")


class ExaminerProfileDetailSerializer(serializers.ModelSerializer):
    """Owner view — phone visible, writable fields."""
    user = UserNestedSerializer(read_only=True)
    credential = ExaminerCredentialSerializer(read_only=True)

    class Meta:
        model = ExaminerProfile
        fields = (
            "id", "user", "bio", "full_legal_name", "phone",
            "profile_picture", "is_verified", "completed_session_count", "credential",
        )
        read_only_fields = ("is_verified", "completed_session_count")


class ExaminerProfilePublicSerializer(serializers.ModelSerializer):
    """Public view — phone hidden, all read-only."""
    user = UserNestedSerializer(read_only=True)
    credential = ExaminerCredentialSerializer(read_only=True)

    class Meta:
        model = ExaminerProfile
        fields = (
            "id", "user", "bio", "full_legal_name",
            "profile_picture", "is_verified", "completed_session_count", "credential",
        )
        read_only_fields = (
            "id", "user", "bio", "full_legal_name",
            "profile_picture", "is_verified", "completed_session_count", "credential",
        )


class ScoreHistorySerializer(serializers.ModelSerializer):
    session_id = serializers.IntegerField(source="session.pk", read_only=True)

    class Meta:
        model = ScoreHistory
        fields = ("id", "session_id", "overall_band", "created_at")
        read_only_fields = ("id", "session_id", "overall_band", "created_at")


class CandidateProfileDetailSerializer(serializers.ModelSerializer):
    """Owner view — writable fields."""
    user = UserNestedSerializer(read_only=True)
    score_history = ScoreHistorySerializer(many=True, read_only=True)

    class Meta:
        model = CandidateProfile
        fields = (
            "id", "user", "profile_picture", "target_speaking_score",
            "current_speaking_score", "score_history",
        )

    def validate_target_speaking_score(self, value):
        if value is not None:
            if value < 1 or value > 9:
                raise serializers.ValidationError("Score must be between 1.0 and 9.0.")
            if (value * 2) % 1 != 0:
                raise serializers.ValidationError("Score must be a multiple of 0.5.")
        return value

    def validate_current_speaking_score(self, value):
        if value is not None:
            if value < 1 or value > 9:
                raise serializers.ValidationError("Score must be between 1.0 and 9.0.")
            if (value * 2) % 1 != 0:
                raise serializers.ValidationError("Score must be a multiple of 0.5.")
        return value


class CandidateProfilePublicSerializer(serializers.ModelSerializer):
    """Public view — read-only, includes score history."""
    user = UserNestedSerializer(read_only=True)
    score_history = ScoreHistorySerializer(many=True, read_only=True)

    class Meta:
        model = CandidateProfile
        fields = (
            "id", "user", "profile_picture", "target_speaking_score",
            "current_speaking_score", "score_history",
        )
        read_only_fields = (
            "id", "user", "profile_picture", "target_speaking_score",
            "current_speaking_score", "score_history",
        )
