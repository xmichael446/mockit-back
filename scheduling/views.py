import zoneinfo
from datetime import date, datetime
from datetime import timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import User
from session.models import IELTSMockSession, SessionStatus
from session.views import _broadcast
from .models import AvailabilitySlot, BlockedDate, SessionRequest
from .serializers import (
    AvailabilitySlotSerializer,
    BlockedDateSerializer,
    SessionRequestRejectSerializer,
    SessionRequestSerializer,
)
from .services.availability import compute_available_slots, is_currently_available, is_slot_available
from scheduling.services.email import (
    notify_new_request,
    notify_request_accepted,
    notify_request_rejected,
)


def _is_examiner(user):
    return user.role == User.Role.EXAMINER


def _is_candidate(user):
    return user.role == User.Role.CANDIDATE


def _validate_slot_available(examiner_id, slot_id, requested_date):
    """Validate that the given slot is available on the requested date."""
    try:
        status = is_slot_available(examiner_id, slot_id, requested_date)
    except ValueError:
        raise ValidationError("This time slot does not exist in the examiner's schedule.")
    if status != "available":
        raise ValidationError(f"This slot is {status} and cannot be booked.")


class AvailabilitySlotListCreateView(APIView):
    def get(self, request):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can view availability slots."}, status=403
            )
        slots = AvailabilitySlot.objects.filter(examiner=request.user)
        serializer = AvailabilitySlotSerializer(slots, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can create availability slots."}, status=403
            )
        serializer = AvailabilitySlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save(examiner=request.user)
        except IntegrityError:
            return Response(
                {"detail": "You already have an availability slot for this day and time."},
                status=400,
            )
        return Response(serializer.data, status=201)


class AvailabilitySlotDetailView(APIView):
    def patch(self, request, pk):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can update availability slots."}, status=403
            )
        slot = get_object_or_404(AvailabilitySlot, pk=pk, examiner=request.user)
        serializer = AvailabilitySlotSerializer(slot, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can delete availability slots."}, status=403
            )
        slot = get_object_or_404(AvailabilitySlot, pk=pk, examiner=request.user)
        slot.delete()
        return Response(status=204)


class BlockedDateListCreateView(APIView):
    def get(self, request):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can view blocked dates."}, status=403
            )
        blocked = BlockedDate.objects.filter(examiner=request.user)
        serializer = BlockedDateSerializer(blocked, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can create blocked dates."}, status=403
            )
        serializer = BlockedDateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(examiner=request.user)
        return Response(serializer.data, status=201)


class BlockedDateDetailView(APIView):
    def delete(self, request, pk):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can delete blocked dates."}, status=403
            )
        blocked = get_object_or_404(BlockedDate, pk=pk, examiner=request.user)
        blocked.delete()
        return Response(status=204)


class ExaminerAvailableSlotsView(APIView):
    def get(self, request, pk):
        get_object_or_404(User, pk=pk, role=User.Role.EXAMINER)

        week_param = request.query_params.get("week")
        if not week_param:
            return Response(
                {"detail": "week query parameter is required."}, status=400
            )
        try:
            week_date = date.fromisoformat(week_param)
        except ValueError:
            return Response(
                {"detail": "Invalid week format. Use YYYY-MM-DD."}, status=400
            )

        result = compute_available_slots(pk, week_date)

        tz_param = request.query_params.get("timezone")
        if tz_param:
            try:
                zoneinfo.ZoneInfo(tz_param)
                # Timezone conversion is informational — result remains in UTC for now
            except (zoneinfo.ZoneInfoNotFoundError, KeyError):
                pass  # Fall back to UTC

        return Response(result)


class ExaminerIsAvailableView(APIView):
    def get(self, request, pk):
        get_object_or_404(User, pk=pk, role=User.Role.EXAMINER)
        result = is_currently_available(pk)
        return Response(result)


class SessionRequestListCreateView(APIView):
    def get(self, request):
        if _is_examiner(request.user):
            qs = SessionRequest.objects.filter(examiner=request.user)
        else:
            qs = SessionRequest.objects.filter(candidate=request.user)

        status_filter = request.query_params.get("status")
        if status_filter is not None:
            qs = qs.filter(status=status_filter)

        serializer = SessionRequestSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not _is_candidate(request.user):
            return Response(
                {"detail": "Only candidates can submit session requests."}, status=403
            )
        serializer = SessionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        availability_slot = serializer.validated_data["availability_slot"]
        requested_date = serializer.validated_data["requested_date"]

        _validate_slot_available(
            availability_slot.examiner_id,
            availability_slot.id,
            requested_date,
        )

        duplicate = SessionRequest.objects.filter(
            candidate=request.user,
            examiner=availability_slot.examiner,
            availability_slot=availability_slot,
            requested_date=requested_date,
            status__in=[SessionRequest.Status.PENDING, SessionRequest.Status.ACCEPTED],
        ).exists()
        if duplicate:
            return Response(
                {"detail": "You already have an active request for this slot and date."},
                status=400,
            )

        serializer.save(candidate=request.user, examiner=availability_slot.examiner)
        notify_new_request(serializer.instance)
        return Response(serializer.data, status=201)


class AcceptRequestView(APIView):
    def post(self, request, pk):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can accept session requests."}, status=403
            )

        with transaction.atomic():
            try:
                req = SessionRequest.objects.select_for_update().get(
                    pk=pk, examiner=request.user
                )
            except SessionRequest.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)

            req.accept()  # raises ValidationError if not PENDING

            scheduled_at = datetime.combine(
                req.requested_date,
                req.availability_slot.start_time,
                tzinfo=dt_timezone.utc,
            )
            session = IELTSMockSession.objects.create(
                examiner=req.examiner,
                candidate=req.candidate,
                scheduled_at=scheduled_at,
            )
            req.session = session
            req.save(update_fields=["status", "session", "updated_at"])

        # Broadcast and notify AFTER atomic block to prevent stale events on rollback
        _broadcast(
            session.pk,
            "session_request.accepted",
            {"session_request_id": req.pk, "session_id": session.pk},
        )
        notify_request_accepted(req)

        return Response(SessionRequestSerializer(req).data)


class RejectRequestView(APIView):
    def post(self, request, pk):
        if not _is_examiner(request.user):
            return Response(
                {"detail": "Only examiners can reject session requests."}, status=403
            )

        req = get_object_or_404(SessionRequest, pk=pk, examiner=request.user)
        serializer = SessionRequestRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        req.reject(serializer.validated_data["rejection_comment"])
        req.save(update_fields=["status", "rejection_comment", "updated_at"])
        notify_request_rejected(req)

        return Response(SessionRequestSerializer(req).data)


class CancelRequestView(APIView):
    def post(self, request, pk):
        try:
            req = SessionRequest.objects.get(pk=pk)
        except SessionRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        if request.user != req.candidate and request.user != req.examiner:
            return Response(
                {"detail": "You are not a participant in this request."}, status=403
            )

        req.cancel()  # raises ValidationError if not PENDING/ACCEPTED
        req.save(update_fields=["status", "updated_at"])

        return Response(SessionRequestSerializer(req).data)
