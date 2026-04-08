import re
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from session.tasks import run_ai_feedback  # noqa: E402 — imported for task tests
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from main.models import CandidateProfile, User
from questions.models import IELTSSpeakingPart, Question, Topic
from session.models import (
    AIFeedbackJob,
    CriterionScore,
    IELTSMockSession,
    MockPreset,
    ScoreSource,
    SessionRecording,
    SessionResult,
    SessionShare,
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


# ─── Helpers for share/cancel tests ─────────────────────────────────────────

def _create_released_session(suffix=""):
    """Build a completed, released session with scores and a dummy recording."""
    examiner = User.objects.create_user(
        username=f"examiner_share{suffix}",
        password="testpass123",
        role=User.Role.EXAMINER,
        is_verified=True,
    )
    candidate = User.objects.create_user(
        username=f"candidate_share{suffix}",
        password="testpass123",
        role=User.Role.CANDIDATE,
    )
    preset = MockPreset.objects.create(name="Share Preset", owner=examiner)
    session = IELTSMockSession.objects.create(
        examiner=examiner,
        candidate=candidate,
        preset=preset,
        status=SessionStatus.COMPLETED,
        scheduled_at=timezone.now() - timezone.timedelta(hours=2),
    )
    result = SessionResult.objects.create(
        session=session,
        overall_band=Decimal("7.0"),
        is_released=True,
        released_at=timezone.now(),
    )
    for criterion in SpeakingCriterion:
        CriterionScore.objects.create(
            session_result=result,
            criterion=criterion.value,
            band=7,
            feedback="Some feedback",
        )
    return examiner, candidate, session, result


# ─── TestCreateShare ─────────────────────────────────────────────────────────

class TestCreateShare(TestCase):
    """Tests for POST /api/sessions/{pk}/share/"""

    def setUp(self):
        self.examiner, self.candidate, self.session, self.result = _create_released_session("_cs")
        self.examiner_token, _ = Token.objects.get_or_create(user=self.examiner)
        self.candidate_token, _ = Token.objects.get_or_create(user=self.candidate)

    @patch("session.views._broadcast")
    def test_examiner_can_share_released_session(self, mock_broadcast):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/share/")
        self.assertEqual(response.status_code, 201)
        self.assertIn("share_token", response.data)
        self.assertIn("share_url", response.data)

    @patch("session.views._broadcast")
    def test_candidate_can_share_released_session(self, mock_broadcast):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.candidate_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/share/")
        self.assertEqual(response.status_code, 201)
        self.assertIn("share_token", response.data)

    @patch("session.views._broadcast")
    def test_share_unreleased_session_returns_400(self, mock_broadcast):
        self.result.is_released = False
        self.result.save()
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/share/")
        self.assertEqual(response.status_code, 400)

    def test_share_by_non_participant_returns_403(self):
        outsider = User.objects.create_user(
            username="outsider_share",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        token, _ = Token.objects.get_or_create(user=outsider)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/share/")
        self.assertEqual(response.status_code, 403)

    @patch("session.views._broadcast")
    def test_second_share_is_idempotent(self, mock_broadcast):
        """Second POST returns 200 with the same token as the first POST (201)."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        r1 = client.post(f"/api/sessions/{self.session.pk}/share/")
        r2 = client.post(f"/api/sessions/{self.session.pk}/share/")
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.data["share_token"], r2.data["share_token"])


# ─── TestSharedSessionDetail ─────────────────────────────────────────────────

class TestSharedSessionDetail(TestCase):
    """Tests for GET /api/sessions/shared/{token}/"""

    def setUp(self):
        self.examiner, self.candidate, self.session, self.result = _create_released_session("_ssd")
        self.share = SessionShare.objects.create(
            session=self.session,
            created_by=self.examiner,
        )

    def test_public_access_returns_200(self):
        client = APIClient()
        response = client.get(f"/api/sessions/shared/{self.share.share_token}/")
        self.assertEqual(response.status_code, 200)

    def test_response_contains_scores_and_overall_band(self):
        client = APIClient()
        response = client.get(f"/api/sessions/shared/{self.share.share_token}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("scores", response.data)
        self.assertIn("overall_band", response.data)
        self.assertEqual(len(response.data["scores"]), 4)

    def test_scores_do_not_contain_feedback(self):
        """Feedback field must NOT be present in shared scores."""
        client = APIClient()
        response = client.get(f"/api/sessions/shared/{self.share.share_token}/")
        for score in response.data["scores"]:
            self.assertNotIn("feedback", score)

    def test_response_contains_examiner_and_candidate(self):
        client = APIClient()
        response = client.get(f"/api/sessions/shared/{self.share.share_token}/")
        self.assertIn("examiner", response.data)
        self.assertIn("candidate", response.data)

    def test_invalid_token_returns_404(self):
        client = APIClient()
        response = client.get("/api/sessions/shared/invalid-token/")
        self.assertEqual(response.status_code, 404)

    def test_recording_is_none_when_no_recording_exists(self):
        client = APIClient()
        response = client.get(f"/api/sessions/shared/{self.share.share_token}/")
        self.assertIsNone(response.data["recording"])


# ─── TestCancelSession ───────────────────────────────────────────────────────

class TestCancelSession(TestCase):
    """Tests for POST /api/sessions/{pk}/cancel/"""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner_cancel",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.token, _ = Token.objects.get_or_create(user=self.examiner)
        self.preset = MockPreset.objects.create(name="Cancel Preset", owner=self.examiner)

    def _make_session(self, status=SessionStatus.SCHEDULED, has_candidate=False):
        candidate = None
        if has_candidate:
            candidate = User.objects.create_user(
                username=f"cand_cancel_{status}_{has_candidate}",
                password="testpass123",
                role=User.Role.CANDIDATE,
            )
        return IELTSMockSession.objects.create(
            examiner=self.examiner,
            candidate=candidate,
            preset=self.preset,
            status=status,
            scheduled_at=timezone.now() + timezone.timedelta(hours=1),
        )

    @patch("session.views._broadcast")
    def test_cancel_scheduled_no_candidate_returns_200(self, mock_broadcast):
        session = self._make_session(status=SessionStatus.SCHEDULED, has_candidate=False)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = client.post(f"/api/sessions/{session.pk}/cancel/")
        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.status, SessionStatus.CANCELLED)

    @patch("session.views._broadcast")
    def test_cancel_broadcasts_session_cancelled(self, mock_broadcast):
        session = self._make_session(status=SessionStatus.SCHEDULED, has_candidate=False)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        client.post(f"/api/sessions/{session.pk}/cancel/")
        mock_broadcast.assert_called_once_with(session.pk, "session.cancelled", {"session_id": session.pk})

    @patch("session.views._broadcast")
    def test_cancel_expires_invite(self, mock_broadcast):
        session = self._make_session(status=SessionStatus.SCHEDULED, has_candidate=False)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        client.post(f"/api/sessions/{session.pk}/cancel/")
        session.refresh_from_db()
        self.assertIsNotNone(session.invite_expires_at)
        self.assertLessEqual(session.invite_expires_at, timezone.now())

    def test_cancel_session_with_candidate_returns_400(self):
        session = self._make_session(status=SessionStatus.SCHEDULED, has_candidate=True)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = client.post(f"/api/sessions/{session.pk}/cancel/")
        self.assertEqual(response.status_code, 400)

    def test_cancel_in_progress_session_returns_400(self):
        session = self._make_session(status=SessionStatus.IN_PROGRESS, has_candidate=True)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = client.post(f"/api/sessions/{session.pk}/cancel/")
        self.assertEqual(response.status_code, 400)

    def test_cancel_by_non_examiner_returns_403(self):
        """Non-examiner (outsider) cannot cancel someone else's session."""
        session = self._make_session(status=SessionStatus.SCHEDULED, has_candidate=False)
        outsider = User.objects.create_user(
            username="outsider_cancel",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        token, _ = Token.objects.get_or_create(user=outsider)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = client.post(f"/api/sessions/{session.pk}/cancel/")
        self.assertEqual(response.status_code, 403)


# ─── TestMaxSessionsExcludesCancelled ────────────────────────────────────────

class TestMaxSessionsExcludesCancelled(TestCase):
    """Cancelled sessions must not count toward max_sessions."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner_maxsess",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
            max_sessions=2,
        )
        self.token, _ = Token.objects.get_or_create(user=self.examiner)
        self.preset = MockPreset.objects.create(name="Max Sessions Preset", owner=self.examiner)

    @patch("session.views._broadcast")
    def test_cancelled_session_does_not_count(self, mock_broadcast):
        """Create max sessions, cancel one, then creating another succeeds."""
        future = timezone.now() + timezone.timedelta(hours=1)
        future2 = timezone.now() + timezone.timedelta(hours=2)
        future3 = timezone.now() + timezone.timedelta(hours=3)

        # Create 2 sessions (fills the limit)
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=self.preset,
            status=SessionStatus.SCHEDULED,
            scheduled_at=future,
        )
        s2 = IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=self.preset,
            status=SessionStatus.SCHEDULED,
            scheduled_at=future2,
        )

        # Cancel s2
        s2.cancel()
        s2.save(update_fields=["status", "invite_expires_at", "updated_at"])

        # Now create a new session via API — should succeed because s2 is cancelled
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = client.post("/api/sessions/", {
            "scheduled_at": future3.isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 201)

    @patch("session.views._broadcast")
    def test_at_limit_without_cancellations_blocked(self, mock_broadcast):
        """At the limit with no cancellations, creating another session returns 403."""
        future = timezone.now() + timezone.timedelta(hours=1)
        future2 = timezone.now() + timezone.timedelta(hours=2)
        future3 = timezone.now() + timezone.timedelta(hours=3)

        # Fill the limit with active sessions
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=self.preset,
            status=SessionStatus.SCHEDULED,
            scheduled_at=future,
        )
        IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=self.preset,
            status=SessionStatus.SCHEDULED,
            scheduled_at=future2,
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        response = client.post("/api/sessions/", {
            "scheduled_at": future3.isoformat(),
        }, format="json")
        self.assertEqual(response.status_code, 403)


# ─── CriterionScoreSourceTests ───────────────────────────────────────────────

class CriterionScoreSourceTests(TestCase):
    """Tests for ScoreSource enum, CriterionScore.source field, and compute_overall_band filtering."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner_scoresource",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="candidate_scoresource",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.preset = MockPreset.objects.create(name="ScoreSource Test Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner,
            candidate=self.candidate,
            preset=self.preset,
            status=SessionStatus.COMPLETED,
        )
        self.result = SessionResult.objects.create(
            session=self.session,
            overall_band=None,
            is_released=False,
        )

    # ── ScoreSource enum values ──

    def test_score_source_examiner_equals_1(self):
        self.assertEqual(ScoreSource.EXAMINER, 1)

    def test_score_source_ai_equals_2(self):
        self.assertEqual(ScoreSource.AI, 2)

    # ── CriterionScore default source ──

    def test_criterion_score_default_source_is_examiner(self):
        score = CriterionScore.objects.create(
            session_result=self.result,
            criterion=SpeakingCriterion.FC,
            band=7,
        )
        self.assertEqual(score.source, ScoreSource.EXAMINER)

    def test_criterion_score_can_be_created_with_ai_source(self):
        score = CriterionScore.objects.create(
            session_result=self.result,
            criterion=SpeakingCriterion.FC,
            band=6,
            source=ScoreSource.AI,
        )
        self.assertEqual(score.source, ScoreSource.AI)

    # ── unique_together with source ──

    def test_examiner_and_ai_scores_for_same_criterion_can_coexist(self):
        """EXAMINER and AI scores for same result+criterion should not conflict."""
        from django.db import IntegrityError
        CriterionScore.objects.create(
            session_result=self.result,
            criterion=SpeakingCriterion.FC,
            band=7,
            source=ScoreSource.EXAMINER,
        )
        # This should NOT raise
        CriterionScore.objects.create(
            session_result=self.result,
            criterion=SpeakingCriterion.FC,
            band=6,
            source=ScoreSource.AI,
        )
        self.assertEqual(
            CriterionScore.objects.filter(session_result=self.result, criterion=SpeakingCriterion.FC).count(),
            2,
        )

    def test_duplicate_source_for_same_result_criterion_raises_integrity_error(self):
        """Two scores with same result+criterion+source must raise IntegrityError."""
        from django.db import IntegrityError
        CriterionScore.objects.create(
            session_result=self.result,
            criterion=SpeakingCriterion.FC,
            band=7,
            source=ScoreSource.EXAMINER,
        )
        with self.assertRaises(IntegrityError):
            CriterionScore.objects.create(
                session_result=self.result,
                criterion=SpeakingCriterion.FC,
                band=8,
                source=ScoreSource.EXAMINER,
            )

    # ── compute_overall_band filtering ──

    def test_compute_overall_band_with_only_examiner_scores(self):
        """Correct band computed from 4 EXAMINER scores."""
        for criterion, band in zip(SpeakingCriterion, [7, 7, 7, 7]):
            CriterionScore.objects.create(
                session_result=self.result,
                criterion=criterion,
                band=band,
                source=ScoreSource.EXAMINER,
            )
        band = self.result.compute_overall_band()
        # sum=28, 28//2=14, 14/2=7.0
        self.assertEqual(band, 7.0)

    def test_compute_overall_band_ignores_ai_scores(self):
        """4 EXAMINER + 4 AI scores — only EXAMINER scores used in calculation."""
        for criterion, band in zip(SpeakingCriterion, [8, 8, 8, 8]):
            CriterionScore.objects.create(
                session_result=self.result,
                criterion=criterion,
                band=band,
                source=ScoreSource.EXAMINER,
            )
        # Add AI scores with different bands that would change the result if included
        for criterion, band in zip(SpeakingCriterion, [4, 4, 4, 4]):
            CriterionScore.objects.create(
                session_result=self.result,
                criterion=criterion,
                band=band,
                source=ScoreSource.AI,
            )
        band = self.result.compute_overall_band()
        # Only EXAMINER: sum=32, 32//2=16, 16/2=8.0
        self.assertEqual(band, 8.0)

    def test_compute_overall_band_returns_none_when_fewer_than_4_examiner_scores(self):
        """Returns None if fewer than 4 EXAMINER scores even if AI scores exist."""
        # Add 3 EXAMINER scores (not enough)
        for criterion, band in zip(list(SpeakingCriterion)[:3], [7, 7, 7]):
            CriterionScore.objects.create(
                session_result=self.result,
                criterion=criterion,
                band=band,
                source=ScoreSource.EXAMINER,
            )
        # Add 4 AI scores (should not count)
        for criterion, band in zip(SpeakingCriterion, [6, 6, 6, 6]):
            CriterionScore.objects.create(
                session_result=self.result,
                criterion=criterion,
                band=band,
                source=ScoreSource.AI,
            )
        band = self.result.compute_overall_band()
        self.assertIsNone(band)


# ─── AIFeedbackJobTests ──────────────────────────────────────────────────────

class AIFeedbackJobTests(TestCase):
    """Tests for AIFeedbackJob model creation and status transitions."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="examiner_aijob",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="candidate_aijob",
            password="testpass123",
            role=User.Role.CANDIDATE,
        )
        self.preset = MockPreset.objects.create(name="AIJob Test Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner,
            candidate=self.candidate,
            preset=self.preset,
            status=SessionStatus.COMPLETED,
        )

    def test_aifeedbackjob_created_with_default_pending_status(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        self.assertEqual(job.status, AIFeedbackJob.Status.PENDING)

    def test_aifeedbackjob_default_pending_equals_1(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        self.assertEqual(job.status, 1)

    def test_aifeedbackjob_status_transition_to_processing(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        job.status = AIFeedbackJob.Status.PROCESSING
        job.save()
        job.refresh_from_db()
        self.assertEqual(job.status, AIFeedbackJob.Status.PROCESSING)
        self.assertEqual(job.status, 2)

    def test_aifeedbackjob_status_transition_to_done(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        job.status = AIFeedbackJob.Status.DONE
        job.save()
        job.refresh_from_db()
        self.assertEqual(job.status, AIFeedbackJob.Status.DONE)
        self.assertEqual(job.status, 3)

    def test_aifeedbackjob_status_transition_to_failed(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        job.status = AIFeedbackJob.Status.FAILED
        job.save()
        job.refresh_from_db()
        self.assertEqual(job.status, AIFeedbackJob.Status.FAILED)
        self.assertEqual(job.status, 4)

    def test_aifeedbackjob_error_message_stored_when_failed(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        job.status = AIFeedbackJob.Status.FAILED
        job.error_message = "Transcription service unavailable"
        job.save()
        job.refresh_from_db()
        self.assertEqual(job.error_message, "Transcription service unavailable")
        self.assertEqual(job.status, AIFeedbackJob.Status.FAILED)

    def test_aifeedbackjob_error_message_is_null_by_default(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        self.assertIsNone(job.error_message)

    def test_aifeedbackjob_fk_to_session(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        self.assertEqual(job.session_id, self.session.pk)

    def test_aifeedbackjob_related_name(self):
        job = AIFeedbackJob.objects.create(session=self.session)
        self.assertIn(job, self.session.ai_feedback_jobs.all())


class RunAIFeedbackTaskTests(TestCase):
    """Integration tests for the run_ai_feedback background task."""

    def setUp(self):
        from session.tasks import run_ai_feedback  # noqa: F401 (imported here to fail RED if missing)
        self.examiner = User.objects.create_user(
            username="task_examiner",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        preset = MockPreset.objects.create(name="Task Test Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=preset,
            status=SessionStatus.COMPLETED,
        )
        self.job = AIFeedbackJob.objects.create(session=self.session)

    MOCK_ASSESSMENT_RESULT = [
        {"criterion": 1, "band": 7, "feedback": "Good fluency and coherence throughout."},
        {"criterion": 2, "band": 6, "feedback": "Some grammatical errors noted."},
        {"criterion": 3, "band": 7, "feedback": "Good range of vocabulary used."},
        {"criterion": 4, "band": 6, "feedback": "Generally clear pronunciation."},
    ]

    @patch("session.services.assessment.assess_session", return_value=MOCK_ASSESSMENT_RESULT)
    @patch("session.services.transcription.transcribe_session", return_value="transcript")
    def test_task_transitions_to_done(self, mock_transcribe, mock_assess):
        """run_ai_feedback transitions job from PENDING to DONE."""
        from session.tasks import run_ai_feedback
        self.assertEqual(self.job.status, AIFeedbackJob.Status.PENDING)
        run_ai_feedback(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, AIFeedbackJob.Status.DONE)

    def test_task_handles_missing_job(self):
        """run_ai_feedback with non-existent job_id does not raise."""
        from session.tasks import run_ai_feedback
        try:
            run_ai_feedback(99999)
        except Exception as exc:
            self.fail(f"run_ai_feedback raised unexpectedly: {exc}")

    @patch("session.services.assessment.assess_session", return_value=MOCK_ASSESSMENT_RESULT)
    @patch("session.services.transcription.transcribe_session", return_value="enqueue transcript")
    def test_async_task_enqueue(self, mock_transcribe, mock_assess):
        """async_task can enqueue run_ai_feedback and it executes in sync mode."""
        from django_q.tasks import async_task
        async_task('session.tasks.run_ai_feedback', self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, AIFeedbackJob.Status.DONE)

    @patch("session.services.assessment.assess_session", return_value=MOCK_ASSESSMENT_RESULT)
    @patch("session.services.transcription.transcribe_session", return_value="Fake transcript content")
    def test_task_transcribes_and_stores(self, mock_transcribe, mock_assess):
        """run_ai_feedback calls transcribe_session and stores result in job.transcript."""
        from session.tasks import run_ai_feedback
        run_ai_feedback(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.transcript, "Fake transcript content")
        self.assertEqual(self.job.status, AIFeedbackJob.Status.DONE)

    def test_task_fails_on_transcription_error(self):
        """run_ai_feedback sets FAILED status when transcribe_session raises RuntimeError."""
        from session.tasks import run_ai_feedback
        with patch("session.services.transcription.transcribe_session", side_effect=RuntimeError("Audio file not found")):
            run_ai_feedback(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, AIFeedbackJob.Status.FAILED)
        self.assertIn("Audio file not found", self.job.error_message)

    @patch("session.services.assessment.assess_session", return_value=MOCK_ASSESSMENT_RESULT)
    @patch("session.services.transcription.transcribe_session", return_value="test transcript")
    def test_task_creates_ai_scores(self, mock_transcribe, mock_assess):
        """run_ai_feedback creates 4 CriterionScore records with source=AI (AIAS-02)."""
        from session.tasks import run_ai_feedback
        run_ai_feedback(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, AIFeedbackJob.Status.DONE)
        self.assertEqual(CriterionScore.objects.filter(source=ScoreSource.AI).count(), 4)
        # Verify each criterion has the expected band from MOCK_ASSESSMENT_RESULT
        for entry in self.MOCK_ASSESSMENT_RESULT:
            self.assertTrue(
                CriterionScore.objects.filter(
                    source=ScoreSource.AI,
                    criterion=entry["criterion"],
                    band=entry["band"],
                ).exists(),
                f"Expected CriterionScore with criterion={entry['criterion']}, band={entry['band']}",
            )

    @patch("session.services.assessment.assess_session", return_value=MOCK_ASSESSMENT_RESULT)
    @patch("session.services.transcription.transcribe_session", return_value="test transcript")
    def test_task_stores_feedback(self, mock_transcribe, mock_assess):
        """run_ai_feedback stores non-empty feedback text on each AI score (AIAS-03)."""
        from session.tasks import run_ai_feedback
        run_ai_feedback(self.job.pk)
        ai_scores = CriterionScore.objects.filter(source=ScoreSource.AI)
        self.assertEqual(ai_scores.count(), 4)
        for score in ai_scores:
            self.assertIsNotNone(score.feedback)
            self.assertNotEqual(score.feedback, "")
        # Verify specific feedback text from MOCK_ASSESSMENT_RESULT is stored
        self.assertTrue(
            CriterionScore.objects.filter(
                source=ScoreSource.AI,
                criterion=1,
                feedback="Good fluency and coherence throughout.",
            ).exists()
        )

    @patch("session.services.assessment.assess_session", side_effect=RuntimeError("Claude API error"))
    @patch("session.services.transcription.transcribe_session", return_value="test transcript")
    def test_task_fails_on_claude_error(self, mock_transcribe, mock_assess):
        """run_ai_feedback sets FAILED when assess_session raises RuntimeError (AIAS-02 error path)."""
        from session.tasks import run_ai_feedback
        run_ai_feedback(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, AIFeedbackJob.Status.FAILED)
        self.assertIn("Claude API error", self.job.error_message)
        self.assertEqual(CriterionScore.objects.filter(source=ScoreSource.AI).count(), 0)

    @patch("session.services.assessment.assess_session", side_effect=RuntimeError("Claude response missing criteria"))
    @patch("session.services.transcription.transcribe_session", return_value="test transcript")
    def test_task_fails_on_missing_criterion(self, mock_transcribe, mock_assess):
        """run_ai_feedback sets FAILED when assess_session raises 'missing criteria' error (AIAS-02)."""
        from session.tasks import run_ai_feedback
        run_ai_feedback(self.job.pk)
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, AIFeedbackJob.Status.FAILED)
        self.assertIn("missing criteria", self.job.error_message)


# ─── TranscriptionServiceTests ───────────────────────────────────────────────

class TranscriptionServiceTests(TestCase):
    """Unit tests for session.services.transcription.transcribe_session."""

    def setUp(self):
        from session.models import SessionPart, SessionQuestion, SessionRecording

        self.examiner = User.objects.create_user(
            username="examiner_transcription",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        preset = MockPreset.objects.create(name="Transcription Test Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=preset,
            status=SessionStatus.COMPLETED,
        )
        self.job = AIFeedbackJob.objects.create(session=self.session)

        # Create a recording with a dummy audio file
        self.recording = SessionRecording.objects.create(
            session=self.session,
            audio_file=SimpleUploadedFile("test.webm", b"fake audio data", content_type="audio/webm"),
        )

        # Create SessionPart and SessionQuestions for initial_prompt tests
        self.topic = Topic.objects.create(
            name="Transcription Test Topic",
            part=IELTSSpeakingPart.PART_1,
            slug="transcription-test-topic",
        )
        self.question1 = Question.objects.create(
            topic=self.topic,
            text="Tell me about your hometown",
        )
        self.question2 = Question.objects.create(
            topic=self.topic,
            text="What do you like to do in your free time",
        )
        self.part = SessionPart.objects.create(
            session=self.session,
            part=IELTSSpeakingPart.PART_1,
        )
        self.sq1 = SessionQuestion.objects.create(
            session_part=self.part,
            question=self.question1,
            order=1,
        )
        self.sq2 = SessionQuestion.objects.create(
            session_part=self.part,
            question=self.question2,
            order=2,
        )

    def _make_mock_model(self, segment_text=" Hello this is a test. "):
        mock_segment = MagicMock()
        mock_segment.text = segment_text
        mock_model_instance = MagicMock()
        mock_model_instance.transcribe.return_value = (iter([mock_segment]), MagicMock())
        return mock_model_instance

    def test_calls_whisper_with_correct_params(self):
        """WhisperModel constructed with WHISPER_MODEL_SIZE, device='cpu', compute_type='int8'."""
        from session.services.transcription import transcribe_session
        mock_model_instance = self._make_mock_model()

        with patch("faster_whisper.WhisperModel", return_value=mock_model_instance) as MockModel:
            transcribe_session(self.job)
            MockModel.assert_called_once_with("base", device="cpu", compute_type="int8")

    def test_transcribe_returns_text(self):
        """transcribe_session returns a non-empty string containing segment text."""
        from session.services.transcription import transcribe_session
        mock_model_instance = self._make_mock_model(" Hello this is a test. ")

        with patch("faster_whisper.WhisperModel", return_value=mock_model_instance):
            result = transcribe_session(self.job)

        self.assertIn("Hello this is a test.", result)

    def test_initial_prompt_built_from_questions(self):
        """transcribe() called with initial_prompt containing question texts joined by '. '."""
        from session.services.transcription import transcribe_session
        mock_model_instance = self._make_mock_model()

        with patch("faster_whisper.WhisperModel", return_value=mock_model_instance):
            transcribe_session(self.job)

        call_kwargs = mock_model_instance.transcribe.call_args[1]
        initial_prompt = call_kwargs.get("initial_prompt", "")
        self.assertIn("Tell me about your hometown", initial_prompt)
        self.assertIn("What do you like to do in your free time", initial_prompt)
        # Verify joined by ". "
        self.assertIn(". ", initial_prompt)

    def test_missing_recording_raises(self):
        """Session without a recording raises RuntimeError with 'no associated recording'."""
        from session.models import SessionRecording
        from session.services.transcription import transcribe_session

        # Create a session with NO recording
        session_no_recording = IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=MockPreset.objects.create(name="No Recording Preset", owner=self.examiner),
            status=SessionStatus.COMPLETED,
        )
        job_no_recording = AIFeedbackJob.objects.create(session=session_no_recording)

        with self.assertRaises(RuntimeError) as ctx:
            transcribe_session(job_no_recording)
        self.assertIn("no associated recording", str(ctx.exception).lower())

    def test_missing_audio_file_raises(self):
        """Recording with empty audio_file.path raises RuntimeError."""
        from session.services.transcription import transcribe_session

        # Create a recording with no actual file on disk
        # We patch os.path.isfile to simulate missing file
        with patch("os.path.isfile", return_value=False):
            with self.assertRaises(RuntimeError) as ctx:
                transcribe_session(self.job)
        self.assertIn("Audio file not found", str(ctx.exception))


# ─── AIFeedbackTriggerTests ───────────────────────────────────────────────────

class AIFeedbackTriggerTests(TestCase):
    """Tests for POST/GET /api/sessions/<id>/ai-feedback/ endpoints."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="trigger_examiner", password="pass", email="trigger_ex@example.com",
            role=1, is_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="trigger_candidate", password="pass", email="trigger_cand@example.com", role=2
        )
        self.other_examiner = User.objects.create_user(
            username="trigger_other_ex", password="pass", email="trigger_other@example.com",
            role=1, is_verified=True,
        )
        self.preset = MockPreset.objects.create(name="Trigger Test Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner,
            candidate=self.candidate,
            preset=self.preset,
            status=SessionStatus.COMPLETED,
        )
        # Create a recording so the task has something to work with
        self.recording = SessionRecording.objects.create(
            session=self.session,
            audio_file="recordings/test.webm",
        )
        self.examiner_token = Token.objects.create(user=self.examiner)
        self.candidate_token = Token.objects.create(user=self.candidate)
        self.other_token = Token.objects.create(user=self.other_examiner)

    @patch("session.views.async_task")
    def test_trigger_creates_job_and_returns_202(self, mock_async_task):
        """POST as examiner creates an AIFeedbackJob and returns 202 with job_id and Pending status."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 202)
        self.assertIn("job_id", response.data)
        self.assertEqual(response.data["status"], "Pending")
        self.assertEqual(AIFeedbackJob.objects.filter(session=self.session).count(), 1)
        mock_async_task.assert_called_once()

    @patch("session.views.async_task")
    def test_trigger_non_owner_returns_403(self, mock_async_task):
        """POST as a different examiner (not session owner) returns 403."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.other_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 403)
        mock_async_task.assert_not_called()

    @patch("session.views.async_task")
    def test_trigger_non_completed_session_returns_400(self, mock_async_task):
        """POST on a non-COMPLETED session returns 400."""
        self.session.status = SessionStatus.SCHEDULED
        self.session.save(update_fields=["status"])
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 400)
        mock_async_task.assert_not_called()

    @patch("session.views.async_task")
    def test_trigger_duplicate_returns_409(self, mock_async_task):
        """POST when a PENDING job exists returns 409."""
        AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.PENDING)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 409)
        mock_async_task.assert_not_called()

    @patch("session.views.async_task")
    def test_trigger_allows_retry_after_failed(self, mock_async_task):
        """POST when the only existing job has FAILED status allows creating a new job (202)."""
        AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.FAILED)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 202)
        self.assertEqual(AIFeedbackJob.objects.filter(session=self.session).count(), 2)
        mock_async_task.assert_called_once()

    @patch("session.views.async_task")
    def test_trigger_returns_429_when_monthly_limit_reached(self, mock_async_task):
        """POST when examiner has reached the monthly limit returns 429."""
        # Create 10 DONE jobs for this examiner this month
        for _ in range(10):
            AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.DONE)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Monthly AI feedback limit reached", response.data["detail"])
        mock_async_task.assert_not_called()

    @patch("session.views.async_task")
    def test_trigger_allows_when_under_limit(self, mock_async_task):
        """POST when examiner has 9 jobs this month allows creating a new one (202)."""
        for _ in range(9):
            AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.DONE)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 202)
        mock_async_task.assert_called_once()

    @patch("session.views.async_task")
    def test_trigger_excludes_failed_from_count(self, mock_async_task):
        """POST when examiner has 10 FAILED jobs this month still allows a new job (202)."""
        for _ in range(10):
            AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.FAILED)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 202)
        mock_async_task.assert_called_once()

    @patch("session.views.async_task")
    def test_trigger_resets_count_each_month(self, mock_async_task):
        """POST when examiner has 10 DONE jobs from LAST month allows a new job (202)."""
        # Compute previous month start
        now = timezone.now()
        # Go back to last month by subtracting enough days then floor to 1st
        last_month_end = now.replace(day=1) - timezone.timedelta(days=1)
        last_month_start = last_month_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        for _ in range(10):
            job = AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.DONE)
            AIFeedbackJob.objects.filter(pk=job.pk).update(created_at=last_month_start)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 202)
        mock_async_task.assert_called_once()

    @patch("session.views.async_task")
    def test_trigger_counts_across_sessions(self, mock_async_task):
        """Jobs across different sessions for same examiner all count toward the monthly limit."""
        # Create a second completed session for the same examiner
        session2 = IELTSMockSession.objects.create(
            examiner=self.examiner,
            candidate=self.candidate,
            preset=self.preset,
            status=SessionStatus.COMPLETED,
        )
        # Create a third completed session to trigger on
        session3 = IELTSMockSession.objects.create(
            examiner=self.examiner,
            candidate=self.candidate,
            preset=self.preset,
            status=SessionStatus.COMPLETED,
        )
        # 5 DONE jobs on session1, 5 DONE jobs on session2 = 10 total
        for _ in range(5):
            AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.DONE)
        for _ in range(5):
            AIFeedbackJob.objects.create(session=session2, status=AIFeedbackJob.Status.DONE)

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.post(f"/api/sessions/{session3.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 429)
        self.assertIn("Monthly AI feedback limit reached", response.data["detail"])
        mock_async_task.assert_not_called()

    def test_get_returns_latest_job_status(self):
        """GET as examiner returns the latest job status and transcript."""
        job = AIFeedbackJob.objects.create(
            session=self.session,
            status=AIFeedbackJob.Status.DONE,
            transcript="Test transcript",
        )
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.get(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["job_id"], job.pk)
        self.assertEqual(response.data["status"], "Done")
        self.assertEqual(response.data["transcript"], "Test transcript")

    def test_get_no_job_returns_404(self):
        """GET when no AI feedback job exists for the session returns 404."""
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        response = client.get(f"/api/sessions/{self.session.pk}/ai-feedback/")
        self.assertEqual(response.status_code, 404)


# ─── AssessmentServiceTests ───────────────────────────────────────────────────

class AssessmentServiceTests(TestCase):
    """Unit tests for session.services.assessment.assess_session."""

    def setUp(self):
        from session.models import SessionPart, SessionQuestion

        self.examiner = User.objects.create_user(
            username="examiner_assessment",
            password="testpass123",
            role=User.Role.EXAMINER,
            is_verified=True,
        )
        preset = MockPreset.objects.create(name="Assessment Test Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner,
            preset=preset,
            status=SessionStatus.COMPLETED,
        )
        self.job = AIFeedbackJob.objects.create(session=self.session, transcript="test transcript")

        # Create SessionPart and SessionQuestions for question context tests
        self.topic = Topic.objects.create(
            name="Assessment Test Topic",
            part=IELTSSpeakingPart.PART_1,
            slug="assessment-test-topic",
        )
        self.question1 = Question.objects.create(
            topic=self.topic,
            text="Tell me about your childhood",
        )
        self.question2 = Question.objects.create(
            topic=self.topic,
            text="What is your favourite hobby",
        )
        self.part = SessionPart.objects.create(
            session=self.session,
            part=IELTSSpeakingPart.PART_1,
        )
        SessionQuestion.objects.create(session_part=self.part, question=self.question1, order=1)
        SessionQuestion.objects.create(session_part=self.part, question=self.question2, order=2)

    def _mock_anthropic_response(self, assessment_data):
        """Build a mock anthropic module and client returning the given assessment_data."""
        mock_block = MagicMock()
        mock_block.type = "tool_use"
        mock_block.input = assessment_data
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = "tool_use"
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_module = MagicMock()
        mock_module.Anthropic.return_value = mock_client
        return mock_module, mock_client

    def _valid_assessment_data(self):
        return {
            "fluency_and_coherence": {"band": 7, "feedback": "Good fluency and coherence throughout."},
            "grammatical_range_and_accuracy": {"band": 6, "feedback": "Some grammatical errors noted."},
            "lexical_resource": {"band": 7, "feedback": "Good range of vocabulary used."},
            "pronunciation": {"band": 6, "feedback": "Generally clear pronunciation."},
        }

    def test_builds_question_context(self):
        """assess_session builds user message containing session questions and transcript (AIAS-04)."""
        import sys
        from session.services.assessment import assess_session

        mock_module, mock_client = self._mock_anthropic_response(self._valid_assessment_data())
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            assess_session(self.job)

        call_kwargs = mock_client.messages.create.call_args[1]
        user_message = call_kwargs["messages"][0]["content"]
        self.assertIn("Tell me about your childhood", user_message)
        self.assertIn("What is your favourite hobby", user_message)
        self.assertIn("[Part 1]", user_message)
        self.assertIn("test transcript", user_message)

    def test_returns_four_criteria(self):
        """assess_session returns a list of 4 dicts with criterion, band, feedback (AIAS-02)."""
        import sys
        from session.services.assessment import assess_session

        mock_module, mock_client = self._mock_anthropic_response(self._valid_assessment_data())
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            result = assess_session(self.job)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 4)
        criterion_values = {entry["criterion"] for entry in result}
        self.assertEqual(criterion_values, {1, 2, 3, 4})
        for entry in result:
            self.assertIn("criterion", entry)
            self.assertIn("band", entry)
            self.assertIn("feedback", entry)

    def test_raises_on_missing_tool_use_block(self):
        """assess_session raises RuntimeError containing 'tool_use' when no tool_use block in response."""
        import sys
        from session.services.assessment import assess_session

        mock_block = MagicMock()
        mock_block.type = "text"
        mock_response = MagicMock()
        mock_response.content = [mock_block]
        mock_response.stop_reason = "end_turn"
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_module = MagicMock()
        mock_module.Anthropic.return_value = mock_client

        with patch.dict(sys.modules, {"anthropic": mock_module}):
            with self.assertRaises(RuntimeError) as ctx:
                assess_session(self.job)
        self.assertIn("tool_use", str(ctx.exception))

    def test_raises_on_invalid_band(self):
        """assess_session raises RuntimeError containing 'Invalid band' when band is out of range."""
        import sys
        from session.services.assessment import assess_session

        bad_data = self._valid_assessment_data()
        bad_data["fluency_and_coherence"]["band"] = 0  # invalid: must be 1-9

        mock_module, _ = self._mock_anthropic_response(bad_data)
        with patch.dict(sys.modules, {"anthropic": mock_module}):
            with self.assertRaises(RuntimeError) as ctx:
                assess_session(self.job)
        self.assertIn("Invalid band", str(ctx.exception))


