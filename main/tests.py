from decimal import Decimal

from django.test import TestCase
from main.models import CandidateProfile, ExaminerCredential, ExaminerProfile, ScoreHistory, User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


class ProfileSignalTests(TestCase):
    def test_examiner_profile_auto_created(self):
        user = User.objects.create_user(
            username="examiner1", password="testpass123", role=User.Role.EXAMINER
        )
        self.assertTrue(hasattr(user, "examiner_profile"))
        self.assertIsInstance(user.examiner_profile, ExaminerProfile)

    def test_candidate_profile_auto_created(self):
        user = User.objects.create_user(
            username="candidate1", password="testpass123", role=User.Role.CANDIDATE
        )
        self.assertTrue(hasattr(user, "candidate_profile"))
        self.assertIsInstance(user.candidate_profile, CandidateProfile)

    def test_no_duplicate_profile_on_user_update(self):
        user = User.objects.create_user(
            username="examiner2", password="testpass123", role=User.Role.EXAMINER
        )
        profile_id = user.examiner_profile.pk
        user.first_name = "Updated"
        user.save()
        user.refresh_from_db()
        self.assertEqual(user.examiner_profile.pk, profile_id)


class PhoneValidationTests(TestCase):
    def test_valid_uzbek_phone(self):
        user = User.objects.create_user(
            username="exam_phone", password="testpass123", role=User.Role.EXAMINER
        )
        profile = user.examiner_profile
        profile.phone = "+998901234567"
        profile.full_clean()  # Should not raise

    def test_invalid_phone_rejected(self):
        from django.core.exceptions import ValidationError
        user = User.objects.create_user(
            username="exam_bad_phone", password="testpass123", role=User.Role.EXAMINER
        )
        profile = user.examiner_profile
        profile.phone = "12345"
        with self.assertRaises(ValidationError):
            profile.full_clean()

    def test_empty_phone_allowed(self):
        user = User.objects.create_user(
            username="exam_no_phone", password="testpass123", role=User.Role.EXAMINER
        )
        profile = user.examiner_profile
        profile.phone = ""
        profile.full_clean()  # Should not raise (blank=True)


class ExaminerProfileAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.examiner = User.objects.create_user(
            username="api_examiner", password="testpass123", role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.token = Token.objects.create(user=self.examiner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_get_own_profile(self):
        response = self.client.get("/api/profiles/examiner/me/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("user", response.data)
        self.assertIn("phone", response.data)
        self.assertEqual(response.data["user"]["id"], self.examiner.pk)
        self.assertEqual(response.data["user"]["username"], "api_examiner")

    def test_patch_own_profile(self):
        response = self.client.patch(
            "/api/profiles/examiner/me/",
            {"bio": "IELTS expert", "full_legal_name": "Test Examiner", "phone": "+998901234567"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bio"], "IELTS expert")
        self.assertEqual(response.data["full_legal_name"], "Test Examiner")
        self.assertEqual(response.data["phone"], "+998901234567")

    def test_is_verified_read_only(self):
        response = self.client.patch(
            "/api/profiles/examiner/me/",
            {"is_verified": True},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["is_verified"])  # Should remain False

    def test_completed_session_count_read_only(self):
        response = self.client.patch(
            "/api/profiles/examiner/me/",
            {"completed_session_count": 999},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["completed_session_count"], 0)  # Should remain 0

    def test_candidate_cannot_access_examiner_me(self):
        candidate = User.objects.create_user(
            username="noexam", password="testpass123", role=User.Role.CANDIDATE,
        )
        token = Token.objects.create(user=candidate)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/profiles/examiner/me/")
        self.assertEqual(response.status_code, 404)


class ExaminerProfilePublicTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.examiner = User.objects.create_user(
            username="pub_examiner", password="testpass123", role=User.Role.EXAMINER,
            is_verified=True,
        )
        profile = self.examiner.examiner_profile
        profile.phone = "+998901234567"
        profile.bio = "Public bio"
        profile.save()

        self.viewer = User.objects.create_user(
            username="viewer", password="testpass123", role=User.Role.CANDIDATE,
        )
        self.token = Token.objects.create(user=self.viewer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_public_profile_hides_phone(self):
        profile = self.examiner.examiner_profile
        response = self.client.get(f"/api/profiles/examiner/{profile.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("phone", response.data)
        self.assertEqual(response.data["bio"], "Public bio")

    def test_public_profile_404_for_nonexistent(self):
        response = self.client.get("/api/profiles/examiner/99999/")
        self.assertEqual(response.status_code, 404)


class ExaminerCredentialTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.examiner = User.objects.create_user(
            username="cred_examiner", password="testpass123", role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.token = Token.objects.create(user=self.examiner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_put_creates_credential(self):
        response = self.client.put(
            "/api/profiles/examiner/me/credential/",
            {
                "listening_score": "8.5",
                "reading_score": "8.0",
                "writing_score": "7.5",
                "speaking_score": "9.0",
                "certificate_url": "https://example.com/cert.pdf",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["speaking_score"], "9.0")

    def test_put_updates_existing_credential(self):
        ExaminerCredential.objects.create(
            examiner_profile=self.examiner.examiner_profile,
            speaking_score=Decimal("7.0"),
        )
        response = self.client.put(
            "/api/profiles/examiner/me/credential/",
            {"speaking_score": "8.5"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["speaking_score"], "8.5")

    def test_get_credential_404_when_none(self):
        response = self.client.get("/api/profiles/examiner/me/credential/")
        self.assertEqual(response.status_code, 404)


class CandidateProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.candidate = User.objects.create_user(
            username="api_candidate", password="testpass123", role=User.Role.CANDIDATE
        )
        self.token = Token.objects.create(user=self.candidate)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_get_own_profile(self):
        response = self.client.get("/api/profiles/candidate/me/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("user", response.data)
        self.assertIn("score_history", response.data)

    def test_patch_target_speaking_score_valid(self):
        response = self.client.patch(
            "/api/profiles/candidate/me/",
            {"target_speaking_score": "7.5"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["target_speaking_score"], "7.5")

    def test_patch_target_speaking_score_invalid_step(self):
        response = self.client.patch(
            "/api/profiles/candidate/me/",
            {"target_speaking_score": "7.3"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_target_speaking_score_out_of_range(self):
        response = self.client.patch(
            "/api/profiles/candidate/me/",
            {"target_speaking_score": "10.0"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_patch_current_speaking_score_writable(self):
        response = self.client.patch(
            "/api/profiles/candidate/me/",
            {"current_speaking_score": "6.5"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_speaking_score"], "6.5")

    def test_examiner_cannot_access_candidate_me(self):
        examiner = User.objects.create_user(
            username="nocandidate", password="testpass123", role=User.Role.EXAMINER,
            is_verified=True,
        )
        token = Token.objects.create(user=examiner)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = self.client.get("/api/profiles/candidate/me/")
        self.assertEqual(response.status_code, 404)


class CandidateProfilePublicTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.candidate = User.objects.create_user(
            username="pub_candidate", password="testpass123", role=User.Role.CANDIDATE,
        )
        self.viewer = User.objects.create_user(
            username="exam_viewer", password="testpass123", role=User.Role.EXAMINER,
            is_verified=True,
        )
        self.token = Token.objects.create(user=self.viewer)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")

    def test_examiner_can_view_candidate_profile(self):
        profile = self.candidate.candidate_profile
        response = self.client.get(f"/api/profiles/candidate/{profile.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("score_history", response.data)
