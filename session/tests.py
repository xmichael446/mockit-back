import re
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from main.models import CandidateProfile, User
from questions.models import Topic
from session.models import (
    CriterionScore,
    IELTSMockSession,
    MockPreset,
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
