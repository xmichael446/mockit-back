import re
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from main.models import CandidateProfile, User
from questions.models import Topic
from session.models import (
    CriterionScore,
    IELTSMockSession,
    MockPreset,
    SessionResult,
    SessionStatus,
    SpeakingCriterion,
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


class SessionStartTransactionTests(TestCase):
    """Tests that session start rolls back on room creation failure (EDGE-01)."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner_tx_test",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="candidate_tx_test",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.preset = MockPreset.objects.create(name="Test Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner,
            candidate=self.candidate,
            preset=self.preset,
        )

    @patch("session.views.create_room", side_effect=Exception("HMS API down"))
    def test_rollback_on_room_failure(self, mock_create_room):
        """If create_room() raises, session status must remain SCHEDULED."""
        client = APIClient()
        client.force_authenticate(user=self.examiner)
        response = client.post(f"/api/sessions/{self.session.pk}/start/")
        self.assertEqual(response.status_code, 502)

        # Reload from DB -- status must still be SCHEDULED
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.SCHEDULED)
        self.assertIsNone(self.session.started_at)

    @patch("session.views.create_room", return_value="room-123")
    @patch("session.views.generate_app_token", return_value="token-abc")
    def test_successful_start_commits(self, mock_token, mock_room):
        """Successful start commits status + room_id."""
        client = APIClient()
        client.force_authenticate(user=self.examiner)
        response = client.post(f"/api/sessions/{self.session.pk}/start/")
        self.assertEqual(response.status_code, 200)

        self.session.refresh_from_db()
        self.assertEqual(self.session.status, SessionStatus.IN_PROGRESS)
        self.assertEqual(self.session.video_room_id, "room-123")
        self.assertIsNotNone(self.session.started_at)

    @patch("session.views.create_room", side_effect=Exception("HMS API down"))
    @patch("session.views._broadcast")
    def test_no_broadcast_on_failure(self, mock_broadcast, mock_create_room):
        """_broadcast must NOT be called if room creation fails."""
        client = APIClient()
        client.force_authenticate(user=self.examiner)
        response = client.post(f"/api/sessions/{self.session.pk}/start/")
        self.assertEqual(response.status_code, 502)
        mock_broadcast.assert_not_called()


class ReleaseResultScoreUpdateTests(TestCase):
    """Tests for CandidateProfile.current_speaking_score auto-update on result release."""

    def _create_full_session_with_result(self, candidate=None, has_candidate_profile=True):
        """Helper: create examiner, optional candidate, session, result with all 4 scores."""
        examiner = User.objects.create_user(
            username=f"examiner_release_{self.id()}",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        if candidate is None and has_candidate_profile:
            candidate = User.objects.create_user(
                username=f"candidate_release_{self.id()}",
                password="testpass123",
                role=User.Role.CANDIDATE,
            )
            # CandidateProfile auto-created by signal — verify it exists
            CandidateProfile.objects.get_or_create(user=candidate)

        preset = MockPreset.objects.create(name="Release Test Preset", owner=examiner)
        session = IELTSMockSession.objects.create(
            examiner=examiner,
            candidate=candidate,
            preset=preset,
            status=SessionStatus.COMPLETED,
        )
        result = SessionResult.objects.create(
            session=session,
            overall_band=Decimal("7.0"),
            is_released=False,
        )
        for criterion in SpeakingCriterion:
            CriterionScore.objects.create(
                session_result=result,
                criterion=criterion.value,
                band=7,
            )
        return examiner, candidate, session, result

    @patch("session.views._broadcast")
    def test_release_updates_candidate_current_speaking_score(self, mock_broadcast):
        """After releasing a result, candidate's current_speaking_score equals overall_band."""
        examiner, candidate, session, result = self._create_full_session_with_result()
        client = APIClient()
        client.force_authenticate(user=examiner)

        response = client.post(f"/api/sessions/{session.pk}/result/release/")
        self.assertEqual(response.status_code, 200)

        profile = CandidateProfile.objects.get(user=candidate)
        self.assertEqual(profile.current_speaking_score, result.overall_band)

    @patch("session.views._broadcast")
    def test_release_no_candidate_profile_no_error(self, mock_broadcast):
        """Releasing result for candidate without CandidateProfile does not error."""
        examiner = User.objects.create_user(
            username=f"examiner_noprofile_{self.id()}",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        guest = User.objects.create_user(
            username=f"guest_noprofile_{self.id()}",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        # Remove any auto-created profile so guest has no profile
        CandidateProfile.objects.filter(user=guest).delete()

        preset = MockPreset.objects.create(name="No Profile Preset", owner=examiner)
        session = IELTSMockSession.objects.create(
            examiner=examiner,
            candidate=guest,
            preset=preset,
            status=SessionStatus.COMPLETED,
        )
        result = SessionResult.objects.create(
            session=session,
            overall_band=Decimal("6.5"),
            is_released=False,
        )
        for criterion in SpeakingCriterion:
            CriterionScore.objects.create(
                session_result=result,
                criterion=criterion.value,
                band=6,
            )

        client = APIClient()
        client.force_authenticate(user=examiner)
        response = client.post(f"/api/sessions/{session.pk}/result/release/")
        self.assertEqual(response.status_code, 200)

    @patch("session.views._broadcast")
    def test_release_no_candidate_no_error(self, mock_broadcast):
        """Releasing result for session with candidate=None does not error."""
        examiner = User.objects.create_user(
            username=f"examiner_nocandidate_{self.id()}",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        preset = MockPreset.objects.create(name="No Candidate Preset", owner=examiner)
        session = IELTSMockSession.objects.create(
            examiner=examiner,
            candidate=None,
            preset=preset,
            status=SessionStatus.COMPLETED,
        )
        result = SessionResult.objects.create(
            session=session,
            overall_band=Decimal("5.0"),
            is_released=False,
        )
        for criterion in SpeakingCriterion:
            CriterionScore.objects.create(
                session_result=result,
                criterion=criterion.value,
                band=5,
            )

        client = APIClient()
        client.force_authenticate(user=examiner)
        response = client.post(f"/api/sessions/{session.pk}/result/release/")
        self.assertEqual(response.status_code, 200)

    @patch("session.views._broadcast")
    def test_re_release_updates_current_speaking_score(self, mock_broadcast):
        """Re-releasing a result (idempotent) still updates current_speaking_score correctly."""
        examiner, candidate, session, result = self._create_full_session_with_result()
        client = APIClient()
        client.force_authenticate(user=examiner)

        # First release
        response = client.post(f"/api/sessions/{session.pk}/result/release/")
        self.assertEqual(response.status_code, 200)

        profile = CandidateProfile.objects.get(user=candidate)
        self.assertEqual(profile.current_speaking_score, result.overall_band)

        # Second release (idempotent) — should still succeed and keep score correct
        response = client.post(f"/api/sessions/{session.pk}/result/release/")
        self.assertEqual(response.status_code, 200)

        profile.refresh_from_db()
        self.assertEqual(profile.current_speaking_score, result.overall_band)
