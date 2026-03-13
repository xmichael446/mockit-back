import uuid

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import GuestJoinSerializer, LoginSerializer, RegisterSerializer, UserMinimalSerializer


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Create a new user account. Returns an auth token on success.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserMinimalSerializer(user).data}, status=201)


class LoginView(APIView):
    """
    POST /api/auth/login/
    Authenticate and receive a token.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserMinimalSerializer(user).data})


class LogoutView(APIView):
    """
    POST /api/auth/logout/
    Invalidate the current auth token.
    """

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=204)


class MeView(APIView):
    """
    GET /api/auth/me/
    Return the currently authenticated user.
    """

    def get(self, request):
        return Response(UserMinimalSerializer(request.user).data)


class GuestJoinView(APIView):
    """
    POST /api/auth/guest-join/
    Join a session as an ephemeral guest candidate — no registration required.

    Body: {"invite_token": "<uuid>", "first_name": "Alice"}
    Returns: {"token": "<drf-token>", "user": {...}, "session_id": <int>}

    Creates a throwaway User with is_guest=True and role=CANDIDATE, scoped to
    the session via guest_session FK. The returned DRF token works for both
    REST and WebSocket (ws/session/<id>/?token=<token>).

    The guest user is also set as the session's candidate so the examiner can
    start the session immediately.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GuestJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = serializer.get_session()

        # Create an ephemeral guest user
        random_suffix = uuid.uuid4().hex[:10]
        guest_username = f"guest_{random_suffix}"
        entered_name = serializer.validated_data.get("first_name", "").strip()
        from .models import User
        guest = User.objects.create(
            username=guest_username,
            first_name=entered_name or "Guest",
            last_name="",
            email="",
            role=User.Role.CANDIDATE,
            is_guest=True,
            guest_session=session,
            is_active=True,
        )
        # Guest accounts have no usable password
        guest.set_unusable_password()
        guest.save(update_fields=["password"])

        # Assign the guest as the session candidate
        session.candidate = guest
        session.invite_accepted_at = timezone.now()
        session.save(update_fields=["candidate", "invite_accepted_at", "updated_at"])

        # Broadcast invite accepted event to any waiting examiner
        from asgiref.sync import async_to_sync
        from channels.layers import get_channel_layer
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"session_{session.pk}",
            {
                "type": "session_event",
                "data": {
                    "type": "invite.accepted",
                    "session_id": session.pk,
                    "candidate": {
                        "id": guest.pk,
                        "username": guest.username,
                        "first_name": guest.first_name,
                        "last_name": guest.last_name,
                        "is_guest": True,
                    },
                    "invite_accepted_at": session.invite_accepted_at.isoformat(),
                },
            },
        )

        token, _ = Token.objects.get_or_create(user=guest)
        return Response(
            {
                "token": token.key,
                "user": UserMinimalSerializer(guest).data,
                "session_id": session.pk,
            },
            status=201,
        )
