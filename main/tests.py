from django.test import TestCase
from main.models import CandidateProfile, ExaminerProfile, User


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
