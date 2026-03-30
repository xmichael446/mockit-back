from datetime import date, datetime, time
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase

from main.models import User
from scheduling.models import AvailabilitySlot, BlockedDate
from scheduling.services.availability import compute_available_slots, is_currently_available
from session.models import IELTSMockSession, SessionStatus


class TestComputeAvailableSlots(TestCase):
    """Unit tests for compute_available_slots() service function."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner1",
            password="testpass123",
            role=User.Role.EXAMINER,
        )
        # Monday 09:00 and Monday 14:00 slots
        self.slot_0900 = AvailabilitySlot.objects.create(
            examiner=self.examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(9, 0),
        )
        self.slot_1400 = AvailabilitySlot.objects.create(
            examiner=self.examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(14, 0),
        )

    def test_returns_seven_days(self):
        """compute_available_slots returns a list of 7 day-dicts."""
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))  # Monday
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 7)
        for day in result:
            self.assertIn("date", day)
            self.assertIn("slots", day)

    def test_available_slot(self):
        """Monday has 2 slots both with status='available' when no bookings or blocks."""
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        monday = next(d for d in result if d["date"] == "2026-03-30")
        self.assertEqual(len(monday["slots"]), 2)
        for slot in monday["slots"]:
            self.assertEqual(slot["status"], "available")

    def test_booked_slot(self):
        """09:00 slot is booked when a SCHEDULED session falls at 09:00 on that day."""
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            status=SessionStatus.SCHEDULED,
            scheduled_at=datetime(2026, 3, 30, 9, 0, tzinfo=dt_timezone.utc),
        )
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        monday = next(d for d in result if d["date"] == "2026-03-30")
        slot_0900 = next(s for s in monday["slots"] if s["start"] == "09:00")
        slot_1400 = next(s for s in monday["slots"] if s["start"] == "14:00")
        self.assertEqual(slot_0900["status"], "booked")
        self.assertEqual(slot_1400["status"], "available")

    def test_blocked_date(self):
        """All Monday slots are blocked when a BlockedDate exists for that Monday."""
        BlockedDate.objects.create(
            examiner=self.examiner,
            date=date(2026, 3, 30),
        )
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        monday = next(d for d in result if d["date"] == "2026-03-30")
        for slot in monday["slots"]:
            self.assertEqual(slot["status"], "blocked")

    def test_blocked_overrides_booked(self):
        """Blocked status takes priority over booked — day blocked means all slots blocked."""
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            status=SessionStatus.SCHEDULED,
            scheduled_at=datetime(2026, 3, 30, 9, 0, tzinfo=dt_timezone.utc),
        )
        BlockedDate.objects.create(
            examiner=self.examiner,
            date=date(2026, 3, 30),
        )
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        monday = next(d for d in result if d["date"] == "2026-03-30")
        for slot in monday["slots"]:
            self.assertEqual(slot["status"], "blocked")

    def test_no_slots_returns_empty_days(self):
        """Examiner with no AvailabilitySlot rows gets 7 empty day-objects."""
        examiner2 = User.objects.create_user(
            username="examiner2",
            password="testpass123",
            role=User.Role.EXAMINER,
        )
        result = compute_available_slots(examiner2.id, date(2026, 3, 30))
        self.assertEqual(len(result), 7)
        for day in result:
            self.assertEqual(day["slots"], [])

    def test_nullable_scheduled_at_excluded(self):
        """Sessions with scheduled_at=None do not affect slot status."""
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            status=SessionStatus.SCHEDULED,
            scheduled_at=None,
        )
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        monday = next(d for d in result if d["date"] == "2026-03-30")
        for slot in monday["slots"]:
            self.assertEqual(slot["status"], "available")


class TestIsCurrentlyAvailable(TestCase):
    """Unit tests for is_currently_available() service function."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner_avail",
            password="testpass123",
            role=User.Role.EXAMINER,
        )
        # Monday 09:00 slot
        self.slot = AvailabilitySlot.objects.create(
            examiner=self.examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(9, 0),
        )

    def test_available_when_slot_covers_now(self):
        """Returns is_available=True when examiner has a slot covering now, no blocks, no bookings."""
        # 2026-03-30 is a Monday; freeze at 09:30 UTC
        frozen_now = datetime(2026, 3, 30, 9, 30, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=frozen_now):
            result = is_currently_available(self.examiner.id)
        self.assertTrue(result["is_available"])
        self.assertIsNotNone(result["current_slot"])

    def test_unavailable_when_blocked(self):
        """Returns is_available=False when today is a BlockedDate."""
        BlockedDate.objects.create(
            examiner=self.examiner,
            date=date(2026, 3, 30),
        )
        frozen_now = datetime(2026, 3, 30, 9, 30, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=frozen_now):
            result = is_currently_available(self.examiner.id)
        self.assertFalse(result["is_available"])
        self.assertIsNone(result["current_slot"])

    def test_unavailable_when_no_matching_slot(self):
        """Returns is_available=False when no slot covers current time."""
        # Freeze at 12:00 — examiner only has 09:00 slot (09:00-10:00)
        frozen_now = datetime(2026, 3, 30, 12, 0, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=frozen_now):
            result = is_currently_available(self.examiner.id)
        self.assertFalse(result["is_available"])
        self.assertIsNone(result["current_slot"])

    def test_unavailable_when_booked(self):
        """Returns is_available=False when slot exists but session is booked in it."""
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            status=SessionStatus.SCHEDULED,
            scheduled_at=datetime(2026, 3, 30, 9, 0, tzinfo=dt_timezone.utc),
        )
        frozen_now = datetime(2026, 3, 30, 9, 30, tzinfo=dt_timezone.utc)
        with patch("django.utils.timezone.now", return_value=frozen_now):
            result = is_currently_available(self.examiner.id)
        self.assertFalse(result["is_available"])
        # current_slot is NOT None — slot exists but occupied
        self.assertIsNotNone(result["current_slot"])
