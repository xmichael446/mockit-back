import re

from django.test import TestCase
from rest_framework.exceptions import ValidationError

from main.models import User
from questions.models import Topic
from session.models import (
    IELTSMockSession,
    MockPreset,
    SessionStatus,
    _generate_invite_token,
)


class SessionStateMachineTests(TestCase):
    """Tests for IELTSMockSession state machine guard and transition methods."""

    def _create_session(self, status=SessionStatus.SCHEDULED, has_candidate=True):
        examiner = User.objects.create_user(
            username=f"examiner_{self.id()}_{status}_{has_candidate}",
            password="testpass123",
            role=User.Role.EXAMINER,
        )
        candidate = None
        if has_candidate:
            candidate = User.objects.create_user(
                username=f"candidate_{self.id()}_{status}_{has_candidate}",
                password="testpass123",
                role=User.Role.CANDIDATE,
            )
        preset = MockPreset.objects.create(name="Test Preset", owner=examiner)
        session = IELTSMockSession.objects.create(
            examiner=examiner,
            candidate=candidate,
            preset=preset,
            status=status,
        )
        return session

    # ── can_start ──

    def test_can_start_scheduled_with_candidate(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=True)
        self.assertTrue(session.can_start())

    def test_can_start_not_scheduled(self):
        session = self._create_session(status=SessionStatus.IN_PROGRESS, has_candidate=True)
        self.assertFalse(session.can_start())

    def test_can_start_no_candidate(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=False)
        self.assertFalse(session.can_start())

    # ── start ──

    def test_start_valid(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=True)
        session.start()
        self.assertEqual(session.status, SessionStatus.IN_PROGRESS)
        self.assertIsNotNone(session.started_at)

    def test_start_invalid_status(self):
        session = self._create_session(status=SessionStatus.IN_PROGRESS, has_candidate=True)
        with self.assertRaises(ValidationError):
            session.start()

    def test_start_no_candidate(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=False)
        with self.assertRaises(ValidationError) as ctx:
            session.start()
        self.assertIn("no candidate", str(ctx.exception).lower())

    # ── can_end ──

    def test_can_end_in_progress(self):
        session = self._create_session(status=SessionStatus.IN_PROGRESS, has_candidate=True)
        self.assertTrue(session.can_end())

    def test_can_end_not_in_progress(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=True)
        self.assertFalse(session.can_end())

    # ── end ──

    def test_end_valid(self):
        session = self._create_session(status=SessionStatus.IN_PROGRESS, has_candidate=True)
        session.end()
        self.assertEqual(session.status, SessionStatus.COMPLETED)
        self.assertIsNotNone(session.ended_at)

    def test_end_invalid(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=True)
        with self.assertRaises(ValidationError):
            session.end()

    # ── assert_in_progress ──

    def test_assert_in_progress_valid(self):
        session = self._create_session(status=SessionStatus.IN_PROGRESS, has_candidate=True)
        # Should not raise
        session.assert_in_progress()

    def test_assert_in_progress_invalid(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=True)
        with self.assertRaises(ValidationError):
            session.assert_in_progress()

    # ── can_join ──

    def test_can_join_in_progress(self):
        session = self._create_session(status=SessionStatus.IN_PROGRESS, has_candidate=True)
        self.assertTrue(session.can_join())

    # ── can_accept_invite ──

    def test_can_accept_invite_scheduled(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=False)
        self.assertTrue(session.can_accept_invite())

    def test_can_accept_invite_not_scheduled(self):
        session = self._create_session(status=SessionStatus.IN_PROGRESS, has_candidate=False)
        self.assertFalse(session.can_accept_invite())

    def test_can_accept_invite_already_accepted(self):
        session = self._create_session(status=SessionStatus.SCHEDULED, has_candidate=True)
        self.assertFalse(session.can_accept_invite())


class InviteTokenTests(TestCase):
    """Tests for the _generate_invite_token function."""

    def test_token_format(self):
        pattern = re.compile(r"^[a-z]{3}-[a-z]{4}$")
        for _ in range(20):
            token = _generate_invite_token()
            self.assertRegex(token, pattern, f"Token '{token}' does not match xxx-yyyy format")

    def test_token_no_digits(self):
        for _ in range(20):
            token = _generate_invite_token()
            self.assertFalse(
                any(c.isdigit() for c in token),
                f"Token '{token}' contains digits",
            )


class PresetImmutabilityTests(TestCase):
    """Tests for MockPreset save/delete immutability when sessions exist."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner_preset_test",
            password="testpass123",
            role=User.Role.EXAMINER,
        )

    def _create_preset_with_session(self):
        preset = MockPreset.objects.create(name="Test Preset", owner=self.examiner)
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=preset,
            status=SessionStatus.SCHEDULED,
        )
        return preset

    def test_preset_save_no_sessions(self):
        preset = MockPreset.objects.create(name="Lonely Preset", owner=self.examiner)
        preset.name = "Updated Preset"
        preset.save()  # Should not raise

    def test_preset_save_with_sessions(self):
        preset = self._create_preset_with_session()
        preset.name = "Modified Name"
        with self.assertRaises(ValidationError):
            preset.save()

    def test_preset_delete_no_sessions(self):
        preset = MockPreset.objects.create(name="Deletable Preset", owner=self.examiner)
        preset.delete()  # Should not raise

    def test_preset_delete_with_sessions(self):
        preset = self._create_preset_with_session()
        with self.assertRaises(ValidationError):
            preset.delete()

    def test_preset_create_always_allowed(self):
        # A brand new preset can always be saved
        preset = MockPreset(name="Brand New Preset", owner=self.examiner)
        preset.save()  # Should not raise
        self.assertIsNotNone(preset.pk)
