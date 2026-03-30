from datetime import date, datetime, time, timedelta
from datetime import timezone as dt_timezone
from unittest.mock import patch

from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from main.models import User
from scheduling.models import AvailabilitySlot, BlockedDate, SessionRequest
from scheduling.services.availability import compute_available_slots, is_currently_available
from session.models import IELTSMockSession, SessionStatus


class TestSessionRequestModel(TestCase):
    """Unit tests for SessionRequest model state machine."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="sr_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="sr_candidate",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.slot = AvailabilitySlot.objects.create(
            examiner=self.examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(9, 0),
        )

    def _make_request(self):
        return SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=date(2026, 3, 30),
        )

    def test_default_status_is_pending(self):
        """SessionRequest created with default status PENDING (status == 1)."""
        req = self._make_request()
        self.assertEqual(req.status, SessionRequest.Status.PENDING)

    def test_accept_from_pending(self):
        """accept() on PENDING request sets status to ACCEPTED (status == 2)."""
        req = self._make_request()
        req.accept()
        self.assertEqual(req.status, SessionRequest.Status.ACCEPTED)

    def test_reject_from_pending(self):
        """reject('reason') on PENDING request sets status to REJECTED (status == 3) and stores rejection_comment."""
        req = self._make_request()
        req.reject("Not available")
        self.assertEqual(req.status, SessionRequest.Status.REJECTED)
        self.assertEqual(req.rejection_comment, "Not available")

    def test_cancel_from_pending(self):
        """cancel() on PENDING request sets status to CANCELLED (status == 4)."""
        req = self._make_request()
        req.cancel()
        self.assertEqual(req.status, SessionRequest.Status.CANCELLED)

    def test_cancel_from_accepted(self):
        """cancel() on ACCEPTED request sets status to CANCELLED (status == 4)."""
        req = self._make_request()
        req.accept()
        req.cancel()
        self.assertEqual(req.status, SessionRequest.Status.CANCELLED)

    def test_accept_raises_if_already_accepted(self):
        """accept() on ACCEPTED request raises ValidationError."""
        req = self._make_request()
        req.accept()
        with self.assertRaises(ValidationError):
            req.accept()

    def test_accept_raises_if_rejected(self):
        """accept() on REJECTED request raises ValidationError."""
        req = self._make_request()
        req.reject("reason")
        with self.assertRaises(ValidationError):
            req.accept()

    def test_reject_raises_if_accepted(self):
        """reject() on ACCEPTED request raises ValidationError."""
        req = self._make_request()
        req.accept()
        with self.assertRaises(ValidationError):
            req.reject("reason")

    def test_cancel_raises_if_rejected(self):
        """cancel() on REJECTED request raises ValidationError."""
        req = self._make_request()
        req.reject("reason")
        with self.assertRaises(ValidationError):
            req.cancel()

    def test_cancel_raises_if_cancelled(self):
        """cancel() on CANCELLED request raises ValidationError."""
        req = self._make_request()
        req.cancel()
        with self.assertRaises(ValidationError):
            req.cancel()


class TestComputeAvailableSlotsWithRequests(TestCase):
    """Unit tests for compute_available_slots() with SessionRequest awareness."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="req_slots_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="req_slots_candidate",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        # Monday 09:00 slot
        self.slot = AvailabilitySlot.objects.create(
            examiner=self.examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(9, 0),
        )

    def _get_monday_slot(self, result):
        monday = next(d for d in result if d["date"] == "2026-03-30")
        return next(s for s in monday["slots"] if s["start"] == "09:00")

    def test_accepted_request_marks_slot_booked(self):
        """Slot with an ACCEPTED SessionRequest for the same date shows status 'booked'."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=date(2026, 3, 30),
        )
        req.accept()
        req.save()
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        slot_status = self._get_monday_slot(result)
        self.assertEqual(slot_status["status"], "booked")

    def test_pending_request_slot_still_available(self):
        """Slot with a PENDING SessionRequest still shows status 'available'."""
        SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=date(2026, 3, 30),
        )
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        slot_status = self._get_monday_slot(result)
        self.assertEqual(slot_status["status"], "available")

    def test_cancelled_request_slot_still_available(self):
        """Slot with a CANCELLED SessionRequest still shows status 'available'."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=date(2026, 3, 30),
        )
        req.cancel()
        req.save()
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        slot_status = self._get_monday_slot(result)
        self.assertEqual(slot_status["status"], "available")

    def test_blocked_date_takes_priority_over_accepted_request(self):
        """Blocked date still takes priority over ACCEPTED request (status 'blocked' not 'booked')."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=date(2026, 3, 30),
        )
        req.accept()
        req.save()
        BlockedDate.objects.create(
            examiner=self.examiner,
            date=date(2026, 3, 30),
        )
        result = compute_available_slots(self.examiner.id, date(2026, 3, 30))
        slot_status = self._get_monday_slot(result)
        self.assertEqual(slot_status["status"], "blocked")


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


# ─── API Integration Tests ────────────────────────────────────────────────────


class TestAvailabilitySlotAPI(TestCase):
    def setUp(self):
        self.examiner = User.objects.create_user(
            username="api_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.examiner_token = Token.objects.create(user=self.examiner)
        self.examiner2 = User.objects.create_user(
            username="api_examiner2",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.examiner2_token = Token.objects.create(user=self.examiner2)
        self.candidate = User.objects.create_user(
            username="api_candidate",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.candidate_token = Token.objects.create(user=self.candidate)
        self.client = APIClient()

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_create_slot(self):
        self._auth(self.examiner_token)
        resp = self.client.post(
            "/api/scheduling/availability/",
            {"day_of_week": 0, "start_time": "09:00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(AvailabilitySlot.objects.count(), 1)

    def test_create_slot_invalid_time_not_on_hour(self):
        self._auth(self.examiner_token)
        resp = self.client.post(
            "/api/scheduling/availability/",
            {"day_of_week": 0, "start_time": "08:30"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_slot_too_early(self):
        self._auth(self.examiner_token)
        resp = self.client.post(
            "/api/scheduling/availability/",
            {"day_of_week": 0, "start_time": "07:00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_slot_too_late(self):
        self._auth(self.examiner_token)
        resp = self.client.post(
            "/api/scheduling/availability/",
            {"day_of_week": 0, "start_time": "22:00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_create_duplicate_slot(self):
        self._auth(self.examiner_token)
        AvailabilitySlot.objects.create(
            examiner=self.examiner, day_of_week=0, start_time=time(9, 0)
        )
        resp = self.client.post(
            "/api/scheduling/availability/",
            {"day_of_week": 0, "start_time": "09:00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_candidate_cannot_create_slot(self):
        self._auth(self.candidate_token)
        resp = self.client.post(
            "/api/scheduling/availability/",
            {"day_of_week": 0, "start_time": "09:00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_list_own_slots(self):
        self._auth(self.examiner_token)
        AvailabilitySlot.objects.create(
            examiner=self.examiner, day_of_week=0, start_time=time(9, 0)
        )
        AvailabilitySlot.objects.create(
            examiner=self.examiner, day_of_week=1, start_time=time(10, 0)
        )
        resp = self.client.get("/api/scheduling/availability/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)

    def test_patch_own_slot(self):
        self._auth(self.examiner_token)
        slot = AvailabilitySlot.objects.create(
            examiner=self.examiner, day_of_week=0, start_time=time(9, 0)
        )
        resp = self.client.patch(
            f"/api/scheduling/availability/{slot.pk}/",
            {"start_time": "10:00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

    def test_patch_other_examiner_slot(self):
        self._auth(self.examiner2_token)
        slot = AvailabilitySlot.objects.create(
            examiner=self.examiner, day_of_week=0, start_time=time(9, 0)
        )
        resp = self.client.patch(
            f"/api/scheduling/availability/{slot.pk}/",
            {"start_time": "10:00"},
            format="json",
        )
        self.assertEqual(resp.status_code, 404)

    def test_delete_slot(self):
        self._auth(self.examiner_token)
        slot = AvailabilitySlot.objects.create(
            examiner=self.examiner, day_of_week=0, start_time=time(9, 0)
        )
        resp = self.client.delete(f"/api/scheduling/availability/{slot.pk}/")
        self.assertEqual(resp.status_code, 204)
        self.assertEqual(AvailabilitySlot.objects.count(), 0)


class TestBlockedDateAPI(TestCase):
    def setUp(self):
        self.examiner = User.objects.create_user(
            username="bd_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.examiner_token = Token.objects.create(user=self.examiner)
        self.candidate = User.objects.create_user(
            username="bd_candidate",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.candidate_token = Token.objects.create(user=self.candidate)
        self.client = APIClient()

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    def test_create_blocked_date(self):
        self._auth(self.examiner_token)
        resp = self.client.post(
            "/api/scheduling/blocked-dates/",
            {"date": "2026-04-01", "reason": "Holiday"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)

    def test_delete_blocked_date(self):
        self._auth(self.examiner_token)
        blocked = BlockedDate.objects.create(
            examiner=self.examiner, date=date(2026, 4, 1), reason="Holiday"
        )
        resp = self.client.delete(f"/api/scheduling/blocked-dates/{blocked.pk}/")
        self.assertEqual(resp.status_code, 204)

    def test_candidate_cannot_create(self):
        self._auth(self.candidate_token)
        resp = self.client.post(
            "/api/scheduling/blocked-dates/",
            {"date": "2026-04-01"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_list_own_blocked_dates(self):
        self._auth(self.examiner_token)
        BlockedDate.objects.create(examiner=self.examiner, date=date(2026, 4, 1))
        BlockedDate.objects.create(examiner=self.examiner, date=date(2026, 4, 2))
        resp = self.client.get("/api/scheduling/blocked-dates/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 2)


class TestAvailableSlotsEndpoint(TestCase):
    def setUp(self):
        self.examiner = User.objects.create_user(
            username="slots_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.examiner_token = Token.objects.create(user=self.examiner)
        AvailabilitySlot.objects.create(
            examiner=self.examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(9, 0),
        )
        self.candidate = User.objects.create_user(
            username="slots_candidate",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.candidate_token = Token.objects.create(user=self.candidate)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.candidate_token.key}")

    def test_returns_seven_days(self):
        resp = self.client.get(
            f"/api/scheduling/examiners/{self.examiner.pk}/available-slots/?week=2026-03-30"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 7)

    def test_missing_week_param(self):
        resp = self.client.get(
            f"/api/scheduling/examiners/{self.examiner.pk}/available-slots/"
        )
        self.assertEqual(resp.status_code, 400)

    def test_invalid_week_format(self):
        resp = self.client.get(
            f"/api/scheduling/examiners/{self.examiner.pk}/available-slots/?week=bad-date"
        )
        self.assertEqual(resp.status_code, 400)

    def test_nonexistent_examiner(self):
        resp = self.client.get(
            "/api/scheduling/examiners/99999/available-slots/?week=2026-03-30"
        )
        self.assertEqual(resp.status_code, 404)

    def test_non_examiner_user_returns_404(self):
        resp = self.client.get(
            f"/api/scheduling/examiners/{self.candidate.pk}/available-slots/?week=2026-03-30"
        )
        self.assertEqual(resp.status_code, 404)


class TestIsAvailableEndpoint(TestCase):
    def setUp(self):
        self.examiner = User.objects.create_user(
            username="isavail_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.examiner_token = Token.objects.create(user=self.examiner)
        self.candidate = User.objects.create_user(
            username="isavail_candidate",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.candidate_token = Token.objects.create(user=self.candidate)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")

    def test_returns_is_available_field(self):
        resp = self.client.get(
            f"/api/scheduling/examiners/{self.examiner.pk}/is-available/"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("is_available", resp.data)

    def test_non_examiner_returns_404(self):
        resp = self.client.get(
            f"/api/scheduling/examiners/{self.candidate.pk}/is-available/"
        )
        self.assertEqual(resp.status_code, 404)


def _next_monday():
    """Return the next Monday (never today even if today is Monday)."""
    today = date.today()
    days_ahead = (7 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


class TestSessionRequestAPI(TestCase):
    def setUp(self):
        self.examiner = User.objects.create_user(
            username="req_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.examiner_token = Token.objects.create(user=self.examiner)
        self.candidate = User.objects.create_user(
            username="req_candidate",
            password="testpass123",
            role=User.Role.CANDIDATE,
            is_verified=True,
        )
        self.candidate_token = Token.objects.create(user=self.candidate)
        self.other_user = User.objects.create_user(
            username="other_user",
            password="testpass123",
            role=User.Role.CANDIDATE,
            is_verified=True,
        )
        self.other_token = Token.objects.create(user=self.other_user)
        self.client = APIClient()

        # Monday 09:00 slot — DayOfWeek.MON == 0
        self.slot = AvailabilitySlot.objects.create(
            examiner=self.examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(9, 0),
        )
        self.next_monday = _next_monday()

    def _auth(self, token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    # ── Submit tests ──────────────────────────────────────────────────────────

    def test_submit_request(self):
        """Candidate submitting a valid request returns 201 with status=PENDING."""
        self._auth(self.candidate_token)
        resp = self.client.post(
            "/api/scheduling/requests/",
            {
                "availability_slot": self.slot.pk,
                "requested_date": self.next_monday.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["status"], SessionRequest.Status.PENDING)
        self.assertEqual(SessionRequest.objects.count(), 1)

    def test_submit_by_examiner(self):
        """Examiner attempting to submit a request returns 403."""
        self._auth(self.examiner_token)
        resp = self.client.post(
            "/api/scheduling/requests/",
            {
                "availability_slot": self.slot.pk,
                "requested_date": self.next_monday.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_submit_booked_slot(self):
        """Submitting a request for a booked slot returns 400."""
        # Create an accepted request first to mark slot as booked
        req = SessionRequest.objects.create(
            candidate=self.other_user,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )
        req.accept()
        req.save()

        self._auth(self.candidate_token)
        resp = self.client.post(
            "/api/scheduling/requests/",
            {
                "availability_slot": self.slot.pk,
                "requested_date": self.next_monday.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_submit_weekday_mismatch(self):
        """Submitting a request where date weekday != slot day_of_week returns 400."""
        self._auth(self.candidate_token)
        # next_monday is Monday (weekday=0); slot is also Monday — use Tuesday instead
        next_tuesday = self.next_monday + timedelta(days=1)
        resp = self.client.post(
            "/api/scheduling/requests/",
            {
                "availability_slot": self.slot.pk,
                "requested_date": next_tuesday.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_submit_duplicate(self):
        """Submitting a duplicate active request for the same slot+date returns 400."""
        # First request
        SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )

        self._auth(self.candidate_token)
        resp = self.client.post(
            "/api/scheduling/requests/",
            {
                "availability_slot": self.slot.pk,
                "requested_date": self.next_monday.isoformat(),
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    # ── List tests ────────────────────────────────────────────────────────────

    def test_list_examiner(self):
        """GET by examiner returns only requests addressed to them."""
        SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )
        # Another request for a different examiner should not appear
        other_examiner = User.objects.create_user(
            username="other_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        other_slot = AvailabilitySlot.objects.create(
            examiner=other_examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(10, 0),
        )
        SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=other_examiner,
            availability_slot=other_slot,
            requested_date=self.next_monday,
        )

        self._auth(self.examiner_token)
        resp = self.client.get("/api/scheduling/requests/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["examiner"], self.examiner.pk)

    def test_list_candidate(self):
        """GET by candidate returns only their own requests."""
        SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )
        # Other user's request should not appear
        other_examiner = User.objects.create_user(
            username="other_examiner2",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        other_slot = AvailabilitySlot.objects.create(
            examiner=other_examiner,
            day_of_week=AvailabilitySlot.DayOfWeek.MON,
            start_time=time(10, 0),
        )
        SessionRequest.objects.create(
            candidate=self.other_user,
            examiner=other_examiner,
            availability_slot=other_slot,
            requested_date=self.next_monday,
        )

        self._auth(self.candidate_token)
        resp = self.client.get("/api/scheduling/requests/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["candidate"], self.candidate.pk)

    def test_list_filter_status(self):
        """GET ?status=1 filters requests by status PENDING."""
        pending_req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )
        # Create a rejected request for same candidate
        rejected_req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday + timedelta(weeks=1),
        )
        rejected_req.reject("Not available")
        rejected_req.save()

        self._auth(self.candidate_token)
        resp = self.client.get("/api/scheduling/requests/?status=1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)
        self.assertEqual(resp.data[0]["id"], pending_req.pk)

    # ── Accept tests ──────────────────────────────────────────────────────────

    def test_accept_creates_session(self):
        """POST accept by examiner creates IELTSMockSession with correct scheduled_at."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )

        self._auth(self.examiner_token)
        resp = self.client.post(f"/api/scheduling/requests/{req.pk}/accept/")
        self.assertEqual(resp.status_code, 200)

        req.refresh_from_db()
        self.assertEqual(req.status, SessionRequest.Status.ACCEPTED)
        self.assertIsNotNone(req.session)

        session = req.session
        self.assertEqual(session.examiner, self.examiner)
        self.assertEqual(session.candidate, self.candidate)
        self.assertEqual(session.status, SessionStatus.SCHEDULED)

        expected_scheduled_at = datetime.combine(
            self.next_monday, self.slot.start_time, tzinfo=dt_timezone.utc
        )
        self.assertEqual(session.scheduled_at, expected_scheduled_at)

    def test_accept_by_candidate(self):
        """POST accept by candidate returns 403."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )

        self._auth(self.candidate_token)
        resp = self.client.post(f"/api/scheduling/requests/{req.pk}/accept/")
        self.assertEqual(resp.status_code, 403)

    def test_accept_already_accepted(self):
        """POST accept on an already-accepted request returns 400 (state machine guard)."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )
        # Accept once via direct model call
        req.accept()
        session = IELTSMockSession.objects.create(
            examiner=req.examiner,
            candidate=req.candidate,
            scheduled_at=datetime.combine(
                req.requested_date, self.slot.start_time, tzinfo=dt_timezone.utc
            ),
        )
        req.session = session
        req.save()

        self._auth(self.examiner_token)
        resp = self.client.post(f"/api/scheduling/requests/{req.pk}/accept/")
        self.assertEqual(resp.status_code, 400)

    # ── Reject tests ──────────────────────────────────────────────────────────

    def test_reject_with_comment(self):
        """POST reject with rejection_comment sets status=REJECTED."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )

        self._auth(self.examiner_token)
        resp = self.client.post(
            f"/api/scheduling/requests/{req.pk}/reject/",
            {"rejection_comment": "Not available on this date"},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)

        req.refresh_from_db()
        self.assertEqual(req.status, SessionRequest.Status.REJECTED)
        self.assertEqual(req.rejection_comment, "Not available on this date")

    def test_reject_without_comment(self):
        """POST reject without rejection_comment returns 400."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )

        self._auth(self.examiner_token)
        resp = self.client.post(
            f"/api/scheduling/requests/{req.pk}/reject/",
            {},
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    # ── Cancel tests ──────────────────────────────────────────────────────────

    def test_cancel_by_candidate(self):
        """POST cancel by candidate on ACCEPTED request sets status=CANCELLED."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )
        req.accept()
        session = IELTSMockSession.objects.create(
            examiner=req.examiner,
            candidate=req.candidate,
            scheduled_at=datetime.combine(
                req.requested_date, self.slot.start_time, tzinfo=dt_timezone.utc
            ),
        )
        req.session = session
        req.save()

        self._auth(self.candidate_token)
        resp = self.client.post(f"/api/scheduling/requests/{req.pk}/cancel/")
        self.assertEqual(resp.status_code, 200)

        req.refresh_from_db()
        self.assertEqual(req.status, SessionRequest.Status.CANCELLED)

    def test_cancel_by_examiner(self):
        """POST cancel by examiner on ACCEPTED request sets status=CANCELLED."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )
        req.accept()
        session = IELTSMockSession.objects.create(
            examiner=req.examiner,
            candidate=req.candidate,
            scheduled_at=datetime.combine(
                req.requested_date, self.slot.start_time, tzinfo=dt_timezone.utc
            ),
        )
        req.session = session
        req.save()

        self._auth(self.examiner_token)
        resp = self.client.post(f"/api/scheduling/requests/{req.pk}/cancel/")
        self.assertEqual(resp.status_code, 200)

        req.refresh_from_db()
        self.assertEqual(req.status, SessionRequest.Status.CANCELLED)

    def test_cancel_unrelated_user(self):
        """POST cancel by an unrelated user returns 403."""
        req = SessionRequest.objects.create(
            candidate=self.candidate,
            examiner=self.examiner,
            availability_slot=self.slot,
            requested_date=self.next_monday,
        )

        self._auth(self.other_token)
        resp = self.client.post(f"/api/scheduling/requests/{req.pk}/cancel/")
        self.assertEqual(resp.status_code, 403)
