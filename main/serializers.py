import uuid

from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework import serializers

from .models import User


class UserMinimalSerializer(serializers.ModelSerializer):
    role_label = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "first_name", "last_name", "email", "role", "role_label", "is_guest", "max_sessions")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ("username", "password", "first_name", "email")

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data, role=User.Role.EXAMINER)
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


class GuestJoinSerializer(serializers.Serializer):
    """
    Validates an invite token and resolves the associated session.
    Used by POST /api/auth/guest-join/.
    """
    invite_token = serializers.UUIDField()
    first_name = serializers.CharField(required=False, max_length=150, allow_blank=True, default="")

    def validate_invite_token(self, value):
        from session.models import IELTSMockSession, SessionStatus
        try:
            session = IELTSMockSession.objects.select_related("candidate").get(
                invite_token=value
            )
        except IELTSMockSession.DoesNotExist:
            raise serializers.ValidationError("Invalid invite token.")

        if session.status != SessionStatus.SCHEDULED:
            raise serializers.ValidationError(
                f"Session is not accepting guests (status: {session.get_status_display()})."
            )

        if session.candidate is not None:
            raise serializers.ValidationError("This invite has already been accepted.")

        if session.invite_expires_at and timezone.now() > session.invite_expires_at:
            raise serializers.ValidationError("This invite has expired.")

        self._session = session
        return value

    def get_session(self):
        return self._session
