from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from datetime import datetime
from django.utils import timezone
import logging
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import F
from main.models import CandidateProfile, ExaminerProfile, ScoreHistory, User
from questions.models import Question, FollowUpQuestion
from questions.serializers import QuestionDetailSerializer
from .models import (
    AIFeedbackJob,
    IELTSMockSession,
    MockPreset,
    Note,
    SessionFollowUp,
    SessionPart,
    SessionQuestion,
    SessionRecording,
    SessionResult,
    SessionShare,
    SessionStatus,
    SpeakingCriterion,
)
from .serializers import (
    AcceptInviteSerializer,
    CriterionScoreSerializer,
    MockPresetCreateSerializer,
    MockPresetSerializer,
    NoteSerializer,
    SessionCreateSerializer,
    SessionFollowUpSerializer,
    SessionPartSerializer,
    SessionQuestionSerializer,
    SessionRecordingSerializer,
    SessionResultSerializer,
    SessionResultWriteSerializer,
    SessionSerializer,
    SharedSessionSerializer,
)
from .services.hms import create_room, generate_app_token
from django_q.tasks import async_task

audit = logging.getLogger("mockit.audit")


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _session_qs():
    return (
        IELTSMockSession.objects
        .select_related("examiner", "candidate", "preset")
        .prefetch_related("preset__part_1", "preset__part_2", "preset__part_3")
    )


def _is_examiner(user):
    return user.role == User.Role.EXAMINER


def _is_candidate(user):
    return user.role == User.Role.CANDIDATE


def _event_time(request):
    """Use client-provided ISO timestamp if present, otherwise server time.

    Clients can send ``"client_ts": "2024-01-05T14:05:00.123Z"`` in the
    request body so that recording-playback offsets reflect the actual moment
    the user pressed the button, not when the server processed the request.
    """
    client_ts = request.data.get("client_ts")
    if client_ts:
        try:
            dt = datetime.fromisoformat(client_ts)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            return dt
        except (ValueError, TypeError):
            pass
    return timezone.now()


