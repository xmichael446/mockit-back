from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone

from django.utils import timezone

from scheduling.models import AvailabilitySlot, BlockedDate, SessionRequest
from session.models import IELTSMockSession, SessionStatus


def compute_available_slots(examiner_id: int, week_date: date) -> list[dict]:
    """
    Returns a list of 7 day-objects covering the ISO week containing week_date.

    Each day-object:
        {
            "date": "2026-03-30",
            "slots": [
                {
                    "slot_id": <int>,
                    "start": "09:00",
                    "end": "10:00",
                    "status": "available" | "booked" | "blocked"
                },
                ...
            ]
        }

    Status logic (blocked takes priority over booked):
    - "blocked"   — the day appears in the examiner's BlockedDate records
    - "booked"    — an IELTSMockSession (SCHEDULED or IN_PROGRESS) falls within the slot window
    - "available" — neither blocked nor booked
    """
    # Compute the Monday of the week containing week_date
    week_start = week_date - timedelta(days=week_date.weekday())
    week_end = week_start + timedelta(days=7)

    # Fetch all recurring slots for this examiner (ordered by day/time per model Meta)
    slots_qs = AvailabilitySlot.objects.filter(examiner_id=examiner_id)

    # Fetch booked sessions within this week window
    # Note: scheduled_at__isnull=False is required — scheduled_at is nullable (Pitfall 6)
    booked_sessions = IELTSMockSession.objects.filter(
        examiner_id=examiner_id,
        status__in=[SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS],
        scheduled_at__isnull=False,
        scheduled_at__date__gte=week_start,
        scheduled_at__date__lt=week_end,
    ).values_list("scheduled_at", flat=True)
    booked_starts = set(booked_sessions)

    # Fetch accepted session requests within this week window
    accepted_requests = SessionRequest.objects.filter(
        examiner_id=examiner_id,
        status=SessionRequest.Status.ACCEPTED,
        requested_date__gte=week_start,
        requested_date__lt=week_end,
    ).values_list("availability_slot_id", "requested_date")
    accepted_booked = {(slot_id, req_date) for slot_id, req_date in accepted_requests}

    # Fetch blocked dates within this week window
    blocked_dates = set(
        BlockedDate.objects.filter(
            examiner_id=examiner_id,
            date__gte=week_start,
            date__lt=week_end,
        ).values_list("date", flat=True)
    )

    result = []
    for offset in range(7):
        current_day = week_start + timedelta(days=offset)
        day_slots = []

        for slot in slots_qs:
            if slot.day_of_week != current_day.weekday():
                continue

            # Build aware UTC datetimes for slot boundaries (Pitfall 1: must be aware)
            slot_start_dt = datetime.combine(current_day, slot.start_time, tzinfo=dt_timezone.utc)
            slot_end_dt = slot_start_dt + timedelta(hours=1)

            # Determine status — blocked takes priority over booked
            if current_day in blocked_dates:
                status = "blocked"
            elif any(slot_start_dt <= bs < slot_end_dt for bs in booked_starts):
                status = "booked"
            elif (slot.id, current_day) in accepted_booked:
                status = "booked"
            else:
                status = "available"

            day_slots.append({
                "slot_id": slot.id,
                "start": slot.start_time.strftime("%H:%M"),
                "end": slot_end_dt.strftime("%H:%M"),
                "status": status,
            })

        # Sort by start time (already ordered by model Meta, but make explicit)
        day_slots.sort(key=lambda s: s["start"])
        result.append({"date": current_day.isoformat(), "slots": day_slots})

    return result


def is_currently_available(examiner_id: int) -> dict:
    """
    Returns whether the examiner is currently available.

    Response:
        {
            "is_available": bool,
            "current_slot": {"start": "09:00", "day_of_week": 0} | None
        }

    Logic:
    1. If today is a BlockedDate -> False, no slot
    2. Find any AvailabilitySlot covering the current time (start <= now < start+1h)
    3. If no such slot -> False, no slot
    4. If a session (SCHEDULED/IN_PROGRESS) occupies that slot -> False, but slot returned
    5. Otherwise -> True, slot returned
    """
    now = timezone.now()  # UTC-aware
    today = now.date()
    current_time = now.time().replace(second=0, microsecond=0)  # floor to minute

    # Check if today is blocked
    if BlockedDate.objects.filter(examiner_id=examiner_id, date=today).exists():
        return {"is_available": False, "current_slot": None}

    # Find a slot covering now: slot.start_time <= current_time < slot.start_time + 1h
    matching_slot = None
    for slot in AvailabilitySlot.objects.filter(examiner_id=examiner_id, day_of_week=today.weekday()):
        slot_end = (datetime.combine(today, slot.start_time) + timedelta(hours=1)).time()
        if slot.start_time <= current_time < slot_end:
            matching_slot = slot
            break

    if not matching_slot:
        return {"is_available": False, "current_slot": None}

    # Check for a booked session in this slot window
    slot_start_dt = datetime.combine(today, matching_slot.start_time, tzinfo=dt_timezone.utc)
    slot_end_dt = slot_start_dt + timedelta(hours=1)
    is_booked = IELTSMockSession.objects.filter(
        examiner_id=examiner_id,
        status__in=[SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS],
        scheduled_at__gte=slot_start_dt,
        scheduled_at__lt=slot_end_dt,
    ).exists()

    current_slot = {
        "start": matching_slot.start_time.strftime("%H:%M"),
        "day_of_week": matching_slot.day_of_week,
    }

    if is_booked:
        return {"is_available": False, "current_slot": current_slot}

    return {"is_available": True, "current_slot": current_slot}