class AIFeedbackDeliveryTests(TestCase):
    """Tests for AI scores in GET response and WebSocket broadcast."""

    def setUp(self):
        self.examiner = User.objects.create_user(
            username="delivery_examiner", password="pass", email="del_ex@example.com",
            role=1, is_verified=True,
        )
        self.candidate = User.objects.create_user(
            username="delivery_candidate", password="pass", email="del_cand@example.com", role=2,
        )
        self.preset = MockPreset.objects.create(name="Delivery Preset", owner=self.examiner)
        self.session = IELTSMockSession.objects.create(
            examiner=self.examiner, candidate=self.candidate,
            preset=self.preset, status=SessionStatus.COMPLETED,
        )
        self.recording = SessionRecording.objects.create(
            session=self.session, audio_file="recordings/test.webm",
        )
        self.examiner_token = Token.objects.create(user=self.examiner)
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.examiner_token.key}")
        self.url = f"/api/sessions/{self.session.pk}/ai-feedback/"

    def test_get_done_includes_ai_scores(self):
        """GET when job is DONE returns scores array with 4 AI criteria."""
        job = AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.DONE)
        result = SessionResult.objects.create(session=self.session)
        for criterion, band in [(1, 7), (2, 6), (3, 7), (4, 7)]:
            CriterionScore.objects.create(
                session_result=result, criterion=criterion,
                source=ScoreSource.AI, band=band, feedback=f"Feedback for {criterion}",
            )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["scores"]), 4)
        criteria = [s["criterion"] for s in response.data["scores"]]
        self.assertIn("Fluency and Coherence", criteria)
        for score in response.data["scores"]:
            self.assertIn("criterion", score)
            self.assertIn("band", score)
            self.assertIn("feedback", score)

    def test_get_pending_has_no_scores(self):
        """GET when job is PENDING returns scores=None."""
        AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.PENDING)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["scores"])

    def test_get_done_no_scores_returns_empty(self):
        """GET when job is DONE but no AI scores exist returns empty list."""
        AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.DONE)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["scores"], [])

    def test_get_scores_excludes_examiner_source(self):
        """GET only returns AI source scores, not EXAMINER source."""
        job = AIFeedbackJob.objects.create(session=self.session, status=AIFeedbackJob.Status.DONE)
        result = SessionResult.objects.create(session=self.session)
        for criterion in [1, 2, 3, 4]:
            CriterionScore.objects.create(
                session_result=result, criterion=criterion,
                source=ScoreSource.AI, band=7, feedback="AI feedback",
            )
            CriterionScore.objects.create(
                session_result=result, criterion=criterion,
                source=ScoreSource.EXAMINER, band=6, feedback="Examiner feedback",
            )
        response = self.client.get(self.url)
        self.assertEqual(len(response.data["scores"]), 4)

    @patch("session.views._broadcast")
    @patch("session.services.assessment.assess_session")
    @patch("session.services.transcription.transcribe_session")
    def test_broadcast_called_on_done(self, mock_transcribe, mock_assess, mock_broadcast):
        """run_ai_feedback calls _broadcast with ai_feedback_ready after success."""
        mock_transcribe.return_value = "Test transcript"
        mock_assess.return_value = [
            {"criterion": i, "band": 7, "feedback": f"Feedback {i}"} for i in [1, 2, 3, 4]
        ]
        job = AIFeedbackJob.objects.create(session=self.session)
        run_ai_feedback(job.pk)
        mock_broadcast.assert_called_once_with(
            self.session.pk, "ai_feedback_ready",
            {"job_id": job.pk, "session_id": self.session.pk},
        )

    @patch("session.views._broadcast")
    @patch("session.services.transcription.transcribe_session", side_effect=Exception("Transcription failed"))
    def test_broadcast_not_called_on_failure(self, mock_transcribe, mock_broadcast):
        """run_ai_feedback does NOT call _broadcast when the job fails."""
        job = AIFeedbackJob.objects.create(session=self.session)
        run_ai_feedback(job.pk)
        mock_broadcast.assert_not_called()