def _broadcast(session_id, event_type, data):
    """Broadcast a WebSocket event to all clients connected to this session."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"session_{session_id}",
        {
            "type": "session_event",
            "data": {"type": event_type, **data},
        },
    )


# ─── Presets ──────────────────────────────────────────────────────────────────

class MockPresetListCreateView(APIView):
    """
    GET  /api/presets/  — list all presets (examiner only)
    POST /api/presets/  — create a new preset (examiner only)
    """

    def get(self, request):
        presets = (
            MockPreset.objects
            .filter(owner=request.user)
            .prefetch_related("part_1", "part_2", "part_3")
            .order_by("-created_at")
        )
        return Response(MockPresetSerializer(presets, many=True).data)

    def post(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Only examiners can create presets."}, status=403)
        serializer = MockPresetCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        preset = serializer.save(owner=request.user)
        return Response(MockPresetSerializer(preset).data, status=201)


class MockPresetDeleteView(APIView):
    """
    DELETE /api/presets/<pk>/
    Owner only. Deletes a preset if it is not used by any session.
    """

    def delete(self, request, pk):
        try:
            preset = MockPreset.objects.get(pk=pk)
        except MockPreset.DoesNotExist:
            return Response({"detail": "Preset not found."}, status=404)

        if preset.owner != request.user:
            return Response({"detail": "Only the preset owner can delete it."}, status=403)

        if IELTSMockSession.objects.filter(preset=preset).exists():
            return Response({"detail": "Cannot delete a preset that is used by existing sessions."}, status=400)

        preset.delete()
        return Response(status=204)


# ─── Sessions ─────────────────────────────────────────────────────────────────

class SessionListCreateView(APIView):
    """
    GET  /api/sessions/  — list the current user's sessions (as examiner or candidate)
    POST /api/sessions/  — create a new scheduled session (examiner only)
    """

    def get(self, request):
        qs = (
            _session_qs()
            .filter(Q(examiner=request.user) | Q(candidate=request.user))
            .order_by("-created_at")
        )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response(SessionSerializer(qs, many=True).data)

    def post(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Only examiners can create sessions."}, status=403)

        session_count = IELTSMockSession.objects.filter(examiner=request.user).exclude(status=SessionStatus.CANCELLED).count()
        if session_count >= request.user.max_sessions:
            return Response(
                {"detail": f"Session limit reached. You can have at most {request.user.max_sessions} sessions."},
                status=403,
            )

        serializer = SessionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        session = serializer.save(examiner=request.user)
        audit.info("action=session.create user=%s session=%s timestamp=%s", request.user.pk, session.pk, timezone.now().isoformat())
        session = _session_qs().get(pk=session.pk)
        return Response(SessionSerializer(session).data, status=201)


class SessionDetailView(APIView):
    """
    GET /api/sessions/<id>/  — retrieve a session (participants only)
    """

    def get(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner and request.user != session.candidate:
            return Response({"detail": "You are not a participant of this session."}, status=403)

        return Response(SessionSerializer(session).data)


class AcceptInviteView(APIView):
    """
    POST /api/sessions/accept-invite/  — candidate accepts an invitation token
    The authenticated user must have the Candidate role.
    """
    throttle_scope = "accept_invite"

    def post(self, request):
        if not _is_candidate(request.user):
            return Response({"detail": "Only candidates can accept invites."}, status=403)

        serializer = AcceptInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = serializer.validated_data["session"]
        session.candidate = request.user
        session.invite_accepted_at = timezone.now()
        session.save(update_fields=["candidate", "invite_accepted_at", "updated_at"])

        session = _session_qs().get(pk=session.pk)

        _broadcast(session.pk, "invite.accepted", {
            "session_id": session.pk,
            "candidate": {
                "id": request.user.pk,
                "username": request.user.username,
                "first_name": request.user.first_name,
                "last_name": request.user.last_name,
            },
            "invite_accepted_at": session.invite_accepted_at.isoformat(),
        })

        return Response(SessionSerializer(session).data)


class StartSessionView(APIView):
    """
    POST /api/sessions/<id>/start/
    Examiner starts the session. Creates the 100ms video room.
    Broadcasts: session.started
    """

    def post(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the session examiner can start the session."}, status=403)

        session.start()  # raises ValidationError if not SCHEDULED or no candidate

        try:
            with transaction.atomic():
                session.save(update_fields=["status", "started_at", "updated_at"])
                room_id = create_room(session.pk)
                session.video_room_id = room_id
                session.save(update_fields=["video_room_id", "updated_at"])
        except ValidationError:
            raise  # let DRF handle model validation errors
        except Exception as exc:
            return Response({"detail": f"Failed to create video room: {exc}"}, status=502)

        hms_token = generate_app_token(room_id, request.user.pk, settings.HMS_EXAMINER_ROLE)

        _broadcast(pk, "session.started", {
            "session_id": pk,
            "started_at": session.started_at.isoformat(),
        })
        audit.info("action=session.start user=%s session=%s timestamp=%s", request.user.pk, pk, timezone.now().isoformat())

        session = _session_qs().get(pk=session.pk)
        data = SessionSerializer(session).data
        data["hms_token"] = hms_token
        data["room_id"] = room_id
        return Response(data)


class JoinSessionView(APIView):
    """
    POST /api/sessions/<id>/join/
    Returns a 100ms app token for the authenticated user to join the video call.
    Session must be IN_PROGRESS.
    """

    def post(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner and request.user != session.candidate:
            return Response({"detail": "You are not a participant of this session."}, status=403)

        session.assert_in_progress()

        if not session.video_room_id:
            return Response({"detail": "Video room is not available."}, status=400)

        role = (
            settings.HMS_EXAMINER_ROLE
            if request.user == session.examiner
            else settings.HMS_CANDIDATE_ROLE
        )
        hms_token = generate_app_token(session.video_room_id, request.user.pk, role)

        return Response({"room_id": session.video_room_id, "hms_token": hms_token})


class EndSessionView(APIView):
    """
    POST /api/sessions/<id>/end/
    Examiner ends the session.
    Broadcasts: session.ended
    """

    def post(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the session examiner can end the session."}, status=403)

        session.end()  # validates IN_PROGRESS, sets status=COMPLETED + ended_at
        session.save(update_fields=["status", "ended_at", "updated_at"])

        # Increment examiner's completed session count atomically
        ExaminerProfile.objects.filter(user=session.examiner).update(
            completed_session_count=F("completed_session_count") + 1
        )

        _broadcast(pk, "session.ended", {
            "session_id": pk,
            "ended_at": session.ended_at.isoformat(),
        })
        audit.info("action=session.end user=%s session=%s timestamp=%s", request.user.pk, pk, timezone.now().isoformat())

        session = _session_qs().get(pk=session.pk)
        return Response(SessionSerializer(session).data)


# ─── Session Parts ─────────────────────────────────────────────────────────────

class SessionPartView(APIView):
    """
    GET  /api/sessions/<pk>/parts/        — list all parts (participants)
    POST /api/sessions/<pk>/parts/        — start a part (examiner only)
      Body: {"part": 1|2|3}
    Broadcasts: part.started
    """

    def _get_session(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return None, Response({"detail": "Not found."}, status=404)
        if request.user != session.examiner and request.user != session.candidate:
            return None, Response({"detail": "You are not a participant of this session."}, status=403)
        return session, None

    def get(self, request, pk):
        session, err = self._get_session(request, pk)
        if err:
            return err
        parts = (
            SessionPart.objects
            .filter(session=session)
            .select_related("session")
            .order_by("part")
        )
        return Response(SessionPartSerializer(parts, many=True).data)

    def post(self, request, pk):
        session, err = self._get_session(request, pk)
        if err:
            return err

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can start a part."}, status=403)

        session.assert_in_progress()

        part_num = request.data.get("part")
        if part_num not in (1, 2, 3):
            return Response({"detail": "part must be 1, 2, or 3."}, status=400)

        if SessionPart.objects.filter(session=session, part=part_num).exists():
            return Response({"detail": f"Part {part_num} has already been started."}, status=400)

        part = SessionPart.objects.create(
            session=session,
            part=part_num,
            started_at=_event_time(request),
        )

        _broadcast(pk, "part.started", {
            "part": part_num,
            "part_id": part.pk,
            "started_at": part.started_at.isoformat(),
        })

        return Response(SessionPartSerializer(part).data, status=201)


class EndSessionPartView(APIView):
    """
    POST /api/sessions/<pk>/parts/<part_num>/end/
    End a session part (examiner only).
    Broadcasts: part.ended
    """

    def post(self, request, pk, part_num):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can end a part."}, status=403)

        session.assert_in_progress()

        try:
            part = SessionPart.objects.get(session=session, part=part_num)
        except SessionPart.DoesNotExist:
            return Response({"detail": f"Part {part_num} has not been started."}, status=404)

        if part.ended_at is not None:
            return Response({"detail": f"Part {part_num} has already ended."}, status=400)

        part.ended_at = _event_time(request)
        part.save(update_fields=["ended_at", "updated_at"])

        _broadcast(pk, "part.ended", {
            "part": part_num,
            "part_id": part.pk,
            "ended_at": part.ended_at.isoformat(),
        })

        return Response(SessionPartSerializer(part).data)


# ─── Available Questions ───────────────────────────────────────────────────────

class AvailableQuestionsView(APIView):
    """
    GET /api/sessions/<pk>/parts/<part_num>/available-questions/

    Returns all questions from the session preset's topics for this part,
    annotated with whether each question has been asked in this session.
    Examiner-only. Session must have a preset.

    Response shape per question:
      {
        "session_question_id": <int|null>,   # null if not yet asked
        "asked": <bool>,
        "question": { ...QuestionDetailSerializer fields... }
      }
    """

    def get(self, request, pk, part_num):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Examiner only."}, status=403)

        if not session.preset:
            return Response({"detail": "This session has no preset."}, status=400)

        if part_num not in (1, 2, 3):
            return Response({"detail": "part_num must be 1, 2, or 3."}, status=400)

        part_field = {1: "part_1", 2: "part_2", 3: "part_3"}[part_num]
        topics = getattr(session.preset, part_field).all()

        questions = (
            Question.objects
            .filter(topic__in=topics)
            .select_related("topic")
            .prefetch_related("follow_ups")
            .order_by("topic__name", "pk")
        )

        # Build a set of already-asked question IDs for this session/part
        asked_map = {}  # question_id → session_question_id
        try:
            session_part = SessionPart.objects.get(session=session, part=part_num)
            for sq in SessionQuestion.objects.filter(session_part=session_part):
                asked_map[sq.question_id] = sq.pk
        except SessionPart.DoesNotExist:
            pass

        result = []
        for q in questions:
            sq_id = asked_map.get(q.pk)
            result.append({
                "session_question_id": sq_id,
                "asked": sq_id is not None,
                "question": QuestionDetailSerializer(q).data,
            })

        return Response(result)


# ─── Ask a Question ────────────────────────────────────────────────────────────

class AskQuestionView(APIView):
    """
    POST /api/sessions/<pk>/parts/<part_num>/ask/
    Body: {"question_id": <int>}

    Marks a question as asked (creates SessionQuestion with asked_at=now).
    The SessionPart must already exist (i.e. the part must have been started).
    The question must belong to one of the preset's topics for this part.
    Broadcasts: question.asked
    """

    def post(self, request, pk, part_num):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can ask questions."}, status=403)

        session.assert_in_progress()

        try:
            session_part = SessionPart.objects.get(session=session, part=part_num)
        except SessionPart.DoesNotExist:
            return Response({"detail": f"Part {part_num} has not been started yet."}, status=400)

        question_id = request.data.get("question_id")
        if not question_id:
            return Response({"detail": "question_id is required."}, status=400)

        try:
            question = Question.objects.select_related("topic").prefetch_related("follow_ups").get(pk=question_id)
        except Question.DoesNotExist:
            return Response({"detail": "Question not found."}, status=404)

        # Validate the question belongs to this part's preset topics
        if session.preset:
            part_field = {1: "part_1", 2: "part_2", 3: "part_3"}[part_num]
            topic_ids = set(getattr(session.preset, part_field).values_list("id", flat=True))
            if question.topic_id not in topic_ids:
                return Response(
                    {"detail": "This question does not belong to the preset topics for this part."},
                    status=400,
                )

        # Prevent asking the same question twice in the same part
        if SessionQuestion.objects.filter(session_part=session_part, question=question).exists():
            return Response({"detail": "This question has already been asked in this part."}, status=400)

        from django.db.models import Max
        max_order = SessionQuestion.objects.filter(session_part=session_part).aggregate(m=Max("order"))["m"]
        order = (max_order or 0) + 1
        sq = SessionQuestion.objects.create(
            session_part=session_part,
            question=question,
            order=order,
            asked_at=_event_time(request),
        )

        _broadcast(pk, "question.asked", {
            "session_question_id": sq.pk,
            "part": part_num,
            "order": order,
            "asked_at": sq.asked_at.isoformat(),
            "question": QuestionDetailSerializer(question).data,
        })

        return Response(SessionQuestionSerializer(sq).data, status=201)


# ─── Session Question Actions ─────────────────────────────────────────────────

class SessionQuestionListView(APIView):
    """
    GET /api/sessions/<pk>/parts/<part_num>/questions/
    List all SessionQuestions asked so far in a part (participants only).
    """

    def get(self, request, pk, part_num):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner and request.user != session.candidate:
            return Response({"detail": "You are not a participant of this session."}, status=403)

        try:
            session_part = SessionPart.objects.get(session=session, part=part_num)
        except SessionPart.DoesNotExist:
            return Response([], status=200)

        qs = (
            SessionQuestion.objects
            .filter(session_part=session_part)
            .select_related("question__topic")
            .prefetch_related("question__follow_ups", "session_follow_ups__follow_up", "notes")
            .order_by("order")
        )
        return Response(SessionQuestionSerializer(qs, many=True).data)


class AnswerStartView(APIView):
    """
    POST /api/sessions/<pk>/session-questions/<sq_id>/answer-start/
    Candidate signals they have started answering.
    Broadcasts: question.answer_started
    """

    def post(self, request, pk, sq_id):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.candidate:
            return Response({"detail": "Only the candidate can signal answer start."}, status=403)

        session.assert_in_progress()

        try:
            sq = SessionQuestion.objects.get(pk=sq_id, session_part__session=session)
        except SessionQuestion.DoesNotExist:
            return Response({"detail": "Session question not found."}, status=404)

        if sq.asked_at is None:
            return Response({"detail": "Question has not been asked yet."}, status=400)

        if sq.answer_started_at is not None:
            return Response({"detail": "Answer has already been started."}, status=400)

        sq.answer_started_at = _event_time(request)
        sq.save(update_fields=["answer_started_at", "updated_at"])

        _broadcast(pk, "question.answer_started", {
            "session_question_id": sq_id,
            "answer_started_at": sq.answer_started_at.isoformat(),
        })

        return Response(SessionQuestionSerializer(sq).data)


class EndQuestionView(APIView):
    """
    POST /api/sessions/<pk>/session-questions/<sq_id>/end/
    Examiner ends the current question.
    Broadcasts: question.ended
    """

    def post(self, request, pk, sq_id):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can end a question."}, status=403)

        session.assert_in_progress()

        try:
            sq = SessionQuestion.objects.get(pk=sq_id, session_part__session=session)
        except SessionQuestion.DoesNotExist:
            return Response({"detail": "Session question not found."}, status=404)

        if sq.asked_at is None:
            return Response({"detail": "Question has not been asked yet."}, status=400)

        if sq.ended_at is not None:
            return Response({"detail": "Question has already ended."}, status=400)

        sq.ended_at = _event_time(request)
        sq.save(update_fields=["ended_at", "updated_at"])

        _broadcast(pk, "question.ended", {
            "session_question_id": sq_id,
            "ended_at": sq.ended_at.isoformat(),
        })

        return Response(SessionQuestionSerializer(sq).data)


# ─── Follow-Ups ───────────────────────────────────────────────────────────────

class AskFollowUpView(APIView):
    """
    POST /api/sessions/<pk>/session-questions/<sq_id>/follow-ups/
    Body: {"follow_up_id": <int>}
    Examiner asks a follow-up on the current question.
    Broadcasts: followup.asked
    """

    def post(self, request, pk, sq_id):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can ask follow-ups."}, status=403)

        session.assert_in_progress()

        try:
            sq = SessionQuestion.objects.select_related("question").get(
                pk=sq_id, session_part__session=session
            )
        except SessionQuestion.DoesNotExist:
            return Response({"detail": "Session question not found."}, status=404)

        follow_up_id = request.data.get("follow_up_id")
        if not follow_up_id:
            return Response({"detail": "follow_up_id is required."}, status=400)

        try:
            follow_up = FollowUpQuestion.objects.get(pk=follow_up_id, question=sq.question)
        except FollowUpQuestion.DoesNotExist:
            return Response(
                {"detail": "Follow-up not found or does not belong to this question."},
                status=404,
            )

        sf = SessionFollowUp.objects.create(
            session_question=sq,
            follow_up=follow_up,
            asked_at=_event_time(request),
        )

        _broadcast(pk, "followup.asked", {
            "session_follow_up_id": sf.pk,
            "session_question_id": sq_id,
            "asked_at": sf.asked_at.isoformat(),
            "follow_up": {"id": follow_up.pk, "text": follow_up.text},
        })

        return Response(SessionFollowUpSerializer(sf).data, status=201)


class EndFollowUpView(APIView):
    """
    POST /api/sessions/<pk>/session-follow-ups/<sf_id>/end/
    Examiner ends a follow-up question.
    Broadcasts: followup.ended
    """

    def post(self, request, pk, sf_id):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can end follow-ups."}, status=403)

        session.assert_in_progress()

        try:
            sf = SessionFollowUp.objects.get(
                pk=sf_id,
                session_question__session_part__session=session,
            )
        except SessionFollowUp.DoesNotExist:
            return Response({"detail": "Session follow-up not found."}, status=404)

        if sf.ended_at is not None:
            return Response({"detail": "Follow-up has already ended."}, status=400)

        sf.ended_at = _event_time(request)
        sf.save(update_fields=["ended_at", "updated_at"])

        _broadcast(pk, "followup.ended", {
            "session_follow_up_id": sf_id,
            "session_question_id": sf.session_question_id,
            "ended_at": sf.ended_at.isoformat(),
        })

        return Response(SessionFollowUpSerializer(sf).data)


# ─── Notes ────────────────────────────────────────────────────────────────────

class NoteListCreateView(APIView):
    """
    GET  /api/sessions/<pk>/session-questions/<sq_id>/notes/
    POST /api/sessions/<pk>/session-questions/<sq_id>/notes/
    Body: {"content": "..."}
    Examiner-only.
    Broadcasts on create: note.added
    """

    def _get_sq(self, request, pk, sq_id):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return None, None, Response({"detail": "Not found."}, status=404)
        if request.user != session.examiner:
            return None, None, Response({"detail": "Examiner only."}, status=403)
        try:
            sq = SessionQuestion.objects.get(pk=sq_id, session_part__session=session)
        except SessionQuestion.DoesNotExist:
            return None, None, Response({"detail": "Session question not found."}, status=404)
        return session, sq, None

    def get(self, request, pk, sq_id):
        session, sq, err = self._get_sq(request, pk, sq_id)
        if err:
            return err
        notes = Note.objects.filter(session_question=sq).order_by("created_at")
        return Response(NoteSerializer(notes, many=True).data)

    def post(self, request, pk, sq_id):
        session, sq, err = self._get_sq(request, pk, sq_id)
        if err:
            return err

        content = request.data.get("content", "").strip()
        if not content:
            return Response({"detail": "content is required."}, status=400)
        if len(content) > 1000:
            return Response({"detail": "content must be 1000 characters or fewer."}, status=400)

        note = Note.objects.create(session_question=sq, content=content)

        _broadcast(pk, "note.added", {
            "note_id": note.pk,
            "session_question_id": sq_id,
            "content": content,
            "created_at": note.created_at.isoformat(),
        })

        return Response(NoteSerializer(note).data, status=201)


class NoteDeleteView(APIView):
    """
    DELETE /api/sessions/<pk>/notes/<note_id>/
    Examiner-only. Broadcasts: note.deleted
    """

    def delete(self, request, pk, note_id):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Examiner only."}, status=403)

        try:
            note = Note.objects.get(
                pk=note_id,
                session_question__session_part__session=session,
            )
        except Note.DoesNotExist:
            return Response({"detail": "Note not found."}, status=404)

        sq_id = note.session_question_id
        note.delete()

        _broadcast(pk, "note.deleted", {
            "note_id": note_id,
            "session_question_id": sq_id,
        })

        return Response(status=204)


# ─── Results ──────────────────────────────────────────────────────────────────

class SessionResultView(APIView):
    """
    GET  /api/sessions/<pk>/result/   — get result (examiner always; candidate only if released)
    POST /api/sessions/<pk>/result/   — create or update result + scores (examiner only)
      Body: {"scores": [{"criterion": 1, "band": 7, "feedback": "..."}]}
    """

    def _get_session(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return None, Response({"detail": "Not found."}, status=404)
        if request.user != session.examiner and request.user != session.candidate:
            return None, Response({"detail": "You are not a participant."}, status=403)
        return session, None

    def get(self, request, pk):
        session, err = self._get_session(request, pk)
        if err:
            return err

        try:
            result = SessionResult.objects.prefetch_related("scores").get(session=session)
        except SessionResult.DoesNotExist:
            return Response({"detail": "No result yet."}, status=404)

        if request.user == session.candidate and not result.is_released:
            return Response({"detail": "Result has not been released yet."}, status=403)

        return Response(SessionResultSerializer(result).data)

    def post(self, request, pk):
        session, err = self._get_session(request, pk)
        if err:
            return err

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can submit results."}, status=403)

        serializer = SessionResultWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result, _ = SessionResult.objects.get_or_create(session=session)

        for score_data in serializer.validated_data["scores"]:
            from .models import CriterionScore
            CriterionScore.objects.update_or_create(
                session_result=result,
                criterion=score_data["criterion"],
                defaults={"band": score_data["band"], "feedback": score_data.get("feedback")},
            )

        update_fields = ["overall_band", "updated_at"]
        result.overall_band = result.compute_overall_band()
        if "overall_feedback" in serializer.validated_data:
            result.overall_feedback = serializer.validated_data["overall_feedback"]
            update_fields.append("overall_feedback")
        result.save(update_fields=update_fields)
        audit.info("action=result.submit user=%s session=%s timestamp=%s", request.user.pk, pk, timezone.now().isoformat())

        result = SessionResult.objects.prefetch_related("scores").get(pk=result.pk)
        return Response(SessionResultSerializer(result).data, status=201)


class ReleaseResultView(APIView):
    """
    POST /api/sessions/<pk>/result/release/
    Examiner releases the result to the candidate.
    Broadcasts: result.released
    """

    def post(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can release results."}, status=403)

        try:
            result = SessionResult.objects.prefetch_related("scores").get(session=session)
        except SessionResult.DoesNotExist:
            return Response({"detail": "No result to release. Submit scores first."}, status=400)

        # EDGE-02: Require all 4 criterion scores before release
        existing_criteria = set(result.scores.values_list("criterion", flat=True))
        required_criteria = {c.value for c in SpeakingCriterion}
        missing = required_criteria - existing_criteria
        if missing:
            missing_names = sorted(
                SpeakingCriterion(c).name for c in missing
            )
            return Response(
                {"detail": f"Cannot release: missing scores for {', '.join(missing_names)}"},
                status=400,
            )

        result.is_released = True
        result.released_at = timezone.now()
        result.save(update_fields=["is_released", "released_at", "updated_at"])

        # Append score history record for candidate
        if session.candidate and result.overall_band is not None:
            try:
                candidate_profile = CandidateProfile.objects.get(user=session.candidate)
                ScoreHistory.objects.get_or_create(
                    candidate_profile=candidate_profile,
                    session=session,
                    defaults={"overall_band": result.overall_band},
                )
                candidate_profile.current_speaking_score = result.overall_band
                candidate_profile.save(update_fields=["current_speaking_score", "updated_at"])
            except CandidateProfile.DoesNotExist:
                pass  # Guest candidates created before Phase 4 migration have no profile

        _broadcast(pk, "result.released", {
            "session_id": pk,
            "overall": str(result.overall_band) if result.overall_band else None,
            "overall_feedback": result.overall_feedback,
            "released_at": result.released_at.isoformat(),
            "scores": CriterionScoreSerializer(result.scores.all(), many=True).data,
        })
        audit.info("action=result.release user=%s session=%s timestamp=%s", request.user.pk, pk, timezone.now().isoformat())

        return Response(SessionResultSerializer(result).data)


# ─── Recording ─────────────────────────────────────────────────────────────────

class SessionRecordingView(APIView):
    """
    POST /api/sessions/<pk>/recording/
      Upload a webm audio recording for this session (examiner only).
      Body: multipart/form-data with field `audio_file`.

    GET  /api/sessions/<pk>/recording/
      Retrieve the recording URL and timecodes for every part, question,
      and follow-up (participants only).
    """

    # MultiPartParser handles the file upload POST; JSONParser covers the GET (no body, but
    # keeps DRF happy if content-type isn't set by the client).
    parser_classes = [MultiPartParser, JSONParser]

    def _get_session(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return None, Response({"detail": "Not found."}, status=404)
        if request.user != session.examiner and request.user != session.candidate:
            return None, Response({"detail": "You are not a participant of this session."}, status=403)
        return session, None

    def post(self, request, pk):
        session, err = self._get_session(request, pk)
        if err:
            return err

        if request.user != session.examiner:
            return Response({"detail": "Only the examiner can upload recordings."}, status=403)

        if hasattr(session, "recording"):
            return Response({"detail": "A recording already exists for this session."}, status=400)

        if "audio_file" not in request.FILES:
            return Response({"detail": "audio_file is required."}, status=400)

        # recording_started_at must be an ISO 8601 string sent as a form field alongside
        # the file. Without it, offsets fall back to session.started_at which will be
        # wrong if the client started recording at a different moment.
        recording_started_at = None
        raw_start = request.data.get("recording_started_at")
        if raw_start:
            from django.utils.dateparse import parse_datetime
            recording_started_at = parse_datetime(raw_start)
            if recording_started_at is None:
                return Response(
                    {"detail": "recording_started_at must be a valid ISO 8601 datetime string."},
                    status=400,
                )

        recording = SessionRecording.objects.create(
            session=session,
            audio_file=request.FILES["audio_file"],
            recording_started_at=recording_started_at,
        )

        return Response(
            SessionRecordingSerializer(recording, context={"request": request}).data,
            status=201,
        )

    def get(self, request, pk):
        session, err = self._get_session(request, pk)
        if err:
            return err

        try:
            recording = session.recording
        except SessionRecording.DoesNotExist:
            return Response({"detail": "No recording found for this session."}, status=404)

        return Response(
            SessionRecordingSerializer(recording, context={"request": request}).data
        )


# ─── Share ────────────────────────────────────────────────────────────────────

class CreateShareView(APIView):
    """
    POST /api/sessions/<pk>/share/
    Examiner or candidate creates (or retrieves) a shareable link for a released session.
    """

    def post(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner and request.user != session.candidate:
            return Response({"detail": "You are not a participant of this session."}, status=403)

        # Session must have a released result
        try:
            result = session.result
        except SessionResult.DoesNotExist:
            return Response({"detail": "Session has no result yet."}, status=400)

        if not result.is_released:
            return Response({"detail": "Session result has not been released yet."}, status=400)

        share, created = SessionShare.objects.get_or_create(
            session=session,
            defaults={"created_by": request.user},
        )
        status_code = 201 if created else 200
        return Response(
            {
                "share_token": share.share_token,
                "share_url": f"/api/sessions/shared/{share.share_token}/",
            },
            status=status_code,
        )


class SharedSessionDetailView(APIView):
    """
    GET /api/sessions/shared/<share_token>/
    Public endpoint — no authentication required.
    Returns recording + timeline + band scores + profiles (no feedback, no notes).
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, share_token):
        try:
            share = SessionShare.objects.select_related(
                "session__examiner",
                "session__candidate",
                "session__result",
                "session__recording",
            ).get(share_token=share_token)
        except SessionShare.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        session = share.session
        data = SharedSessionSerializer(session, context={"request": request}).data
        return Response(data)


