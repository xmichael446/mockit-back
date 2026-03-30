import zoneinfo
from datetime import date

from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from main.models import User
from .models import AvailabilitySlot, BlockedDate
from .serializers import AvailabilitySlotSerializer, BlockedDateSerializer
from .services.availability import compute_available_slots, is_currently_available


def _is_examiner(user):
    return user.role == User.Role.EXAMINER


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
