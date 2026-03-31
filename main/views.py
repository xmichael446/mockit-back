import uuid

from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import CandidateProfile, EmailVerificationToken, ExaminerCredential, ExaminerProfile, User
from .serializers import (
    CandidateProfileDetailSerializer,
    CandidateProfilePublicSerializer,
    ExaminerCredentialSerializer,
    ExaminerProfileDetailSerializer,
    ExaminerProfilePublicSerializer,
    GuestJoinSerializer,
    LoginSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserMinimalSerializer,
    VerifyEmailSerializer,
)
from .services.email import send_verification_email


def _is_examiner(user):
    return user.role == User.Role.EXAMINER


def _is_candidate(user):
    return user.role == User.Role.CANDIDATE


class RegisterView(APIView):
    """
    POST /api/auth/register/
    Create a new user account. Returns an auth token on success.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_scope = "register"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        if user.role == User.Role.CANDIDATE:
            user.is_verified = True
            user.save(update_fields=["is_verified"])
            token, _ = Token.objects.get_or_create(user=user)
            return Response({"token": token.key, "user": UserMinimalSerializer(user).data}, status=201)
        verification = EmailVerificationToken.objects.create(user=user)
        email_sent = send_verification_email(user, verification.token)
        response_data = {"message": "Account created. Check your email to verify your address."}
        if not email_sent:
            response_data["email_warning"] = "Verification email could not be sent. You can request a new one later."
        return Response(response_data, status=201)


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
        if not user.is_verified and not user.is_guest and user.role != User.Role.CANDIDATE:
            return Response(
                {"error": "email_not_verified", "message": "Please verify your email before logging in."},
                status=403,
            )
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


class VerifyEmailView(APIView):
    """
    POST /api/auth/verify-email/
    Verify a user's email address using the token from the verification email.
    Returns an auth token on success, logging the user in immediately.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token_obj = serializer.get_token_obj()
        user = token_obj.user
        user.is_verified = True
        user.save(update_fields=["is_verified"])
        token_obj.is_used = True
        token_obj.save(update_fields=["is_used"])
        auth_token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": auth_token.key, "user": UserMinimalSerializer(user).data})


class ResendVerificationView(APIView):
    """
    POST /api/auth/resend-verification/
    Resend a verification email. Always returns 200 to avoid user enumeration.
    Invalidates any existing unused tokens and issues a fresh one.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        try:
            user = User.objects.get(email=email, is_verified=False, is_guest=False)
        except User.DoesNotExist:
            # Return 200 regardless — no user enumeration
            return Response({"message": "If that email exists and is unverified, a new link has been sent."})
        # Invalidate existing unused tokens
        EmailVerificationToken.objects.filter(user=user, is_used=False).update(is_used=True)
        verification = EmailVerificationToken.objects.create(user=user)
        email_sent = send_verification_email(user, verification.token)
        response_data = {"message": "If that email exists and is unverified, a new link has been sent."}
        if not email_sent:
            response_data["email_warning"] = "Verification email could not be sent. Please try again later."
        return Response(response_data)


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
    throttle_scope = "guest_join"

    def post(self, request):
        serializer = GuestJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = serializer.get_session()

        # Create an ephemeral guest user
        random_suffix = uuid.uuid4().hex[:10]
        guest_username = f"guest_{random_suffix}"
        entered_name = serializer.validated_data.get("first_name", "").strip()
        guest = User.objects.create(
            username=guest_username,
            first_name=entered_name or "Guest",
            last_name="",
            email="",
            role=User.Role.CANDIDATE,
            is_guest=True,
            is_verified=True,
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


class ExaminerDirectoryView(ListAPIView):
    """
    GET /api/profiles/examiners/
    Any authenticated user. Lists all examiner public profiles (paginated).
    Phone field is hidden.

    Query parameters:
    - is_verified: 'true' to show only verified, 'false' for unverified only
    - ordering: 'completed_session_count' (asc) or '-completed_session_count' (desc)
    """
    serializer_class = ExaminerProfilePublicSerializer

    def get_queryset(self):
        qs = ExaminerProfile.objects.select_related("user", "credential").all()

        is_verified_param = self.request.query_params.get("is_verified")
        if is_verified_param is not None:
            if is_verified_param.lower() == "true":
                qs = qs.filter(is_verified=True)
            elif is_verified_param.lower() == "false":
                qs = qs.filter(is_verified=False)

        ordering_param = self.request.query_params.get("ordering")
        if ordering_param in ("completed_session_count", "-completed_session_count"):
            qs = qs.order_by(ordering_param)
        else:
            qs = qs.order_by("pk")

        return qs


class ExaminerProfileMeView(APIView):
    """
    GET  /api/profiles/examiner/me/  — Retrieve own examiner profile (examiner only)
    PATCH /api/profiles/examiner/me/ — Update own examiner profile (examiner only)
    """
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Examiner profile not found."}, status=404)
        profile, _ = ExaminerProfile.objects.get_or_create(user=request.user)
        return Response(ExaminerProfileDetailSerializer(profile).data)

    def patch(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Examiner profile not found."}, status=404)
        profile, _ = ExaminerProfile.objects.get_or_create(user=request.user)
        serializer = ExaminerProfileDetailSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ExaminerProfilePublicView(APIView):
    """
    GET /api/profiles/examiner/<id>/ — View examiner's public profile (any authenticated user)
    """

    def get(self, request, pk):
        try:
            profile = ExaminerProfile.objects.select_related("user", "credential").get(pk=pk)
        except ExaminerProfile.DoesNotExist:
            return Response({"detail": "Examiner profile not found."}, status=404)
        return Response(ExaminerProfilePublicSerializer(profile).data)


class ExaminerCredentialView(APIView):
    """
    GET  /api/profiles/examiner/me/credential/ — Retrieve own credential
    PUT  /api/profiles/examiner/me/credential/ — Create or update own credential
    """

    def get(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Examiner profile not found."}, status=404)
        profile, _ = ExaminerProfile.objects.get_or_create(user=request.user)
        try:
            credential = profile.credential
        except ExaminerCredential.DoesNotExist:
            return Response({"detail": "No credential found."}, status=404)
        return Response(ExaminerCredentialSerializer(credential).data)

    def put(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Examiner profile not found."}, status=404)
        profile, _ = ExaminerProfile.objects.get_or_create(user=request.user)
        credential, _ = ExaminerCredential.objects.get_or_create(examiner_profile=profile)
        serializer = ExaminerCredentialSerializer(credential, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CandidateProfileMeView(APIView):
    """
    GET  /api/profiles/candidate/me/  — Retrieve own candidate profile (candidate only)
    PATCH /api/profiles/candidate/me/ — Update own candidate profile (candidate only)
    """
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request):
        if not _is_candidate(request.user):
            return Response({"detail": "Candidate profile not found."}, status=404)
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        return Response(CandidateProfileDetailSerializer(profile).data)

    def patch(self, request):
        if not _is_candidate(request.user):
            return Response({"detail": "Candidate profile not found."}, status=404)
        profile, _ = CandidateProfile.objects.get_or_create(user=request.user)
        serializer = CandidateProfileDetailSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CandidateProfilePublicView(APIView):
    """
    GET /api/profiles/candidate/<id>/ — View candidate's public profile (any authenticated user)
    """

    def get(self, request, pk):
        try:
            profile = CandidateProfile.objects.select_related("user").prefetch_related("score_history").get(pk=pk)
        except CandidateProfile.DoesNotExist:
            return Response({"detail": "Candidate profile not found."}, status=404)
        return Response(CandidateProfilePublicSerializer(profile).data)