# ─── Cancel ───────────────────────────────────────────────────────────────────

class CancelSessionView(APIView):
    """
    POST /api/sessions/<pk>/cancel/
    Examiner cancels a SCHEDULED session with no candidate.
    Broadcasts: session.cancelled
    """

    def post(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the session examiner can cancel the session."}, status=403)

        session.cancel()  # raises ValidationError if not cancellable
        session.save(update_fields=["status", "invite_expires_at", "updated_at"])

        _broadcast(session.pk, "session.cancelled", {"session_id": session.pk})

        return Response({"detail": "Session cancelled."})


# ─── AI Feedback ──────────────────────────────────────────────────────────────

class AIFeedbackTriggerView(APIView):
    """
    POST /api/sessions/<id>/ai-feedback/
    Examiner triggers AI feedback transcription on a completed session.
    Returns 202 Accepted with job id and initial status.

    GET /api/sessions/<id>/ai-feedback/
    Examiner or candidate retrieves the latest AI feedback job status and transcript.
    """

    def post(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner:
            return Response({"detail": "Only the session examiner can trigger AI feedback."}, status=403)

        if session.status != SessionStatus.COMPLETED:
            return Response({"detail": "Session must be completed before triggering AI feedback."}, status=400)

        with transaction.atomic():
            # Lock all jobs for this examiner's sessions to prevent race conditions
            existing_jobs = list(
                AIFeedbackJob.objects.select_for_update()
                .filter(session__examiner=request.user)
                .values_list("status", "created_at")
            )

            # Check for in-progress job on THIS session
            if AIFeedbackJob.objects.filter(
                session=session,
                status__in=[AIFeedbackJob.Status.PENDING, AIFeedbackJob.Status.PROCESSING],
            ).exists():
                return Response(
                    {"detail": "An AI feedback job is already in progress for this session."},
                    status=409,
                )

            # Monthly usage limit check
            now = timezone.now()
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            monthly_count = sum(
                1 for status, created_at in existing_jobs
                if created_at >= month_start and status != AIFeedbackJob.Status.FAILED
            )
            limit = settings.AI_FEEDBACK_MONTHLY_LIMIT
            if monthly_count >= limit:
                return Response(
                    {"detail": f"Monthly AI feedback limit reached ({limit}/{limit}). Resets next month."},
                    status=429,
                )

            job = AIFeedbackJob.objects.create(session=session)

        async_task('session.tasks.run_ai_feedback', job.pk)
        return Response({"job_id": job.pk, "status": "Pending"}, status=202)

    def get(self, request, pk):
        try:
            session = _session_qs().get(pk=pk)
        except IELTSMockSession.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != session.examiner and request.user != session.candidate:
            return Response({"detail": "You are not a participant of this session."}, status=403)

        job = AIFeedbackJob.objects.filter(session=session).order_by("-created_at").first()
        if job is None:
            return Response({"detail": "No AI feedback job found for this session."}, status=404)

        return Response({
            "job_id": job.pk,
            "status": job.get_status_display(),
            "transcript": job.transcript,
            "error_message": job.error_message,
        })
